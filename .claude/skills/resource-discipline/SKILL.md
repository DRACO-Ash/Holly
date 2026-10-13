---
name: resource-discipline
description: How to spend the least time and tokens for the best result. Use when deciding whether to run a gate, spawn a subagent, launch a workflow or attempt an App Store upload, whenever a task is costing more cycles than it should, and to know when to STOP fixing something.
---

# Resource discipline

> The governing principle: every check can be run at one of several rungs that differ in cost by more than two orders of magnitude. Push every check to the cheapest rung that can catch it, and reserve the expensive rungs for confirmation, not discovery. Nearly all wasted spend comes from catching at a high rung what a low rung could have caught.

## Purpose and scope

The standard is executed with an AI assistant that spends time and tokens, and the App Store gate spends whole upload cycles, so spending them well is itself a skill. This is the durable way to get the best result without over-committing resources. Scope is the economics of the tooling. The collaboration pattern is `working-with-ai`; the loop legs are `testing-standards` and `ci-cd`; the upload contract is `appstore-gate-compliance`.

## When to use

● Deciding whether to run a gate, spawn a subagent, launch a workflow, or attempt an upload.
● A task is taking more gate re-runs or upload cycles than it should.
● Scoping a change so it clears every rung in one pass.

## The cost ladder (the governing model)

Cheapest to most expensive, for this baseline:

| Rung | Tool | Rough cost | Catches |
|---|---|---|---|
| 1 | `Grep` / `Glob` / region `Read` | near-free, instant | known facts, cross-file consistency, "does X exist" |
| 2 | `build.mjs --check` | seconds | artifact drift from source |
| 3 | `npm run test:fast` | seconds | syntax, analyser and zip assertions, static security greps |
| 4 | full `npm test` (browser leg) | seconds plus a browser | render regressions on desktop and mobile |
| 5 | `Explore` / a general-purpose subagent | thousands of tokens | fan-out reads, "where does this live" |
| 6 | one binding gate subagent | tens of thousands of tokens | a correctness, security, or deploy verdict |
| 7 | a parallel gate pair or a workflow | a multiple of rung 6 | independent verification at scale |
| 8 | an App Store upload cycle | a full human-in-the-loop deploy attempt, capped at two retries per pipeline | only the server-side SonarQube ruleset, the image scan, a coverage-on-new-code gate, and the duplication condition |

The rule that falls out of it: never spend a rung-6 verifier to find what a rung-1 grep would find, and never spend a rung-8 upload to discover a rule you could have written to from the start.

**Know what each rung actually proves, and say "unverified" when none of them proves it.** A rung is a proxy for a gate only where it computes the same thing the gate computes. A pipeline simulation computes coverage the way your `sonar-project.properties` declares it, so it is not a proxy for a platform check that ignores that file and scores only the release delta: one project's simulation was green at 99.2% while the gate read 76.5%, and it re-uploaded six times before reading the coverage report itself (`appstore-gate-compliance` section 2.1). When a number is only knowable at rung 8, do not call it passing at rung 3. Name it unverified, make everything else acceptance-by-construction so it is the single remaining variable, and never let a rung-8 attempt be the instrument that tests a hypothesis a local read of the artefact could settle.

## Before satisfying a gate condition, compute whether it CAN be satisfied

The most expensive mistake available is diligently fixing findings against a condition that is
arithmetically out of reach. A gate reported `Line coverage is 20.9% (required: 80%)` and told us to
add unit tests. The uploaded package contained 4,471 analysable lines, of which 2,707 were browser
wiring that no node test runner can import: **the ceiling was 39.5%**, so the instruction could not
be followed and every test written towards it was waste.

One division would have said so. So do the division first:

● **A coverage floor?** covered-able lines over total analysed lines. If the ceiling is under the
  floor, stop and change what is analysed.
● **A "zero new issues" condition on a large legacy surface?** count the findings and the lines they
  live in, then decide between cleaning and excluding. 203 findings across 2,707 lines of another
  era's idiom is a rewrite, not a fix, and one of the findings was a false positive.
● **A condition on generated or vendored content?** it is almost always cheaper to stop shipping it
  than to make it comply.

