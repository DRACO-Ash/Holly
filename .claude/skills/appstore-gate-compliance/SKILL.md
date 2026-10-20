---
name: appstore-gate-compliance
description: Bluestaq App Store upload-gate compliance for container apps: the deploy contract, a root-caused failure catalogue, and the pipeline-simulation practice. Use when DEBUGGING a failed App Store upload, or scaffolding an app to be gate-compliant from the first commit.
---

# Bluestaq App Store upload-gate compliance

> The failure this skill prevents: a green local verification loop and passing binding reviews are necessary, never sufficient. The App Store runs its own pipeline against the literal contents of your uploaded zip, in its own environment, and every gap between what your loop checks and what the platform executes is a release you lose. This skill closes that gap. It composes with `app-store-deployment` (the authoritative platform reference), `packaging` (the package contract), `dependencies` and `security-hardening` (the scanners and container hardening), `deploy-recipes` (per-stack Dockerfiles), `testing-standards` (coverage and environment-dependent assertions), `code-architecture` (behaviour-preserving refactors), `observability-and-audit` (how failures surface), and `app-store-readiness` (the pre-flight score).

## Purpose and scope

Lessons distilled from a real thirteen-failure cycle. The single most important structural fact: the pipeline's stages run strictly in sequence, and each stage runs only after the one before it passes, so the platform reveals its requirements ONE GATE AT A TIME. You cannot see the image scanner's policy while SonarQube is failing, nor SonarQube's ruleset while the test stage is failing, nor the deploy-stage runtime faults until every earlier gate is green. Budget one upload per stage when retrofitting an unprepared codebase, or scaffold to the full checklist in section 3 and pay none of it. An app passed its full local loop (ten suites), a binding engineering review, a binding security review, and a binding deploy-gate, then failed the platform pipeline in under eight seconds; the corrected uploads then failed on an environment assertion, on five successive SonarQube waves, on three image policy scans, and on four deploy-stage runtime faults. Every root cause was a contract mismatch between what the local loop verified and what the platform executes; all were preventable at scaffold time. The failure classes map one-to-one onto the pipeline's stages, in order, because each stage only runs once the previous one passes. Scope is the upload-gate and deploy contract and the controls that keep you inside it. It does not restate the platform schema (`app-store-deployment`) or the deploy procedure (`release-and-deploy`).

**Owns:** DIAGNOSIS: why a real upload failed, root-caused by stage, and how to be compliant from the first commit. Reach for this when something is already broken.

**Does not own:** the platform reference (`app-store-deployment`), building the artifact (`packaging`), or the pre-submit score (`app-store-readiness`).

## When to use

● Writing or reviewing a packaging script or a Dockerfile for an App Store submission.
● Scaffolding a new container app, so it is gate-compliant from the first commit.
● Diagnosing a pipeline that failed on upload despite a green local loop.

## 1. The platform contract (what actually happens to your upload)

The App Store does not run your Continuous Integration (CI). It copies your uploaded zip into a GitLab project it owns, **adds its own generated `.gitlab-ci.yml` to that checkout**, and runs the generated pipeline on a government-cloud runner behind a registry mirror, with no network guarantee to public endpoints.

For a node-container template the observed stages, strictly in order, are:

● **Install**: dependency install from your lockfile.
● **Test**: `npm test -- --coverage` executed at the checkout root, with `GITLAB_CI=true` in the environment. If this exits non-zero, every later stage is SKIPPED and the deploy is dead.
● **Code Quality**: a SonarQube scan with a hard server-side quality gate. Observed thresholds: line coverage at least 80% (read from the lcov report your test stage must emit), zero open violations (bugs, code smells), security hotspots all resolved or reviewed, and reliability and security-review ratings capped. A committed `sonar-project.properties` at the repo root is respected for sources and tests scoping, the coverage report path, and coverage exclusions. Respected by the SonarQube gate itself, that is: the platform runs TWO coverage checks, and the second one honours none of that configuration (section 2.1).
● **Container Build and image policy scan**: `docker build` using the Dockerfile at the archive root, then a policy scan of the built image that judges the base image's own contents, including its layer history, not only your code.
● **Deploy**: the platform schedules the pod and probes its health. This is where runtime-only faults surface for the first time: a non-root container against a root-owned volume add-on needs `securityContext.fsGroup` or every write is `EACCES`; the operator's environment tab must be empty for a code-defaults app (anything typed there overrides the injected values); and a health probe that hangs (a stalled mount) is silently killed by the platform. A pipeline that fails with ZERO stages run is not a stage failure at all: it is app-record residue (a deleted-and-recreated app orphaned its records or GitLab project) or a slug with a double hyphen breaking platform naming.

Detection follows `app-store-deployment`'s template table: a `Dockerfile` at the archive root means a container template; a server manifest at root with no Dockerfile is detected as its stack template; static files with no server marker are static-html.

**Two binding consequences**:

1. For a quality-gated (node, python, java) template, your uploaded zip must be a self-sufficient, testable source tree that emits the coverage report the gate reads, not a build artefact and not a stripped runtime bundle.
2. Your test suite runs in the platform's environment, not yours: extra platform-committed files exist in the checkout (at minimum the generated `.gitlab-ci.yml`), the runner may be offline to public endpoints, and `GITLAB_CI=true` is set. Any assertion about the environment itself must be written for that environment.

## 2.0 READ THIS FIRST

> This skill is long and it has earned every line, and that is the problem: it is past the length
> where a reader reads rather than skims. A second project recorded the same fault in its own
> standard, and its answer was the right one - **a mechanical checklist at the top before another
> rule**. So the checklist is first. The rest of the skill is why each line is there, and you need it
> when a line fails you, not before.

### The pre-upload checklist (nine lines, in order)

1. **Does every file in the archive need to be there?** The archive IS the analysed surface. Removing
   a file is a legitimate fix and usually the cheapest one (§2.1, Failure 16).
2. **Can each gate condition be MET on what is left?** Compute the ceiling before you try to satisfy
   it. A structurally-uncoverable file caps the whole submission's coverage (§2.1, §2.0 below).
3. **Where does the window open?** The gate scores changed code since your **previous upload**.
   Read the recorded baseline; if there is not one, you cannot answer any of this (§2.3).
4. **Score all FOUR conditions, not one.** Issues 0, coverage at least 80%, duplication at most 3%,
   hotspots reviewed (§2.2). A build can be perfect on three and fail.
5. **Count an absent file at 0%.** A file the coverage report never mentions is uncovered wholesale,
   not absent from the arithmetic (§2.3).
6. **Prove your local checker can SEE the code** before you believe it (§2.3, five classes).
7. **Run one local rung per PIPELINE STAGE**, enumerated from the pipeline page, and reproduce the
   TRANSPORT, not just the tree (§2.0 below, §4).
8. **Read your own diff.** A release that is mostly tooling written to satisfy the gate is a release
   the gate will score as new code (§2.3).
9. **Say "necessary conditions met", never "this will pass"** (§2.3).

## 2.0.1 Eight uploads, one root cause, and the log said it every time

**The platform prints its own contract in the first twenty lines of every job log, and it printed the
cause of the eighth failure in the log of the first.** Read the log as a SPECIFICATION, not as an
error report. These four lines appear in every run:

| Log line | What it tells you | The local rung it demands |
|---|---|---|
| `Using platform executor with image ...node:24-alpine` | the runtime, and that it carries almost nothing | run the archive on a MINIMAL PATH (node, npm, sh) |
| `Checking out <sha> as detached HEAD (ref is refs/merge-requests/N/head)` | **the upload is reconstituted as a GIT REPOSITORY and checked out** | round-trip the archive through `git init/add/commit/archive` before testing it |
| `$ npm ci`, `$ npm test -- --coverage`, `$ npm run build` | the exact stage commands, verbatim | run each one from the round-tripped archive |
| the stage list on the pipeline page | every stage that can fail | one rung per stage, not one rung per artefact you know about |

That second line was in the log of upload one. It was read eight times and used on the eighth,
after an archive shipped `coverage/` as an EMPTY DIRECTORY so the lcov reporter had somewhere to
write. Unzipping recreates an empty directory; **git cannot represent one**, because it indexes
files. The directory vanished in the checkout and the test stage died with
`ENOENT: coverage/lcov.info` at exit 7, before a single test ran.

