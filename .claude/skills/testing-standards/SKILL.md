---
name: testing-standards
description: Test strategy, tooling, and craft. Use when writing or running tests, debugging a red test, or judging whether a suite protects the code. Covers the static validate-plus-render-check-plus-security-greps loop, server node:test with lcov coverage, in-process HTTP via the app factory, parity and security-property tests, a Playwright browser smoke test, and building tests in as you code. Coverage at least 80%.
---

# Testing standards

> Stack note: the commands shown here are the Node example. For Python, Java, Go, Rust, or .NET, run the equivalent canonical step from `toolchain-adapters`. The principle in this skill is what binds; the command is illustrative.

## Purpose and scope

The test strategy and patterns that keep the suite reliable across both archetypes. The static artifact runs a three-part verification loop: inline-JS syntax validation, a headless render-check on desktop and mobile, and static security greps. The server app runs `node:test` unit tests with built-in coverage, in-process HTTP tests via the app factory, cross-runtime parity tests, security-property tests, and a single Playwright browser smoke test. Scope is testing and coverage. It does not cover CI orchestration (`ci-cd`) or the deploy gate (`release-and-deploy`).

## When to use

- Writing or changing a test, or judging whether coverage is adequate.
- Deciding which tier a behaviour belongs to.

## Prerequisites

- `environment-setup`. Static needs Node and the headless browser driver; server unit tests need only Node, the smoke test needs a browser.

## Procedure (static: the verification loop)

1. **Validate inline-JS syntax.** Extract the inline script and run `node --check`. Expected: `JS syntax: OK`.
2. **Render-check headless on two viewports.** Load the artifact in a headless browser at desktop and mobile sizes; assert core behaviour (search, selection, an injection-inertness probe) and fail on any non-allow-listed console error. Expected: two `PASS` lines.
3. **Run static security greps.** Assert no dynamic code, no egress, no message listeners; the escaper covers all five characters; link-safety counts match; the CSP is locked. Expected: `STATIC CHECKS: PASS`. These three are wired as `npm test`.
4. **Unit-test non-trivial inline logic out of band.** Render-check is a smoke test, not a logic test, and it needs a browser the build sandbox often cannot run. When the artifact holds real decision or validation logic (a recommender, a parser, a state machine), mark its pure functions with sentinel comments (for example `/* X:START */ ... /* X:END */`), and add a check script that reads the artifact, extracts the block between the sentinels, evaluates it in a `node:vm` context with light stubs, and asserts edge cases. Wire it into `npm test` and the deployability check so a regression in the logic blocks the loop and a merge, even when the browser leg is deferred to CI. The point: a single-file artifact must not have logic that no test can reach.

## Procedure (server: tiered tests)

1. **Unit tests with the built-in runner**, asserting with `node:assert`, run with coverage to lcov so static analysis can read it.
   ```
   node --test --experimental-test-coverage \
     --test-reporter=lcov --test-reporter-destination=coverage/lcov.info test/<files>
   ```
2. **In-process HTTP via the factory.** Build the app with injected fakes, `listen(0)` on an ephemeral port, drive it with `node:http` against temp-dir-isolated state.
3. **Parity tests** for any rule duplicated across runtimes: assert the server implementation and the client mirror agree (numeric rules to a fixed precision; shared constants deep-equal).
4. **Injected fixed time.** Functions depending on "now" take the date as a defaulted parameter so a test passes a fixed date.
5. **One browser smoke test** (Playwright) that boots the real seeded server, renders every view asserting zero page errors, and exercises a critical flow with expensive or external calls mocked.
6. **Security-property tests:** boundary rejection, anti-shrink merge, the concurrency rev guard, the prototype-pollution strip, and auth required/not-required.

## Craft: build, debug, and audit tests

The strategy above sets what to test and the coverage floor; this is the day-to-day craft of getting there. Language-agnostic; for the concrete test and coverage command, see `toolchain-adapters`.