**The general rule: when a gate condition is expensive, the first question is not "how do I satisfy
it" but "is the thing being measured the right thing to be measuring".** Four upload cycles here were
spent moving one file in and out of a package, because each move fixed one condition and broke
another, and nobody had computed that the file could never satisfy both.

## When a rung-8 gate fails you, bring its RULES down the ladder, not just its verdict

An upload gate that fails is expensive twice: once for the cycle, and again because the natural
response is to fix the findings and re-upload, which buys a verdict rather than a check. **Fix the
findings, then move the rule.** Take the exact rule families the report named, assert them at the
cheapest rung that can see them, and watch each one fail before trusting it.

This baseline paid for the lesson at the SonarQube gate: 315 issues, 100+ smells and 14 security
hotspots, and nothing local scored a single one of those rules. The fix was two moves, and the second
is the durable one: shrink what is analysed (an allowlist archive), then assert the named rule
families in the packager so a non-compliant archive cannot be BUILT. A local analyser was not
available, so the check states what it cannot see rather than implying coverage it does not have.

The general form: **a gate you can only run at rung 8 is a gate you are not running.** You will not
get a full local replica, and you do not need one. You need the subset the gate has actually failed
you for, at a rung you can afford to run on every build.

## Enforce by cost tier (quality and efficiency are one lever)

Building to standard from the start and spending the least time are not opposites; they are solved by the same move, assigning each check to the cheapest rung that enforces it. A deterministic, universal rule (a secret, an em-dash, a baked `ENV PORT`, a stale lockfile) belongs in a PRE-WRITE HOOK: it fires in milliseconds, blocks at the keystroke before the artifact exists, and so can never cause a round-trip or reach a gate or your attention. This is why "silly" trivia costs nothing when placed right: the answer to not wanting to spend time on em-dashes is not to drop the rule, it is to enforce it invisibly at rung 0. Mechanical faults (drift, contrast, coverage, a lint class) belong in the deterministic loop, seconds on every edit. Only judgment, is this logic correct, is it secure, does it read right, belongs in a binding gate, run once per change on a self-verified green tree so it CONFIRMS rather than discovers.

Seen this way, the doom loop of endless remediation and the fear of over-checking trivia are the SAME defect: a check running at too expensive a rung. An em-dash caught by a gate is slow and infuriating; the same em-dash caught by a hook is free and invisible. A correctness bug discovered by a gate after building is a doom loop; the same bug caught by writing the check first is a pass. So the efficient move is never to add checks, it is to RELOCATE each to its cheapest rung, and to build only the checks a project's real risks warrant (a guard for a defect class this project does not have is the process-bloat `learn-from-feedback` warns against). Push trivia down to hooks, mechanical faults to the loop, and reserve the gate's expensive attention for what only judgment can settle; then the standard is met from the first commit and the round-trip count, the dominant cost, stays at one.

## Compute the route per ask (adaptive, one fixed objective)

There is no single fixed process to run every time; there is one fixed OBJECTIVE, fully cleared and releasable, as fast as possible, with the standards held, and a route to it computed fresh for each ask. So at every point where you plan or execute a request, spend the first moment on the route, not the habit: name the aim, scope to the smallest change that achieves it, then work out which rungs and gates that change actually needs and in what order, and take that path. A pure version stamp or comment fix is a trivial amend, verified by the loop and not re-gated (the operating cadence below); a logic change needs the loop and the engineering gate; a change to a security surface adds the security gate; a visual change adds the design critic; a deploy adds the deploy-gate and a human yes. Running more than the ask triggers is waste; running less is a defect. Then sequence the chosen route to one clean pass, self-verify to green, freeze the tree, gate once, so the cheapest complete route is also the fastest. The route changes with every ask; the objective does not. This is the same principle as the cost ladder and the cost tiers above, applied one level up, to the whole shape of a task rather than to a single check: optimise the path to cleared-and-releasable, per ask, every time.

## Per-tool discipline