**So the root cause across all eight is one thing: the model of the platform was built by inference
from failures, one attribute at a time, and the local simulation was rebuilt each time to model THE
LAST FAILURE rather than the target.** Every fix was correct and every simulation was faithful to the
previous failure and unfaithful to the platform. That is why the count kept going up while each
individual repair was sound.

**Ask the feasibility question BEFORE the compliance question.** Four of the nine cycles here were
spent making a 20,000-line browser client pass a gate designed for server code: converting 534 `var`
declarations, extracting eight functions, rewriting eleven regexes. Then the file left the analysed
surface anyway, because it never needed to be uploaded. The order that would have saved those cycles
is:

1. **Does this file need to be in the archive at all?** The archive is the analysed surface, so
   every file you ship is a file the gate scores. Take it out before you clean it.
2. **If it must ship, can the condition be met at all?** A generated single-file client is 0%
   coverable by a unit-test runner, so shipping it puts a coverage ceiling on the whole submission
   that no amount of test-writing can lift.
3. **Only then, how do I make it pass?**

Doing this in the wrong order is expensive and it FEELS like progress the whole time, because every
individual fix is real and every one of them lands.

**And know the WINDOW before you read any local number.** The gate scores four conditions on the code
that changed since your **previous upload**, so a repository at 99.7% coverage can be rejected at
0.0% with both figures correct. A second project took ten consecutive rejections, each after a clean
local run, and every one was caused by the release immediately before it. Section 2.3 is the model;
`docs/UPLOAD-BASELINE.json` is where this project keeps the boundary, because nothing on the platform
writes it back to you.

**What to do instead, in order:**

1. **Enumerate the STAGES from the pipeline page** and give each one a local rung. Not the artefacts
   you happen to know about: the Dockerfile not running a build is not evidence that the platform
   does not (it runs App Build as its own stage).
2. **Enumerate the ENVIRONMENT from the log header** and encode each fact as a property of the local
   fixture: the image, the transport, the commands.
3. **Reproduce the transport, not just the tree.** A zip is not a checkout. Anything git cannot carry
   does not arrive: empty directories, permissions beyond the exec bit, mtimes, symlinks.
4. **Read the project's own documentation before inferring.** `CLAUDE.md` named the build step in
   plain words for the whole sequence and was overridden by an inference.

## 2.1 (superseded heading kept for the anchor) seven uploads, one root cause, and it was documented all along

Seven consecutive uploads of one app failed, on seven different-looking faults. They were not seven
problems. **The whole sequence was one defect in method**, and this baseline's own
`app-store-deployment` skill had already described it:

> *"the platform reveals its requirements ONE GATE AT A TIME... Retrofitting an unprepared codebase
> therefore costs roughly one upload per stage; scaffold to the full checklist and pay none of it."*

That sentence predicted the exact bill and named the remedy, and it went unread while the bill was
paid seven times. **So before your first upload, do these four things.**

**1. Enumerate the STAGES and build one local rung per stage.** `setup → check → build → test → scan
→ package → containerize → container-scan → deploy`. Every stage is a separate contract. Two of the
seven failures came from assuming a stage did not exist: the `test` stage runs on a container with
the language runtime and little else (no `git`, `bash`, `tar` or `zip`), and the `build` stage runs
`npm run build` even when your image copies a prebuilt artifact and discards whatever it produces.
A stage you have not run locally is a stage you will discover at rung 8.

**2. The ARCHIVE is the analysed surface AND the coverage denominator.** Every file you upload is
scored for issues and hotspots and counted in the coverage denominator, whether or not the container
runs it. `sonar.sources` and `sonar.exclusions` do NOT protect you: both were declared correctly, the
properties file shipped, and the excluded paths were scored anyway. **The archive is the only control
you have.** Allowlist it, never denylist it.

**3. Check the gate conditions for FEASIBILITY before trying to satisfy them.** This is the step whose
absence cost the most. One upload reported `Line coverage is 20.9% (required: 80%)` and advised
"add unit tests". Arithmetic said otherwise: the archive shipped 2,707 lines of browser wiring, 61%
of everything analysed and 0% coverable by a node test runner, so the coverage **ceiling was 39.5%**.
No quantity of tests could pass that gate. When a condition looks expensive, compute its ceiling
first: if it is unreachable, the answer is architectural (ship less, or ship it differently), and
every hour spent on findings is wasted. Four of the seven uploads were spent oscillating between two
failing states because this was never computed.

**4. Compute every gate condition LOCALLY, over the extracted archive.** Not "does `npm test` pass".
The coverage percentage, the issue families, the hotspots, the duplication ratio, each stage's
command. Six uploads asked only whether the suite passed, and the seventh failed on a number nothing
local was computing.

**And one warning about local proxies.** A proxy that reports clean while the gate reports a finding
is worse than no proxy, because it converts uncertainty into false confidence. One regex here was
"fixed", reported clean by the local scan, and flagged by the gate in the very next upload. State
what each proxy cannot see, out loud, next to the check.

## 2. Failure catalogue (observed, root-caused, fixed)