**Build tests in as you code.**
- Test with the change, in the same commit; a change without its test is not done. Test first when the behaviour is well specified, immediately after when exploring, and keep the loop green throughout.
- Spend by the pyramid: many fast unit tests, fewer integration, very few end-to-end. Test logic where it is cheapest; do not push it into slow end-to-end tests.
- Shape every test arrange, act, assert: one action, one observable outcome, one reason to fail.
- Make tests deterministic by construction: inject time (pass "now" as a defaulted parameter), seed randomness, isolate state. No wall-clock or network dependence in the unit tier.
- Prefer fakes you control over mocking everything; mock only the expensive, external, or non-deterministic. Assert observable behaviour, not a private detail a harmless refactor would change.
- Mutation-proof a new guard before you submit it, do not let a reviewer prove it for you. A guard, validator, or invariant is unfinished until a mutation shows it can fail: in a COPY of the tree (never the working tree), delete or invert the code the guard protects, run only that suite, confirm it goes red, then discard the copy. Name the mutant and the suite it kills in the commit, so the proof is part of the record. A boundary guard needs a boundary mutant, not just an existence mutant: move the threshold by one in each direction (a floor of 4 that still passes at 1 is not tested), and the fixture must be able to exercise the bound it claims to test (a cap of 25 asserted with 9 rows asserts nothing). Measured: seven mutants over four guards took about four minutes against a copy; the same information arriving as a gate FAIL cost roughly forty plus the reviewer's whole re-read.
- **Mutate each control SEPARATELY, because a test that asserts their conjunction asserts none of them.** Measured across five consecutive releases on one rate limiter, as its parts grew: at the first round it had four load-bearing parts (a cap, a floor, a refuse-when-nothing-is-evictable guard, and the freeing of refilled entries) and a reviewer deleted each one individually with the whole suite green. Adding bin-ordered eviction and a batch size took it to six, and a scan cooldown plus the cap's own MAGNITUDE to eight, and each round the reviewer repeated the exercise on the parts that then existed. One test failed only when several were broken at once, which reads as coverage and is not. The rule: one named case per control, and the mutant list in the commit. Note the growth pattern, because it is the durable part: every part added to a control is a new mutant nobody has run, so the mutation list is re-run whole on every change to the control, not extended at the end.
- **Commit the mutant, do not merely name it.** The rule above says to name the mutant in the commit; measured over one release, that is too weak. Forty-four mutants were run against a scratch copy across seven review rounds, named in commit messages, and discarded. The proof became a sentence nobody could re-run, so the next person to touch those controls would have had to rebuild the battery from prose, and in practice would not have. Keep a committed battery (`scripts/mutation-battery.mjs` here, `npm run mutants`): a table of control, file, exact text, replacement, run against a COPY, non-zero if any mutant survives. Two properties make it a check rather than a list: it **fails on a missing anchor**, so a refactor that moves the code announces that the proof stopped measuring instead of passing silently; and it **declares its equivalent mutants**, the ones inside an asserted band that no case may distinguish, so it cannot quietly stop discriminating. Keep it out of the inner loop; it costs minutes where the loop costs seconds.
- **A battery is worth what it DISCRIMINATES, not what it runs.** "I re-ran the mutants and nothing survived" was stated in this baseline and was false: the battery moved one constant to 1 and to 5000, and 5000 was caught by an unrelated ceiling, so nothing in it tested the range that mattered. A reviewer then moved the same constant to 150 and the suite stayed green. Before trusting a green battery, ask which mutant would fail if the control drifted by a LITTLE, not by everything. Boundary mutants earn their place here; existence mutants are the cheap half.
- **A self-referential probe asserts that the code agrees with itself.** A case that reads `T + THE_CONSTANT - 1` and `T + THE_CONSTANT` moves with the constant and therefore cannot see the constant move. Every behavioural probe for one cooldown had that shape, so an eightfold drift shipped green. At least one probe of a bound must use a FIXED literal, chosen against the shipped value and stated as such.
- **A correction is higher-risk than the work it corrects, and deserves more scrutiny, not less.** Over one release, five of the last twelve review findings were defects in the corrections rather than in the original work, including one that understated a live pre-authentication amplification fivefold while purporting to fix an overstatement. A correction is written under time pressure, about an assertion, by someone who has just been told they were wrong; all three push towards a fast confident edit. Re-measure a corrected figure from its own operands before publishing it, and treat "this is just fixing what the reviewer said" as the moment to slow down.
- **A guard-shaped case can be vacuous for the machinery, not the logic, and only a mutant shows it.** A case written to isolate one control (an eviction floor) passed identically with that control set to zero, for two reasons neither visible in the code: the fixture's own parameters made the eviction batch size 1, and a cooldown elsewhere in the control meant only its first arrival triggered a pass at all, so the eviction could never reach the entry the floor protects. The test named the right control, asserted the right outcome, and could not fail. When a control's behaviour depends on other constants in the same unit, derive the fixture's parameters from them and assert the PREMISE (that the pass ran, and reached the entry in question) before asserting the outcome.
- **Name the workload your fixture assumes, then build the one it does not.** The same limiter's every fixture filled its map with entries in the state where the property holds BY CONSTRUCTION, so the attack was structurally invisible to all of them: an attacker held the map in the other state and every request paid a full scan, an amplification of order 10^2 to 10^3 that the suite could not see. **Quote a ratio with both operands, its conditions, and where the measurement is noisy, its SPREAD.** That one was measured four times on four machines, each pairing the attack against fresh addresses below the cap in one warmed process: 200-225us against 0.199us, 161us against 0.118us, 107-176us against 0.152-0.336us, and 114-173us against 0.167-0.567us. Ratios from 201x to 1,364x, which is what those four pairs produce when a reader divides them. **FOUR** published point figures from that data were unsupported, the last three written while correcting the one before: 1,209x (no recorded pair produces it), a "correction" to 241x that paired the attack against a COLD-process baseline and understated a pre-authentication hole fivefold in an exported standard, a restoration of the first, and then a SPAN, "306x to 1,366x", whose own endpoints were not derivable from the operands printed beside them. A range is not automatically honest: it is a figure like any other, and it has to come out of the numbers next to it. **When a sub-microsecond operand swings three- to fivefold between runs, a point figure is a fourth reader's correction waiting to happen. Publish the range and the order of magnitude, which is what the argument actually rests on, and be as suspicious of a figure that flatters you as of one that alarms you.** A performance or resource argument that depends on the traffic is not a bound, because the traffic is the attacker's to choose. If your evidence assumes a distribution, say so in the test name, and add the adversarial one.
- **Make every case prove its own premise.** A case that hides a value must assert that it IS hidden before asserting the scan finds it, or it is not evidence of anything: a three-case table offered as proof that one design beat another turned out to have two cases that behaved identically under both designs. The premise assertion pays for itself immediately, and did here, catching a fixture that destroyed its own evidence with a `gc --prune` on the release that added it.
- **An assertion that holds whether the control exists or not is the commonest defect in this baseline.** Eleven are named in this baseline, and ALL ELEVEN are listed here, because a count that stops short of its own number is the defect in the next rule down and this list shipped stale twice: at eight while the tree already named a ninth, then at nine while the tree named a tenth in four files. Nine shipped across two releases, each found by a gate rather than by the suite: (1) a bound compared to itself; (2) a default-cap case inserting 200 entries against a cap of 10,000, so `size <= CAP` held whether the cap existed or not; (3) a scope check that was true only in the repository and not in the extracted package; (4) a fixture using a long query where the code strips the query; (5) one using a file extension the scanner never reads; (6) an early `return` inside a test guard, so everything after it was unreachable; (7) a `doesNotMatch` that held with the whole rule deleted; (8) an assertion that "some captured line" was short, non-vacuous only by the accident that one line was captured; and (9) the guard-shaped-but-vacuous eviction-floor case two rules above. Then (10), live at HEAD three releases after it was written: a rate-limiter case whose own comment claimed to assert a COUNT OF PASSES when nothing counted passes, so deleting the control it named left it green. And (11), the first fix for (10): it asserted a work counter was AT MOST the map size, a bound satisfied by zero, so a counter stuck at zero passed it. Note where (11) was caught, because it is the only cheerful item on the list: by the author's own mutation run, before it was committed, which is where the other ten should have been caught. Before committing an assertion, delete the thing it protects and watch it fail. If it cannot fail, it is documentation, not a test.
- **A line that cannot be watched fail should not look like a guard.** One early return was semantically equivalent to its own mutant (the loop guard below it already handled the case), so no test could ever kill it while it read as a control. Delete it or make it load-bearing; leaving it is a claim of protection nobody can check.
- Verification confirms a belief; it does not form one. Measure the value before you write it, do not assert it and let the gate check your reasoning. On one release the correlation was exact: every fix that computed the number first (a contrast ratio by WCAG arithmetic before a hex was chosen, a row count measured at each commit, a probe mutation-proved before submission) passed first time, and every fix that reasoned and left the gate to check it failed. A gate that keeps catching your figures is telling you the figures were guessed; produce each one from a command in the session, so the gate confirms what you already measured instead of discovering what you assumed. State the command's SCOPE beside the number, not just the command: a filtered query presented as the complete record is the same defect as an unmeasured figure, and it reads as authoritative. Two cases, both real: a continuous-integration run list filtered to one branch produced a "first green run since" claim that was wrong twice over, two other runs having been green all along (`docs/retrospectives/conference-scout-v0.3.3-v0.4.9.md`, section 5.1); and a recalled round count, published as measured, was inflated from four to seven because nobody grepped the audit log (`docs/retrospectives/mission-control-v3.2.55-v3.2.62.md`, What did not go well). This baseline made the same error in the same week: see the comment at the top of `.github/workflows/verify.yml`. If the figure came from a subset, say which subset.