● **The verification loop (rungs 2 to 4).** Run `test:fast` after every source edit; it is deterministic and cheap and catches most regressions. Run the full loop with the browser leg only at commit boundaries, and treat continuous integration as the binding source of truth for that leg when the local browser is awkward. Batch edits, then verify once, rather than running the full loop between micro-edits.
● **The binding gates (rung 6) are verifiers, not iterators.** They are the most expensive thing invoked routinely. Front-load internal consistency with a rung-1 sweep and a self-review before calling one, because a FAIL that needs a re-review costs roughly twice. Batch the change so a gate runs once, not per half-change. Run independent gates concurrently (engineering and security in one message), and re-run only the gate whose inputs actually changed.
● **Subagents and Explore (rung 5).** Use `Explore` for genuine fan-out, because it returns the conclusion not the file dumps and keeps the caller's context small. Read a region directly (rung 1) when the file and line are already known. Do not spawn a subagent for a single known fact. Send independent subagents in one message so they run in parallel. Read a subagent's verdict from its FINAL message only, anchored to line start: a substring grep over the whole transcript matches the instruction in your own prompt (which literally contains "VERDICT: PASS or VERDICT: FAIL") and reports a false result.
● **Workflows (rung 7) are for scale and adversarial confidence, not for bounded tasks.** Orchestrating many agents for a task one context can hold is the exact over-commitment to avoid; reserve them for a repo-wide migration or an exhaustive audit with adversarial verification.
● **Skills (rung 1 to load).** Invoking the skill that owns a concern is cheap and deterministic; rediscovering its content by reading source is not. Load the owner rather than re-deriving the standard. This is a token saver.
● **Rung 8 has a HARD ceiling, not just a high price: one retry per job, two per pipeline, with a sixty-second cooldown.** So an upload buys about three chances to learn something, total, and a blind retry spends one to learn nothing. The single exception is a job reporting that analysis did not run, which is a platform fault and a legitimate retry; everything else needs the diagnosis before the retry. Local rounds are effectively unlimited, which is the actual arithmetic behind every "move it down a rung" rule here (`appstore-gate-compliance` section 2.2).
● **App Store uploads (rung 8) are the most expensive resource there is,** because each failed upload is a full human-in-the-loop cycle and failures come in waves. This is why writing to the gate from the first line and running a local checker are the highest-return investments in the system: every rule moved from "discovered at upload" to "written correctly" or "caught locally" converts a rung-8 cycle into a rung-3 second (`appstore-gate-compliance`).

## Token hygiene (always on)

● Read the region you need, not the whole file; prefer `Grep` and `Glob` over shell reads.
● Do not re-read a file you just edited to verify it; the edit already confirmed the write.
● Do not re-derive facts already established, or re-run a search another agent ran.
● Keep diffs minimal (the surgical-edit rule): fewer changed lines is less for a gate to read and fewer new-code lines for the SonarQube gate to flag, so efficiency and compliance point the same way.
● Use the scratchpad for temporary files so the tree stays clean and no extra check is triggered.
● Keep running commentary minimal: report the decision, the blocker, and what shipped, not a step-by-step narration of every edit and check. Prose the reader must read is itself a token cost; a change is documented by its diff and audit row, not by a paragraph describing it.

## Right-sizing effort and model

Match the reasoning tier to the task: a rename, a version bump, or a grep sweep does not need high reasoning effort or the top model; the hardest verify or adjudicate step does. When delegating, let a subagent inherit the session model unless a cheaper tier clearly fits. Do not pay for maximum reasoning on work a lower rung could finish.

## Operating cadence (how a change moves from edit to shipped)

The cheapest cycle is the one not repeated. Move a change through these steps, not a gate per micro-edit:

● **Batch to a whole, self-consistent change, then gate once.** Group related edits into one release rather than gating each half-change; the surgical-edit rule keeps the batched diff readable. Fewer releases means proportionally fewer rung-6 cycles, which are the dominant spend.
● **Sweep before you gate (rung 1).** Before invoking a gate, grep the cross-file invariants a gate should never be spent discovering: counts, ids, version and edition stamps, references to a renamed thing. A gate that FAILs on a grep-findable fact cost a whole extra cycle.
● **Route the gates by what changed.** The binding engineering gate runs on every shippable change, on its final state. The security gate runs only when the security surface changed. The advisory design-critic is for net-new visual or interaction design, or a real contrast, theme, or accessibility risk; it is not run for reusing an already-approved pattern or removing an element, where a single self-checked screenshot settles it.
● **Do not gate what is not yet reachable at runtime.** A binding gate is for code a user or the platform can actually reach. Scaffolding, an unwired module, or infrastructure with no runtime path yet is verified by the deterministic loop and a read, not by a rung-6 review; gate it when it goes live. Gating unreachable infra spends the most expensive rung on code nothing runs.
● **Self-verify a trivial amend; do not re-spawn the gate.** After a gate PASS, a trivial follow-up (a count or comment fix, dead-code deletion, or a change the reviewer itself named safe) is confirmed by the deterministic loop, not another rung-6 review. Re-run a gate only when the amend changes behaviour the gate reasoned about.
● **Budget the expensive confirmations.** Screenshot only a visual change that genuinely needs an eye (a new layout, a contrast or theme risk), one or two shots, not a full matrix; trust the render-check for interaction. Keep status to a line unless a gate FAILs, a decision is needed, or more is asked.

● **Pin the subjective target before building it.** Cycles-to-green is about verification; the same waste exists in requirements. A feel, mood, or look target left as a bare adjective ("make it flow", "less corporate") is discovered one release at a time, and each pass carries a full loop, gate, merge, and package. Fix the target up front with a concrete reference and an acceptance line (`flight-plan`), then build to it once and batch the passes behind it. Across one project roughly a dozen presentation-only releases converged on an identity a pinned reference would have reached in a few.
● **Read the VERB of the instruction, and ask when it is doing no work.** The single most expensive item in one project's ten-rejection window was not a gate failure at all: seven commits rebuilt an interface in answer to an instruction that asked only for it to be **examined**, and one further commit reversed part of them. One clarifying question at the start would have cost a minute (Adam Field, Event SCOUT, 1 September 2026). Examine, assess, review and check are not build. When the verb and the apparent intent disagree, the question is cheaper than either reading, and it is cheaper by two orders of magnitude. This is the same instrument as pinning a subjective target, one step earlier: pin the SCOPE before pinning the target.
● **A whole class of tests failing at once is an environment fact until proven otherwise.** Half an hour went on diagnosing 22 browser-test failures in that window that were entirely a version mismatch between the pinned test runner and the browser installed in the container; nothing in the repository was at fault and no change was needed. Before root-causing a wave, ask what the failures have in common that is not your code: one tool, one runner, one install. And when the answer is a workaround everybody repeats, that is a defect in the setup, not a habit.
● **Measure a budget AFTER the fixes, never between them.** A legacy debt budget was set three times in one sitting there, because each measurement caught the tree mid-repair. A number read off a half-finished state is re-read, and each re-read is a full round.

● **Integrate continuously; do not diverge a branch.** A long-lived branch that drifts from the line others are committing to buys a reconciliation release with no feature in it. Merge little and often, or keep the branch a strict superset, so the merge back is clean.
● **Remove what a change orphans, in the same change.** Deleting an element leaves its CSS and JavaScript dead; clean them in the same edit rather than deferring a tidy the pace never reaches. Deferred dead code is re-noted release after release and read by every gate in between.
● **The environment is part of the build; do not contend with a live gate, and diagnose "stuck" with evidence.** A binding gate subagent is itself a heavy consumer, so a running gate makes the box busy: on a small core count, launching the full test suite while a gate runs starves both and both crawl. A detached background agent also does not survive an ephemeral container being reclaimed during an idle wait, so it silently dies and a re-run tells you nothing new; keep wait windows short or schedule a check-in rather than ending a turn into a long idle. And when work seems "stuck", spend a minute on evidence before hypothesising: uptime (a reclaimed container), the process list (a gate eating the cores), and the output file's mtime (progressing slowly versus hung) separate the three causes fast. Guessing the cause of stuck is itself the waste.

The target is cycles-to-green = 1 at each rung: a change that was right before it was checked.

## Verification round-trips: the dominant cost, measured