Fourteen real failures, each root-caused and fixed, are catalogued in full in `references/failure-catalogue.md` (thirteen from one cycle, plus Failure 14, a second project's seven-upload coverage saga, summarised in section 2.1). Read that file when diagnosing a specific pipeline failure, or when you want the root-cause narrative behind a checklist item. The fixes are already condensed into the checklist (section 3), the decision rules, and the standards below, so scaffolding a compliant app does not require the catalogue; debugging a live failure usually does.

The classes map one-to-one onto the pipeline stages, in order, because each stage runs only once the previous one passes:

● **Install and Test** (Failures 1 to 5): the test suite banned from the package (died in eight seconds); a test orchestrator that assumed a prior build; a security scan that fail-opened on a registry outage; a baked `ENV` default that defeated the platform's injected value; and a negative environment assertion guaranteed-false only on the platform's checkout.
● **Code Quality** (Failure 6): the SonarQube gate across five successive waves (620 to 2 open violations, coverage 0% to 80%), teaching that a findings report is a sample not the population, that the profile reveals rules progressively, and that mechanical rule-clearing swaps carry semantic traps.
● **Image policy scan** (Failures 8 to 10): the scan flags the base image not your code (npm toolchain and suid bits); it reads layer history, so an in-place `chmod` cannot clear it (flatten to `FROM scratch`); and your own later instruction (`adduser` setting setgid on the home) re-introduces the class the sweep just cleared (sweep last).
● **Deploy** (Failures 11 to 13): guidance prose pasted as an environment-variable value; a root-owned volume refusing writes from the non-root container (`securityContext.fsGroup`); and a pod dying silently after a clean boot because a health probe hung rather than failed.

**Failure 15, Install and Test: the test image has only the language runtime, and the suite shelled
out.** Cost TWO upload cycles, and the second one is the instructive half.

**Cycle one.** A suite whose security cases build real repository fixtures died with
`spawnSync git ENOENT`, having passed locally and in GitHub Actions for the life of the project. The
controls were fine and in fact behaved correctly there: the scans returned their fail-closed "could
not run" branch. It was the CASES that assumed a tool. Fixed by detecting git and skipping those
cases, and a local simulation was added that ran the extracted archive with git removed from `PATH`.
It passed.

**Cycle two, on the same class.** The next upload failed on `bash`, `tar` and `zip`. A `bash -c
'tar | tar'` tree copy had produced an EMPTY directory, so every rung case failed on a missing file
rather than on anything it tested, and the archive fixtures had no `zip`. **The local simulation had
removed only git, so it agreed with the developer's machine, which is the one environment nobody
needed reassurance about.** A simulation more generous than its target proves nothing about the
target, and a fix shaped like one tool cannot see the second one standing in the same position.

**Cycle three, and the one that names the class.** With every tool handled, the upload failed again,
this time with all tests passing: `build.mjs --check` rebuilt the artifact from the platform's own
sources and computed a bundle file count of **68 against the committed 74**, because the tree it was
handed holds six fewer `.claude` files than the tree the artifact was built from. No tool was
missing. The check was RIGHT: it correctly detected that its input was not the repository. Running it
there was wrong.

**THE CLASS IS NOT "A MISSING TOOL". IT IS A REPOSITORY CHECK RUNNING WHERE THERE IS NO REPOSITORY.**
`npm test` was doing two different jobs:

● **Application tests** ask "does the code work". They import a module and assert on a return value,
  need nothing but the language runtime, and are what the platform's stage exists to run and what its
  coverage gate reads.
● **Repository rungs** ask "is this working tree internally consistent": artifact in sync with
  source, bundle edition matching the manifest, no credential in git history, the packager producing
  what the store expects. Their subject IS the repository and its toolchain.

Every one of the three failures was category 2 running where its premises do not hold, and each
looked like its own bug. Fixing them one at a time is enumerating against a surface the platform
chooses, which is the doom-loop shape `resource-discipline` names: **the third consecutive failure of
the same check is a finding about the instrument.**

**The fix is a split, not another skip.** `npm test` carries only portable application tests;
`npm run verify` adds every repository rung and is what developers, CI and the pre-upload check run.
The platform can no longer fail a repository check because it is never handed one, and this is a
separation rather than a conditional skip: the repository checks still run in full, everywhere they
mean something. Guard the split in both directions, because it decays silently the moment somebody
adds a test to the wrong list: nothing portable may spawn a process or read the working tree, and
every analysed source must stay reachable from the portable list (the first attempt at the split
dropped one test file and took three modules out of the lcov with it, which the platform's separate
coverage check would have scored at 0%).

**And where the tool was incidental, remove the dependency rather than skipping it.** A tree copy
written as `bash -c 'tar | tar'` becomes `fs.cpSync` and then works everywhere; a git-history scan
cannot. Removing beats skipping, because the case then RUNS on the constrained machine.

**Make the local simulation faithful in every dimension the platform differs in, not just the one
that last bit you.** Minimal `PATH` (an allowlist: the runtime, its package manager and `sh`) AND a
perturbed tree (delete some files and require `npm test` to be indifferent). The first two
simulations ran against a byte-perfect copy of our own tree, so neither could have seen cycle three.
Watched red: putting one repository check back into the portable run turns the tree-perturbation leg
NO-GO while the minimal-PATH leg stays green.

**And prefer removing the dependency to skipping it.** Ask whether the tool is the case's SUBJECT or
merely incidental to it. The tree copy was incidental, so `fs.cpSync` replaced the shell pipeline and
those ten cases now RUN on the platform rather than skipping. Only the cases whose subject IS the
tool (a git-history scan; an `unzip`-backed archive scan; a rule written in shell) are skipped, with
a stated reason.

**Then guard the skip**, because a suite quietly dropping security cases and reporting green is worse
than the failure it replaced. Two counter-guards: one explicit variable (`REQUIRE_ALL_TOOLS=1`, named
for the SET and not for any one tool) set in the CI that MUST run them, turning a missing tool there
into a red suite; and a line in the loop's own output naming the missing tools on every run. Key the
variable explicitly and never on `CI`: the platform sets `CI` too and is exactly the environment the
skip exists for. Finally, check the aggregate coverage still clears the gate with those cases
skipped. Here it fell from 100% to 96.5% against an 80% floor, which is a measurement, not a
presumption.

**Failure 16, Code Quality: the archive IS the analysed surface, and a denylist archive ships the
whole repository into the gate.** Reported 315 new issues (max 0), 100+ code smells and 14 security
hotspots at 0% (required 100%). Not one finding was in code the container runs. The packager copied
the working tree minus an exclusion list, so the upload carried the client sources (534 `var`
declarations in one browser file), every build script, the skill bundle, a retrospective and a splash
image. **`sonar.sources` and `sonar.exclusions` did not save it:** `scripts/**` and `src/*` were both
excluded in the committed `sonar-project.properties`, which shipped in the archive, and both were
scored anyway. Treat those keys as a declaration the platform may ignore, never as the control.

**The control is the archive.** Cut it to an ALLOWLIST of what the two consumers actually need: the
image build (whatever the `Dockerfile` COPYs) and the platform's test stage (`npm ci`, then
`npm test`, so the entrypoint, its imports, and the tests of code that ships). Everything else in the
repository is deliberately absent, and the repository's own checks still run at home where they mean
something. Measured here: 800-odd files and 13.3MB became 13 files and 2.9MB, and the analysed
surface went to **0 `var`, 0 dynamic execution, 0 PATH use, 0 backtracking-prone regexes**, leaving a
single cognitive-complexity refactor in the one runtime file that had one.

**A denylist is the same defect as a denylist simulation** (Failure 15): it can only exclude what has
already burned you, and it silently widens every time somebody adds a directory. An allowlist makes
addition the deliberate act, which is right, because on this platform adding a file to the archive
adds it to the quality gate.

**Then score the rules locally, at the point the archive is built.** The gate is rung 8; nothing
cheaper was scoring any of its rules. A full analyser is not available offline, so assert the rule
FAMILIES the gate actually reported over the archive's JavaScript, and fail the packager closed:
`var`, dynamic execution, PATH, and nested-quantifier regexes. Declare what it cannot see (cognitive
complexity, and any rule this project has not yet been failed by) so nobody reads it as the gate.
Watched red on all four families before it was trusted.

**Failure 17, App Build: `npm run build` is its own stage, and the archive trim removed its inputs.**
The upload died on `Cannot find module scripts/build.mjs` with every test passing. The archive had
been cut to an allowlist for the image build and the test stage, on the reasoning that the Dockerfile
COPYs a prebuilt artifact and therefore nothing builds. **The Dockerfile not running a build is not
evidence that the platform does not:** App Build is a separate stage, and the project's own CLAUDE.md
named it in plain words the whole time. Lesson: enumerate the platform's STAGES, not the artefacts you
happen to know about, and make each one a local rung. `npm run deployable` now runs `npm run build`
from the extracted archive on a minimal PATH, so an allowlist can never again omit something a stage
reads.

**And the sting: an allowlist that must carry the build inputs cannot dodge the quality gate.** The
same trim that broke App Build was also what made the gate clean, so once `src/` and `.claude/` came
back, so did the findings. The code had to be fixed rather than hidden:

● **658 `var` declarations to `let`/`const`.** Mechanical, and NOT safe as a blind codemod. Two real
  breaks appeared, neither visible to a syntax check or a unit test, both caught by the browser
  render-check: a `typeof X !== "undefined"` guard on a declaration that had moved into a temporal
  dead zone (safe under `var`, THROWS under `let`), and a top-level binding a harness reached through
  `window.X` (a top-level `var` is a property of the global object, a `let` is not). If you do this
  conversion, run the real client in a real browser afterwards. Nothing else will tell you.
● **Five keyword assumptions in our own tooling.** Checkers that pinned `^\s*var NAME =` silently
  stopped matching, and the one that blanked the big embedded payloads stopped blanking them: the
  scanned view grew by 8,107 characters, the comment heuristics then ran through an embedded base64
  image, and a real link disappeared from the view. It failed CLOSED, which is why it was a red check
  and not a silent hole. Write checkers against `(?:var|let|const)`.
● **Seven ambiguous regexes.** The flagged idiom is `(^|\n)\s*`, where `\s` can match the newline the
  alternation just consumed, giving the engine two ways to match one string. `^[ \t]*` with the `/m`
  flag says the same thing with one.
● **Five functions over the cognitive-complexity ceiling**, reduced by extraction into named groups,
  never by deleting branches. Where the branches are a security ORDER, state the order in the code.
● **One smell in the refactor itself:** `(x && x.y)` where the gate wants `x?.y`. The gate scores NEW
  code, so a refactor is not a free move; everything you touch is rescored.

A prior-cycle failure (Failure 7) was stale platform configuration surviving an archetype pivot; a separate class is app-record residue or a double-hyphen slug, which fails with ZERO stages run rather than at a stage. All are detailed in the reference file.