**Debug a red test, hypothesis-first.**
- Reproduce it in isolation first; if it only fails in the full run, suspect shared state or order.
- Two strikes on a defect class means stop fixing and build a reproduction harness first. If the same class fails a check or a gate twice, each fix so far has been a partial model of the problem submitted as if complete; the third attempt must begin with a script that reproduces the original failure, not another guess. On one project a status-poller defect took four submissions, each re-opening the hole the last closed, and only passed once the reproduction came first. The harness is cheaper than the third round.
- Read the assertion (the symptom), form one hypothesis about the cause, test that one change, rerun. Do not change several things at once.
- Bisect the input or the diff (`git bisect`) to the smallest failing case.
- Decide whose fault it is: a real defect (fix the code) or a brittle test (fix the test). Never loosen an assertion to turn red green.
- Hunt flakiness deliberately (time, order, concurrency, network): loop it to confirm, then remove the cause. A flaky test is treated as failing.
- Never trust a check you did not run; paste the real failing output (the gate doctrine applies to your own debugging).

**When an interaction "does not work", debug the binding path first, not the handler body.**
- Reproduce before you fix. For any "X does not respond" report, the first artefact is a script (jsdom or Playwright) that drives the real build and reproduces X. Ship code only when that probe goes red then green. A theory you did not probe is a guess.
- Prove the handler was bound before you inspect what it does. "Did my code run" precedes "is my code correct": a one-line log in the binding loop, or an assertion that the listener is present, settles it in seconds.
- Ascend the ladder from the bottom; the bug is usually two rungs below where the eye lands. Rung 0: is the element in the deployed DOM (view the deployed artefact, not the source)? 1: is a handler bound? 2: did the binding function complete? 3: did it throw earlier (every raw `getElementById(id).addEventListener` is a null-deref if the element was removed, and one throw unwinds the rest of init and kills every later handler)? 4: is the click reaching the handler? 5: does the handler run but state not change? 6: is the DOM updated but not visible (`display`, `visibility`, `pointer-events`, `opacity`, `z-index` on the element and its ancestors)? Most interaction bugs live at rung 2 or 3.
- A try/catch is a shield after diagnosis, never a probe before it. A try/catch that never fires is a placebo; wrapping code to "catch the throw" tells you nothing. Use the stack trace or a targeted probe.
- A green suite while the app is unusable is a broken suite. Assert the primary journey, not just DOM shape: boot the app, click each tab and control, and assert the target view or state actually changed. The render-check already walks the four tabs (`scripts/render-check.mjs`); keep that habit, a suite that never simulates a click cannot catch a dead handler.