When verification feels expensive, the bill is almost always the NUMBER of gate round-trips, not the runtime of any single check. Measured on one release, 74% of commits were gate remediation rather than feature work, and each gate round paid for the verification loop roughly three times: yours before submitting, plus one inside each reviewer agent that re-runs the loop to verify its own findings. Narrowing what a round inspects saves minutes; making each round the LAST round saves days. So:

● **Meter it.** Count feature commits against remediation commits per release; above 50% remediation, the defect is in the fix method (fix by class, `appstore-gate-compliance`), not the gate. Count the full-loop runs per gate round; three is typical and usually two too many. Attribute the waste to the right axis, round-trip count, per-run runtime, or re-run frequency, and fix the largest, which is almost always round-trip count.
● **Freeze the tree at gate submission.** Run the full loop on the exact tree you submit, and do not commit again until the gate returns; a change made while a reviewer is measuring invalidates its verdict (a reviewer cannot certify a state that moved while it was measuring it). Freezing is not etiquette, it is what makes a verdict mean anything.
● **Run the loop once, share the result.** On the frozen tree, run the loop once and hand the reviewers the recorded result (exit status, counts, coverage, the lcov path) rather than have each re-run it; a reviewer re-runs only to challenge the recorded result.
● **Capture once, query the capture.** Never re-run a suite to read a different part of its output (the coverage table on one run, the pass and fail totals on another); write the run to a file and grep the file.
● **Never diff-scope a binding REVIEW gate.** Scope the TEST tier by what changed; never narrow the reviewer. The gate's value is precisely that it looks where the fix did not: on one release a defect class survived seven rounds because each round fixed only the sites the reviewer named, and a diff-scoped gate would have passed rounds two through seven while the class still lived in untouched files. Route WHICH gates run by what changed (skip the security gate when no security surface moved), but never narrow a gate you do run so it cannot catch the class elsewhere.

## Decision rules (the pre-invocation checklist)

Before invoking anything above rung 3, ask:
● **Can a cheaper rung catch this?** If a grep or the fast loop can, use it.
● **Is this discovery or confirmation?** Use expensive verifiers to confirm a change believed correct, never to find what a cheap check would have caught.
● **Is the change whole and self-consistent yet?** If not, finish it before gating, so the gate runs once.
● **Are these subtasks independent?** If yes, run them in one parallel batch.
● **Does the scale justify orchestration?** A workflow for a bounded task is over-commitment.
● **Which pipeline stage would this finding fail?** Name it before you open a round. If the honest answer is "none", the finding is backlog, not a blocker: record it and move on. Measured on another project: four of seven releases went to adversarially hardening a local secret scanner the deployment pipeline never runs, while the stage that did block, code quality, went unexamined and rejected the upload (`docs/retrospectives/mission-control-v3.2.55-v3.2.62.md`, Waste, first item). A reviewer told to break a pattern-matching guard will succeed indefinitely, so bound the round by the threat model the pipeline actually enforces.
● **Is this fix new, unreviewed code?** It is. A fix made under gate pressure carries the next defect at a rate worth planning for: 7 of 19 commits on one project attributed their defect to the previous fix, a 37% rate (`docs/retrospectives/ask-staqs-r65-r83.md`, Summary), another recorded four fail-opens each introduced by the fix for the last one (`docs/retrospectives/mission-control-v3.2.55-v3.2.62.md`, What did not go well), and this baseline's own worst regression came from a fix that deleted live code while tightening a checker (V2.124 in the in-app change log). So the fix gets the same mutation proof and the same gate as the thing it replaced, and a long hardening run does not converge just because it is long: if each fix draws a new finding, stop fixing and question whether the mechanism should exist.

## Standards (checkable assertions)

● The deterministic loop is run before any gate; the gates are run only on a green loop.
● Gates are routed by what changed and run in parallel; only the gate whose inputs changed is re-run after a fix.
● No expensive rung is used to discover what a cheaper rung would catch; no upload is spent to discover a writeable-from-the-start rule.
● Related changes are batched to one gated release; a rung-1 consistency sweep precedes the gate; a trivial amend after a PASS is loop-verified, not re-gated; the advisory design review is reserved for net-new design or a real invariant risk.
● Diffs are minimal; temporary work stays in the scratchpad; established facts are not re-derived.

## When to STOP fixing (the rule this baseline learned the expensive way)