**Failure 18, DAST Scan: the container is started with none of your settings, and a fail-closed
start serves nothing.** Holly V0.7 (October 2026) passed every other stage but Code Quality, then
failed DAST with `no_report`: "the scanner got no answer from http://dast-target:8080 within 300
seconds". The scan runs the image with `APPSTORE_DAST_SCAN=true` and **none of the app's
environment variables or secrets**, against an empty scan database, in one memory-limited job
with a browser, and it blocks on High and Critical findings (the platform's scan log and console).
An app that rightly refuses to start without its signing key or database therefore never listens.
The log's own advice: make settings optional at start, or generate a throwaway value when
`APPSTORE_DAST_SCAN=true`; listen on 0.0.0.0:8080; retry the database for about a minute rather
than once; expect no data. Lesson: **fail-closed start-up needs a scan path, gated on the flag
alone**, that fills in throwaway values, turns outbound work off, and serves the probes and the UI,
answering a request that needs a missing backing service with a plain 503; log one line naming
what it filled in, never a value. How the scan's database reaches the container is not stated
(`TBC, re-verify`): handle both a database and none. Rung: run the built image with nothing but
`APPSTORE_DAST_SCAN=true` and require a 200 on 8080 well inside 300 seconds. Retrying the same
image fails the same way, the log says.

## 2.1 The coverage gate is two checks, and the second ignores your configuration

A second project spent SEVEN successive uploads failing Code Quality on line coverage, 66% to 76% against the 80% floor, while its local `src/` coverage sat at 99% and its pipeline simulation passed at 99.2%. Each theory was disproven by the next upload. The mechanism, once the lcov was finally read:

● **The platform runs two coverage checks, not one.** SonarQube's own gate honours `sonar.coverage.exclusions` and was PASSING at 94.1%. A separate report gate does not honour them, and that was the one failing. A number one check quotes back tells you nothing about the other.
● **The failing check measures coverage on NEW or CHANGED code** (the default "Sonar way" condition), not overall coverage. Adding roughly a hundred lines of tests to old, already-covered files moved it one tenth of a point.
● **It ignores `sonar.sources` entirely.** Removing the browser client from `sonar.sources` did not move the number by a single point, which is the proof rather than the theory: the gate counts files your configuration excludes.
● **A file absent from the lcov counts as 0%.** The client was one 7,001-line top-level DOM script with no exports, so `node --test` could not import it and the report never attributed the lines the browser smoke exercised. Those lines read a permanent 0% and dragged the metric down however well the server was tested.

**The only lever that ever moved it** was converting 0%-counted lines into node-covered lines. Extracting 183 lines of genuinely pure logic into an importable module and unit-testing it moved the platform metric by 8.8 points, the one measured rate in the whole saga; a later 280-line extraction was sized against that rate to clear the floor with margin. Extraction, never exclusion-on-a-guess and never fabrication: do not mark a browser file covered without executing it, and do not add assertion-free tests to inflate a number.

**A coverage-config change is a hypothesis, measured before it ships, never shipped to be measured.** One release added a file to `sonar.coverage.exclusions` on a guess about where the uncovered mass sat, and coverage got WORSE, 76.5% to 66.4%, because exclusion removes a file's COVERED lines along with its uncovered ones: excluding a net-positive file lowers the metric. Read the lcov and do the arithmetic first. The same release hid a second trap: SonarQube's Ant-style `public/**` does not match files sitting directly under `public/`, so the largest top-level file was never excluded at all. A directory needs both `public/*` and `public/**`.

**Prevention, at scaffold time.** Author front-end logic as importable pure modules with a thin DOM-wiring layer on top (`code-architecture`, `frontend-and-rendering`), so new logic is node-coverable and only the wiring stays browser-only. A structurally-uncoverable no-exports monolith is a gate failure accumulating quietly, and every release that adds an untested browser handler drags the new-code delta down even when the rest of the tree is green.

## 2.2 The gate is FOUR conditions on changed code, and one of them usually has no local rung

Read alongside 2.1: that section is about which coverage number the platform reads, this one is about what else it reads at the same time. From the platform's own Code Quality Gate reference, the gate scores four conditions on **changed code**, all four of which must hold:

● **New issues: 0.** The class every project already fights (section 2.1 and the catalogue).
● **Coverage on changed code: at least 80%.** Two checks, one of which ignores your configuration (2.1).
● **Duplicated lines on changed code: at most 3%.**
● **Security hotspots: reviewed.**

**The duplication condition is the one that ships unmeasured.** Violations have a local analyser, coverage has an lcov and a simulation, hotspots have a reviewer. Duplication routinely has nothing, so a project discovers the threshold only when a stage that had been green fails on it. Wire a local proxy from the first commit, in the loop, next to the analyser: read the same scope from the committed `sonar-project.properties`, normalise to code lines, hash a sliding ten-line window, and fail over 3%. It cannot be the platform's number, because SonarQube's detector is token-based and its block size is platform configuration you cannot read, so treat a green proxy as an early warning with margin and reconcile against the platform's reported density at the first upload. The reference implementation in this project is `scripts/duplication-check.mjs` over `scripts/lib/duplication.mjs`, with the detector unit-tested including a **positive** case: a duplication check that has never been shown to fail is not a check.

**When it does fail, extract; never exclude.** The 2.1 lesson transfers exactly. An exclusion that moves a duplication number is the same class of guess as an exclusion that moved a coverage number the wrong way, and the honest fix is one named function where there were two copies.

**Scoping facts that change what you measure locally:**

● **Test files are excluded from the COVERAGE denominator, and are analysed for ISSUES.** A test cannot lift coverage by existing, and only the code it executes counts, so mirror the coverage exclusion in the local proxy by removing `sonar.tests` from the scope. But the issues condition is a different question, and the answer is the opposite one. A second project believed tests were out of scope entirely for four releases, on the evidence that three consecutive runs reported nothing in one; the fourth run reported a tautological assertion in a test file. **Three clean runs are a run of luck, not a rule.** A negative result from a scan is evidence about that scan, not about the scope, and the distance between the two is however long your luck lasts.
● **Build output and dependency directories are excluded automatically.** You do not need to earn those exclusions, and listing them is documentation rather than control.
● **Vendored third-party source is analysed as your own code.** A copied library, a generated bundle, or an embedded corpus inside an analysed path counts against all four conditions, duplication most of all, because vendored trees are where near-identical blocks live. Keep vendored and generated content out of `sonar.sources`, and record the residual risk rather than assuming an exclusion holds: `sonar.exclusions` is exactly the kind of configuration the second coverage check ignores.

**Hotspots cannot be cleared by the app owner.** The disposition is recorded against the finding by the platform team, so the owner-side move is always to remove the pattern in code (de-backtrack the regex, use a cryptographic random) and never to plan on reviewing it away. Budget a platform conversation, not a dashboard click.

**The retry budget is small and it is a hard constraint on triage.** One retry per job, two per pipeline, with a sixty-second cooldown. That caps how many diagnose-and-retry rounds an upload gets before it is dead, which is the arithmetic behind the whole simulate-first practice in section 4: cheap local rounds are effectively unlimited, on-platform rounds are three. The one failure that is a legitimate retry rather than a diagnosis is **"analysis did not run"**, which is a platform fault, not a code fault. Everything else spends a retry to learn nothing.

**Environment variables: `save_env_vars` is a full replacement, capped at 50 variables.** The replacement semantics are already in `app-store-deployment`; the cap is the new fact, and it is a design constraint on a config-heavy app rather than a runtime error you can debug.

> `TBC, re-verify`: the platform's node-react template requirement list includes `npm run build` producing a `dist/` directory. This baseline's `build` script produces a single-file artifact at the repository root instead, and a container template builds from the `Dockerfile`, so it is not clear whether the `dist/` line is a binding requirement of the detected template or a description of the React default. Confirm with the platform team before an upload that relies on either reading; do not reshape a working build on the strength of a documentation line.

## 2.3 The window: what "changed code" actually means, and why a green local check is not evidence

Section 2.2 says the gate scores four conditions on changed code. This section is about the word
**changed**, because a second project (Event SCOUT, `BStaq-APF/Conference-Scout`, v0.4.9 to v0.5.12,
reported by Adam Field on 1 September 2026) took **ten consecutive rejections**, every one of them
after a clean local run, and the whole sequence resolves to a misreading of that one word.

**The arithmetic that settles it.** Release 0.5.10 was rejected with `Line coverage is 0.0%` while
the repository stood at **99.7%**. Nothing was broken. That release's diff contained exactly one file
the analyser counts as production code: a browser script of 40 added lines that no node test can
execute. Zero covered out of forty to cover is 0.0%, exactly. **Both numbers were correct, and only
one of them was about the thing being scored.**

● **The window is the previous UPLOAD.** Not the previous pass, not the previous release, not the
  last tag. The platform's mirror advances on every upload, whether the gate passed or failed. A
  window one release wide is the only thing that produces 0.0% from that diff.
● **So every rejection in that ledger was caused by the release immediately before it** - all ten.
  That is not an observation about fresh code being buggier. That IS the window.
● **And the largest single failure class is "the fix for the last rejection caused the next one".**
  A coverage rung written to prevent a coverage failure spawned a subprocess and introduced two
  security hotspots. A helper written to close one rejection carried both of the next one's smells.
  **The tooling you add to satisfy the gate is the surface the gate scores next.** Across that window
  `test/` took 2,671 added lines and `scripts/` took 1,337, against 614 in `src/`. Prefer removing a
  dependency to making one compliant; prefer an idiom this repository has already carried through the
  gate; prefer not doing the thing at all. The release that finally passed was the smallest and least
  novel of the eleven, and that is the only experimental result in the whole window.

**Nothing records your upload history, so record it yourself.** A failed upload leaves no tag, no
branch and no note in your repository. That project observed merge-request numbers 17, 23, 24, 26 and
27, with gaps implying at least one upload whose result never reached them. If the baseline every
local reading depends on is not written into the tree, it is being carried in somebody's head and it
will be wrong. **One file, one commit id, updated in the commit after a package is handed over**, and
a rung that refuses to report a window rather than guessing one. In this baseline that is
`docs/UPLOAD-BASELINE.json` and `scripts/upload-baseline.mjs --check`, wired into `npm run deployable`.

**Attribute function-level findings across the whole function, not to their line.** Cognitive
complexity and its relatives are reported at the function's DECLARATION line, and count as new code
when any line inside the function changed. A changed-lines view that asks only about the finding's own
line reports clean on real findings; that one cost part of a cycle.

**Confirmed, at a second site: analysis-scope exclusions are not honoured.** That project spelled
every excluded directory both ways, `dir/*` and `dir/**`, on a defensible theory about Ant-style path
semantics, and the next run reported 29 findings in an excluded file with both spellings in place.
Keep the both-ways spelling, because it costs nothing and it is right for the SonarQube-honouring
check (section 2.1). Do not treat the file as a control. **Assume everything in the repository is
analysed, counted for coverage and counted for duplication, whatever the scope file says**, and note
what that makes the archive: the only control you have (Failure 16).

### The five ways a local checker reports green while wrong

Each of the ten rejections sorts into one of these, and the class names the fix.

1. **It could not SEE the code.** That project's rule engine blanked template literals through to the
   closing backtick, so every interpolated expression was unlinted. In an interface that builds its
   markup from templates, that is most of the logic: 29 findings invisible while the checker reported
   clean. This baseline had the same class in a different spelling and did not know it until this
   report was ingested: the packager's scan preprocessed with `sed 's://.*::'`, which truncates a
   line at its first `//` **including one inside a string**, so every rule was blind to the remainder
   of any line carrying a URL. **So: prove the preprocessing can see the code.** Ship a command that
   prints what the rule engine reads after blanking, and look at it with your eyes
   with your eyes. A first draft of one rule there raised 558 false
   positives from a preprocessed copy in which every quoted string had become the same run of spaces;
   printing one sample would have caught it in seconds.
2. **It measured a different thing.** Whole-tree coverage instead of coverage on changed lines;
   whole-file issue counts instead of issues on changed lines. Both look healthy at exactly the moment
   they are worthless. **Measure what the gate measures, on the lines the gate measures, or report no
   number.** Label every whole-tree figure as not the gate's.
3. **Two lists of the same rules drifted.** A whole-tree run named fourteen rules by hand while the
   changed-lines view held twenty-nine; the fifteen in the difference ran in only one view, and a
   duplicate key in a module's own exports survived a green local run and reached the gate as a Bug.
   **Derive every rule list from one place, and test that the views agree.** The trusted list will
   always be the shorter one.
4. **A finding was attributed to a line nobody diffed.** The function-level rule above.
5. **The fix for the last rejection caused the next one.** Above, and the largest class.

### Rules this produces

● **Refuse to certify.** The honest output of any local check is **"necessary conditions met"**, never
  "this will pass". A subset check that claims to be the gate is worse than no check, because the next
  rejection teaches the reader to ignore it. State what the check cannot see next to every clean
  result, not in a comment at the top of the file.
● **Refuse to report a number you cannot stand behind.** No coverage report means "run the tests
  first", not 0% and not 100%. No diff means "this was run wrong", not "clean". **The most dangerous
  output a compliance tool can produce is a comfortable number derived from nothing.** In particular,
  the naive intersection of a diff with a coverage report finds no coverable line in a file the report
  never mentions and returns a flattering 100%; treat a file absent from the report as uncovered
  wholesale. That single arithmetic choice is the difference between predicting the 0.0% rejection and
  missing it. (This baseline's `scripts/archive-coverage.mjs` counts absent files at zero for the same
  reason, over the whole shipped surface rather than the changed lines.)
● **Know which lever moves the number, because effort is not a lever.** Writing more node tests aimed
  at browser code buys exactly nothing when that file never appears in the coverage report at all.
  Two levers do move it. **Extraction**: relocate pure logic into an importable module and unit-test
  it, measured at one site as 8.8 points per 183 lines (§2.1), and it surfaces real defects while it
  runs - one such move exposed an event with a latitude and no longitude producing a NaN distance,
  which costed a domestic event as intercontinental because every comparison against NaN is false.
  **Guarding `main()`**: an entry point whose top level calls `main()` cannot be imported, so it is
  absent from the report and scored at 0%; put the call behind a direct-invocation guard
  (`if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) main();`) and the
  module becomes requireable and coverable. Three entry points moved from absent to covered that way,
  and the tests earned their place independently. This baseline already uses that idiom in
  `scripts/ci-test.mjs` and `scripts/embed-bundle.mjs`; `server/index.mjs` is the shipped case, and it
  is deliberately left as a declared coverage exclusion while the archive stands at 94.52% against an
  80% floor - reach for the lever when the margin needs it, not before, because the entrypoint of a
  running container is not a file to refactor for a number you already have.
● **A directory is a test directory only if the analyser is told so, by the INCLUSION.** A file inside
  `sonar.tests` that does not match `sonar.test.inclusions` (a fixture, a helper, a shared builder, a
  browser spec) is treated as production code with no coverage and counted at 0%. Mirror the inclusion
  pattern in every local proxy, never the directory name, or the proxy is kinder than the platform in
  exactly the case it exists to catch (`scripts/archive-coverage.mjs` was, until this was ingested).
● **Replay before you hypothesise.** Given a gate report and the commit it was cut from, reproduce the
  exact file and line locally, first, before forming a theory. Everything that project learned and kept
  came from a replay; everything it guessed at cost an hour. Guessing at a gate report costs a full
  cycle per guess.
● **Sweep the family, not the instance.** The one round that swept a whole rule family across the tree,
  rather than fixing the single instance the report named, took no longer and closed five shapes
  instead of one. This is the same rule as "a findings report is a SAMPLE, not the population" in the
  decision rules, measured a second time at a second site.
● **Where a local rule and the gate disagree, the gate is the authority.** Three local rules there were
  narrowed on judgement, and one of those judgements recorded a shape as a deliberate known miss
  because the broad rule also flagged ordinary patterns. The next gate raised three of exactly that
  shape.
● **Spend a retry only against a written diagnosis.** One per job, two per pipeline (section 2.2). If
  you cannot say what you expect to change, do not spend it. The only legitimate blind retry is a job
  reporting that **analysis did not run**, which is a platform fault rather than a finding.
● **Flag hotspots distinctly from issues.** A hotspot does not clear by re-uploading; it clears when
  the code changes or a platform-side review completes. Presenting the two together invites a wasted
  retry against a budget of three.
● **Never put a fail-closed check in a lifecycle hook.** npm runs `pretest` before `test`, so a
  non-zero `pretest` means **not one test runs** and the platform reports "Tests failed" with no output
  at all: a helpful local check becomes a silent, undiagnosable build failure. That project wrote this
  rule down and then left the trap in place for eight more releases, in a different form, because a
  rule in a document is not a guard. Put the check in the loop, where its failure carries a message,
  and commit the case that turns red if anyone reinstates the hook.

## 3. Build-compliant-from-start checklist

Apply at scaffold time for any app targeting the App Store container template. For the Node reference stack these scaffold-time defaults ship as copy-ready files under `deploy-recipes/templates/node/` (the hardened flattened `Dockerfile`, `run-tests.mjs`, `sonar-project.properties`, `eslint.config.mjs`, `package-appstore.sh`, and `simulate-pipeline.sh`); copy them, do not re-derive them. A skill's checklist is a liability until it is materialised in the scaffold.

● `Dockerfile` at the repo and package root, multi-stage, lean base, non-root numeric user, `EXPOSE 8080`, and a healthcheck on an unauthenticated `/healthz` that proves storage with a real WRITE (not an existence check, which passes on a read-only or root-owned mount), races a hard TIMEOUT strictly shorter than the platform's probe, and returns the resolved data dir and the exact errno in its 503 body so a screenshot is a full diagnosis.
● Boot emits one decisive log line recording whether storage accepted a write, and ready and unready transitions log, so a pod that is silently killed still leaves a narrative. A health probe that can hang converts an infrastructure fault into an undiagnosable silent liveness kill.
● Runtime stage hardened for the image policy scan from day one: package-manager toolchain removed (npm/corepack/yarn on Node, pip on Python; the build stage keeps it), base packages upgraded, and nothing in the final stage the CMD does not need. The scanner judges what ships, not what runs.
● The suid/sgid sweep is the LAST mutation in the prep stage, after user creation and all file copies: `find / -xdev -perm /6000 \( -type f -o -type d \) -exec chmod a-s {} +`, fail closed. Later instructions can violate the invariant (busybox `adduser` sets setgid on the home it creates), so nothing may follow the sweep; leave the sticky bit (the policy tests `/6000` only).
● The shipped stage is FLATTENED: hygiene in a `prep` stage, then `FROM scratch` with one `COPY --from=prep / /` and re-declared metadata (including explicit PATH). The scanner reads layer history, and a single clean layer is the only construction with none.
● The operator console state for a code-defaults app is an EMPTY environment tab; platform-injected variables live at the pod level, so anything typed into the tab is an override and a liability. A non-root container using the file-storage add-on needs an operations request to set `securityContext.fsGroup`, or the root-owned mount refuses every write.
● No `ENV PORT=` and no `ENV DATA_DIR=` in the Dockerfile. Code defaults carry those values; platform injection wins.
● Storage-path resolution: explicit variable, then platform-injected variable, then default. Boot validation: absolute, not root, writable; fail closed loudly.
● `npm test` is green in a fresh clone with only an install step before it; the orchestrator self-builds any artefact a suite reads.
● Build and test entrypoints run in the platform's minimal shell, not just your login shell. The container base is commonly Alpine, whose `/bin/sh` is BusyBox with no `bash`; a `package.json` script or a build step that shells out to `bash`, or uses a bash-only feature (arrays, `[[ ]]`, `pipefail`), dies with `sh: bash: not found` at the platform build even though it ran locally. Keep the build and test steps pure to your runtime (for Node, pure `node` scripts), or `sh`-portable, and simulate them under `sh`.
● The package script produces a source zip: Dockerfile and lockfiles at root, source, build tooling, tests, docs. Banned: `node_modules`, built output, version-control metadata, any `.env`.
● `.dockerignore` and the package allowlist are separate contracts. One shapes the image, the other shapes the upload.
● Every external scanner has its offline behaviour defined and tested: honest skip on offline runners, hard fail on the authoritative networked runner.
● Every negative assertion is classified per environment: enforced everywhere, or gated on `GITLAB_CI`. No assertion may be guaranteed-false on the machine that gates the deploy.
● `.gitignore` blocks `.env`, `.env.local`, `.env.*.local`, local data directories, and `coverage/` from day one.
● Coverage tooling wired from the first commit: the platform's exact test command emits the report the gate reads (lcov at `coverage/lcov.info` for Node; per-stack paths in `deploy-recipes`); `sonar-project.properties` committed with sources, tests, report path, and any honest exclusions.
● Front-end logic authored as importable pure modules from the first commit, with a thin DOM-wiring layer on top, so it is node-coverable. A no-exports client monolith is unfixable by configuration once the second coverage check counts it at 0% (section 2.1).
● Coverage on new code is a release condition, not an end-of-project one: every new or changed executable line in a release carries a test. Each directory named in an exclusion or source glob is spelled both ways (`dir/*` and `dir/**`), and every coverage-config change is arithmetic read from the lcov, not a guess.
● A duplication proxy in the per-commit loop, scoped from the committed `sonar-project.properties` with tests removed, failing over 3% (section 2.2). It is the fourth gate condition and the one most often measured for the first time on the platform. Vendored and generated content stays out of `sonar.sources`, because the platform analyses it as your own code.
● A Sonar-equivalent static-analysis pass in the per-commit loop (cognitive complexity at most 15, loop shapes, comparators, ARIA and contrast rules), so violations are fixed one at a time instead of six hundred at once. Make it concrete, not aspirational: for a Node project wire the ESLint `unicorn` and `sonarjs` plugin sets and cap cognitive complexity at 15 (SonarQube rule S3776), because the local default `complexity` rule measures cyclomatic complexity at 20, which is looser and different, so a function passes locally and fails on upload. Other stacks wire the equivalent SonarQube-profile analyser (`deploy-recipes`). If the local profile is looser than the platform profile anywhere, that gap is a future upload failure: two whole classes surfaced only on upload in one project because the local profile lacked them, the preferred-optional-chain rule (`x && x.y` to `x?.y`) and the missing-sort-comparator rule (S2871).
● In a shared-global-scope bundle, a naming convention for module helpers (unique per-module prefixes) from the start.
● A release version bump edits the lockfile by path, never by search-and-replace (see Decision rules).
● A pipeline-simulation script exists and runs before every upload (section 4).
● **The image starts as the DAST scan starts it:** with `APPSTORE_DAST_SCAN=true` and nothing else, it serves `/`, the health paths and the UI on 0.0.0.0:8080 within seconds, filling in throwaway values for what it would otherwise refuse without, under that flag alone, and a smoke rung proves it on the built image (Failure 18).
● **An upload baseline is recorded in the repository** from the first handover: one file, one commit id, the version and the platform's outcome, updated in the commit after a package is handed over. A pre-upload rung reads it, prints which changed files the archive actually ships (those are the gate's new code), and REFUSES rather than guessing when the record is missing. Nothing on the platform writes this boundary back to you (section 2.3).
● **Every local gate proxy can show what it reads.** A scan that preprocesses its input ships a mode that prints the preprocessed view, and its clean result names what it cannot see and claims "necessary conditions met", never a pass. Rule families live in ONE list, so a whole-tree view and a changed-lines view cannot drift.
● **No `pre`/`post` npm lifecycle hook.** A non-zero `pretest` means the platform runs no tests and reports "Tests failed" with no output; checks belong in the loop, where a failure carries a message. Guard it with a committed case (section 2.3).
● Ship often, so the new-code window stays small. The SonarQube gate scores NEW code against a zero-violations bar, and every shipped release resets that baseline; a long unshipped backlog means the next upload re-scans the whole accumulated range as new code, so one missed rule spelling anywhere in six stacked releases fails the whole upload. Prefer small, shipped increments; if work must stack, run the local analyser over the WHOLE accumulated range, not just the latest diff. (This trades against batching for gate cost in `resource-discipline`: batch the local binding gates, but do not let releases stack unshipped against the platform's new-code window.)

## 4. The transferable practice: simulate the platform pipeline exactly

The single highest-value control, refined by each failure. Simulate what the platform does, INCLUDING the files and environment it adds to your checkout, against the artefact, not the repo:

```
npm run package:appstore                              # produce the actual upload artefact
unzip -q the-package.zip -d /tmp/sim                  # what the platform will check out
printf 'stages: [test]\n' > /tmp/sim/.gitlab-ci.yml   # the platform commits its own CI file
cd /tmp/sim
npm ci                                                # the platform's install stage
GITLAB_CI=true npm test -- --coverage                 # the platform's exact command AND environment
test -s coverage/lcov.info                            # the artefact the SonarQube gate reads
```

If that sequence is not green, the upload will fail regardless of what the repo's own CI says. The simulation must reproduce the platform's checkout state and environment, not just its command, and must verify the coverage artefact exists. The three gates the simulation cannot fully reproduce are the SonarQube ruleset, the image policy scan (both server-side), and any coverage-on-new-code report gate; the mitigations are a per-commit analyser that keeps the violation count at zero, a flattened, hardened runtime image (Failures 8 and 9) that passes the scan by construction, and a client authored as coverable modules (section 2.1) so the delta metric is satisfiable at all. The duplication condition (section 2.2) is a fourth such gate, mitigated by the local proxy rather than reproduced by it.

Note the budget the simulation is buying you: one retry per job and two per pipeline (section 2.2). Local rounds are effectively free and on-platform rounds are three, so every check you move down a rung is bought cheaply against a budget that runs out.

**Know which of your local numbers is a proxy for which gate.** This simulation computes coverage the SonarQube-honouring way, over the sources and exclusions you declared, so it is not a proxy for a gate that ignores both and scores only the release delta. One project's simulation was green at 99.2% while the gate read 76.5%, for six uploads. A number no local rung can reproduce is UNVERIFIED, not passing; say so in those words, and make everything the simulation does cover acceptance-by-construction so the unverifiable number is the only variable left at upload.

## 5. Behavioural traits (for working with Claude on a deployment)

Phrased as habits to ask for and to review against (`working-with-ai`):

● **One gate at a time.** The pipeline reveals its requirements sequentially; a report for one stage is not the whole contract. Scaffold to the full checklist so you never pay per-stage discovery.
● **A findings report is a sample, not the work list.** Fix by rule class, eradicate by grep across every spelling, and measure the population directly; never treat one scan's page of issues as complete.
● **Contract-first packaging.** Obtain the platform's execution contract (what runs, where, with what network, with what added files) before writing a packaging script. Distrust any inherited exclusion list.
● **Fresh-environment paranoia.** Treat "works here" as unverified until proven from the actual artefact, under the platform's environment, with its added files present. Make the simulation a named script and harden it after every platform failure.
● **Negative-assertion environment audit.** Every "must not exist" rule has an enforcement context; a rule guaranteed-false on the deploy runner is a self-inflicted outage.
● **Coverage is an artefact, not a virtue.** Emit the report the gate reads and confirm it exists; a comprehensive suite that emits nothing scores 0%. And the artefact is judged over a scope you may not control: read which files are IN it and which are absent at 0% (section 2.1).
● **Read the artefact the gate reads, not only the log.** When a metric will not move, stop theorising and open the thing the gate opens: for coverage that is the lcov (which files it lists, which are missing, what the real denominator is). Two disproven theories in a row is not bad luck, it means the mechanism is not understood, and the next attempt should be a read rather than a guess. Six uploads were spent on theories that one local read of the report settled in minutes.
● **Fail-open hunting on gates.** Ask what a tool emits when its dependency is absent, and whether your parser distinguishes "clean" from "could not check". Reproduce the outage; do not reason about it.
● **The scanner judges what ships, not what runs.** Base-image contents and layer history are in scope; harden and flatten the runtime rather than editing your code when an image scan fails.
● **Silent-success suspicion.** The most expensive failures worked visibly while the durable behaviour was wrong (an ephemeral write, an unchecked advisory, a suid bit in an earlier layer). Verify the durable effect: restart and re-read, sever the dependency and re-scan.
● **Behaviour-preserving refactors, proved independently.** When you refactor to clear a metric, prove behaviour over hostile inputs with a parity harness and a render smoke, not just the suite you had.
● **User-confirmed actions fail loudly.** A compliance sweep that adds `.catch` handlers must surface an operator-initiated failure (a restore, a destructive delete) as a visible error, never to `console.debug`; only best-effort background work may log quietly (`observability-and-audit`).
● **Honest degradation vocabulary.** Passed (verified), skipped (could not verify, stated loudly, compensating control named), failed (verified bad); never conflate them.
● **After two failures of one mechanism, change the mechanism, not the value.** A deploy cycle is expensive; re-tuning the same approach a third time (the same env-var channel, the same fix spelling) usually means the mechanism is wrong, not the value. When the same fix fails twice, step out and change the approach.
● **Never let the app die silently.** Health probes race a hard timeout, boot logs its storage verdict once, and state transitions narrate; an infrastructure fault must become a named log line, not an undiagnosable kill. Health-check with a real write, and return the errno in the 503 so a screenshot diagnoses it.
● **Read the failing log before theorising, and the RAW log not the summary.** Every platform failure was diagnosed in one pass because the log was read verbatim and the failure reproduced locally before any fix was written. The failure summary prints `N/A` where the raw job log names the file and mode; obtain the raw log first, and when a hypothesis and a log line disagree, the log line wins. A pod log can interleave multiple pod generations, and a crash-looping app pod beside a healthy add-on pod (ClamAV) localises the fault to configuration or the app, not the infrastructure.

## Decision rules

● **Green local loop, about to upload?** Run the section 4 simulation against the actual artefact, with the platform's added file, `GITLAB_CI=true`, and a `coverage/lcov.info` check. A green repo loop is not a green upload.
● **An image scan fails on `suid_or_guid_set` or base-package CVEs?** It is the base image, not your code. Remove the toolchain, strip suid bits from files and directories, upgrade base packages, and flatten to `FROM scratch` with one `COPY --from=prep / /`. If a partial fix moves the count rather than zeroing it, the scanner is reading layer history; flatten.
● **A negative assertion ("X must not exist")?** Classify it ours-only (gated on `GITLAB_CI`) or everywhere; never let one be guaranteed-false on the deploy runner.
● **Mirroring an external analyser that reveals findings one wave at a time?** Inherit its WHOLE recommended profile locally, do not hand-pick the rules it has so far named: hand-picking guarantees a next wave, because the local gate can only hold the classes the platform has already caught. One project cleared five SonarQube waves this way before inheriting the full recommended profile (217 rules, not 21 hand-picked) and grepping for the two classes the linter cannot see without type information. Where the local mirror genuinely cannot enforce a rule the analyser runs, record the gap explicitly and enforce it another way, naming the real detector rather than inventing a plausible rule name. And decline a suggested fix that changes behaviour, in writing, with the divergence stated: an analyser once offered `x <= 0` for `!(x > 0)`, which differ on NaN, so the code kept an explicit finite check instead.
● **A findings report of any kind (Sonar, audit, a reviewer's named line)?** It is a SAMPLE, never the population. Before fixing, enumerate the population: grep every syntactic spelling of the defect across the whole analysed scope, deliberately (positive and negated forms, guard and expression forms, single-line and multi-line forms, and the copying variant of any mutating API), and record the count and the exact command that produced it so the number is checkable. Then ship a MECHANISED check that fails on the CLASS, not tests for the named instances, so the next occurrence cannot reappear; where the linter cannot see the class (no type information, generated code, a prose rule), a grep test is the right instrument and must state what it cannot see. The anti-pattern this closes was measured at roughly three calendar days: eight consecutive review rounds on one defect class, each fixing only the sites the previous reviewer happened to name, ending only when the sweep finally became a test that fails on the whole class, which is what round one should have produced.
● **A gate metric will not move across attempts?** Stop attempting. The next action is to read the artefact the gate reads and establish the mechanism, not to try a second cause. For a coverage gate: generate coverage locally, open the lcov, and answer three questions before anything else. Which files are in the report? Which are absent, and therefore counted at 0%? What is the real denominator? Then fix the mechanism (extraction for a structurally-uncoverable file) rather than the number, and never change a coverage exclusion as an experiment on the platform's clock (section 2.1).
● **A release version bump?** Surgical, never search-and-replace. It touches exactly the lockfile's root `version` and `packages[""].version` and `package.json`; verify `git diff package-lock.json` shows exactly two changed lines and never touch a line containing `node_modules/` (a repo-wide replace has twice corrupted a lockfile record, caught only by the binding gate).
● **A mechanical swap to clear a rule?** It can change behaviour on the wider input domain; prove the truth table over hostile inputs and keep a risky guard inside a try block if the domain is not pinned. Known traps from the field: `localeCompare` is not the code-unit sort order, so swapping a comparator into it silently reorders anything whose checksums or migration order depend on the exact order; `Number.isNaN` does not coerce where the old `isNaN` did; and `x && x.y` to `x?.y` changes the produced value from the falsy left operand to `undefined`. Require a parity harness or an exact-order comparator, not just a green existing suite.
● **An app pod crash-loops or dies after a clean boot (deploy stage)?** It is configuration or the app, not infrastructure, if a sibling add-on pod is healthy. Read the raw pod log first. A fail-closed boot error quoting a value means a variable was set wrong (often guidance prose pasted into the env tab; delete it, the tab should be empty). `EACCES` on a write means the non-root container hit a root-owned mount (an ops request for `securityContext.fsGroup`). A clean boot then a silent `SIGTERM` with growing restart gaps means a hanging health probe killed by kubelet liveness back-off (add a hard probe timeout and a boot storage-write log line).
● **A pipeline fails with ZERO stages run?** Not a stage failure: app-record residue from a deleted-and-recreated app, or a slug with a double hyphen. Recreate under a fresh single-hyphen slug and confirm the old records and GitLab project are cleared.
● **A build or test step dies with `sh: bash: not found` (or a bash-only feature is undefined)?** The platform ran it under a minimal `sh` (BusyBox on Alpine), not bash. Rewrite the step pure to your runtime or `sh`-portable, and simulate it under `sh`; do not add bash to the image to paper over it.

## Standards (checkable assertions)

● For a quality-gated template, the uploaded package is a testable source tree that emits coverage: `npm test -- --coverage` at the checkout root passes in a fresh unzip after `npm ci`, under `GITLAB_CI=true`, and writes a non-empty `coverage/lcov.info`.
● A `sonar-project.properties` is committed declaring sources, tests, the coverage path, and any exclusions (coverage metric only, each with a written rationale); a per-commit static-analysis pass keeps violations at zero.
● Every file that carries logic appears in the lcov, so nothing is counted at 0% by absence; front-end logic is importable and unit-tested, and every new or changed executable line in a release is covered.
● No coverage-exclusion or source glob is changed without the lcov arithmetic that predicts the effect, and each directory glob is spelled both `dir/*` and `dir/**`.
● The runtime image ships no package manager, no suid/sgid bits on files or directories, and is flattened to a single layer (`FROM scratch` with one `COPY --from=prep / /`), so the policy scan finds nothing in layer history.
● The packaging allowlist and `.dockerignore` are distinct; every negative assertion is classified per environment; no `ENV PORT=`/`ENV DATA_DIR=`; injected paths resolve in code with boot validation.
● A release bump changes exactly two lockfile lines; operator-initiated failures surface visibly.
● The health endpoint proves storage with a real write, races a timeout shorter than the platform's probe, and returns the resolved dir and errno in its 503 body; boot logs its storage verdict once; the operator env tab is empty for a code-defaults app; a non-root container using the volume add-on has `securityContext.fsGroup` set.
● A pipeline-simulation script reproducing the platform's checkout, environment, and coverage artefact runs before every upload.
● The built image serves HTTP 200 on 0.0.0.0:8080 when run with `APPSTORE_DAST_SCAN=true` and no other variable, and any relaxation of start-up checks is gated on that flag alone and logged.
● The upload baseline (the commit the gate's changed-code window opens at) is recorded in the repository and read by a pre-upload rung that refuses, rather than guesses, when it is absent; every whole-tree number a local check reports is labelled as not the gate's number.
● Every local gate proxy declares what it cannot see next to its clean result, claims only "necessary conditions met", and can print the preprocessed view its rules actually read; its rule families are derived from one list.
● `package.json` declares no `pre`/`post` lifecycle hook, guarded by a committed case, so no check can convert itself into a silent test-stage failure.
● Build and test entrypoints are pure to the runtime or `sh`-portable (no `bash` dependency and no bash-only feature), because the platform runs them under a minimal shell (BusyBox `sh` on Alpine), and are simulated under `sh`.
● The local static-analysis profile is the platform's, not a looser default (for Node, `unicorn` and `sonarjs` with cognitive complexity capped at 15); a rule that can fire on the platform can fire locally. Releases are shipped small rather than stacked unshipped, or the whole accumulated range is analysed before upload, so the new-code window and its blast radius stay small.

## Failure modes and remedies

● **Pipeline dies seconds in, downstream skipped.** A suite or config was excluded from the package. Fix: ship tests, docs, runner config; keep them out of the image via `.dockerignore`; re-run the simulation.
● **One assertion fails only on the platform.** A negative assertion is guaranteed-false in the platform's checkout. Fix: gate it on `GITLAB_CI`.
● **Code Quality fails on coverage 0%.** The suite emitted no lcov. Fix: run under a coverage tool on `--coverage`, emit and commit the config, verify the file is non-empty.
● **Code Quality fails on coverage while your local coverage is high.** A second check is scoring new or changed code over a scope your config does not control, and files absent from the lcov count as 0%. Fix: read the lcov, list the absent files, extract their pure logic into importable modules and unit-test it, and size the extraction against the measured points-per-line rate. Do not touch an exclusion as an experiment (section 2.1).
● **Code Quality fails on hundreds of violations, and again on rescan.** No per-commit analyser, and reports are samples. Fix: wire the analyser; eradicate by rule class and residual grep across every spelling; prove refactors behaviour-preserving.
● **Image scan fails on `suid_or_guid_set N/A` after a chmod.** The scanner reads layer history. Fix: flatten to one clean layer via a `prep` stage and `FROM scratch`.
● **A user-confirmed action silently failed.** A compliance `.catch` logged instead of surfacing. Fix: classify handlers by who initiated; operator-initiated failures show a visible error.

## Verification

Simulate the pipeline (section 4): green, with a non-empty `coverage/lcov.info`. Run the per-commit analyser: zero violations. Grep the suite for negative file-existence checks: each is gated per environment. Build the image (or, if the registry is blocked, verify against the upstream base and let the platform build fail loudly): the final stage is `FROM scratch` with one `COPY`, no toolchain, no suid bits, and the policy scan reports no critical. `git diff package-lock.json` on a release bump shows exactly two lines. Deploy, restart, re-read persisted state: it survives.

## Glossary

● **One gate at a time:** the pipeline runs stages in sequence and reveals each stage's requirements only after the previous passes; budget one upload per stage when retrofitting.
● **Image policy scan:** the platform's scan of the built image; it judges the base image's contents and layer history (suid/sgid bits, vendored CVEs), not only your code. Owner: `security-hardening`, `app-store-deployment`.
● **Layer history / flatten:** an image is immutable layers; a later `chmod` cannot clear an earlier layer's bit, so ship a single clean layer via `FROM scratch` and one `COPY --from=prep / /`.
● **Quality gate:** the SonarQube Code Quality gate; fails on coverage below 80%, any open violation, an unreviewed hotspot, or a rating over cap.
● **Coverage on new code:** the "Sonar way" default condition, which scores only the lines a release adds or changes rather than the whole tree; a second report check applies it while ignoring `sonar.sources` and `sonar.coverage.exclusions`, so old tests cannot move it and configuration cannot hide from it.
● **Structurally-uncoverable file:** a source file a unit runner cannot import (a top-level DOM script with no exports), so no report ever attributes its lines and the gate counts them at 0%. The fix is extraction into importable modules, never exclusion and never fabricated tests.
● **Progressive rule revelation:** the profile surfaces new rule classes across successive scans; plan three to five cycles when retrofitting.
● **Fail-open:** a control that maps "could not verify" to "passed"; the opposite of fail closed.
● **Deploy stage:** where the platform schedules and probes the running pod; runtime-only faults (fsGroup, env-tab overrides, hanging health probes) surface here for the first time. Owner: `release-and-deploy`, `observability-and-audit`.
● **fsGroup:** the pod `securityContext` field that makes a mounted volume group-writable to a non-root container; without it a root-owned add-on volume refuses every write (`EACCES`).
● **Liveness back-off:** kubelet restarting the SAME pod name with growing gaps after failed liveness probes; a NEW pod name each time is instead the deployment controller.
● **Raw job log vs failure summary:** the summary prints `N/A` for paths the raw job log names in full; obtain the raw log before theorising, and the log line beats the hypothesis.
● Other terms: `glossary`.

## Provenance

Distilled from a real App Store thirteen-failure cycle across five gate classes: packaging (the test suite excluded from the zip), an environment-dependent negative assertion (false only on the platform's checkout), five successive SonarQube quality-gate waves (620 to 2 open violations, converging only once fixing switched from report-driven to grep-verified class eradication across every syntactic spelling), three container image policy scans (base-image contents, then layer history closed by flattening, then instruction ordering closed by running the sweep last), and four deploy-stage runtime faults (guidance prose pasted as an env value in two variables, a root-owned volume refusing non-root writes, and a hanging health probe silently killed), with an app-record residue class where a recreated app or a double-hyphen slug fails with zero stages run. The remediations root-caused each defect, reproduced each adversarial attack, proved every refactor behaviour-preserving with parity harnesses and a render smoke, and hardened the pipeline simulation, the runtime image, and the health probe so each class cannot recur. The controls are cross-referenced to the owning baseline skills so a gap routes back to its owner. Section 2.1 and the coverage rules are distilled from a second project's record: seven successive uploads (V1.30 to V1.36) failing the Code Quality gate on coverage while its local number sat at 99% and its pipeline simulation at 99.2%, root-caused only when the lcov was read, and closed by extracting pure logic out of a 7,001-line no-exports client at a measured 8.8 points per 183 lines.