**Audit a suite so coverage is not mistaken for safety.**
- Treat coverage as a floor, not a target: a covered line can assert nothing.
- Check assertion strength: would the test pass against broken code? A test with no real assertion is theatre.
- Think in mutations: if you flipped a comparison, dropped a guard, or returned early, would a test go red? Where not, the line is covered but unprotected.
- Find and quarantine flakes; never let a known flake run un-quarantined.
- Catalogue the smells: over-mocking, brittle selectors, slow tests in the fast tier, hidden order dependence, wall-clock or network reliance.
- Cover the boundaries (empty, null, max, malformed) and the security properties (boundary rejection, injection-inertness of reflected input, auth required where it must be), not just the happy path.
- Test the visible STATE of every control, not only its data path. A control's visibility and enabled/disabled logic is code: assert the field shows when the server says it is needed, the button disables when it should. A whole feature once shipped dead behind a green 360-test suite because a control read `state.scanPinRequired`, a property nothing ever assigned (the real one was `state.status.scanPinRequired`), so the field was always hidden and no test exercised that path. Two cheap guards catch this class: an assertion on the control's rendered state, and, while authoring, a grep for where a property is ever assigned before trusting a read of it (a read of a never-assigned property is a silent typo the type-free path hides).
- A comment is a claim, and a claim is tested too. A superlative or a count in prose ("every committed file", "26 candidates", "always", "never") either gets a test that fails if it becomes untrue, or a recorded command that reproduces the number, or it is narrowed to what the code actually holds. In one project's last two releases, four separate findings were prose that outran the code, not code that was wrong; the worst was a guard commented "reads every committed text file" that walked a hand-kept list missing forty-two files, including the one whose whole purpose was to enumerate secret-bearing variables. Grade such a defect by what the control is FOR: a false comment on a convenience helper is cosmetic, but a false comment on the thing that verifies a hard rule is a fail-open. And when a control cannot see something, state the blind spot in the control itself, not only in a review reply.

## Simulate the TRANSPORT, not just the tree

A deployment platform rarely runs your files the way you handed them over. Ours turns the upload into
a git repository and checks it out, which the job log states in its third line. Every local
simulation before the eighth failure just unzipped the archive, and an unzip preserves things a
checkout cannot:

● **Empty directories.** Git indexes files; a directory with no files has nothing to represent. An
  archive that shipped an empty `coverage/` so a reporter had somewhere to write passed every local
  check and died on the platform with `ENOENT` before a single test ran.
● **Permissions** beyond the executable bit, **mtimes**, and **symlinks**.

So build the fixture the way the target does: `git init`, `add -A`, `commit`, then materialise from
the commit (`git archive HEAD | tar -x`). What survives that is exactly what the platform gets. And
assert the premise, because a simulation that silently produces an empty tree passes every leg for
the wrong reason.

**The general rule: a check that depends on the transport is not a check.** Prefer a command that
creates what it needs over a file or directory that has to survive the journey.

## Prove your checker can SEE the code before you trust what it says

A checker that reads its input through a preprocessing step - stripping comments, blanking strings,
normalising whitespace - has a second failure mode nobody looks for. It does not go red wrongly. **It
goes GREEN while blind**, with total confidence, over exactly the region the preprocessing ate.