Everything above is about spending the least to get a thing right. This section is about the
opposite failure, and it is the one that actually happened here: spending without bound on something
that was already right.

**The third consecutive failure of the same check is a finding about the INSTRUMENT, not about the
check.** Count the rounds. One failure is a bug in your fix. Two is a bug in your understanding.
Three is the wrong tool for the property, and the fourth round will find a fourth escape, because you
are enumerating against a surface the other side gets to choose from.

Measured, in this repository, V2.140 to V2.141: a source-text rung asserting that one function is a
constant-time comparison failed five consecutive binding reviews. Each round closed one route and the
next round found the next: payload inside the body, then above the anchor, then in a sibling
declaration, then in the import, then in a re-binding at the call site. The shipped code was correct
in every one of those rounds and was confirmed correct by every reviewer. Fourteen commits produced
eight lines of shipped code. The loop ended when a human asked whether it was a loop.

**The rule applies to a failing UPLOAD exactly as it applies to a failing review**, and it is easier
to miss there because each cycle arrives days apart and wearing a different error message. Three App
Store uploads failed on one class here (no `git`; then no `bash`, `tar`, `zip`; then a tree with six
fewer files). Each was fixed on its own terms and each fix passed a local simulation, because the
simulation was rebuilt to model the last failure rather than the target. Nobody counted to three. The
counter does not care that the messages differ: **same check, third failure, change the instrument.**

**AND COUNT THE ROUNDS ON THE COMPONENT, NOT ONLY ON THE CHECK. This is the level the rule was
missing, and it cost seventeen rounds of binding review to find out.** The rule above counts
consecutive failures of one CHECK, and it works: applied inside a scanner here it correctly retired a
character list, then a keyword list, then a lookback window, then a suppression marker, then a hundred
and thirty-five lines of hand-written lexer. Each of those was the right call. **And the component
kept generating rounds anyway**, because "change the instrument" was being applied one level too low
every time: the instrument under review was never the regex or the lexer, it was the decision to have
a local approximation of an undecidable property at all.

So keep a second counter. **The third consecutive gate round on one COMPONENT is a finding about
whether the component should exist**, and the question to ask at that point is not "what does this
mechanism need next" but the two the loop cannot ask itself:

● **What is this component FOR, and what does it buy over the checks that already exist?** Measure it,
  in one command, on the real surface. Here the answer was on record from the start and nobody read
  it: the scanner's marginal value over the archive allowlist plus the existing loop was a regression
  alarm on seven files we own. The allowlist is what took the hotspot count from fourteen to zero.
● **Is the property DECIDABLE by this class of instrument?** If the honest answer is no, the correct
  output is a narrowed claim and a declared residual, not a better mechanism. A control whose stated
  scope is wider than its mechanism will produce a finding every round for ever, because every round
  finds a real input outside the mechanism and inside the claim. Narrowing the claim is what ends it.

**And notice who stopped it.** Both times this baseline has run a loop like this - V2.140 and this one
- it ended when a HUMAN asked whether it was a loop. That is the defect to design against, because a
loop that needs an outsider to name it has no internal trigger at all. Two counters, both cheap: the
per-check one above, and a per-component one that fires at three rounds and asks the two questions.
Write the count in the commit, so the next round starts from a number rather than from a feeling.

**What to do at the third failure**, in order of preference:

● **Change the instrument, not the pattern.** A regex over source text cannot establish which binding
  a caller reaches; an AST that resolves the identifier can. If the property must stay mechanically
  gated, pay for the right instrument once.
● **Declare the gap and route it to review.** Name the property unverified in the register, exactly
  as a genuinely unmeasurable one is named, keep whatever partial check you have as a labelled
  best-effort regression aid, and let the binding review own it. **An honest gap beats a rung that
  reads closed and is not**, and it costs one edit instead of five rounds.
● **Accept the residual and write it down.** Some properties are not worth an instrument. Say so with
  the reasoning, so the next reader inherits a decision rather than an oversight.

Three related stopping signals, all of which fired in that stretch and none of which were heeded:

● **The diff is mostly prose.** If a round changes no runtime code, it cannot have fixed a runtime
  defect. Measure it: `git diff --numstat <base>..HEAD` grouped by directory. Fourteen commits, 324
  lines of test, 237 of change log, 8 of shipped code, is a number you can read in ten seconds and it
  says the work finished several rounds ago.
● **The findings are about your own last round.** When most findings are defects in the corrections
  rather than in the original work, the loop is self-feeding. Five of the last twelve were.
● **The cost of the guard exceeds the cost of the thing guarded.** Five review rounds to protect five
  lines that nobody is editing is not a trade anyone would make deliberately.

**The doom loop is not a failure of rigour, it is rigour pointed at the wrong rung.** It feels
identical from the inside to doing a careful job, which is why it needs a counter and not a
judgement.

## Scope every gate brief to the changed surface (measured: 42% cheaper, and it found MORE)

A binding reviewer reads what you point it at. Point it at a whole diff and it reads the whole diff;
point it at two files and name what is out of scope, and it reads those two properly. Measured over
twelve gate invocations on one release, from the tool's own usage reports:

| Brief | Tokens | Tool calls |
|---|---|---|
| Security, unscoped, round 1 | 190,700 | 89 |
| Security, rounds 2 to 8, average | about 107,000 | about 53 |
| Security, round 10, tight brief | 42,406 | 26 |
| Engineering, whole diff | 111,154 | 44 |
| **Engineering, scoped to ONE file** | **64,038** | **21** |

**The scoped brief cost 58% of the unscoped one on the same commit, used half the tool calls, and
found a defect the wide brief had missed** (a false PASS in a harness). Round 10 cost 22% of round 1.
There is no quality trade here: a reviewer with a narrow subject goes deeper into it.

What a scoped brief contains: the files in scope, an explicit sentence naming what is OUT of scope and
why, the specific question you cannot answer yourself, and the measurements you have already taken so
the reviewer confirms rather than rediscovers. Say what you want attacked. "Review this" is the
expensive form of "I have not decided what I need".

## A budget you have never added up is not a budget

The same release that produced the table above cost **about 1,220,000 subagent tokens across twelve
gate rounds, and shipped 8 lines of runtime code.** That ratio was available at any point from about
the sixth round. Nobody totalled it until a human asked whether the work had become a loop.

So: total it. **Every third gate round, before starting the fourth**, out loud, in the units that
matter. A cadence is the whole point: "periodically" is what produced the 1,220,000, because the
review that would have caught it was always available and never due.

● **Tokens:** sum the subagent usage reports for the task so far.
● **Diff composition:** `git diff --numstat <base>..HEAD` grouped by directory. Runtime code against
  prose against tests, in ten seconds. Fourteen commits, 324 lines of test, 237 of change log and 8 of
  shipped code is a sentence you can read at a glance and it says the work finished several rounds ago.
● **Wall clock:** the loop's own budget line, and the slowest case (`duration_ms` per case).

This sits next to the stopping rule above because it is the same defect seen from the other side. The
stopping rule tells you when a check has failed too often; this tells you when the whole effort has
cost too much. **Both are counters rather than judgements, because from the inside a doom loop feels
exactly like doing a careful job.**

## Three cheaper habits the same release paid for

Small, and each one measured rather than reasoned.

● **A prose invariant belongs in a `--check` script, not in a reviewer's attention.** A consistency
  fact (a version cited in two files, a cross-reference that must resolve, an edition stamp) costs
  milliseconds to assert and roughly a tenth of a gate round to write. Evidence: the pack-edition
  rung caught a stale edition on its **first** run, eight commits old, that twelve gate rounds had
  never reported, and the reference rung then found a dangling skill name three releases old. A gate
  reads what it is pointed at; a script reads the same thing on every commit for ever. So when a
  reviewer finds a consistency defect, the fix is the script, not the correction.

● **Batch the rounds, not just the findings within a round.** Findings were correctly batched and the
  ROUNDS were not, which is how one rung consumed five of them. Before invoking a gate, ask what else
  is ready to go in the same tree; after a verdict, fix everything it raised plus everything you have
  since noticed, and re-gate once. A gate invocation is a rung-6 cost whatever it carries, so carry a
  full load.