Two instances, at two sites, found the same week. A reporting project's rule engine blanked template
literals through to the closing backtick, so every interpolated expression was unlinted: in an
interface that builds its markup from templates that is most of the logic, and **29 real findings were
invisible while the checker reported clean**, for releases (Adam Field, Event SCOUT, 1 September 2026).
This baseline had the same class in a different spelling and did not know it: the packager's
analysed-surface scan preprocessed with `sed 's://.*::'`, which truncates a line at its first `//`
**including a `//` inside a string literal**, so a line reading `const url = "https://x"; var y = 1;`
reached the rules as `const url = "https:` and none of the five families could fire on the rest of it.
A URL in a string is not an exotic input.

So:

● **Ship a mode that prints what the rule engine reads**, and read it with your eyes when you add a
  rule and whenever an expected finding does not appear. The same project's first draft of one rule
  raised 558 false positives in a single file because it read names from a copy in which every quoted
  string had become the same run of spaces; one printed sample would have caught it in seconds, and
  the lesson had already been paid for once that week on another rule.
● **And then ask whether the preprocessing should exist at all**, because this baseline's own answer
  was no. Sixteen rounds of binding review went into a hand-written lexer in one checker's decision
  path, which was defeated once per round, several times carrying a real executing `eval(` into a
  shipped archive at exit 0. Measured on the seven files that checker actually scanned, the lexer
  prevented ZERO false positives. It existed only to stop prose about a rule raising a finding, and
  nothing on that surface ever needed it. Matching the RAW SOURCE has no lexical state to get wrong.
  A display mode is worth shipping; a display mode with authority over the verdict is a surface with
  no bottom (`appstore-gate-compliance`, and the CHANGE LOG at V2.157 to V2.170).
● **Assert the visibility, not only the verdict.** A committed case that asserts the preprocessed view
  still CONTAINS the code (`assert.ok(view.includes("var sneaky"))`) is the direction a "does the rule
  fire" case cannot cover, because a blind rule and a clean file are indistinguishable from the outside.
● **Preprocess with a scanner, not a line regex.** Comments, strings, template literals and regex
  literals are lexical states; a regex over lines cannot tell them apart, which is the whole defect.
  Where a heuristic is unavoidable (regex literal versus division), make the wrong answer keep code
  VISIBLE rather than hide it, and say so next to the code.
● **Keep one list of rules.** A tool with a whole-tree mode and a changed-lines mode drifts between
  them, and the list that gets trusted is the shorter one: fourteen rules against twenty-nine at that
  site, and a duplicate key in a module's own exports survived a green local run because of the fifteen
  in the difference.
● **A verification that was never committed is not a guard, it is a memory.** That project's safety net
  for behaviour-preserving extraction was a set of differential comparisons run interactively in a
  browser and never committed: they cannot be re-run and cannot fail, so every extraction they blessed
  has been unguarded from the moment the tab closed. This is a harder failure than "not proved": an
  unproved guard at least still runs. If a check only ever ran in somebody's session, the property it
  established is not established.

## A browser is the only thing that can verify browser code

A `var`-to-`let` conversion across a client is the clearest case there is. It passes a syntax check,
it passes every unit test, and it can still be broken in two ways that only execution reveals:

● **A temporal dead zone.** `typeof X !== "undefined"` answers "undefined" for a `var` that has not
  run yet and THROWS for a `let`. So the guard that existed to tolerate absence becomes the thing
  that breaks. Measured here on a 658-declaration conversion: one occurrence, invisible to `node
  --check` and to 309 passing tests, found immediately by the render-check as
  `Cannot access 'LANGS' before initialization`.
● **The global object.** A top-level `var` is a property of `window`; a `let` is not. Any harness or
  cross-script access through `window.NAME` silently stops reaching the binding, and the symptom is a
  timeout rather than an error.

So: keep a browser leg, make it fail on `pageerror`, and run it after any change to client scoping.
And when a test drives the app through a global that only existed because of `var` hoisting, make the
coupling explicit rather than restoring the legacy scoping rule.

## Separate the tests of your CODE from the checks on your REPOSITORY

Most suites hold two different kinds of check under one command, and only one of them travels:

● **Application tests** import a module and assert on a return value. They need the language runtime
  and nothing else.
● **Repository rungs** assert that this working tree is internally consistent: a built artifact
  matches its source, a version matches a manifest, no credential is in the history, the packager
  produces the right shape. Their subject is the repository and its toolchain.

Both are worth having. But a deployment platform runs your test command on a container that has the
runtime and little else, and on a tree that is not your repository, so every repository rung there
is a check whose premises do not hold. **Give them separate commands.** The portable one is what the
platform runs and what your coverage gate reads; the full one is what you and CI run.

This baseline learnt it over three failed uploads that looked like three different bugs (no `git`;
then no `bash`, `tar` or `zip`; then a build-drift check computing a file count of 68 against a
committed 74, with every test passing). Fixing them one at a time is enumerating against a surface
the platform chooses. **The class is not "a missing tool", it is a repository check running where
there is no repository.**