● **Never re-run an expensive check to make an unexplained failure go away, and never pipe a
  diagnostic through a truncating filter.** Both halves come from one incident: `npm run deployable`
  printed `NO` twice with no reproducible cause, and the first occurrence stayed unexplained for most
  of a session because the output was read through `tail -2`, which cut the line naming the cause. Read
  the whole failure once, `grep` for the reason rather than trimming to the verdict, and record what
  you find with its cause even when you decide not to fix it (`docs/AUDIT.md` section 4 carries that
  one, deliberately not re-engineered). A re-run that goes green teaches nothing and costs the check
  twice; the record is the only durable output of an unreproducible failure.

## Match the gate to the change (do not gate prose with a security review)

A binding reviewer finds defects. Given a diff of documentation it will find documentation defects,
and fixing those produces more documentation. That loop is easy to start and hard to notice.

| What changed | Loop | engineering-reviewer | security-reviewer |
|---|---|---|---|
| Runtime code (`server/`, `src/`) | yes | yes | if it touches a control |
| A check, rung or test | yes | yes | if it guards a control |
| Build or packaging scripts | yes | yes | if it decides what ships |
| Skills, docs, change log, comments | yes | **only with the code it describes** | no |

The last row is the rule that was missing. Prose is verified by the rung that reads it (a `--check`
script that compares a figure to its source) and by the review of the change it accompanies, never by
a standalone gate round of its own. If a claim in prose is worth gating, it is worth a rung: cheaper,
repeatable, and it cannot start a conversation.

## Failure modes and remedies

● **A gate FAILs on something a grep would have shown.** Cause: discovery at rung 6. Fix: a rung-1 consistency sweep and self-review before gating.
● **Two gate passes for one change.** Cause: gating a half-change, or an internal contradiction. Fix: finish and self-check the whole change, then gate once.
● **A workflow spun up for a bounded task.** Cause: over-orchestration. Fix: do it in one context; reserve workflows for genuine scale.
● **Repeated upload cycles.** Cause: rules discovered at rung 8. Fix: write to the gate from the first line and run the local checker (`appstore-gate-compliance`, `ci-cd`).
● **Rounds spent on a control the pipeline does not run.** Cause: an unbounded threat model, and no stage named before the round opened. Fix: the "which pipeline stage" rule above; move it to backlog with its measurements.
● **A broad analyser sweep that reports hundreds of findings.** Cause: fixing rules the gate does not run. Measured elsewhere: 562 problems reported where the gate's own classes accounted for 67, and fixing the other 495 would have written a large amount of new code for the next scan to analyse (`docs/retrospectives/ask-staqs-r65-r83.md`, Waste to eliminate). Fix: narrow to the classes the gate has actually reported, and record the rest as a named blind spot rather than a queue.
● **A dozen presentation releases converging on one feel.** Cause: a subjective target discovered by iteration. Fix: pin it with a reference and an acceptance line at kickoff (`flight-plan`), then batch the passes behind it.
● **A reconciliation release with no feature in it.** Cause: an avoidable branch divergence. Fix: integrate continuously or keep the branch a superset.

## Verification

Track cycles-to-green: the number of gate re-runs and upload attempts a change takes. The target is one clean pass at each rung, which is simultaneously the cheapest, the fastest, and the best-quality outcome, because a change that passes first time was right before it was checked.

## Glossary

● **Cost ladder:** the rungs a check can run at, cheapest to most expensive, from a grep to an App Store upload.
● **Cheapest rung that can catch it:** the rule to run each check as low on the ladder as will still catch the problem.
● **Verifier, not iterator:** a gate confirms a change believed correct; it is not a loop for finding what a cheap check would catch.
● **Cycles-to-green:** the count of gate re-runs and upload attempts to reach a pass; the metric to drive to one.
● Other terms: `glossary`.

## Provenance

Distilled from this project's own working evidence, where a gate FAIL that a cross-file grep would have prevented cost an extra binding-review cycle, and from the App Store field reports where rules discovered at upload cost waves of full cycles. The remedy in both was the same: catch every check at the cheapest rung that can catch it, and reserve the expensive rungs for confirmation. Cross-referenced to the owning skills so a gap routes back to its owner.