**Guard the split in both directions**, because it decays the moment somebody adds a test to the
wrong list, silently, with everything green locally: assert that nothing in the portable list spawns
a process or reads the working tree, and that every analysed source is still reachable from it. The
first attempt at this split here dropped one test file and silently took three modules out of the
coverage report, which the platform scores at 0%.

## A test that shells out imports an assumption about the machine

The suite passes on your laptop and in your CI because both have git, docker, a browser and a shell.
The deployment platform's test container has the language runtime and little else, and finds this out
for you at the most expensive rung there is: twenty-three cases of this baseline's own secret-scan
suite died on the App Store with `spawnSync git ENOENT`, after passing everywhere for the life of the
project. The controls were correct; the FIXTURES assumed a tool.

● **Know which of your tests shell out**, and to what. `grep` your suite for the binaries it spawns.
  Anything outside the language runtime is a portability assumption you are making silently.
● **Ask whether the tool is the SUBJECT or merely incidental, and remove it where it is incidental.**
  A tree copy written as `bash -c 'tar | tar'` becomes `fs.cpSync` and then works everywhere; a
  git-history scan cannot. Removing the dependency is strictly better than skipping it, because the
  case then RUNS on the constrained machine rather than merely not failing there.
● **Skip on a missing tool, never fail on it, and never assume it.** Detect the tool once, and skip
  those cases with an explicit reason string naming the tool and why the case needs it.
● **Simulate every dimension the target differs in, not just the one that last bit you.** PATH is
  one dimension; the file tree is another. Two successive simulations here removed tools from a
  byte-perfect copy of our own repository, so neither could see a failure caused by the tree itself
  differing. Add a perturbation per dimension: minimal PATH, and a tree with files deleted.
● **Detect the tools as a SET, and simulate with an ALLOWLIST.** This is the step that costs a second
  cycle when you miss it. Fixing the one tool a failure named leaves every other tool sitting in
  exactly the same position, and a simulation that removes only that tool then agrees with your own
  machine, which is the one environment nobody needed reassurance about. State what the target
  actually has (here: the language runtime, its package manager and `sh`) and run against only that,
  so a new dependency fails by default instead of on the next upload. Doing this found a fourth
  affected file that no single-tool check could reach.
● **Then guard the skip, because a conditional skip is a hole.** A suite that silently drops security
  cases and reports green is worse than the failure it replaced. Two cheap counter-guards: an explicit
  environment variable set in the CI that MUST run them, which turns a missing tool there into a red
  suite; and a line in the loop's own output that names the skip count on every run. Key the variable
  explicitly rather than on `CI`, because the platform that lacks the tool sets `CI` too.
● **Re-measure coverage with the cases skipped.** The whole point is that the platform runs a
  different subset than you do, so the number it scores is not the one you saw.

The general form, which is the same defect as a rung that fails open: **an environmental difference
you have never run under is an untested branch of your test suite.** Run it once, deliberately, with
the tool removed from `PATH`, before the platform runs it for you.

## Decision rules

- **Which tier?** Pure logic to unit; route or middleware behaviour to in-process HTTP via the factory; whole-page render and a flow to the single Playwright smoke test. Do not push logic testing up into e2e.
- **Mock or real?** Mock only expensive, external, or non-deterministic calls; test everything else against the real code.
- **Coverage threshold?** At least 80% over the analysed source. Exclude only genuinely untestable integration glue, and only after unit-testing its pure helpers.
- **Flaky test?** Fix or quarantine immediately; a flaky test is treated as failing.
- **Using node's test runner?** Scope discovery with an explicit glob (`test/*.test.js`). A bare directory argument (`node --test test/`) misbehaves, and a non-test helper file basenamed with a test pattern (`test.mjs`, `x.test.js`) is auto-discovered and run, which can recurse. Never emit a bare `node --test` as the `test` script for a quality-gated template: the platform runs `npm test -- --coverage`, and node's runner rejects the unknown `--coverage` flag with "bad option", failing the test stage and skipping every later gate. The `test` script must own its flags, tolerate the platform's extra argument, scope discovery with an explicit glob, and emit `coverage/lcov.info` (`appstore-gate-compliance`, `deploy-recipes`).
- **A leg cannot run locally?** It is not a pass, and the partial loop is not the loop. The static render-check needs a browser the build sandbox often cannot launch, so it exits with a distinct non-zero code (not 0) and prints an unmissable "deferred to CI" banner: never a green line. Treat Continuous Integration as the binding source of truth for that leg, and never merge while its required check is red. Two specific traps to avoid: running the cheap subset (`test:fast`) and reading it as the whole loop; and merging a pull request before its checks report green. A leg that silently no-ops reads as covered when it was never run, which is how a real defect ships behind a loop that looked green.
- **A negative assertion ("X must not exist", "Y must never be set")?** It has an enforcement context, so classify it before you write it: is the rule about MY repository, or about EVERY checkout of this code? A rule that is correct locally can be guaranteed-false in the deploy environment, because the platform adds files and variables to your checkout (the App Store commits its own `.gitlab-ci.yml` and sets `GITLAB_CI`). Gate the platform-only cases on the runner's identity and record them as an explicit, honest pass; keep the everywhere cases failing loudly. Sweep for these systematically: grep the suite for negative file-existence checks. An assertion that is guaranteed-false on the machine that gates the deploy is a self-inflicted outage (`appstore-gate-compliance`).
- **A suite reads a generated artefact?** `npm test` (or the stack equivalent) must pass in a fresh clone with only an install step before it, because the App Store runs your tests against the uploaded zip with no build step of its own. The orchestrator owns generating any artefact a suite reads: one guard at the top that builds it when absent (`appstore-gate-compliance`).
- **Confusing a comprehensive suite with measured coverage?** They are independent claims. The App Store's SonarQube gate reads only the machine-readable coverage report your test stage emits (lcov at `coverage/lcov.info` for Node; per-stack paths in `deploy-recipes`), so a thorough suite that emits no report scores 0% and fails the gate. Run the suite under a coverage tool on the platform's exact flag, emit the report, and open the file to confirm the number is real; wire this and a Sonar-equivalent static-analysis pass into the loop at scaffold time, when the violation count is zero, not at upload time when it is hundreds (`appstore-gate-compliance`). Where a file cannot be measured honestly, exclude it from the coverage metric only, never from analysis, and record the rationale in `sonar-project.properties`. And know the full shape of what you are writing to: the gate scores FOUR conditions on changed code (new issues 0, coverage at least 80%, duplicated lines at most 3%, hotspots reviewed), with TEST FILES EXCLUDED FROM ALL FOUR. Two consequences for how a suite is judged: a test cannot lift coverage by existing, only the code it executes counts; and the duplication condition, the one condition with no analyser rule behind it, needs its own rung in the loop, scoped the way the gate scopes it (tests removed) so the local number is not optimistic in a way the platform's is not (`appstore-gate-compliance` section 2.2).
- **Asserting on page text in a browser check?** Scope the match to the ELEMENT that displays it, never to `document.body`. In a single-file artifact the inline `<script>` sits inside `<body>`, so `document.body.textContent` contains the source of every string the app can ever show: an assertion looking for a toast message in it passes whether or not the toast ever appeared. That is an assertion with one reachable verdict, which measures nothing (mutation-proof it, as above). Caught in this baseline by a mutant that broke session import and left the check green; scoping the same wait to `#toast` killed it immediately. The general form: when a test searches for a string, ask whether the string is present in the page for a reason OTHER than the behaviour under test.
- **A coverage number that will not move (or a gate that disagrees with your local number)?** Read the lcov, not the summary, and answer three questions before the next attempt: which files are IN the report, which are ABSENT (and therefore counted at 0% by a gate that reads the report rather than your config), and what the real denominator is. Then fix the mechanism rather than the number. The only lever that moves a coverage-on-new-code gate is converting uncovered or unattributed lines into covered lines, and the way to do that for an unimportable file is EXTRACTION: move genuinely pure logic into an importable module and unit-test it. Measure the rate and size the next extraction against it (one record: 8.8 points per 183 extracted lines), because adding tests to files that are already covered moves nothing (measured at one tenth of a point for about a hundred lines of new tests). Never exclude a file from coverage to move a number, because exclusion drops its covered lines too and can make the metric worse (76.5% to 66.4% in that record), and never fabricate coverage by marking a browser file covered without executing it or by adding assertion-free tests (`appstore-gate-compliance` section 2.1).
- **Refactoring to clear a metric (extracting helpers to cut cognitive complexity)?** Prove the behaviour is unchanged independently of the suite you already had: a parity harness comparing old and new outputs on the same seeded inputs, plus a full-page render smoke (`code-architecture`).
- **Loop too slow or costly?** Optimise time and resource without losing depth. Order the loop cheapest-first and put the one heavy leg last: the near-instant checks (syntax validation, pure-logic unit tests, static greps) run before the headless browser render-check, so a cheap failure never pays for a browser launch. In Continuous Integration, cache the browser so it downloads once rather than every run, and gate the render-check behind a path filter so it runs only when the rendered artifact (for the static archetype, `index.html`) actually changed; the deterministic legs still run on every change. Fail safe: when the path filter cannot tell what changed, run the render-check. The coverage and the checks never shrink; only the wasted work does. Server stacks apply the same shape: cache dependencies and any browser, and run the slow suite or container scan only when its inputs change. Before assuming the tests themselves are slow, PROFILE the harness: the setup can dominate. One suite fell from 119s to 54s (2.2x) not by touching the tests but by sharing one in-memory database per process and truncating between tests, because it had been booting a fresh WASM database per test (about 1.9s each, seventy times) while the migrations it blamed cost about 0.1s. Share an expensive fixture across the tests that can safely reuse it, reset state between them, and measure where the wall-clock actually goes before optimising it. Measure the FIXED per-file cost and the MARGINAL per-test cost first (fit a line over a few suites of different sizes): a suite that boots a database, a browser, or a WASM runtime is almost all fixed cost, invisible to per-test profiling. Then split the suite by cost CLASS, not by feature area, and name the cheap tier so it is reachable in one command (a pure-logic tier that runs in a fraction of a second, separate from the expensive-fixture tier), so an edit to a pure module is verified in a blink instead of paying the whole setup. If you add an affected-suites resolver (run only the suites importing the changed files), make it PRINT its estimate and fall back to the full parallel run when the affected set exceeds about a third of the files: scoping wins hugely for a leaf module but can be a net LOSS for a hub module many suites import, because a scoped run serialises what the full run parallelises, and an optimisation silently slower than the thing it replaces is worse than none.

## Standards (checkable assertions)

- Static: `npm test` runs validate, render-check (desktop and mobile), and static-checks, and exits 0 with all green.
- Static: any non-trivial inline logic is reachable by a test, sentinel-extracted and unit-tested out of band, and wired into the loop and the deployability gate.
- A leg that cannot run in the local sandbox exits non-zero with a clear "deferred to CI" banner, never a green pass; CI is the binding source of truth for it and a red required check blocks the merge.
- Every negative assertion is classified per environment; none is guaranteed-false on the platform runner that gates the deploy, and `npm test` passes in a fresh clone with only an install step first (`appstore-gate-compliance`).
- For a quality-gated deploy, the suite emits a non-empty machine-readable coverage report at the path the gate reads, a `sonar-project.properties` scopes it, and a per-commit static-analysis pass keeps violations at zero (`appstore-gate-compliance`).
- Server: `npm test` runs the built-in runner with coverage to `coverage/lcov.info` and exits 0; coverage is at least 80%.
- Every source file that carries logic appears in the coverage report, so nothing is scored at 0% purely by absence, and the report is read (not assumed) whenever a coverage gate and a local number disagree.
- Server: HTTP behaviour is tested in-process via the factory on an ephemeral port with isolated state.
- Server: every cross-runtime rule has a parity test; time-dependent logic uses an injected fixed date.
- Server: security properties each have a test; a browser smoke test renders every view with zero page errors.

## Failure modes and remedies

- **Render-check cannot find the browser driver (static).** Fix: install it and set `BROWSER_DRIVER_PATH` (`environment-setup`).
- **Coverage report missing or at the wrong path (server).** Fix: ensure the pretest step creates `coverage/` and the lcov reporter writes `coverage/lcov.info`.
- **An e2e test fails only in CI.** Fix: the browser is not installed locally; install it or treat CI as the source of truth for the smoke test.
- **A parity test fails after a change.** Fix: re-derive the client copy from the canonical server copy.
- **A test flakes on the wall clock.** Fix: inject a fixed date parameter.

## Verification

Static: `npm test` prints `JS syntax: OK`, two `PASS` lines, and `STATIC CHECKS: PASS`. Server: `npm test` passes with `coverage/lcov.info` produced and coverage at least 80%; `npm run test:e2e` passes with zero page errors.

## Worked example

Server: a new score dimension is added. A unit test asserts the server formula; a parity test asserts the client mirror matches to one decimal; an in-process HTTP test confirms the scored records endpoint; the Playwright smoke test confirms the score view renders with no page errors (the expensive endpoint mocked). `npm test` is all green with coverage written.

## Glossary

- **Verification loop (static):** validate, render-check, static-checks run by `npm test`.
- **In-process test:** building the app via the factory on an ephemeral port without a separate server.
- **Parity test:** asserting two implementations of one rule agree.
- **Smoke test:** the single browser test rendering every view with external calls mocked.
- **Coverage / lcov:** proportion of source exercised, reported as `lcov.info`.
- **Test pyramid:** many unit, fewer integration, very few end-to-end tests.
- **Arrange, act, assert:** the three-part shape of a clear test.
- **Mutation testing:** breaking the code on purpose to check a test catches it.
- **Flaky test:** one that passes and fails without a code change; treated as failing.
- **Test smell:** a pattern (over-mocking, brittleness, slowness, non-determinism) that predicts future failure.
- Other terms: `glossary`.

## Provenance

Merged from the static bundle's validate, render-check, and static-checks scripts and spec, and the server bundle's testing-standards skill (node:test with lcov, in-process HTTP via the factory, parity tests, injected time, security-property tests, Playwright smoke test).

## Field lesson: a strict render-check earns its keep

The static render-check should fail on any browser console error, seed the stored state it needs, and dismiss the splash before it probes the page. Failing on console errors caught a real defect, an ignored CSP directive, that no static grep would have found. Run the render-check as the binding leg in continuous integration: locally the headless browser download is often blocked by egress policy, so the check should exit "deferred, not a pass" rather than green, and the pipeline stays the source of truth.
