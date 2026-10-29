**BLUESTAQ LIMITED** | Code Quality Catalogue

# Code quality issues raised and resolved in Holly, V0.1 to V0.13

**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify
**Compiled:** 29 October 2026, from commit f8a00bd of the Holly repository (branch `claude/rehydrate-foundations-bundle-abogpu`)
**Covers:** Holly V0.1 (14 October 2026) to V0.13 (21 October 2026)
**Entries:** 444: 342 resolved, 36 accepted with a recorded reason, 14 deferred, 51 open, 1 superseded
**Audience:** Claude Code, and the developers it works with, building other applications, especially Python and FastAPI services with a React and TypeScript front end for the Bluestaq App Store.

> **BLUF**
>
> Holly is a FastAPI server with a React dashboard, deployed on the Bluestaq App Store, whose pipeline runs tests, SonarQube Code Quality (no new issue allowed), dependency and container scans, DAST and Deploy. Five of its eight recorded uploads failed: one at the test stage and four at Code Quality, each time after passing every local check, because nothing local ran the platform's analyser. Every change also went through binding engineering, security and deploy gates, which found races, fail-open controls, untested guards, stale-response bugs, pipeline mismatches and records that claimed more than the evidence held. This file lists every issue with its fix, the guard that now catches it earlier, and the lesson for another application.

## How to use this file

● **Read Part 1 first.** It is short: what the platform failed, a prevention checklist, and every analyser rule at a glance.
● **Search Part 2 when you meet a problem.** Search by rule key (for example `S2004`), by theme heading, or by a word from the problem. Each entry stands alone.
● **Take the Lesson and the Guard, not the Holly details.** File names, commits and figures are Holly's worked example. The **Lesson** and **Applies to** lines are the transferable part, and the **Guard** says how to catch the issue before review.
● **Respect the certainty marker.** An entry marked inference or mixed rests partly on inference recorded at the time. Check it against your own platform before relying on it.
● **Check Part 3 against your own project.** It lists what Holly still carries: open, deferred and accepted items.

# Part 1. Read first

## 1.1 What the platform failed

From `scripts/upload-baseline.txt`, the committed record of every upload handed to the App Store.

| Release | Commit | Platform outcome | What failed |
|---|---|---|---|
| V0.4 | dccfbdc | Failed | Both test jobs failed at the test stage (CQ-297, CQ-298) |
| V0.5 | 56c55a9 | Failed | Code Quality: 68 findings, 5 bugs, 2 vulnerabilities and 61 code smells (Part 1.3) |
| V0.6 | none | Not uploaded | |
| V0.7 | 452e3c7 | Failed | Code Quality: 1 new code smell, S1994 (CQ-004); DAST: no answer on 8080 within 300 seconds (CQ-299) |
| V0.8 | 0ebea48 | Passed | All 11 stages, Deploy included |
| V0.9 | c68a062 | Passed | All 11 stages; the platform gateway then refused the app's own bearer token at runtime (CQ-042) |
| V0.10 | f025c2c | Failed | Code Quality: 2 new code smells, S6819 (CQ-003) |
| V0.11 | 049e162 | Passed | All 11 stages, Deploy included |
| V0.12 | f6951a6 | Failed | Code Quality: 8 new code smells, S2004 6 times, S6557 and S4138 (CQ-002, CQ-005, CQ-006) |
| V0.13 | 0180d55 | Not yet recorded | Packaged 21 October 2026 with V0.12's smells fixed: TBC, re-verify |

## 1.2 Prevention checklist

Each line points to the entries behind it.

1. **Run the platform's analyser rules locally before every upload.** Add every rule key the platform has failed you on to the local lint the moment it fails, and run a wider Sonar way probe before each upload. Holly now lints S2004, S4138, S6557 and part of S7723 in ESLint, S7503 through ruff, S3776 through complexipy at 15, and duplication through pylint. (CQ-001)
2. **Prove a local stand-in before trusting it.** It must reproduce the platform's last real failure on that commit before its clean result counts, with rule thresholds set explicitly rather than left at plugin defaults. (CQ-416)
3. **Treat every review fix as new, unreviewed code.** In Holly the fix for one finding was repeatedly the source of the next: S1994 came from a review fix, S7723 from the S4138 fix, and python:S1940 from a security fix. (CQ-417)
4. **Prove every guard by deleting it.** A test that names a guard is not evidence until removing the guard turns it red for the right reason. (CQ-424, CQ-237)
5. **Rehearse each platform job on the packaged upload,** with only the tools the platform's job has, from the directory the job runs in, and check the coverage report names every source file the analyser scores. (CQ-313, CQ-310, CQ-297)
6. **Build the image from the upload and start it as each scan stage does,** the DAST scan's start with no settings included. (CQ-312, CQ-299)
7. **Record every upload,** failed ones included, as the baseline the quality gate scores new code against, and require a higher version for any changed upload. (CQ-302)
8. **Lock before read-modify-write, and never hold a lock across a network call.** (CQ-111, CQ-112)
9. **Validate every external value at the boundary,** its type, its storability and its size, and fail closed on anything unexpected. (CQ-058, CQ-120, CQ-060)
10. **Match keywords in user-controlled text on the raw value,** treating each hidden character as a mark that can neither split the word nor join a letter onto it. (CQ-057)
11. **Guard every asynchronous answer against a newer request,** and never assume one poll page holds everything that arrived. (CQ-162, CQ-158)
12. **Prefer native elements to ARIA roles, content keys to index keys, and shallow callbacks to deep nesting.** (CQ-003, CQ-008, CQ-002)
13. **Audit every lockfile on every run,** tooling included; lock new packages behind a cooldown, and record a waiver when the only fix is younger than it. (CQ-345, CQ-348, CQ-346)
14. **Mark every claim in the records as fact or inference,** and re-check every place a finding touched before recording it closed. (CQ-433, CQ-363)
15. **Run the review as a controlled process.** Gate the exact tree before committing it. Re-run the security gate when another gate's fix touches a control. Bound each round by what would actually fail. Give reviewers the disk and permissions they need to produce run evidence, and let them write nothing in the repository they review. (CQ-421, CQ-422, CQ-431, CQ-420, CQ-436)


## 1.3 SonarQube and static-analysis rules at a glance

Every rule key the App Store's SonarQube, a gate or a local proxy raised. The full story of each is in its entry.

| Entry | Rule | What trips it | Lesson | Guard in Holly |
|---|---|---|---|---|
| CQ-001 | Code Quality gate, 0 new issues allowed (Sonar way profile); no single rule key | Platform static analysis not mirrored locally, so a zero-new-issue quality gate fails uploads that passed every local check | Where a platform gate allows zero new issues, run the same rule profile at the same thresholds on every change before upload, calibrated against a past failing upload as a positive control; review by reading cannot anticipate an analyser, and every fix enters the next upload's new-code window. | frontend/eslint.config.js, run by `npm run lint` in scripts/verify.sh, for S2004, S4138, S6557 and part of S7723. S1994 and S6819, which failed the V0.7 and V0.10 uploads, have no committed lint rule, and the gate's probe lives in scratch, not in the repository (inference). Python has no Sonar run: ruff (RUF029 for S7503, pylint max-args 13 for S107), complexipy at 15 (S3776) and pylint duplicate-code only. The platform's verdict on V0.13 is not in the sources. |
| CQ-002 | typescript:S2004 | Functions nested more than four levels deep inside effect, timer and promise callbacks | Lift the body of a nested callback into a named helper or a memoised callback before it reaches a fifth function level, and when emulating an analyser locally set each rule's threshold to the platform's value, not the plugin's default. | frontend/eslint.config.js: a `no-restricted-syntax` selector `:function :function :function :function :function` whose message cites S2004, run by `npm run lint` in the verification loop; on V0.12's code the lint reports exactly the platform's lines. The gate's Sonar way probe sets sonarjs no-nested-functions to 4. |
| CQ-003 | typescript:S6819 | Explicit ARIA role on a generic element where a native element carries that role | Use the native element (output, fieldset with legend, button, a) rather than an ARIA role on a generic element, and check the cascade when swapping the element so the page still looks the same. | The page tests find both confirmations by role: putting both back to `<p>` failed 5 tests. No committed lint rule (frontend/eslint.config.js has no jsx-a11y). From V0.12 the engineering gate runs jsx-a11y prefer-tag-over-role as a proxy; a `role="img"` on BrandPlate.tsx predates the window and is not counted. |
| CQ-004 | typescript:S1994 | Loop whose stop condition tests different variables from those its update changes | Write search-until-free loops as while loops whose condition and update act on the same value, and run the analyser over every fix for a review finding, since that fix enters the next upload's new-code window. | None as a lint rule (frontend/eslint.config.js mirrors S2004, S4138, S6557 and S7723 only); frontend/src/utils/keys.test.ts unchanged. |
| CQ-005 | typescript:S6557 | Anchored regular expression used for a prefix test where startsWith would do | Test a fixed prefix or suffix with startsWith or endsWith, and scope a type-aware lint rule to the files its TypeScript project covers. | frontend/eslint.config.js: `@typescript-eslint/prefer-string-starts-ends-with` at error. It needs type information, so a round 1 engineering minor moved it into the `src/**` block where `projectService` reads the TypeScript project (elsewhere `eslint .` would throw). |
| CQ-006 | typescript:S4138 | Index for loop over a simple repetition, where the rule's own for-of suggestion would change behaviour | Replace an index loop that only counts with an array builder or a for-of over the right collection, and check what the replacement iterates over (code units against code points) and whether it trips another rule. | frontend/eslint.config.js: `@typescript-eslint/prefer-for-of` at error; the U+0130 tests in comms.test.ts cover the offsets. |
| CQ-007 | typescript:S7723 | Built-in constructor called without new, introduced by the fix for another rule | Check a fix for one analyser finding against the whole profile, and when a selector stands in for a rule, test it against the rule's full definition and claim only the part it covers. | frontend/eslint.config.js: a `no-restricted-syntax` CallExpression selector for a listed built-in called without `new` ('Call a built-in constructor with new (SonarQube S7723)'). Deferred: `Object()` with no arguments, `Float16Array()`, and `new` on String, Number, Boolean, Symbol or BigInt (none in the code); a snippet run gave 6 reports from unicorn against 2 from the project lint. |
| CQ-008 | S6479 | Array index used as the React key for a list | Key list items by a stable identity, or by content with a collision-free repeat suffix, never by the array index; a comment does not suppress an analyser rule. | frontend/src/utils/keys.test.ts, with the colliding input as a case. No committed lint rule; the engineering gate's proxy runs eslint-plugin-react no-array-index-key. |
| CQ-009 | S3358 (TypeScript in V0.5, Python in V0.12) | Nested conditional (ternary) expressions | Write a choice of three or more outcomes as a small helper with early returns or as a lookup table, in every language the analyser reads. | None in the loop. The round 7 engineering gate walked the AST for an IfExp nested in an IfExp and grepped src/app; engineering mutants on both branches of `loadErrorMessage` were killed. |
| CQ-010 | S8414 | CORS middleware not the outermost layer, so error responses from inner layers lose CORS headers | Make CORS the outermost middleware so every response, errors included, carries its headers, and record what the move changes for preflight requests before it ships. | tests/test_app.py: three tests pin the order, two of them red under the old order, among them a coarse-limit 429 to an allowed origin carrying the CORS header; SECURITY.md row with its trip-wire. |
| CQ-011 | S8392 | Development server bound to every network interface | Bind development servers to loopback and keep 0.0.0.0 only in the production entry point the platform's contract needs, with a test on each. | tests/test_entrypoints.py `test_dev_server_binds_loopback_on_the_resolved_port` pins the loopback bind; the container smoke rung probes 8080 on the image. |
| CQ-012 | S8541 | Package install in the image build allowed to run source builds; install wheels only | Install image dependencies from hash-pinned binary wheels only, so no package code runs at build time. | The flag in the Dockerfile, with a comment naming the reason; the container smoke rung builds the image with it. No separate check. |
| CQ-013 | S930 | Analyser reports a wrong argument count on a compiled library call (false positive), cleared by simplifying the call | When the gate cannot be waived, clear a false positive by an equivalent simpler call, after confirming that the dropped arguments did not protect anything. | none recorded |
| CQ-014 | S2871 | Array sort without a compare function | Give every sort an explicit comparator, and where output must stay byte-stable choose a code-unit comparator rather than localeCompare. | None standing; scripts/test-bundled-licences.mjs does not pin the order, and the comparison was a one-off by the gate. |
| CQ-015 | S1082 and S6847 (raised together on the same element) | Click handler on a non-interactive element with no keyboard equivalent | Navigate with a real link or button, never a click handler on a list item or div, so keyboard and assistive technology users can reach it. | frontend/src/pages/Dashboard.test.tsx opens a notice by its link and checks its href; the engineering gate's mutant on the link's `to` was killed. |
| CQ-016 | S6811 | ARIA attribute on an element whose role does not support it (aria-sort on a button) | Put each ARIA state on an element whose role supports it, and assert it by role in tests. | frontend/src/components/SortableHeader.test.tsx asserts the columnheader carries aria-sort and the button does not; mutants removing it from the th or setting it to "none" were killed. |
| CQ-017 | S7746 | Promise.reject returned inside async code instead of throwing | Throw inside async functions and interceptors, and pin each rewritten error path with a test that fails if it is removed. | frontend/src/api/client.test.ts cases, each red under its mutant. |
| CQ-018 | S7744 | Object spread with a redundant empty-object fallback | Spread a possibly undefined object directly, and test that a retry keeps the caller's headers. | frontend/src/api/client.test.ts retry-headers case, red under its mutant. |
| CQ-019 | S6481 | React context provider value rebuilt on every render | Memoise a context provider's value and its callbacks, and keep stale-response guards when refactoring effects. | No dedicated memo test recorded; the engineering gate's mutants on both `!cancelled` guards in AuthContext and on the auth memo with empty dependencies were killed by existing tests. |
| CQ-020 | S1192 | The same string literal repeated across a module | Name a string used more than twice in a module, especially identifiers such as audit actions that must match exactly. | none recorded |
| CQ-021 | S7632 | Lint suppression comment carrying trailing prose on the same line | Keep a suppression directive alone on its line and put the justification in a comment above it. | none recorded |
| CQ-022 | S8431 | Container base image named by tag and digest together | Pin base images by digest alone and record the source tag in a comment. | none recorded beyond the Dockerfile's header comment stating the rule |
| CQ-023 | S7781 | Global regular-expression replace used for a literal string | Use replaceAll with a string for literal replacements, and keep any text-matching mutation tests in step with the code. | scripts/mutation-battery.mjs matches the plugin's source text and fails a mutant whose text is not found exactly once, so a drift between code and battery fails it. |
| CQ-024 | S4666 | The same CSS selector declared in two rule blocks | Merge duplicate selectors, checking that no rule between them changes the cascade. | none recorded |
| CQ-025 | S1874 | Deprecated API or value in use | Replace deprecated values and APIs when they are found, configuration files included, since any edit near them can bring them into the analyser's new-code window. | none recorded |
| CQ-026 | S6772 | JSX text followed by an element on the next line without explicit spacing | Write the space between JSX text and a following element explicitly. | None recorded. The engineering gate's report lists 'both ShiftLog labels' among its killed mutants, but ShiftLog has only one S6772 label, so which labels those mutants covered is unclear. |
| CQ-027 | S6759 | React component props not marked read-only | Type component props as Readonly from the start. | none recorded |
| CQ-028 | S6582 | Null guard followed by property access instead of optional chaining | Use optional chaining for guarded property reads. | none recorded; the engineering gate's mutants on both optional chains were killed |
| CQ-029 | S6571 | Union of literal types with string, which collapses to string | Type a field the server leaves open as string and name the known values in a comment, or narrow it at the boundary. | none recorded |
| CQ-030 | S7776 | Constant array used for membership tests instead of a Set | Use a Set for repeated membership tests. | none recorded; the engineering gate's mutant on the feed Set was killed |
| CQ-031 | typescript:S5852 | Backtracking regular expression, a slow-regex security hotspot | Parse untrusted or large text with linear scans rather than alternation regexes, and treat a hotspot the owner cannot clear as a blocker. | frontend/src/components/Markdown.test.tsx renders every block kind; the gate's proxy (eslint-plugin-sonarjs) covers the rule; no committed lint rule. |
| CQ-032 | typescript:S4624 | Nested template literal | Build a conditional fragment in its own variable before interpolating it. | The gate's proxy (eslint-plugin-sonarjs); no committed lint rule. |
| CQ-033 | python:S1940 | Inverted boolean comparison used to make NaN fail closed | State edge cases such as NaN explicitly (math.isnan) rather than relying on an inverted comparison. | The float and NaN test cases; no local rule (fact from the gate). That SonarQube flags the original is inference, not confirmed with a Sonar Python run. |
| CQ-034 | typescript:S1117 | Callback parameter shadowing a state variable in the enclosing component | When extracting a callback, name its parameters so none shadows an outer variable, even where the gate would not count it. | none (no-shadow is not enabled in frontend/eslint.config.js) |
| CQ-035 | python:S7503 | Async route handlers that never await | Declare a handler async only when it awaits, and enable a local linter rule that mirrors the analyser's check. | ruff RUF029 (a preview rule, enabled explicitly) in pyproject.toml's select list, run by scripts/verify.sh; the config names it the local twin of python:S7503. |
| CQ-036 | python:S3776 (local proxy: complexipy, at most 15 per function) | Cognitive complexity above the limit, caught locally before upload | Run a cognitive-complexity check at the platform's threshold on every change and split decisions into named helpers when it fails. | scripts/verify.sh: `complexipy src --max-complexity-allowed 15`, the step naming SonarQube rule S3776. |
| CQ-037 | pylint duplicate-code (local proxy for SonarQube duplication) | Duplicated block between two callers, caught by a local duplication proxy | Share a helper as soon as a block repeats, and run a duplication check stricter than the platform's gate. | scripts/verify.sh: pylint duplicate-code over sonar.sources, tests excluded as the gate excludes them; any repeated block of 4 lines fails, stricter than the 3% gate. It cannot see repeats inside one file. |
| CQ-038 | ruff PLR0911 (too-many-return-statements) | Too many return statements in a validation helper | When a validator grows another early exit, extract the guard into a named predicate instead of adding a return. | ruff in the verification loop (pyproject.toml selects the PL family) |
| CQ-039 | ruff S105 (local); SonarQube S2068 hotspot (project note) | Names containing TOKEN, PASSWORD or SECRET bound to string literals trip hard-coded credential rules | Avoid credential-shaped names for literals that are not secrets, and justify each suppression, because a hotspot can block a gate the owner cannot clear. | ruff S rules in the verification loop; the secret-scan hook; a project rule never to give such names a string literal. |
| CQ-040 | ruff S101 | assert used for a runtime check in application code | Raise an explicit exception for runtime checks; keep assert for tests. | ruff check over src and tests in scripts/verify.sh |
| CQ-041 | none (platform scoring question) | Unknown whether the quality gate counts test files as changed code, and hotspots in tests the owner cannot clear | Find out early which files the platform's analyser and coverage gate count, and keep test code clean of hotspot patterns until you know. | Practice only: no credential-shaped literals in tests, neutral names for typed values. |

## 1.4 Entries by theme and status

| Theme | Entries | Resolved | Accepted | Deferred | Open |
|---|---|---|---|---|---|
| SonarQube and static-analysis rules (CQ-001 to CQ-041) | 41 | 38 | 0 | 0 | 3 |
| Security controls (CQ-042 to CQ-110) | 69 | 45 | 15 | 2 | 7 |
| Server correctness and concurrency (CQ-111 to CQ-157) | 47 | 42 | 0 | 2 | 3 |
| Frontend, React and accessibility (CQ-158 to CQ-207) | 50 | 43 | 2 | 4 | 1 |
| Testing (CQ-208 to CQ-296) | 89 | 68 | 3 | 2 | 16 |
| Build, packaging, pipeline and container (CQ-297 to CQ-343) | 47 | 35 | 7 | 2 | 3 |
| Dependencies and supply chain (CQ-344 to CQ-355) | 12 | 8 | 2 | 1 | 1 |
| Documentation and records (CQ-356 to CQ-414) | 59 | 42 | 2 | 1 | 13 |
| Review process (CQ-415 to CQ-444) | 30 | 21 | 5 | 0 | 4 |

# Part 2. The catalogue

Each entry: a reusable title; the rule key where there is one; who raised it; the releases; the symptom in Holly; the root cause; the fix; the guard that now catches it earlier; the lesson for another application; and evidence quoted from Holly's records. **Certainty** says whether the entry rests on recorded fact, on inference, or on both.


## 2.1 SonarQube and static-analysis rules


### CQ-001 Platform static analysis not mirrored locally, so a zero-new-issue quality gate fails uploads that passed every local check

● **Rule:** `Code Quality gate, 0 new issues allowed (Sonar way profile); no single rule key` · **Raised by:** app-store-sonarqube; app owner · **Severity:** platform-fail (four failed uploads) · **Status:** open · **Certainty:** mixed
● **Releases:** V0.5 (68 findings), V0.7 (1), V0.10 (2), V0.12 (8) raised by the platform; V0.13 (local lint for the three rules that failed V0.12's upload and S7723's missing-new side, and a calibrated Sonar way probe in the engineering gate)
● **Applies to:** any stack with a SonarQube (or similar) zero-new-issue quality gate
● **Symptom:** Four uploads passed the verification loop and both review gates and then failed the App Store's Code Quality stage: V0.5 (56c55a9, zip d947cfea) on 68 findings (5 bugs, 2 vulnerabilities, 61 code smells); V0.7 (452e3c7, zip 91043942) on 1 new code smell (taken to be S1994, inference recorded in V0.8's row); V0.10 (f025c2c, zip 0abd6241) on 2 (S6819); V0.12 (f6951a6, zip d78e841f) on 8 (S2004 x6, S6557, S4138). After V0.12 the owner asked why the gates were testing at all if they could not anticipate the smells. The platform scores new code against the previous upload, passed or failed, so V0.6's fixes (never uploaded) first counted in V0.7's window (inference from the baseline record's rule).
● **Root cause:** The dashboard's ESLint set was the recommended JavaScript and TypeScript rules with react-hooks and react-refresh, and Python had ruff, mypy, complexipy and pylint duplicate-code; none ran SonarQube's TypeScript rules (fact, V0.13 row). When the 68 findings were folded into V0.6 the owner said to leave sonarjs out. From V0.12 the engineering gate ran an ad hoc proxy (eslint-plugin-sonarjs 4.2.2 with every rule, react no-array-index-key, jsx-a11y prefer-tag-over-role), but at the plugin's defaults; the plugin's S2004 threshold is 5 where the platform reported at 4 (fact), which is the likely reason six S2004 smells passed every V0.12 gate round (inference).
● **Fix:** Each platform report was fixed at the file and line given in the next release (V0.6, V0.8, V0.11, V0.13); V0.6 replayed all 68 against the uploaded commit. V0.13 added the three rules that failed V0.12's upload, and S7723's missing-new side, to frontend/eslint.config.js without the sonarjs plugin (a no-restricted-syntax selector each for S2004 and S7723, @typescript-eslint/prefer-for-of, @typescript-eslint/prefer-string-starts-ends-with); on V0.12's code it reports exactly the platform's 8 at the same lines. The engineering gate's Sonar way probe (eslint-plugin-sonarjs 4.2.2 with S2004 at 4, unicorn, typescript-eslint, core and React rules mapped to Sonar way keys, plus jsx-a11y and others) runs on the old and new trees with V0.12's 8 smells as a positive control, and a separate SonarQube sweep challenged each candidate against SonarJS's rule metadata. scripts/upload-baseline.txt (from V0.6) records every upload so the window can be read.
● **Guard:** frontend/eslint.config.js, run by `npm run lint` in scripts/verify.sh, for S2004, S4138, S6557 and part of S7723. S1994 and S6819, which failed the V0.7 and V0.10 uploads, have no committed lint rule, and the gate's probe lives in scratch, not in the repository (inference). Python has no Sonar run: ruff (RUF029 for S7503, pylint max-args 13 for S107), complexipy at 15 (S3776) and pylint duplicate-code only. The platform's verdict on V0.13 is not in the sources.
● **Lesson:** Where a platform gate allows zero new issues, run the same rule profile at the same thresholds on every change before upload, calibrated against a past failing upload as a positive control; review by reading cannot anticipate an analyser, and every fix enters the next upload's new-code window.
● **Evidence:** docs/AUDIT-LOG.md, V0.13 row: "Why the gates missed them (fact): SonarQube's TypeScript rules were not run locally, and the dashboard's ESLint set had none of the three." Also: the app owner's message; gate report: find:security-and-config; scripts/upload-baseline.txt; gate report: Engineering gate V0.12.

### CQ-002 Functions nested more than four levels deep inside effect, timer and promise callbacks

● **Rule:** `typescript:S2004` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (6 code smells) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.12 (introduced in 62ba4aa, raised by the platform on upload), V0.13 (fixed in 559a9d0, lint rule added)
● **Applies to:** React and TypeScript (any JavaScript or TypeScript analysed by SonarQube)
● **Symptom:** V0.12's upload (f6951a6) failed Code Quality on 6 S2004 smells, 'Refactor this code to not nest functions more than 4 levels deep', at frontend/src/components/comms/ChannelConversation.tsx:133, 134, 141 and 142 and CommsFeed.tsx:102 and 103. The poll answer was handled inline: component, useEffect, setInterval callback, .then callback, then the map, filter and state-updater arrows at a fifth level. Five of the six lines date from the first Comms commit (62ba4aa) and one from the round 1 fix (f6056cd); no V0.12 gate round flagged them.
● **Root cause:** Poll-answer logic written inline in a promise callback inside a timer callback inside an effect. The local ESLint set had no nesting rule, and the gate's proxy used eslint-plugin-sonarjs at its default threshold of 5, not the platform's 4 (fact for the thresholds; that this explains the miss is inference).
● **Fix:** 559a9d0: a pure helper `unseen(items, shown)` in frontend/src/utils/comms.ts replaces the inline Set and filter in both components, and a channel's poll answer moves into its own useCallback, `arrive`, called from the .then callback; the effect's dependencies become [channelId, arrive], with the cancelled guard and the message order unchanged. Every function sits at 4 levels or fewer.
● **Guard:** frontend/eslint.config.js: a `no-restricted-syntax` selector `:function :function :function :function :function` whose message cites S2004, run by `npm run lint` in the verification loop; on V0.12's code the lint reports exactly the platform's lines. The gate's Sonar way probe sets sonarjs no-nested-functions to 4.
● **Lesson:** Lift the body of a nested callback into a named helper or a memoised callback before it reaches a fifth function level, and when emulating an analyser locally set each rule's threshold to the platform's value, not the plugin's default.
● **Evidence:** the app owner's message: "Refactor this code to not nest functions more than 4 levels deep. typescript:S2004" Also: docs/AUDIT-LOG.md, V0.13 row; gate report: Engineering gate V0.13 (fast); frontend/src/components/comms/ChannelConversation.tsx at f6951a6; f6056cd.

### CQ-003 Explicit ARIA role on a generic element where a native element carries that role

● **Rule:** `typescript:S6819` · **Raised by:** app-store-sonarqube (V0.10); engineering-reviewer (V0.12) · **Severity:** platform-fail (2 code smells); BLOCKER at the V0.12 engineering gate · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised by the platform), V0.11 (fixed); V0.12 (recurred, caught by the engineering gate in round 1, fixed in f6056cd)
● **Applies to:** React and TypeScript; any HTML front end analysed by SonarQube
● **Symptom:** V0.10's upload (f025c2c, zip 0abd6241) failed Code Quality, 'New issues: 2 (max allowed: 0)', 9 of 10 stages passed, on S6819 'Use <output> instead of the "status" role' at frontend/src/pages/Users.tsx:255 and ChangePassword.tsx:101, each a confirmation `<p role="status">`; neither the loop nor V0.10's three gates flagged it. In V0.12 round 1 the engineering gate found three new `role="group"` segmented switches at CommsFeed.tsx:145, Mattermost.tsx:195 and Help.tsx:101, for which the analyser suggests `<fieldset>`.
● **Root cause:** ARIA roles put on a paragraph or div where a native element carries the role; the dashboard's ESLint had no jsx-a11y rule. `role="alert"` is not flagged, since alert has no native element.
● **Fix:** V0.11 (c8af9ad): each confirmation is `<output className="status-line">`, which carries the status role itself. The first fix set `.status-line` to `margin: 1em 0`, moving the layout about 3 pixels against the record's 'looks as before' (engineering MAJOR); round 2 set the paragraph's own `0 0 var(--space-3)`. In the Comms work, before its gates, `<output>` replaced every `role="status"`. V0.12 (f6056cd): each switch is a `<fieldset className="segmented">` with a visually hidden `<legend>` keeping the accessible name, with a CSS reset for the fieldset.
● **Guard:** The page tests find both confirmations by role: putting both back to `<p>` failed 5 tests. No committed lint rule (frontend/eslint.config.js has no jsx-a11y). From V0.12 the engineering gate runs jsx-a11y prefer-tag-over-role as a proxy; a `role="img"` on BrandPlate.tsx predates the window and is not counted.
● **Lesson:** Use the native element (output, fieldset with legend, button, a) rather than an ARIA role on a generic element, and check the cascade when swapping the element so the page still looks the same.
● **Evidence:** scripts/upload-baseline.txt: "Code Quality failed it on 2 new code smells (S6819, Users.tsx:255 and ChangePassword.tsx:101)" Also: session summaries; gate report: Engineering gate V0.12; docs/AUDIT-LOG.md, V0.11 row; gate report: Engineering gate on V0.11 hotfix.

### CQ-004 Loop whose stop condition tests different variables from those its update changes

● **Rule:** `typescript:S1994` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (1 code smell) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.6 (introduced by a review fix, never uploaded), V0.7 (raised by the platform), V0.8 (fixed in 117346c)
● **Applies to:** any language analysed by SonarQube (TypeScript here)
● **Symptom:** V0.7's upload (452e3c7, zip 91043942, merge request 3) failed Code Quality on 1 new code smell (DAST failed separately on no_report). The owner gave it as frontend/src/utils/keys.ts:12, where the loop's stop condition tests issued and key while the incrementer updates n, on `for (let n = 2; issued.has(key); n++) key = `${content}#${n}`;`. The loop was V0.6 round 2's answer to an engineering minor (content keys colliding); V0.6 was never uploaded, so V0.7's upload first carried it.
● **Root cause:** A compact for loop that computes the next value in its body; no local rule mirrors S1994, and a fix for one review finding (the S6479 key collision) introduced the next platform finding. That the console's one smell is this finding is recorded as inference.
● **Fix:** 117346c (V0.8): a `while (issued.has(key))` loop that moves the occurrence number and rebuilds the key in its body. The engineering gate found identical keys over 219,531 inputs, forced `#n` collisions included, and no other counting `for (;;)` loop in frontend/src. The owner had a rehearsal zip of this fix alone; the DAST fix superseded it before upload.
● **Guard:** None as a lint rule (frontend/eslint.config.js mirrors S2004, S4138, S6557 and S7723 only); frontend/src/utils/keys.test.ts unchanged.
● **Lesson:** Write search-until-free loops as while loops whose condition and update act on the same value, and run the analyser over every fix for a review finding, since that fix enters the next upload's new-code window.
● **Evidence:** the app owner's message: "This loop's stop condition tests "issued, key" but the incrementer updates "n". typescript:S1994" Also: docs/AUDIT-LOG.md, V0.8 row; gate report: Engineering gate on V0.8 DAST.

### CQ-005 Anchored regular expression used for a prefix test where startsWith would do

● **Rule:** `typescript:S6557` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (1 code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised by the platform), V0.13 (fixed in 559a9d0, lint rule added and scoped in 6085a53)
● **Applies to:** JavaScript and TypeScript
● **Symptom:** One of V0.12's 8 smells: frontend/src/components/Markdown.tsx:31, 'Use 'String#startsWith' method instead', where the in-app manual reader tested a link with `/^https:\/\//.test(href)`.
● **Root cause:** A fixed prefix check written as an anchored regular expression; the local lint did not run typescript-eslint's prefer-string-starts-ends-with, which SonarJS maps to S6557.
● **Fix:** `href.startsWith("https://")`. The security gate ran 23 fixed attack inputs and 200,000 random ones through both forms with 0 differences; case sensitivity, the non-https fallback to plain text and the `rel="noopener noreferrer"` anchor are unchanged.
● **Guard:** frontend/eslint.config.js: `@typescript-eslint/prefer-string-starts-ends-with` at error. It needs type information, so a round 1 engineering minor moved it into the `src/**` block where `projectService` reads the TypeScript project (elsewhere `eslint .` would throw).
● **Lesson:** Test a fixed prefix or suffix with startsWith or endsWith, and scope a type-aware lint rule to the files its TypeScript project covers.
● **Evidence:** the app owner's message: "Use 'String#startsWith' method instead. typescript:S6557" Also: gate report: Security gate V0.13 (fast); frontend/eslint.config.js.

### CQ-006 Index for loop over a simple repetition, where the rule's own for-of suggestion would change behaviour

● **Rule:** `typescript:S4138` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (1 code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised by the platform), V0.13 (fixed in 559a9d0, then 6085a53)
● **Applies to:** JavaScript and TypeScript
● **Symptom:** One of V0.12's 8 smells: frontend/src/utils/comms.ts:115, 'Expected a `for-of` loop instead of a `for` loop with this simple iteration', on `for (let unit = 0; unit < low.length; unit += 1)` in the search highlighter, which pushed the same two offsets once per UTF-16 unit of a lower-cased character, the index unused.
● **Root cause:** A counting loop used only for repetition, with no prefer-for-of rule locally. The rule's suggestion is a trap here: for-of over the string counts code points, not UTF-16 units, and would shift the offsets.
● **Fix:** 559a9d0 used `Array<number>(low.length).fill(at)`, which raised S7723 (see that entry); 6085a53 settled on `Array.from({ length: low.length }, () => at)` and `() => at + char.length`. Security round 2 compared the round 1 and final forms over 200,000 random inputs (U+0130, sharp s, sigma, astral characters and lone surrogates among them) with 0 differences; the round 1 gates had judged the fill equivalent to the old loop.
● **Guard:** frontend/eslint.config.js: `@typescript-eslint/prefer-for-of` at error; the U+0130 tests in comms.test.ts cover the offsets.
● **Lesson:** Replace an index loop that only counts with an array builder or a for-of over the right collection, and check what the replacement iterates over (code units against code points) and whether it trips another rule.
● **Evidence:** the app owner's message: "Expected a 'for-of' loop instead of a 'for' loop with this simple iteration. typescript:S4138" Also: gate report: Engineering gate V0.13 (fast); docs/AUDIT-LOG.md, V0.13 row.

### CQ-007 Built-in constructor called without new, introduced by the fix for another rule

● **Rule:** `typescript:S7723` · **Raised by:** engineering-reviewer; sonar-sweep · **Severity:** minor at the gate; a likely platform failure had it shipped (inference) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.13 (introduced at 559a9d0 and raised in round 1, fixed in 6085a53, lint guard in 32169bf, guard gaps deferred to the next release)
● **Applies to:** JavaScript and TypeScript
● **Symptom:** 559a9d0's S4138 fix, `starts.push(...Array<number>(low.length).fill(at));` and the matching `ends` line at frontend/src/utils/comms.ts:115 and 116, calls `Array()` without `new`. The round 1 engineering gate rated it MINOR and optional, inferring that the platform ignores unicorn-derived rules; the SonarQube sweep confirmed S7723 at both lines and found it in Sonar way since SonarJS 11.4, the same release as S7781, S7746 and S7744, which the platform raised on V0.5.
● **Root cause:** The replacement was checked against the rule it fixed, not the whole profile; S7723 is eslint-plugin-unicorn's new-for-builtins as SonarJS decorates it, exempting only `Object(value)`. The gate's calibration from silent sibling S77xx rules failed, since each silence had another cause (decorators, the ES2020 lib).
● **Fix:** 6085a53: `Array.from({ length: low.length }, () => at)`, chosen over `new Array(n).fill()`, which trips unicorn/no-new-array and S1528 (neither in Sonar way); security round 2's 200,000-input comparison found 0 differences. 32169bf adds a lint guard that reports both of 559a9d0's lines. 0180d55 narrowed the CHANGELOG and audit claim to "S7723's missing-`new` side" after round 2 showed the guard covers only part of the rule.
● **Guard:** frontend/eslint.config.js: a `no-restricted-syntax` CallExpression selector for a listed built-in called without `new` ('Call a built-in constructor with new (SonarQube S7723)'). Deferred: `Object()` with no arguments, `Float16Array()`, and `new` on String, Number, Boolean, Symbol or BigInt (none in the code); a snippet run gave 6 reports from unicorn against 2 from the project lint.
● **Lesson:** Check a fix for one analyser finding against the whole profile, and when a selector stands in for a rule, test it against the rule's full definition and claim only the part it covers.
● **Evidence:** gate report: verify:typescript:S7723@comms.ts:115#0: "S7723 is absent in 11.3.0 and has been in Sonar way in every release since 11.4.0." Also: docs/AUDIT-LOG.md, V0.13 row; gate report: verify:typescript:S7723@comms.ts:116#1; gate report: Engineering gate V0.13 round 2.

### CQ-008 Array index used as the React key for a list

● **Rule:** `S6479` · **Raised by:** app-store-sonarqube (V0.5); engineering-reviewer (V0.12) · **Severity:** platform-fail (code smell); BLOCKER at the V0.12 engineering gate · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed); V0.12 (recurred, engineering gate BLOCKER in round 1, fixed in f6056cd)
● **Applies to:** React and TypeScript
● **Symptom:** V0.5: frontend/src/components/AssistantPanel.tsx keyed its next actions, procedures and open questions, model output with no ids, with `key={idx}`. V0.12 round 1: highlight parts keyed `key={at}` at frontend/src/components/comms/MessageList.tsx:79 and :81, and activity bars `key={hour}` at ActivityTrace.tsx:46, each with a comment justifying the index.
● **Root cause:** Index keys for lists without an id; a justifying code comment was taken to excuse the rule, but a comment suppresses nothing.
● **Fix:** V0.6: `withContentKeys` in frontend/src/utils/keys.ts keys each item by its content, a repeat taking an occurrence number. Round 1's suffix could collide with real content (`["a","a","a#2"]` gave two `a#2`, an engineering minor); round 2 skips any key already issued, the loop that became V0.7's S1994. V0.12 (f6056cd): highlight parts are keyed by their start offset in the message (a `placed()` helper), and bars by the hour carried on each item from a `bars()` helper rather than the map callback's index.
● **Guard:** frontend/src/utils/keys.test.ts, with the colliding input as a case. No committed lint rule; the engineering gate's proxy runs eslint-plugin-react no-array-index-key.
● **Lesson:** Key list items by a stable identity, or by content with a collision-free repeat suffix, never by the array index; a comment does not suppress an analyser rule.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "the assistant panel keys its lists by content, a repeat taking the first occurrence number no earlier key holds (S6479, 'utils/keys.ts')" Also: gate report: Engineering gate on V0.6 tree; gate report: Engineering gate V0.12.

### CQ-009 Nested conditional (ternary) expressions

● **Rule:** `S3358 (TypeScript in V0.5, Python in V0.12)` · **Raised by:** app-store-sonarqube (V0.5); engineering-reviewer (V0.12) · **Severity:** platform-fail (4 code smells); MAJOR at the V0.12 engineering gate · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.5 (raised by the platform, TypeScript), V0.6 (fixed); V0.12 (Python, engineering gate MAJOR in round 6, fixed in 6f7dcd0)
● **Applies to:** any language analysed by SonarQube (TypeScript and Python here)
● **Symptom:** V0.5: four nested ternaries in the dashboard, the sort indicator and aria-sort value in SortableHeader.tsx, the summary button label in ShiftLog.tsx and the load-error message in EventTimersContext.tsx. V0.12 round 6 (56d0dbc): `" " if _parts(char) else _HIDDEN_MARK if _hidden(char) else char` in `_marked` at src/app/services/mattermost_channels.py:159, the only one in src/, new in the round 6 change that answered round 5's finding.
● **Root cause:** A multi-way choice compressed into one expression. Nothing local catches it: ESLint had no such rule, and ruff, pylint and complexipy have none for Python. That SonarQube's Python rule flags the V0.12 line is the gate's inference, counted as a likely new issue under fail-closed.
● **Fix:** V0.6: helpers or lookup records, `INDICATOR` and `ARIA_SORT`, `summaryButtonLabel()` and `loadErrorMessage()`. V0.12: a `_mark(char)` helper with two flat if/return branches; security round 7 compared old and new on all 1,112,064 non-surrogate code points with 0 differences, and tests pin that a space or tab inside the word keeps it open.
● **Guard:** None in the loop. The round 7 engineering gate walked the AST for an IfExp nested in an IfExp and grepped src/app; engineering mutants on both branches of `loadErrorMessage` were killed.
● **Lesson:** Write a choice of three or more outcomes as a small helper with early returns or as a lookup table, in every language the analyser reads.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "four nested ternaries become helpers or lookups (S3358)" Also: gate report as received; commit messages (git log); gate report: Engineering gate V0.12 round 6.

### CQ-010 CORS middleware not the outermost layer, so error responses from inner layers lose CORS headers

● **Rule:** `S8414` · **Raised by:** app-store-sonarqube; engineering-reviewer (side effect) · **Severity:** platform-fail (code smell); MAJOR at the V0.6 engineering gate for the side effect · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed; the side effect failed the engineering gate in round 1 and was settled in rounds 2 and 3)
● **Applies to:** Python and FastAPI or Starlette (any middleware stack)
● **Symptom:** In src/app/factory.py the CORS middleware sat inside the security headers, request id and coarse rate limit, so a coarse-limit 429 to an allowed origin carried no CORS headers.
● **Root cause:** Starlette runs the middleware added last first, and CORS had been added before the inner layers.
● **Fix:** CORS is added last, so it runs first; a 429 to an allowed origin gains the CORS headers, which a 413 already carried. Side effect, failed by the engineering gate as a MAJOR: every preflight now leaves without the security headers, the request id and the coarse limit, which five documents denied. Kept, with a SECURITY.md position and trip-wire, the documents corrected, and tests that the allowed preflight carries no CSP and a fixed `OK` body.
● **Guard:** tests/test_app.py: three tests pin the order, two of them red under the old order, among them a coarse-limit 429 to an allowed origin carrying the CORS header; SECURITY.md row with its trip-wire.
● **Lesson:** Make CORS the outermost middleware so every response, errors included, carries its headers, and record what the move changes for preflight requests before it ships.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "a 429 to an allowed origin gains the CORS headers, which a 413 already carried (S8414; three tests pin it, two of them red under the old order)" Also: gate report: Engineering gate on V0.6 tree; SECURITY.md.

### CQ-011 Development server bound to every network interface

● **Rule:** `S8392` · **Raised by:** app-store-sonarqube; security-reviewer (Vite dev server) · **Severity:** platform-fail (vulnerability) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed; the Vite half raised by the security gate in round 1, fixed in round 2)
● **Applies to:** any server stack (Python and uvicorn, Vite here)
● **Symptom:** `python -m app` (src/app/__main__.py), the local development server, ran uvicorn on 0.0.0.0. The V0.6 round 1 security gate added that the dashboard's Vite dev server also listened on every interface and proxied the API.
● **Root cause:** The development entry point copied the container's bind-all contract, so a local dev server was reachable from the network.
● **Fix:** `python -m app` binds 127.0.0.1 and the Vite server binds 127.0.0.1 and proxies `/api` to it; the container still binds 0.0.0.0 through gunicorn, as the App Store contract requires.
● **Guard:** tests/test_entrypoints.py `test_dev_server_binds_loopback_on_the_resolved_port` pins the loopback bind; the container smoke rung probes 8080 on the image.
● **Lesson:** Bind development servers to loopback and keep 0.0.0.0 only in the production entry point the platform's contract needs, with a test on each.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "'python -m app' binds 127.0.0.1, the container still binding 0.0.0.0 through gunicorn (S8392), and the dashboard's Vite server binds 127.0.0.1 and proxies to it" Also: tests/test_entrypoints.py at 691f25b.

### CQ-012 Package install in the image build allowed to run source builds; install wheels only

● **Rule:** `S8541` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (vulnerability) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** Python container images (the same idea applies to npm install scripts)
● **Symptom:** The Dockerfile's build stage ran `pip install --require-hashes -r requirements-runtime.txt`, which would run a package's build step if no wheel matched.
● **Root cause:** Without `--only-binary :all:`, pip may fall back to a source distribution and run its build scripts during the image build.
● **Fix:** `pip install --only-binary :all: --require-hashes -r requirements-runtime.txt`; all 36 runtime packages that apply on Linux resolve as hash-verified CPython 3.12 x86_64 wheels, and the image was built and smoke-tested with the flag.
● **Guard:** The flag in the Dockerfile, with a comment naming the reason; the container smoke rung builds the image with it. No separate check.
● **Lesson:** Install image dependencies from hash-pinned binary wheels only, so no package code runs at build time.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "pip installs with '--only-binary :all:' (S8541), all 36 runtime packages that apply on Linux resolving as CPython 3.12 x86_64 wheels" Also: Dockerfile at 691f25b.

### CQ-013 Analyser reports a wrong argument count on a compiled library call (false positive), cleared by simplifying the call

● **Rule:** `S930` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (bug) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** Python (any analysed language calling compiled extensions)
● **Symptom:** src/app/config.py `_problems` called pydantic's `exc.errors(include_url=False, include_context=False, include_input=False)`; one of V0.5's 5 bugs.
● **Root cause:** A false positive: pydantic-core takes all three keyword arguments, but the analyser's view of the signature did not (that the cause is the analyser's signature model of a compiled extension is inference).
● **Fix:** `exc.errors()` with no arguments. Safe because `_problems` reads only `msg` and `loc`, so no input value can reach the boot message, which the security gate confirmed.
● **Guard:** none recorded
● **Lesson:** When the gate cannot be waived, clear a false positive by an equivalent simpler call, after confirming that the dropped arguments did not protect anything.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "'config.py' calls 'exc.errors()' with no arguments (S930, a false positive: pydantic-core takes all three, and '_problems' reads only 'msg' and 'loc')" Also: gate report: Security gate on V0.6 tree.

### CQ-014 Array sort without a compare function

● **Rule:** `S2871` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (bug) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** JavaScript and TypeScript
● **Symptom:** The licence plugin, frontend/bundled-licences.mjs, built its bundled licence index with `[...packages.keys()].sort()`.
● **Root cause:** A bare `sort()` relies on the implicit UTF-16 code-unit order. The obvious locale comparator would have changed the shipped index, since a locale puts "_" before "-".
● **Fix:** An explicit comparator, `(a, b) => (a < b ? -1 : Number(a > b))`, the default order written out, so the index stays byte for byte the same. The engineering gate matched it against the default `sort()` in 20,000 random runs including `-`, `_`, astral characters and U+FFFF.
● **Guard:** None standing; scripts/test-bundled-licences.mjs does not pin the order, and the comparison was a one-off by the gate.
● **Lesson:** Give every sort an explicit comparator, and where output must stay byte-stable choose a code-unit comparator rather than localeCompare.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "the licence plugin sorts by an explicit UTF-16 code-unit comparator, so the index stays byte for byte the same (S2871)" Also: gate report as received; frontend/bundled-licences.mjs at 691f25b.

### CQ-015 Click handler on a non-interactive element with no keyboard equivalent

● **Rule:** `S1082 and S6847 (raised together on the same element)` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (bug) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** React and TypeScript; any web front end
● **Symptom:** Each dashboard notice in frontend/src/pages/Dashboard.tsx was an `<li onClick={() => navigate(...)}>`, opened by a click with no way in from the keyboard.
● **Root cause:** Navigation wired to a click handler on a non-interactive element instead of a link.
● **Fix:** Each notice is one react-router `Link` to `/notifications/{id}` inside its `li`, reached with Tab and opened with Enter, with the global focus ring; CSS keeps the body text colour and drops the underline. The contrast check's pinned pair count moved from 218 to 220 for the link's two new rules, and the security gate confirmed the path always starts /notifications/.
● **Guard:** frontend/src/pages/Dashboard.test.tsx opens a notice by its link and checks its href; the engineering gate's mutant on the link's `to` was killed.
● **Lesson:** Navigate with a real link or button, never a click handler on a list item or div, so keyboard and assistive technology users can reach it.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "each dashboard notice is one react-router link, keyboard reachable, in place of a clickable list item (S1082, S6847)" Also: CHANGELOG.md.

### CQ-016 ARIA attribute on an element whose role does not support it (aria-sort on a button)

● **Rule:** `S6811` · **Raised by:** app-store-sonarqube; V0.5 test-writing · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (recorded as a defect while writing tests, then raised by the platform), V0.6 (fixed)
● **Applies to:** React and TypeScript; any web front end
● **Symptom:** frontend/src/components/SortableHeader.tsx set `aria-sort` on its `<button>` ("none" on unsorted columns), where screen readers do not read it. V0.5's audit row had already recorded the defect.
● **Root cause:** WAI-ARIA 1.2 supports `aria-sort` only on a column or row header.
● **Fix:** `aria-sort` moves to the `<th>`, set only on the column the list is sorted by.
● **Guard:** frontend/src/components/SortableHeader.test.tsx asserts the columnheader carries aria-sort and the button does not; mutants removing it from the th or setting it to "none" were killed.
● **Lesson:** Put each ARIA state on an element whose role supports it, and assert it by role in tests.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "'aria-sort' moves from 'SortableHeader''s button to its column header, set only on the sorted column, which closes the defect V0.5's row records (S6811)" Also: docs/AUDIT-LOG.md, V0.5 row.

### CQ-017 Promise.reject returned inside async code instead of throwing

● **Rule:** `S7746` · **Raised by:** app-store-sonarqube; engineering-reviewer (untested lines) · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed; tests added in rounds 2 and 3)
● **Applies to:** JavaScript and TypeScript
● **Symptom:** frontend/src/api/client.ts returned `Promise.reject(...)` in `attemptRefresh` and in three branches of the axios response interceptor.
● **Root cause:** Promise-style rejection written inside async functions.
● **Fix:** Each became `throw error`, or `throw new Error("No refresh token available")`; the security gate confirmed the behaviour is the same. Round 1's engineering gate found that replacing that new throw with `return ""` left the suite green, so round 2 added a test that with no refresh token the original error rejects and no retry is sent; round 3 added tests that a refused retry refreshes once only and an auth call never refreshes (a security minor on older guards).
● **Guard:** frontend/src/api/client.test.ts cases, each red under its mutant.
● **Lesson:** Throw inside async functions and interceptors, and pin each rewritten error path with a test that fails if it is removed.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "'client.ts' throws in place of 'Promise.reject' and spreads its headers plainly (S7746, S7744)" Also: gate report: Security gate on V0.6 tree; gate report: Engineering gate on V0.6 tree.

### CQ-018 Object spread with a redundant empty-object fallback

● **Rule:** `S7744` · **Raised by:** app-store-sonarqube; engineering-reviewer (untested spread) · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed; test added in round 2)
● **Applies to:** JavaScript and TypeScript
● **Symptom:** The retry in frontend/src/api/client.ts built its headers with `...(config.headers ?? {})`.
● **Root cause:** Spreading undefined is already a no-op, so the fallback adds nothing.
● **Fix:** `...config.headers`. Round 1's engineering gate found that deleting the spread left the suite green, so a retried JSON POST could lose its Content-Type; a test now checks that a retried 401 keeps the caller's custom header.
● **Guard:** frontend/src/api/client.test.ts retry-headers case, red under its mutant.
● **Lesson:** Spread a possibly undefined object directly, and test that a retry keeps the caller's headers.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "'client.ts' throws in place of 'Promise.reject' and spreads its headers plainly (S7746, S7744)" Also: gate report: Engineering gate on V0.6 tree.

### CQ-019 React context provider value rebuilt on every render

● **Rule:** `S6481` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** React and TypeScript
● **Symptom:** frontend/src/context/AuthContext.tsx and EventTimersContext.tsx passed a fresh object literal as the provider `value` on each render, `login` and `logout` as plain inner functions.
● **Root cause:** An unmemoised context value makes every consumer render again whenever the provider renders.
● **Fix:** Both values built with `useMemo`, the auth actions wrapped in `useCallback`, every `!cancelled` stale-response guard kept. One surviving mutant (dropping `timers` from the memo's dependencies) was judged equivalent.
● **Guard:** No dedicated memo test recorded; the engineering gate's mutants on both `!cancelled` guards in AuthContext and on the auth memo with empty dependencies were killed by existing tests.
● **Lesson:** Memoise a context provider's value and its callbacks, and keep stale-response guards when refactoring effects.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "both contexts memoise their value, the auth actions in 'useCallback', every '!cancelled' guard kept (S6481)" Also: gate report as received.

### CQ-020 The same string literal repeated across a module

● **Rule:** `S1192` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** Python (any language)
● **Symptom:** The three sign-in audit actions, "auth.user.login", "auth.token.refresh" and "auth.user.logout", were repeated as literals across src/app/api/v1/routes/auth.py.
● **Root cause:** Audit action names written inline at each call site.
● **Fix:** Module constants `AUDIT_LOGIN`, `AUDIT_REFRESH` and `AUDIT_LOGOUT`, used at every call.
● **Guard:** none recorded
● **Lesson:** Name a string used more than twice in a module, especially identifiers such as audit actions that must match exactly.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "the three sign-in audit actions are module constants (S1192)" Also: src/app/api/v1/routes/auth.py at 691f25b.

### CQ-021 Lint suppression comment carrying trailing prose on the same line

● **Rule:** `S7632` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** Python (ruff or flake8 noqa); the same applies to eslint-disable comments
● **Symptom:** src/app/schemas/auth.py had `token_type: str = "bearer"  # noqa: S105  the OAuth 2 token type, not a secret`.
● **Root cause:** The reason text shared the line with the `# noqa` code.
● **Fix:** `# noqa: S105` stands alone at the end of the line, its reason in a comment on the line above.
● **Guard:** none recorded
● **Lesson:** Keep a suppression directive alone on its line and put the justification in a comment above it.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "'# noqa: S105' stands alone, its reason on the line above (S7632)" Also: src/app/schemas/auth.py at 691f25b.

### CQ-022 Container base image named by tag and digest together

● **Rule:** `S8431` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** any Dockerfile
● **Symptom:** The Dockerfile's FROM lines read `node:22-alpine@sha256:...` and `python:3.12-slim@sha256:...`.
● **Root cause:** A tag beside a digest is ignored by the pull and misleads the reader about what is pulled.
● **Fix:** Each FROM names the repository by digest alone (`FROM python@sha256:...`), the tag it was taken from in a comment above; the digests unchanged.
● **Guard:** none recorded beyond the Dockerfile's header comment stating the rule
● **Lesson:** Pin base images by digest alone and record the source tag in a comment.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "the Dockerfile names its bases by digest alone, the tag in a comment (S8431)" Also: Dockerfile at 691f25b.

### CQ-023 Global regular-expression replace used for a literal string

● **Rule:** `S7781` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** JavaScript and TypeScript
● **Symptom:** frontend/bundled-licences.mjs normalised paths with `.replace(/\\/g, "/")`.
● **Root cause:** A regex with the g flag where a literal `replaceAll` says the same; SonarJS reports it only when the pattern reduces to a plain string.
● **Fix:** `.replaceAll("\\", "/")` in both places; the mutation battery's source strings, which locate code by its text, were updated to follow.
● **Guard:** scripts/mutation-battery.mjs matches the plugin's source text and fails a mutant whose text is not found exactly once, so a drift between code and battery fails it.
● **Lesson:** Use replaceAll with a string for literal replacements, and keep any text-matching mutation tests in step with the code.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "the plugin uses 'replaceAll' (S7781), with the mutation battery's source strings following" Also: gate report: verify:typescript:S7723@comms.ts:115#0; scripts/mutation-battery.mjs at f8a00bd.

### CQ-024 The same CSS selector declared in two rule blocks

● **Rule:** `S4666` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** CSS
● **Symptom:** `.rollup-count` was declared twice in frontend/src/styles/tokens.css, layout in one rule and typography in the other.
● **Root cause:** A rule added in one place and extended in another.
● **Fix:** The two rules merged; the engineering gate checked that nothing between the old and new places sets `align-self`, so the cascade is unchanged.
● **Guard:** none recorded
● **Lesson:** Merge duplicate selectors, checking that no rule between them changes the cascade.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "'.rollup-count''s two rules are one (S4666)" Also: gate report: Engineering gate on V0.6 tree.

### CQ-025 Deprecated API or value in use

● **Rule:** `S1874` · **Raised by:** app-store-sonarqube (V0.5); sonar-sweep (V0.13) · **Severity:** platform-fail (code smell) in V0.5; latent, outside the new-code window, in V0.13 · **Status:** open · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform on CSS), V0.6 (fixed); V0.13 (a latent occurrence in the lint configuration found by the SonarQube sweep, not fixed)
● **Applies to:** CSS; JavaScript and TypeScript configuration
● **Symptom:** V0.5: three rules in frontend/src/styles/tokens.css used `word-break: break-word`. V0.13: the sweep's probe flags `tseslint.config(` at frontend/eslint.config.js:9 as deprecated (line 10 at HEAD); the line was unchanged in the window, so it would count as new only if the platform did not match a moved line.
● **Root cause:** A deprecated CSS value carried from the original stylesheet; the dashboard's flat ESLint config still calls typescript-eslint's `config()` helper, which the probe reports as deprecated.
● **Fix:** V0.6: each became `overflow-wrap: anywhere`, which the engineering gate confirmed matches the specification. V0.13: none; the file still reads `export default tseslint.config(`.
● **Guard:** none recorded
● **Lesson:** Replace deprecated values and APIs when they are found, configuration files included, since any edit near them can bring them into the analyser's new-code window.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "'word-break: break-word' is 'overflow-wrap: anywhere' (S1874)" Also: gate report: find:security-and-config; frontend/eslint.config.js.

### CQ-026 JSX text followed by an element on the next line without explicit spacing

● **Rule:** `S6772` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** React (JSX and TSX)
● **Symptom:** 17 form labels across eight dashboard files (EventTimersPanel 5, Procedures 3, Login 2, Maneuvers 2, Notifications 2, AuditLog, Mattermost and ShiftLog 1 each, counted from the 56c55a9..691f25b diff) put text such as `Username` on one line and the input on the next.
● **Root cause:** JSX drops the line break between text and an element, so the spacing was implicit.
● **Fix:** Each of the 17 labels gains an explicit `{" "}` after its text.
● **Guard:** None recorded. The engineering gate's report lists 'both ShiftLog labels' among its killed mutants, but ShiftLog has only one S6772 label, so which labels those mutants covered is unclear.
● **Lesson:** Write the space between JSX text and a following element explicitly.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "17 labels gain '{" "}' (S6772)" Also: gate report as received; gate report: Engineering gate on V0.6 tree.

### CQ-027 React component props not marked read-only

● **Rule:** `S6759` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** React and TypeScript
● **Symptom:** Eight components took props through plain types: SortableHeader, AssistantPanel, DisplayToggles, ProtectedRoute, TimerRow, NoteRow and the two context providers.
● **Root cause:** Props types declared without `Readonly`.
● **Fix:** Each of the eight prop types is wrapped in `Readonly<...>`.
● **Guard:** none recorded
● **Lesson:** Type component props as Readonly from the start.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "eight prop types are 'Readonly' (S6759)"

### CQ-028 Null guard followed by property access instead of optional chaining

● **Rule:** `S6582` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** JavaScript and TypeScript
● **Symptom:** frontend/src/utils/timerSound.ts tested `c && c.state === "suspended"` and `!c || c.state !== "running"`.
● **Root cause:** Pre-optional-chaining idiom.
● **Fix:** `c?.state === "suspended"` and `c?.state !== "running"`.
● **Guard:** none recorded; the engineering gate's mutants on both optional chains were killed
● **Lesson:** Use optional chaining for guarded property reads.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "'timerSound.ts' uses optional chaining (S6582)"

### CQ-029 Union of literal types with string, which collapses to string

● **Rule:** `S6571` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** TypeScript
● **Symptom:** Three response fields in frontend/src/types/assistant.ts and event_timer.ts were typed `ActionUrgency | string`, `FeedUrgency | string` and `TimerRecurrence | string`.
● **Root cause:** The server types the fields as any string, and a union with `string` documents nothing to the compiler.
● **Fix:** Each typed `string`, with a comment naming the known values.
● **Guard:** none recorded
● **Lesson:** Type a field the server leaves open as string and name the known values in a comment, or narrow it at the boundary.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "three response fields are typed 'string', the known values named in a comment (S6571)"

### CQ-030 Constant array used for membership tests instead of a Set

● **Rule:** `S7776` · **Raised by:** app-store-sonarqube · **Severity:** platform-fail (code smell) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the platform), V0.6 (fixed)
● **Applies to:** JavaScript and TypeScript
● **Symptom:** The dashboard feed's bucket order in frontend/src/pages/Dashboard.tsx was an array checked with `order.includes(...)`.
● **Root cause:** Membership checks against an array.
● **Fix:** `new Set([...])` checked with `.has(...)`, iteration order preserved.
● **Guard:** none recorded; the engineering gate's mutant on the feed Set was killed
● **Lesson:** Use a Set for repeated membership tests.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "the feed's bucket order is a 'Set' (S7776)"

### CQ-031 Backtracking regular expression, a slow-regex security hotspot

● **Rule:** `typescript:S5852` · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised by the engineering gate in round 1, fixed in f6056cd)
● **Applies to:** JavaScript and TypeScript (any language with backtracking regex engines)
● **Symptom:** The new Markdown reader for the in-app manuals parsed inline marks with one alternation regex, `INLINE`, at frontend/src/utils/markdown.ts:24, which eslint-plugin-sonarjs super-linear-regex flags. A hotspot must be cleared by the platform team, not the app owner.
● **Root cause:** Inline Markdown parsing done with a single alternation pattern capable of super-linear backtracking.
● **Fix:** The inline marks are found with `indexOf` scans for the closing delimiters. Round 2 fuzzed the old regex against the new `parseInline` on 300,000 strings with 0 differences on single-line input; the security gate found no backtracking regex left and 20,000 to 30,000-character inputs cheap.
● **Guard:** frontend/src/components/Markdown.test.tsx renders every block kind; the gate's proxy (eslint-plugin-sonarjs) covers the rule; no committed lint rule.
● **Lesson:** Parse untrusted or large text with linear scans rather than alternation regexes, and treat a hotspot the owner cannot clear as a blocker.
● **Evidence:** gate report: Engineering gate V0.12: "**[MAJOR] S5852 slow regex (a security hotspot) at 'frontend/src/utils/markdown.ts:24' ('INLINE').**" Also: gate report: Engineering gate V0.12 round 2; gate report: Security gate V0.12 round 2.

### CQ-032 Nested template literal

● **Rule:** `typescript:S4624` · **Raised by:** engineering-reviewer · **Severity:** BLOCKER (as a new issue against a 0-issue gate) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised by the engineering gate in round 1, fixed in f6056cd)
● **Applies to:** JavaScript and TypeScript
● **Symptom:** A sweep summary string at frontend/src/utils/comms.ts:155 built a template literal inside another template literal.
● **Root cause:** A conditional suffix written inline inside the outer template.
● **Fix:** The inner template moved into its own `const` before the outer one.
● **Guard:** The gate's proxy (eslint-plugin-sonarjs); no committed lint rule.
● **Lesson:** Build a conditional fragment in its own variable before interpolating it.
● **Evidence:** gate report: Engineering gate V0.12: "S4624 nested template literal: 'frontend/src/utils/comms.ts:155'. Fix: put the inner template into its own 'const' first." Also: gate report: Engineering gate V0.12 round 2.

### CQ-033 Inverted boolean comparison used to make NaN fail closed

● **Rule:** `python:S1940` · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.12 (introduced in c2ac5cb, the security round 2 fixes; raised by the engineering gate in round 3 at ccbc7b8; fixed in 8aa5ecc)
● **Applies to:** Python (any language with IEEE floats)
● **Symptom:** `and not delete_at <= 0` at src/app/services/mattermost_channels.py:164, written in c2ac5cb (the security round 2 fixes) so that a NaN `delete_at` archives a channel, matches python:S1940 (boolean checks should not be inverted) and hides why the inversion is there.
● **Root cause:** A NaN-safe comparison expressed by negation instead of an explicit NaN test; pylint's unneeded-not does not flag `not x <= 0`, so no local rule catches it.
● **Fix:** `delete_at > 0 or math.isnan(delete_at)`; the existing NaN case still kills a `delete_at > 0` mutant.
● **Guard:** The float and NaN test cases; no local rule (fact from the gate). That SonarQube flags the original is inference, not confirmed with a Sonar Python run.
● **Lesson:** State edge cases such as NaN explicitly (math.isnan) rather than relying on an inverted comparison.
● **Evidence:** gate report: Engineering gate V0.12 round 3: "Problem (inference, not confirmed with a real Sonar Python run): this matches python:S1940" Also: docs/AUDIT-LOG.md, V0.12 row; commit messages (git log).

### CQ-034 Callback parameter shadowing a state variable in the enclosing component

● **Rule:** `typescript:S1117` · **Raised by:** engineering-reviewer; sonar-sweep · **Severity:** minor (not in Sonar way, so not counted by the gate) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.13 (raised by the engineering gate in round 1, fixed in 6085a53)
● **Applies to:** JavaScript and TypeScript
● **Symptom:** The new `arrive` useCallback's parameter `total` at frontend/src/components/comms/ChannelConversation.tsx:125 shadowed the `total` state declared at :60, which `@typescript-eslint/no-shadow` flags. The sweep's verifier found S1117 has no default quality profile, and V0.12's new shadowing in Markdown.tsx was not reported by the platform.
● **Root cause:** A parameter named after the value it carries (`page.total`) without checking names in the enclosing scope, during the S2004 refactor.
● **Fix:** Renamed `pageTotal`, not `count`, which would shadow the state updater's parameter at :136; the call site passes `page.total` by position.
● **Guard:** none (no-shadow is not enabled in frontend/eslint.config.js)
● **Lesson:** When extracting a callback, name its parameters so none shadows an outer variable, even where the gate would not count it.
● **Evidence:** gate report: Engineering gate V0.13 (fast): "the new parameter 'total' shadows the 'total' state at ':60', and '@typescript-eslint/no-shadow' (Sonar's S1117) flags it as new." Also: gate report: verify:typescript:S1117@ChannelConversation.tsx:125#2; commit messages (git log).

### CQ-035 Async route handlers that never await

● **Rule:** `python:S7503` · **Raised by:** engineering-reviewer and security-reviewer round (which gate is not recorded) · **Severity:** unknown · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (raised at the first gate round on 9616c41, fixed in c0a25dc)
● **Applies to:** Python and FastAPI
● **Symptom:** The scaffold's handlers in src/app/factory.py, `_root`, `_health` and `_status`, were declared `async def` with nothing awaited.
● **Root cause:** Template handlers written async by habit although they do no I/O.
● **Fix:** The handlers are plain functions.
● **Guard:** ruff RUF029 (a preview rule, enabled explicitly) in pyproject.toml's select list, run by scripts/verify.sh; the config names it the local twin of python:S7503.
● **Lesson:** Declare a handler async only when it awaits, and enable a local linter rule that mirrors the analyser's check.
● **Evidence:** commit messages (git log): "Application: handlers are plain functions (SonarQube python:S7503, now" Also: c0a25dc.

### CQ-036 Cognitive complexity above the limit, caught locally before upload

● **Rule:** `python:S3776 (local proxy: complexipy, at most 15 per function)` · **Raised by:** verification-loop · **Severity:** loop-fail · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.10 (update_user, split in af13871), V0.12 (record_sweep, list_bot_channels, split in 62ba4aa); each caught locally by the verification loop's complexity rung (inference from the loop; the round is not recorded)
● **Applies to:** Python (any language analysed by SonarQube)
● **Symptom:** Functions above 15 had to be split: `update_user` in src/app/api/v1/routes/users.py in the V0.10 Users work, and `record_sweep` and `list_bot_channels` in src/app/services/mattermost_channels.py in the Comms work.
● **Root cause:** Branch-heavy handlers and service functions accumulating decisions in one body.
● **Fix:** `update_user` split with `_keep_an_admin`; `record_sweep` and `list_bot_channels` split with `_new_row`, `_note_closing`, `_team` and `_conversation`; the V0.12 round 1 fix's `_mark_lost` was checked by the round 2 engineering gate to keep complexity within 15.
● **Guard:** scripts/verify.sh: `complexipy src --max-complexity-allowed 15`, the step naming SonarQube rule S3776.
● **Lesson:** Run a cognitive-complexity check at the platform's threshold on every change and split decisions into named helpers when it fails.
● **Evidence:** session summaries: "'record_sweep' and 'list_bot_channels' were split with '_new_row', '_note_closing', '_team' and '_conversation'." Also: scripts/verify.sh at f8a00bd; gate report: Engineering gate V0.12 round 2.

### CQ-037 Duplicated block between two callers, caught by a local duplication proxy

● **Rule:** `pylint duplicate-code (local proxy for SonarQube duplication)` · **Raised by:** verification-loop · **Severity:** loop-fail · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised by the loop on e0d7f34, among the gate-fix commits; fixed in b2f1681)
● **Applies to:** Python (any language)
● **Symptom:** The loop's duplication rung failed on e0d7f34: the background evaluation's audit row repeated five lines of the evaluate route's.
● **Root cause:** An audit-row block copied into a second caller.
● **Fix:** Both call `write_evaluation_audit` in the assistant service (b2f1681), which also gives the background row the procedures each evaluation used.
● **Guard:** scripts/verify.sh: pylint duplicate-code over sonar.sources, tests excluded as the gate excludes them; any repeated block of 4 lines fails, stricter than the 3% gate. It cannot see repeats inside one file.
● **Lesson:** Share a helper as soon as a block repeats, and run a duplication check stricter than the platform's gate.
● **Evidence:** commit messages (git log): "The verification loop's duplication rung failed on e0d7f34: the" Also: docs/AUDIT-LOG.md, V0.2 row; scripts/verify.sh at f8a00bd.

### CQ-038 Too many return statements in a validation helper

● **Rule:** `ruff PLR0911 (too-many-return-statements)` · **Raised by:** verification-loop · **Severity:** loop-fail · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.8 (raised by ruff during the DAST start work, fixed in 117346c)
● **Applies to:** Python
● **Symptom:** Ruff's too-many-return-statements check fired on `_database_problems` in src/app/config.py once the DAST scan's no-database branch was added.
● **Root cause:** A new early-return condition added to an existing multi-return validator.
● **Fix:** The condition extracted into `_scan_without_database()`, which `_fail_closed` consults before calling `_database_problems()`.
● **Guard:** ruff in the verification loop (pyproject.toml selects the PL family)
● **Lesson:** When a validator grows another early exit, extract the guard into a named predicate instead of adding a return.
● **Evidence:** session summaries: "**Too many returns.** Ruff's too-many-return-statements check on '_database_problems'; I extracted '_scan_without_database'." Also: 117346c.

### CQ-039 Names containing TOKEN, PASSWORD or SECRET bound to string literals trip hard-coded credential rules

● **Rule:** `ruff S105 (local); SonarQube S2068 hotspot (project note)` · **Raised by:** verification-loop; engineering-reviewer (V0.9) · **Severity:** loop-fail (ruff); hotspot risk the owner cannot clear · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.9 to V0.12 (ruff S105 renames and suppressions during the token-header, Users and Comms work; exact releases not recorded); a standing project rule from then on
● **Applies to:** any stack
● **Symptom:** Ruff S105 fired on constants whose names contain PASSWORD or TOKEN, among them the header-name constant `TOKEN_HEADER = "X-Holly-Token"` in src/app/dependencies.py (V0.9, 83e9696). The V0.9 engineering gate could not tell whether the TypeScript `TOKEN_HEADER` literal would trip a hard-coded-secret rule and judged it low risk.
● **Root cause:** Hard-coded credential rules match on the variable name when a string literal is assigned; Sonar hotspots need the platform team to clear them.
● **Fix:** Constants renamed where possible; header names and fixed token types keep `# noqa: S105` with a reason comment above (precedent: `token_type`); test tokens such as `BOT_TOKEN` use short placeholder values (which the secret-scan hook also required) with `# noqa: S105`; frontend tests hold typed values in neutral names. V0.9 passed all 11 stages, Code Quality included.
● **Guard:** ruff S rules in the verification loop; the secret-scan hook; a project rule never to give such names a string literal.
● **Lesson:** Avoid credential-shaped names for literals that are not secrets, and justify each suppression, because a hotspot can block a gate the owner cannot clear.
● **Evidence:** session summaries: "Never name a constant or variable with PASSWORD, TOKEN or SECRET and give it a string literal; the owner cannot close Sonar hotspots." Also: gate report: Engineering gate on V0.9 round 1.

### CQ-040 assert used for a runtime check in application code

● **Rule:** `ruff S101` · **Raised by:** verification-loop · **Severity:** loop-fail · **Status:** resolved · **Certainty:** inference
● **Releases:** V0.10 to V0.12 (raised and fixed before the gates; exact release not recorded)
● **Applies to:** Python
● **Symptom:** Ruff S101 flagged an assert in application code during the Users or Comms work; the file is not recorded.
● **Root cause:** An assert used as a runtime check, which python -O strips (inference about the reason).
● **Fix:** The assert was removed.
● **Guard:** ruff check over src and tests in scripts/verify.sh
● **Lesson:** Raise an explicit exception for runtime checks; keep assert for tests.
● **Evidence:** session summaries: "A ruff S101 assert was removed."

### CQ-041 Unknown whether the quality gate counts test files as changed code, and hotspots in tests the owner cannot clear

● **Rule:** `none (platform scoring question)` · **Raised by:** other (V0.5 audit row) · **Severity:** unknown · **Status:** open · **Certainty:** mixed
● **Releases:** V0.5 (opened), still open
● **Applies to:** any stack with a SonarQube quality gate
● **Symptom:** V0.5's row leaves open whether the second Code Quality check counts test files, which no coverage report names, as changed code, and SonarQube hotspots in the dashboard's tests, which the app owner could not clear, should the platform analyse them.
● **Root cause:** The platform's scoring and analysis scope are not documented to the project.
● **Fix:** None as a decision. On test files as changed code, the V0.5 row infers they do not block, since the baseline's project passed with its tests in the upload; on hotspots, the tests keep credential-shaped literals out. The V0.13 sweep found the platform analyses the uploaded archive rather than `sonar.sources`, since V0.12's report named frontend files, and left unchecked whether the platform classifies frontend *.test.tsx files as tests.
● **Guard:** Practice only: no credential-shaped literals in tests, neutral names for typed values.
● **Lesson:** Find out early which files the platform's analyser and coverage gate count, and keep test code clean of hotspot patterns until you know.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "Open: whether the second check counts test files, which no coverage report can name, as changed code" Also: gate report: find:security-and-config.

## 2.2 Security controls


### CQ-042 A platform gateway in front of the app can intercept the app's own bearer token in Authorization

● **Rule:** none · **Raised by:** app-owner (live App Store behaviour), then engineering-reviewer (two MAJORs on the fix's tests) · **Severity:** platform failure (sign-in unusable on the live app); MAJOR in fix review · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.8 (raised, live), V0.9 (fixed), V0.11 (confirmed live)
● **Applies to:** any web app behind a platform gateway or service mesh that authenticates requests; FastAPI and React here
● **Symptom:** V0.8 went Active with all 11 stages passed, but signing in as the admin showed the dashboard and dropped straight back to the sign-in page. The browser's record of GET /api/v1/auth/me showed a 401 with an empty body, none of Holly's headers, and WWW-Authenticate: Bearer error="invalid_token" naming 'Signed JWT rejected'. The same sequence against the V0.8 image locally stayed signed in, so no local rung could see it. In the fix's round 1 the engineering gate found no test stopping a refresh-and-retry from sending Authorization and no parity test for the header name on each side.
● **Root cause:** The App Store gateway answered for Holly and refused Holly's HS256 token in Authorization as one it could not verify with the platform's keys (fact). That it does so before the app sees the request, for any bearer token the platform did not sign, is inference from the missing headers and the wording (Spring Security's resource server). Every local rung calls the container directly.
● **Fix:** ADR-013: the dashboard sends the access token alone in X-Holly-Token and get_current_user never reads Authorization; the CORS allow-list names X-Holly-Token in place of Authorization; the dashboard refreshes once after a refused /auth/me. The operator manual's section 10 says how to tell the app's 401 from the gateway's, and the app-store-deployment skill gained this app-side exception.
● **Guard:** tests/test_auth.py: a valid token in Authorization alone is refused before any query, and a platform token there beside a valid X-Holly-Token changes nothing; the Vitest adapter answers 401 to any request carrying Authorization, first or retried; tests/test_token_header.py holds the header name equal on both sides; scripts/smoke-container.sh calls /api/v1/auth/me with the token in each header. A local gateway stand-in reproduced V0.8's failure and V0.9's fix.
● **Lesson:** When a platform puts an authenticating gateway in front of the app, do not send the app's own credentials in the headers that gateway owns; carry them in an app-specific header and test, with a stand-in that refuses the platform's header, that no request ever sends it.
● **Evidence:** docs/AUDIT-LOG.md, V0.9 row: "shows a 401 with an empty body, none of the headers Holly sets, and 'WWW-Authenticate: Bearer error="invalid_token"' naming 'Signed JWT rejected: Another algorithm expected, or no matching key(s) ..." Also: docs/AUDIT-LOG.md, V0.11 row.

### CQ-043 A configuration refusal at start-up must name the variable and never echo its value

● **Rule:** none · **Raised by:** container smoke rung, then engineering-reviewer (BLOCKER) and security-reviewer (MAJOR) · **Severity:** BLOCKER · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised and fixed)
● **Applies to:** any stack; Python with pydantic-settings and gunicorn here
● **Symptom:** On 55ab9f1 the smoke rung failed its last check: without APP_SECRET_KEY the container stopped on a raw pydantic traceback that named no variable and echoed part of the raw input, which for a truncated DATABASE_URL can hold part of the password.
● **Root cause:** pydantic's validation error text includes the input value, and the library error was allowed to propagate to the boot log.
● **Fix:** get_settings() turns a validation failure into InvalidSettingsError, which gunicorn prints as one line naming each variable at fault and repeating no value (8800e5a); 5a75af1 pins every path both gates named.
● **Guard:** 5a75af1's tests set five distinctive synthetic secrets beside a problem on each error path and assert no five-character fragment of any of them reaches the message; e7668de later made the refusal tests scan the whole printed traceback for a URL's credential too. The smoke rung requires a boot refusal to name the variable.
● **Lesson:** Wrap configuration validation so a refusal names the setting and the rule broken, never the value; test it by planting known secrets and scanning the whole output, traceback included, for fragments.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "the container smoke rung FAIL on its last check: without APP_SECRET_KEY the container stopped on a raw pydantic traceback that named no variable and echoed part of the raw input" Also: commit messages (git log).

### CQ-044 A secret scan of a release package must fail closed and decide positively what it can read

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer · **Severity:** FAIL (blocking) in four consecutive rounds, then minors · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.1 (six gate rounds, raised and fixed)
● **Applies to:** any release packaging or CI secret scan
● **Symptom:** Round by round on the new upload content net: b56e04c passed member names back to unzip, which reads brackets as a wildcard and lists control characters escaped, so those files were never read and the empty result passed the hook (both gates FAIL). 85962f4 still chose what to read by name, so compressed content under DATA.ZIP, an .xlsx or data.bin passed. 774173a used a list of format signatures, which let zlib, raw deflate, LZMA-alone and a zipapp through. 28de168 accepted UTF-16 behind a byte-order mark, so ASCII behind a stray BOM decoded into characters the rules could not read. ac0c5bc then drew two minors: no case pinned that only a committed allowlist entry counts, and a path listed twice silently took its last entry.
● **Root cause:** Fail-open design: an unreadable file produced empty input, which the hook treats as clean, and every negative enumeration (names, formats, encodings) left an unlisted case through.
● **Fix:** 85962f4 moved the nets into scripts/check-package.sh: extract once, refuse control-character names, walk every file; a missing hook, read error or file-count mismatch reads as 'could not scan' and refuses. 28de168 decides positively: only readable text is scanned and anything else is refused unless scripts/upload-binaries.txt names it. ac0c5bc treats only strict UTF-8 without control characters as text, reads the allowlist from HEAD, and refuses a changed file, a file that is text, an entry naming no packaged file and an entry without a reason or hash; fab9044 also refuses a duplicate entry.
● **Guard:** scripts/test-package-nets.sh, run by verify.sh, holds one case per bypass from every round (11 cases at 85962f4, 200 and more later), including a key-bearing text file beside a pinned binary.
● **Lesson:** A scanner that cannot read something must refuse it, and the set of things it accepts must be defined positively (strict UTF-8 text, plus hash-pinned exceptions), never as a list of formats to skip.
● **Evidence:** docs/AUDIT-LOG.md, V0.1 row: "both FAIL on b56e04c, because its new package content net reported files clean that it could not read" Also: commit messages (git log).

### CQ-045 Integrity checks that read git history must switch off every local override

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer · **Severity:** MAJOR (both gates FAIL in V0.3 round 2 and on 97d90be in V0.6) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised and fixed), V0.6 (raised again for a new check and fixed)
● **Applies to:** any release or review gate written against git
● **Symptom:** V0.3: a replace ref could forge the review record, and the guards against replace refs, grafts and filters could each be deleted with the self-test green; a local textconv or a forged commit-graph moved the version-bump search; ls-tree read pathspecs and quoted names unlike git archive. V0.6: the new scripts/check-baseline.sh left the commit-graph on, so a forged .git/objects/info/commit-graph made git diff read the baseline's tree for a changed commit and an upload changed under the baseline's version passed; then GIT_CONFIG_PARAMETERS in the environment could turn the graph back on, and with its unset removed a forged graph passed both checks.
● **Root cause:** git honours replace refs, grafts, textconv, the commit-graph and environment config by default. In git 2.43 git diff takes each commit's tree from the commit-graph while git show and cat-file read real objects. The packager exported only the replace-ref and graft overrides, and the GIT_CONFIG_* settings in check-reviews.sh's own process did not reach the new script, though its header claimed parity. GIT_CONFIG_PARAMETERS is read after GIT_CONFIG_COUNT, so it wins.
● **Fix:** V0.3 (153c91e, 8c70dbd): each script ignores replace refs and grafts; the bump search ignores textconv, signature display and the commit-graph; files listed with diff-tree; non-regular members refused. V0.6: check-baseline.sh exports core.commitGraph=false; both checks unset GIT_CONFIG_PARAMETERS; SECURITY.md's commit-graph sentence covers the baseline check. The packager's upstream comparison still reads the commit-graph, left as a stated limit (see the upstream-comparison entry).
● **Guard:** scripts/test-package-nets.sh forged-state cases, including 'an upload changed under the baseline's version, behind a forged commit-graph and GIT_CONFIG_PARAMETERS', each forged-graph case run again with GIT_CONFIG_PARAMETERS turning the graph on, red with either override removed.
● **Lesson:** A check that reads repository history to make a release decision must disable every local mechanism that can rewrite what git reports, in every script that reads it, and prove each override with a forged-state test.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "MAJOR: the guard against replace refs could be deleted with the self-test green, and a replace ref" Also: gate report: Security gate on 97d90be; docs/AUDIT-LOG.md, V0.6 row; commit messages (git log).

### CQ-046 Judge archive member names as they land on disk, not as they are listed

● **Rule:** none · **Raised by:** security-reviewer (MAJOR), engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised and fixed over several rounds)
● **Applies to:** any packaging or upload net that inspects zip or tar members
● **Symptom:** unzip lists a DEL or a byte above 0x7E as it stands, so no name check fired, and extraction dropped the byte: prod.en<DEL>v landed as prod.env and CLAUDE<DEL>.md as CLAUDE.md. Later rounds found a backslash passed (an extractor reading it as a separator could land tests/.claude\settings.json under .claude/), grep's [^ -~] missed a raw invalid byte under C.UTF-8, Info-ZIP strips a VMS ;1 suffix so frontend/CLAUDE.md;1 landed as frontend/CLAUDE.md, and a grep error read as no match.
● **Root cause:** Name checks judged the listed name, while extractors rewrite names; locale-dependent character classes; error exits treated as a pass.
● **Fix:** Refuse bytes outside printable ASCII and a backslash; refuse any file that does not land under its listed name; pin LC_ALL=C for the byte-level greps; a grep error refuses (96136cf, 37c1756, d429bff).
● **Guard:** scripts/test-package-nets.sh cases for DEL names, a doubled slash, a backslash, a VMS suffix, a failing grep and a high-byte name through git archive, all run under POSIX and C.UTF-8 (78 cases then).
● **Lesson:** Name-based deny lists over archives must check the name after extraction (round-trip), restrict names to a safe byte set, run byte-exact, and treat any tool error as a refusal.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "MAJOR: a member name holding a DEL or a byte above 0x7E passed every name check and extraction" Also: commit messages (git log).

### CQ-047 A review-verdict record parser must never drop a FAIL or hide one behind control bytes

● **Rule:** none · **Raised by:** security-reviewer (MAJOR), engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised and fixed)
● **Applies to:** any release gate driven by a text record
● **Symptom:** A FAIL filed under another version label was dropped, so the packager wrote the upload with a FAIL last; a carriage return could hide a verdict and a NUL passed the record check because the shell drops it; a mutant reading the working copy instead of the committed record left every case green.
● **Root cause:** Lines were filtered by a free-text label, bytes were read after the shell had altered them, and no case made the working copy and the commit differ.
● **Fix:** Line format 'review <reviewer> <PASS|FAIL> <commit> [# note]'; the last line from each reviewer decides whatever commit it names; the record must be printable ASCII and tab, counted before the shell reads it; read from the commit, now pinned by cases (e40e12b, 153c91e, 8c70dbd).
● **Guard:** Record cases in scripts/test-package-nets.sh, two of which edit the working copy over a committed FAIL and a carriage return.
● **Lesson:** A gate that reads a record of approvals should let the latest verdict per reviewer decide unconditionally, validate the raw bytes before any shell sees them, and read the committed version, with tests where the working copy disagrees.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "MAJOR: a FAIL filed under another version label was dropped, so the packager wrote the upload with a" Also: commit messages (git log).

### CQ-048 Resolve packaging output paths physically and read moving refs once

● **Rule:** none · **Raised by:** security-reviewer (MAJOR and minors), engineering-reviewer (minor: HEAD read twice) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised and fixed)
● **Applies to:** any shell-based build or packaging script
● **Symptom:** HEAD was read twice (a race); the rehearsal zip in dist/ was the upload without the check and a stale zip outlived runs; a rehearsal path through a symlink and .., or a symlinked dist/, reached the upload path; an old checkout could package; command substitution dropped a trailing newline from a directory name and an exported CDPATH sent a relative cd elsewhere, so checks could read a sibling clone.
● **Root cause:** Logical path handling in POSIX shell and repeated reads of a moving ref.
● **Fix:** HEAD resolved once; the last zip removed every run; rehearsals outside dist/, resolved physically and compared with dist/ and its ancestors by inode, never named appstore.zip; only a branch tip not behind upstream packages; paths split without losing a newline; CDPATH unset (e40e12b, 153c91e, 8c70dbd).
● **Guard:** scripts/test-package-nets.sh rehearsal cases and twin clones, one named with a final newline, pinning each script's root.
● **Lesson:** Scripts that write release artefacts must resolve output paths physically, compare by inode rather than string, read refs once, and neutralise shell environment such as CDPATH.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "MAJOR: a rehearsal path through a symlink and .., or a symlinked dist/, reached the upload path" Also: commit messages (git log).

### CQ-049 An upstream comparison that reads errors as 'level' fails open

● **Rule:** none · **Raised by:** security-reviewer (MAJOR), engineering-reviewer (minor); both gates (round 4 minor, the commit-graph route) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised and fixed; commit-graph residual left open)
● **Applies to:** any release gate
● **Symptom:** The check that the packaged branch was not behind upstream passed through a file named like its range, an upstream that had gone or was not stored, a graft, or no upstream at all; the case written for it refused for another reason. In round 4 both gates found the comparison also reads the commit-graph file, so a forged graph in .git/ hides the lag.
● **Root cause:** Error paths of git rev-list read as zero lag, and no end-of-options separator followed the range.
● **Fix:** Ignore grafts, take HEAD only on a local branch, refuse an unresolvable upstream, count the lag with an end-of-options separator after the range and refuse on any error, and say when a branch has no upstream to compare (8c70dbd). The commit-graph route was left open as needing write access to .git/, a limit SECURITY.md states; the packager still sets no commit-graph override.
● **Guard:** scripts/test-package-nets.sh cases modelling the threat: a FAIL upstream, a graft, a file named like the range, a gone upstream, a remote-tracking HEAD.
● **Lesson:** In a release gate every error branch must refuse; a comparison that cannot be computed is a failure, and tests should fail for the reason they are named after.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "MAJOR: the upstream check failed open, through a file named like its range, an upstream that had" Also: commit messages (git log).

### CQ-050 Check every record's classification marking, and audit, before sending data to an external model

● **Rule:** none · **Raised by:** security-reviewer (MAJOR), both gates (round 2), the author's documentation pass · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised over three gate rounds and a documentation pass; fixed, one residual accepted)
● **Applies to:** any app sending stored data to a third-party LLM or API
● **Symptom:** UDL notification content went to Anthropic with no check of its classification marking, though the record the dashboard was built against carried a dissemination marking, and background sendings left no audit row. Round 2: with a database that answers reads but refuses writes, each evaluation and narrative failed when stored, after the call, and the cycle sent the next, up to 20 an hour, with no audit row. The documentation pass found three more gaps: a narrative's publications reached Anthropic before its audit row was written; manoeuvres sent with a cleared notice were unchecked; an older cleared publication could stand in for a newer uncleared one. Round 3: an on-demand evaluation whose store fails after the call leaves no audit row.
● **Root cause:** ADR-006 assumed all data Unclassified; the control covered the primary record only, was applied before choosing the latest publication, and the audit row was ordered after the external call.
● **Fix:** Content reaches the assistant only when its marking is in ASSISTANT_CLEARED_MARKINGS, matched exactly, default ["U"]; uncleared notices store 'Not sent to the assistant'. Every record sent needs a cleared marking; a notice is evaluated only when its latest publication is cleared; each background sending is audited and any failure once a call may be out stops the phase (4a50d16, 1a59034, 62e5dc5). The on-demand residual is accepted in SECURITY.md (7de7d33), its trip-wire reworded to commit a row before the call (6c10fb5).
● **Guard:** Tests in tests/test_background_refresh.py, tests/test_assistant_service.py and tests/test_event_summary.py, including one that the marking is checked after the latest publication is chosen; SECURITY.md trip-wire for the on-demand case.
● **Lesson:** Apply a data-release control to every record that rides along in a prompt, to the version actually chosen, and write or commit the audit row before the external call so a later failure cannot leave a disclosure unrecorded.
● **Evidence:** commit messages (git log): "The security gate found UDL notification content going to Anthropic" Also: SECURITY.md.

### CQ-051 Parse a connection string once, with the driver's parser, and never show parser error text

● **Rule:** none · **Raised by:** engineering-reviewer (minor in round 1, nit in round 4), security-reviewer (minor in round 2, MAJOR in round 3, nit in round 4) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised in rounds 1 to 4, fixed)
● **Applies to:** any app configured by a database URL; SQLAlchemy and PostgreSQL here
● **Symptom:** ?sslmode=require passed boot and failed at first connection; Python's URL parser quoted the password in its own refusal; an unencoded ? in the password made the sslmode rewrite move the @, so SQLAlchemy printed part of the password as a port number in the boot traceback; a second @ followed by / or ? sent a piece of the password to DNS; an underscore in a host name was refused.
● **Root cause:** The URL was parsed by one library, rewritten, re-rendered and parsed again by another, and library error text was echoed in the refusal.
● **Fix:** SQLAlchemy's parser reads the URL once; sslmode is renamed on the parsed query; the parsed URL goes to both engines unrendered; any parse error becomes a fixed message raised outside the except block; a URL with more than one @ is refused before parsing; underscores accepted (de816cc, e7668de, 4676e45, fd8cd4b, 71fc76b).
● **Guard:** Tests run every printable punctuation character, unencoded, through the real start-up hook and Alembic environment and scan the whole traceback for password fragments; the round 4 security gate's 1,337-shape fuzz printed no fragment.
● **Lesson:** Treat a credential-bearing URL as a secret: parse it exactly once with the parser that will use it, never round-trip it through string rendering, and replace parser exceptions with fixed messages.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "MAJOR: a DATABASE_URL password holding an unencoded ? lost the @ after it in the sslmode rewrite, so SQLAlchemy quoted part of the password as a port number in the boot traceback" Also: commit messages (git log).

### CQ-052 Expensive password hashing must not run on the event loop, and in-process limits hold only for one worker

● **Rule:** none · **Raised by:** security-reviewer (MAJOR in V0.2; nit in V0.10) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised and fixed), V0.10 (residual accepted)
● **Applies to:** async Python servers (FastAPI, Starlette) and any app with in-process limits
● **Symptom:** One client could stall and then restart the only worker with sign-ins: bcrypt ran on the event loop and the dummy check for unknown usernames made every attempt pay for it; a restart reset every in-process limit and the daily token cap. In V0.10 bcrypt hashing on the change, create and reset routes ran outside the check slots, limited only by the coarse 600 a minute.
● **Root cause:** CPU-bound hashing in an async handler; rate limits and spend caps held in process memory.
● **Fix:** Sign-in counts every attempt per client address (30 a minute) first, runs bcrypt on worker threads with at most 4 checks at once and answers 503 with Retry-After beyond that (db957da). The single-worker position is recorded in SECURITY.md. V0.10's hashing outside the slots was left as it was, since each hash follows a slot-bound, limited check.
● **Guard:** tests/test_auth.py sign-in-under-load tests (a free event loop during checks, the capacity refusal); SECURITY.md trip-wire to move the counters to PostgreSQL before a second worker or replica.
● **Lesson:** Run password hashing off the event loop behind a bounded pool that refuses when full, and record that in-memory rate limits and caps are only valid with exactly one process.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "one client could stall and restart the only worker with sign-ins, as bcrypt ran on the event loop" Also: SECURITY.md; docs/AUDIT-LOG.md, V0.10 row.

### CQ-053 Reordering middleware to satisfy a lint rule can silently change which responses carry security headers

● **Rule:** `S8414` · **Raised by:** engineering-reviewer (MAJOR), security-reviewer (nit on the CORS row) · **Severity:** MAJOR · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.6 (raised, position accepted and documented)
● **Applies to:** Starlette and FastAPI, and any framework with ordered middleware
● **Symptom:** Fixing SonarQube S8414 by making CORS the outermost middleware meant every preflight (OPTIONS with Access-Control-Request-Method, from any origin, to any path) left without CSP, nosniff, Cache-Control and X-Request-ID and skipped the coarse rate limit, while five documents said every response carried them and SECURITY.md had no position.
● **Root cause:** Starlette answers a preflight inside the CORS middleware without calling inner layers, so moving CORS outside the header and request-id layers changed their reach.
● **Fix:** CORS stays outermost; a SECURITY.md row records the preflight position with a trip-wire; the five documents, the factory comment and request_id.py corrected. The security gate judged it sound: a constant body, nothing reflected, no database, sign-in or body read.
● **Guard:** tests/test_app.py pins both sides: the preflight's fixed body, no request header echoed, no CSP, no request id; a 429 to an allowed origin carrying the CORS headers.
● **Lesson:** When a static-analysis fix reorders middleware, re-derive which responses each layer still touches, test the short-circuit paths explicitly, and record any position it creates.
● **Evidence:** gate report as received: "with CORS outermost, every preflight (OPTIONS carrying Access-Control-Request-Method, from any origin, to any path) now leaves without the security headers and without an 'X-Request-ID'." Also: docs/AUDIT-LOG.md, V0.6 row.

### CQ-054 Validate every value from configuration before it reaches a query or a hash, with one validator for every path

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer (shared MAJOR in round 1) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised and fixed over four rounds)
● **Applies to:** any app that bootstraps accounts or records from environment variables; Python, SQLAlchemy and PostgreSQL here
● **Symptom:** The new first-admin bootstrap only stripped ADMIN_EMAIL: an email over 255 characters or holding non-UTF-8 bytes failed the INSERT with a DBAPIError whose traceback, with the admin's bcrypt hash among its parameters, reached the container log. An ADMIN_PASSWORD holding a lone surrogate raised UnicodeEncodeError in hash_password, naming one character and its position. ADMIN_USERNAME accepted control and bidirectional characters such as U+202E. Round 2 found (a security nit) the older admin CLI, which writes the same table, still had the weak checks.
● **Root cause:** Length and storability were checked for the username only, so the database and the codec acted as validators and their failure paths exposed values; the fix first went to the new code path only.
● **Fix:** Round 2: the bootstrap refuses an over-long, unstorable or unprintable email or username, and a password that is not valid UTF-8, with a RuntimeError naming only the variable, before any session opens. Round 3: the checks move to unstorable_field in the CLI module, shared by the bootstrap and the CLI. Round 4: each field gets its own message.
● **Guard:** tests/test_admin_bootstrap.py and tests/test_create_admin.py assert the value is absent from the message and no session opens; mutants N01, N02, N03 and C10 killed; the smoke rung refuses a 312-character ADMIN_EMAIL at boot and finds no bcrypt hash in the log.
● **Lesson:** Validate outside values (length, encodability, printability) in code before any query, encode or hash, so library error paths never see them, and route every writer of the same record through one validator.
● **Evidence:** gate report: Engineering gate on V0.7: "[MAJOR] 'src/app/admin_bootstrap.py:50' | 'ADMIN_EMAIL' is only stripped, never checked." Also: gate report: Security gate, V0.7 round 2.

### CQ-055 Hide bound parameters on every database engine, and know what that does not hide

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer (shared MAJOR in round 1); engineering-reviewer (round 2 nit, the migrations engine); security-reviewer (round 2 minor on the constraint detail; round 3 nit, the setting unpinned) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised and fixed over rounds 1 to 4)
● **Applies to:** SQLAlchemy and Alembic with PostgreSQL; any ORM that logs parameters
● **Symptom:** A failed INSERT printed SQLAlchemy's [parameters: (...)], password_hash included, to the gunicorn master's stderr and so to the platform log. After the app engine was fixed, the CHANGELOG claimed no failed statement prints its values while the separate Alembic engine in migrations/env.py did not set the option; once set, deleting it left all 1,091 tests green. Round 2 also showed that with a CHECK constraint on app_user, PostgreSQL's own 'Failing row contains' detail prints the hash whatever the client hides (not reachable with the live schema).
● **Root cause:** SQLAlchemy includes bound values in exception text by default; Alembic builds its own engine; the server's DETAIL text echoes the row itself.
● **Fix:** hide_parameters=True on the application engine (round 2) and the migrations engine (round 3), asserted in tests (round 4); SECURITY.md's first-admin row gains a trip-wire to check any value in Python before adding a CHECK, exclusion or NOT NULL constraint on app_user that an outside value could break.
● **Guard:** tests/test_admin_bootstrap.py test_the_engine_never_logs_a_statement_s_values; tests/test_config.py asserts kwargs["hide_parameters"] is True for the migrations engine (mutant E01 killed); SECURITY.md trip-wire.
● **Lesson:** Turn off bound-value logging on every engine the app creates, migrations included, pin each with a test, and still validate values before the database because server-side error detail can echo the row.
● **Evidence:** gate report: Security gate on V0.7: "SQLAlchemy's 'DBAPIError' then prints the statement's parameters, including 'password_hash', to the gunicorn master's stderr and so to the platform log." Also: gate report: Security gate, V0.7 round 3; SECURITY.md.

### CQ-056 Remove a one-time secret from every copy of the process environment, and never make operators put it back

● **Rule:** none · **Raised by:** security-reviewer (minor), engineering-reviewer (MAJOR) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised and fixed over rounds 1 to 4; residual accepted)
● **Applies to:** gunicorn and any pre-fork server; any app seeded from environment secrets
● **Symptom:** Round 1: ADMIN_PASSWORD stayed in the gunicorn master's and the worker's environment for the life of the container. Round 2: after os.environ.pop, gunicorn's cfg.env_orig (copied before on_starting and handed to the worker and to a re-exec) and every /proc/<pid>/environ still held it, where the manual said the worker never held it. Also round 2 (shared MAJOR): the documented step of removing ADMIN_PASSWORD after the first start stopped every later start, and the error's first remedy was to put the password back.
● **Root cause:** gunicorn snapshots os.environ into cfg.env_orig before on_starting runs; /proc/<pid>/environ keeps the start-time block whatever the process does; the bootstrap refused half a pair before counting accounts.
● **Fix:** Round 2 popped ADMIN_PASSWORD from os.environ after the bootstrap; round 3 also popped it from gunicorn's cfg.env_orig (through a getattr fallback, which a round 3 nit said would do nothing silently if gunicorn renamed it) and made the bootstrap count accounts first, reading no value once any exists; round 4 popped server.cfg.env_orig directly, tested against gunicorn's own Config. The /proc residue is an accepted SECURITY.md position, with removing the variables and restarting as the operator control.
● **Guard:** tests/test_gunicorn_conf.py (mutants N10 and G01 killed); the round 4 security gate's live SIGUSR2 re-exec started without the password; the smoke rung starts normally with the password removed after the first start.
● **Lesson:** A bootstrap secret should be consumed and scrubbed before workers fork, including any copy the server framework keeps, and the app must start normally once the secret is removed so operators are never told to restore it.
● **Evidence:** gate report: Engineering gate, V0.7 round 2: "the worker's 'cfg.env_orig' does hold it (gunicorn 'config.py:57' copies 'os.environ' before 'on_starting' runs, and 'workers/base.py:51' hands that copy to the worker)" Also: docs/AUDIT-LOG.md, V0.7 row; SECURITY.md.

### CQ-057 Keyword detection in user-controlled Unicode names: decide on the raw value and mark, do not delete, hidden characters

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (seven gate rounds, raised and fixed; residuals accepted)
● **Applies to:** any keyword, block-list or classification rule over user-controlled Unicode text
● **Symptom:** The rule 'stop pulling a Mattermost channel whose name contains CLOSED' failed open round after round. R1: it saw names only after the display cleaner, which drops whole values it cannot show, so CLOSED beside a zero-width-joiner emoji, a tab or a zero-width space stayed open. R2: invisible characters outside category Cf (combining grapheme joiner, variation selectors, a Hangul filler, NUL) and fullwidth or mathematical bold letters still hid it. R3: unassigned code points (Cn) that are default-ignorable, such as U+E0080 and U+2065, hid it. R4: engineering showed dropping a character could join a letter onto the word and remove the boundary; security (passing, with minors) showed U+202E followed by DESOLC drew as CLOSED, and str.isspace() treated U+001C to U+001F and U+0085 as gaps. R5: one hidden character inside the word with one beside it defeated reading every name two ways. R6: security passed this rule (engineering's FAIL was a nested conditional, likely S3358); R7: both gates passed.
● **Root cause:** A security decision was taken on the output of a display sanitiser, and hidden characters were removed by an enumerated category list, which both misses categories and can join neighbouring letters across a word boundary.
● **Fix:** R1 (f6056cd): is_closed reads the raw name and display name before cleaning or truncation. R2 (c2ac5cb): NFKC, then drop Cf, Mn, Me and Cc and listed default-ignorables. R3 (c00e3d2): Cn dropped too. R4 (fc96e56): two readings, only Zs, Zl, Zp, tab, LF and CR as separators, right-to-left names also read reversed. R5 (56d0dbc): one marked reading, each hidden character becomes a NUL mark that the pattern skips between letters and treats as a boundary beside the word. Accepted in SECURITY.md: a Cyrillic look-alike keeps a channel open (no TR39 confusables skeleton), and an accent with no letter of its own fails safe to closed. A non-string name has no reading, as the code's docstring states. Optional and not taken, per the audit row: lone surrogates, private-use characters and U+2800 are not marked.
● **Guard:** Parametrised close-cases in tests/test_mattermost_channels.py for each round's bypasses and an open-case pinning the accepted look-alike; the author's sweep of 19,823 placements; security round 6's 300,000-name sweep and engineering round 6's 1,058,782-name sweep found none open.
● **Lesson:** Run a text-matching security rule on the raw input, normalise with NFKC, and replace every character that cannot show as a letter with a marker the pattern understands rather than deleting it; prove it with a large generated sweep against a reference, and record what is out of reach (confusables).
● **Evidence:** gate report: Security gate V0.12: "'is_closed' only ever sees names that have already been through 'clean_name'. Any display name 'clean_name' rejects comes back as 'None', and the CLOSED word in it is lost." Also: gate report: Security gate V0.12 round 3; gate report as received; SECURITY.md; docs/AUDIT-LOG.md, V0.12 row.

### CQ-058 Check the type of untrusted JSON values before using them, and skip a malformed record rather than abort the batch

● **Rule:** none · **Raised by:** not named for V0.2 (listed among the fixes to the imported code); engineering-reviewer and security-reviewer independently on the Comms work (MAJOR) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (imported code fixed); V0.12 (raised in the Comms work's first gate round, run as 'V0.11 round 1' before the V0.11 hotfix took that number; fixed in 0a60d93)
● **Applies to:** any service ingesting third-party JSON; Python here
● **Symptom:** V0.2: a malformed Mattermost post aborted the run or stalled every later run on it; a non-object answer was not a client error; ids reached a request path unchecked; numeric satellite ids from UDL crashed evaluations and summaries. Comms work: a Mattermost channel whose type was a JSON array or object raised TypeError: unhashable type at 'kind not in PULLED_TYPES'; it escaped sweep_channels and the ingest, which caught only MattermostClientError, so every cycle aborted with nothing pulled, Find channels answered 500 and the status light stayed green.
● **Root cause:** Boundary code trusted upstream shapes and compared a raw value with a set, breaking the module's own promise that one malformed record is skipped; no test had a non-string type.
● **Fix:** V0.2 (55ab9f1): malformed posts skipped and counted, non-object answers refused, ids checked, numeric ids handled. Comms fix (0a60d93): a _kind helper returns the type only when it is a string, used in both places, so the record is counted as skipped.
● **Guard:** test_a_type_that_is_not_text_is_counted_skipped_not_raised with a type of ["O"] and {}; the V0.12 engineering mutation battery killed the non-string-type mutant.
● **Lesson:** At an integration boundary, check each field's type before any operation that assumes it (hashing, set membership, arithmetic) and keep the 'skip and count one bad record' promise with a test for each wrong type.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "That error escapes 'sweep_channels' (:239) and 'ingest_mattermost_messages' (:269), which catch only 'MattermostClientError'." Also: gate report: Security gate on V0.11 round 1; CHANGELOG.md; session summaries.

### CQ-059 Bound the parsing of untrusted JSON: catch RecursionError and cap retry scans

● **Rule:** none · **Raised by:** security-reviewer (V0.2 round 1, the recursion; the 20-brace bound came in the round 2 fixes, gate not named; Comms round 1, MAJOR) · **Severity:** MAJOR (Comms round 1) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (LLM replies, raised and fixed); V0.12 (Mattermost: raised in the Comms work's first gate round, then labelled V0.11; fixed in 0a60d93)
● **Applies to:** Python services decoding untrusted JSON, including LLM output
● **Symptom:** V0.2: a model reply nested beyond Python's recursion limit raised RecursionError, so the route answered 500 and the background loop re-billed the notice every cycle; a reply full of opening braces held the event loop for over a second because the tolerant parser retried from every brace. Comms work: deeply nested JSON from Mattermost raised RecursionError, which is not a ValueError, so it escaped api_client.py's decode handler and stopped the cycle.
● **Root cause:** Decode handlers caught only ValueError; tolerant extraction had no attempt bound.
● **Fix:** V0.2: deep nesting is an AssistantError raised at once (eae7e54) and the parser tries at most 20 opening braces (a4e8d55). Comms fix (0a60d93): _get_json catches (ValueError, RecursionError) and raises the service's own 'response was not valid JSON' client error.
● **Guard:** A test pins the 20-brace bound; a client test feeds 100,000 nested brackets; the V0.12 engineering gate killed the RecursionError mutant.
● **Lesson:** Python's json raises RecursionError on deep nesting, so every untrusted decode must catch it alongside ValueError, and any retrying or tolerant parser needs a hard attempt limit.
● **Evidence:** gate report: Security gate on V0.11 round 1: "Deeply nested JSON reaches the same state: RecursionError is not a ValueError, so it escapes 'api_client.py:57'." Also: commit messages (git log).

### CQ-060 A background job's health indicator must fail closed on any unexpected exception

● **Rule:** none · **Raised by:** security-reviewer (MAJOR), engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the Comms work's first gate round, then labelled V0.11; fixed in 0a60d93)
● **Applies to:** any app with background jobs and a status page
● **Symptom:** SWEEP_STATE.last_at was set before the try block and only MattermostClientError was caught, so a crashed sweep left the Comms page showing ok: true, problem: null with a fresh time (after a restart, ok: null with a fresh time) while nothing was pulled.
● **Root cause:** Status updated optimistically before the work, and the error handler covered one exception type only.
● **Fix:** sweep_channels gains a catch-all branch that rolls back, sets ok False with a fixed message ('The channel sweep failed unexpectedly; the server log has the detail.') and logs the traceback (0a60d93).
● **Guard:** test_any_other_failure_fails_closed_in_holly_s_words; the V0.12 engineering gate killed the rollback mutant.
● **Lesson:** Record success only after the work completes, and give every background job a catch-all that marks it failed in the app's own words, so monitoring never shows green over a crash.
● **Evidence:** gate report: Security gate on V0.11 round 1: "Because :234 sets 'last_at' before the try, the page then shows 'ok: true, problem: null' with a fresh 'last_at' (reproduced live)." Also: gate report: Engineering gate on V0.11 round 1; gate report: Security gate V0.12.

### CQ-061 Never let a client auto-retry a sign-in, and pin that rule with a test

● **Rule:** none · **Raised by:** security-reviewer (V0.6 minor, V0.9 minor), engineering-reviewer (V0.9 MAJOR) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised and fixed), V0.9 (raised again as MAJOR and fixed)
● **Applies to:** any SPA with token refresh; React and TypeScript here
● **Symptom:** V0.6: client.ts's retry and auth-endpoint guards were untested. V0.9 round 2: after the refresh logic changed, dropping /auth/login from the refresh skip list left every test green, so a wrong password typed with a refresh token held would be sent twice.
● **Root cause:** The no-refresh rule for session calls was untested on the sign-in path after the skip list was reworked.
● **Fix:** V0.6 round 3: tests that a refused retry refreshes once only and that an auth call never refreshes. V0.9 round 3: only sign-in, refresh and sign-out skip the refresh, with a test that a refused sign-in never refreshes even with a refresh token held.
● **Guard:** Client tests in frontend/src/api/client.test.ts, red when the skip list is changed (the skip-list mutant killed in V0.9 round 3).
● **Lesson:** A client's refresh-and-retry wrapper must exclude credential-bearing calls, and that exclusion needs its own test, because a retried sign-in resends the password.
● **Evidence:** docs/AUDIT-LOG.md, V0.9 row: "dropping '/auth/login' from the skip list left every test green, and a wrong password typed with a refresh token held would be sent twice" Also: docs/AUDIT-LOG.md, V0.6 row.

### CQ-062 Parse request bodies only after authentication, with per-route size caps

● **Rule:** none · **Raised by:** security-reviewer (the anonymous multipart parse), engineering-reviewer (the orphan file) · **Severity:** not graded in the sources · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised and fixed)
● **Applies to:** FastAPI and Starlette; any framework that parses bodies before auth
● **Symptom:** An anonymous 10.5 MiB multipart POST was parsed and spooled to disk before its 401, since FastAPI reads a declared form before any dependency runs, and every route accepted 11 MiB; a failed or cancelled upload could leave an orphan file because the write ran outside the clean-up.
● **Root cause:** Form parameters declared on the route are parsed before auth dependencies; one global body cap; file write outside the clean-up.
● **Fix:** Every route takes at most 256 KiB; only POST /api/v1/procedures takes 11 MiB and reads its form itself after sign-in, with at most one file and two fields; the write sits inside a clean-up that runs on any exception, cancellation included (763194b, 48c1a6e).
● **Guard:** Tests that fail against the previous route; tests driven below the middleware for cancellation; 48c1a6e pins the one-file, two-field rule.
● **Lesson:** Do not declare large form or file parameters on a route whose authentication is a dependency; read the body yourself after sign-in, cap body size per route, and clean up partial writes on every exit path.
● **Evidence:** commit messages (git log): "The security gate showed an anonymous 10.5 MiB multipart POST being"

### CQ-063 Refuse or skip text the database cannot store at every boundary, before any external call

● **Rule:** none · **Raised by:** security-reviewer (V0.2 rounds 2 and 3, Comms round 1), engineering-reviewer (V0.2 round 4) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (UDL records, LLM replies and requests, raised and fixed); V0.12 (Mattermost posts: raised in the Comms work's first gate round, then labelled V0.11; fixed in 0a60d93)
● **Applies to:** PostgreSQL-backed apps; Python with pydantic here
● **Symptom:** V0.2: one UDL record holding a NUL or lone surrogate failed the whole pull; a model reply holding an escaped NUL passed validation and failed the store after the call, stalling background evaluation at that notice every cycle; a shift note holding a NUL went to the assistant and then failed its write with a 500, and a NUL in a sign-in, query or other field answered 500. Comms work: a Mattermost post holding a NUL failed the batch insert and rolled back the whole cycle, so the high-water mark never moved and every later cycle stalled at that post while the page said ok.
● **Root cause:** PostgreSQL refuses NUL in text and JSON (and lone surrogates), and nothing checked storability where data entered.
● **Fix:** The storability rule moved to app/db/storable.py so every boundary shares it: call_claude and parse_evaluation refuse unstorable replies (d795588); StorableText in app/schemas/common.py gives a 422 for every request text field, upload field, file name and free-text query parameter before any query, call or write (2ba91a8); the Comms fix skips and counts posts whose raw JSON fails json_problem.
● **Guard:** Tests per field and parameter, a test that a refused note never reaches the assistant, tests red when either reply check or the nested walk is removed, and Mattermost tests with a NUL in the message and the raw post (mutant killed in V0.12).
● **Lesson:** Know what your store cannot hold (NUL, lone surrogates) and enforce it with one shared rule at every entry point, requests, upstream records and model output alike, before anything is sent or billed.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "request text with a NUL reached the assistant before its write failed" Also: commit messages (git log); gate report: Security gate on V0.11 round 1.

### CQ-064 Validation error responses must not echo the refused value or its length

● **Rule:** none · **Raised by:** security-reviewer (nits) · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (value echo, raised and fixed), V0.10 (length, raised and fixed)
● **Applies to:** FastAPI and pydantic; any framework with verbose default validation errors
● **Symptom:** V0.2: FastAPI's default 422 echoed each submitted value, so a sign-in with an over-long password returned the password, and a lone surrogate in a JSON body made it a 500 with the value in the traceback. V0.10: the custom handler passed pydantic's message through, so a too-short password came back as 'at least 12 items after validation, not 8', disclosing its length; the engineering gate found V0.9 already returned lengths for other fields.
● **Root cause:** The default RequestValidationError handler includes 'input'; pydantic ends length messages with the actual length.
● **Fix:** V0.2 (2544473, 22cc091): a handler answers each refusal with the error's type, place and message only, through the same middleware so it keeps the security headers and request id. V0.10: _without_length strips the ', not N' suffix for every 422.
● **Guard:** Two sign-in tests that FastAPI's default handler turns red; mutant R20 (length stripping removed) killed.
● **Lesson:** Replace the framework's default validation handler so refusals carry the rule broken but never the input or anything derived from it, such as its length.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "FastAPI's default 422 echoed each submitted value, and a lone surrogate in a JSON body made it a 500 with the value in the traceback" Also: gate report: Security gate on V0.10 round 1; CHANGELOG.md.

### CQ-065 Error responses built outside the middleware stack lose security headers and the request id

● **Rule:** none · **Raised by:** V0.1 scaffold gates (inference from the fix commit); security-reviewer nit (V0.2) · **Severity:** nit · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (headers, fixed), V0.2 (request id, fixed)
● **Applies to:** Starlette and FastAPI; any middleware-based framework
● **Symptom:** V0.1: a 500 lacked the strict security headers every other response carried. V0.2: a 500 carried no X-Request-ID.
● **Root cause:** Starlette builds the 500 response outside the middleware that adds the headers and the request id.
● **Fix:** V0.1 (c0a25dc): the factory ensures a 500 keeps the security headers. V0.2 (e0d7f34): the request-id layer leaves the id on the request for the 500 handler; 48c1a6e pins that an error before the id is set still answers with the generic body and headers.
● **Guard:** tests/test_app.py.
● **Lesson:** Test the headers of error responses separately, since a framework's top-level error handler often runs outside the middleware that decorates normal responses.
● **Evidence:** commit messages (git log): "checked locally by ruff RUF029), a 500 keeps the security headers,"

### CQ-066 Pin the set of routes open without sign-in as a reviewed inventory test

● **Rule:** none · **Raised by:** V0.1 scaffold gates (the fix commit names the reviewers' mutants) · **Severity:** not graded in the sources · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (raised and fixed), held since
● **Applies to:** any web API
● **Symptom:** Before c0a25dc no test inventoried the routes, so a new route open to anonymous callers would have failed nothing (inference from the fix). Today every route under /api/v1 needs a token except the probes, /, /status, two health reads and the three sign-in routes.
● **Root cause:** Authentication coverage was not inventoried.
● **Fix:** tests/test_app.py holds the whole route inventory and the public set as literals, as the authentication trip-wire; all 14 mutants the reviewers used or the controls implied are killed (c0a25dc).
● **Guard:** test_only_the_reviewed_routes_are_open_without_sign_in fails on any new public route until it is reviewed.
● **Lesson:** Enumerate every route and assert the exact public set in a test, so adding an unauthenticated route is a reviewed change rather than an accident.
● **Evidence:** commit messages (git log): "Tests: every expectation is a literal, a reviewed route inventory acts" Also: SECURITY.md.

### CQ-067 Name nets must cover every environment-file spelling, including inside allowlist re-admissions

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer (minor findings closed in b56e04c; the .dockerignore change in the round 1 fix, inference) · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (raised and fixed)
● **Applies to:** Docker build contexts, .gitignore and packaging nets
● **Symptom:** Ignore files and the package name net covered only some environment-file names, and packaging scanned names only, so a secret in an unexpected file would ship. In .dockerignore, '!src/' re-admitted the whole subtree, so a .env file under src/ would reach the image.
● **Root cause:** Narrow name patterns; a negated allowlist pattern re-includes everything beneath it.
● **Fix:** Nets cover .env, .env.*, .env-*, .envrc and *.env, and packaging scans each file's content (b56e04c); .dockerignore excludes **/.env and **/.env.* again after '!src/' (c0a25dc).
● **Guard:** scripts/test-package-nets.sh cases.
● **Lesson:** List every environment-file spelling in each ignore and package net, and re-exclude secrets after any allowlist negation, since a negated directory re-admits its whole subtree.
● **Evidence:** commit messages (git log): "environment file (.env, .env.*, .env-*, .envrc, *.env), and packaging" Also: .dockerignore at c0a25dc.

### CQ-068 Refuse tool and agent configuration in the upload by name, with look-alike pass cases

● **Rule:** none · **Raised by:** security-reviewer (suggested the net on 092cf83; .mcp.json as a later nit), engineering-reviewer (only one pass case guarded it) · **Severity:** ungraded follow-up, then nits · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised and fixed)
● **Applies to:** any packaging or release pipeline
● **Symptom:** CLAUDE.md, CLAUDE.local.md, .claude/ and later .mcp.json stayed out of the upload only because the path list omitted them; once refused by name, only one pass case guarded the net against refusing too much.
● **Root cause:** Exclusion by omission with no deny net, and refusal tests without near-miss cases.
● **Fix:** scripts/check-package.sh refuses them by name at any depth and in any case (6d03e18, 96136cf); four look-alike names must pass: myclaude.md, x.claude/, claude.mdx, .claude-cache/ (052921d).
● **Guard:** scripts/test-package-nets.sh cases for each name and each look-alike.
● **Lesson:** Files that must never ship need an explicit deny net, not just absence from an allowlist, and each deny pattern needs near-miss cases proving it does not over-match.
● **Evidence:** commit messages (git log): "CLAUDE.md, CLAUDE.local.md and .claude/ stayed out of the upload only"

### CQ-069 A version read by a pattern can disagree with the version the runtime sees

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised over three rounds, fixed; one residual accepted)
● **Applies to:** any release gate keyed on a version string in source
● **Symptom:** Round 0: an __init__.py with two __version__ lines (0.6.0 then 0.5.0) left Python's version at the baseline's, but version_at returned both lines as one value, so the bump refusal passed. Round 1: __version__ = "0.6.0" followed by __version__: str = "0.5.0" made Python read 0.5.0 and the regex 0.6.0, and check-baseline.sh passed. Round 2 nit: a globals().update(__version__=...) run only under some setting passes both static rules.
● **Root cause:** The packaging checks parsed the version with a pattern and did not require exactly one assignment in a strict form; static checks cannot see run-time assignment.
● **Fix:** Both check-baseline.sh and check-reviews.sh refuse more than one line starting __version__, or one not in the strict form; tests/test_version.py walks the AST and asserts exactly one plain string assignment. The security gate then ran many forms (augmented, tuple, walrus, globals(), look-alike names) and found none where packaging and Python disagree. The globals().update case is accepted as a committer's move the review record covers.
● **Guard:** Nets cases for each script, including an annotated second line; the AST assertion in tests/test_version.py.
● **Lesson:** When a release gate reads a value from source, either evaluate it as the runtime does or require a single strict form and refuse anything else.
● **Evidence:** gate report: Security gate on 97d90be: "Python's effective version stays 0.5.0, the baseline's. 'version_at' returns both lines as one value, which differs from" Also: gate report as received.

### CQ-070 Show only http and https links from untrusted records, with noopener noreferrer, and prove any rewrite of the check equivalent

● **Rule:** `none (V0.13 rewrite for SonarQube S6557)` · **Raised by:** not named for V0.2 (a security change at the fusion, listed under Fixed in the CHANGELOG); security-reviewer (V0.13 verification) · **Severity:** not graded in the sources · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (fixed), V0.13 (rewrite verified)
● **Applies to:** React and any front end rendering untrusted URLs
● **Symptom:** Links taken from UDL records were clickable whatever their scheme, and new-tab links lacked noopener. In V0.13 the in-app manual's Markdown link check was rewritten from a regex test to startsWith for a SonarQube finding.
● **Root cause:** Untrusted URLs rendered without a scheme allowlist.
● **Fix:** Only http and https become links and every new-tab link carries noopener noreferrer (V0.2, 55ab9f1). In V0.13 the security gate proved the rewritten Markdown check identical to the old one: only strings starting exactly with https:// become links.
● **Guard:** Dashboard tests; frontend/src/pages/Help.test.tsx asserts both rel attributes; the V0.13 gate ran 23 attack inputs and 200,000 random ones through both forms.
● **Lesson:** Allowlist link schemes from untrusted data, and when a lint fix rewrites a security check, prove the old and new forms equivalent on attack and random inputs.
● **Evidence:** CHANGELOG.md: "Links from UDL records become clickable only for http and https, and every new-tab link carries 'noopener noreferrer'." Also: gate report: Security gate V0.13 (fast); commit messages (git log).

### CQ-071 Do not show an upstream API's error text to users

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** not graded in the sources · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised and fixed)
● **Applies to:** any app calling an external API
● **Symptom:** The Anthropic API's own error text was stored and shown to analysts.
● **Root cause:** Upstream error messages passed through to the UI.
● **Fix:** Each failure class has a fixed message; the API's text goes to the server log only (eae7e54).
● **Guard:** Assistant client tests (tests/test_claude.py).
● **Lesson:** Map third-party failures to fixed, app-owned messages and keep the provider's text in server logs only.
● **Evidence:** commit messages (git log): "The Anthropic API's own error text was stored and shown to analysts."

### CQ-072 Keep passwords out of argv and do not log failed usernames that name no account

● **Rule:** none · **Raised by:** not named for the --password flag (a V0.2 change to the imported command); the failed-username change came in the security gate's round 1 fix (db957da) · **Severity:** not graded in the sources · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (fixed)
● **Applies to:** any CLI and any sign-in audit trail
● **Symptom:** The imported admin command took the password as a command-line flag, landing it in shell history and the process list; the append-only audit chain recorded every failed username, which may be a password typed into the wrong box.
● **Root cause:** Secrets in command-line arguments; logging raw failed credentials into an immutable store.
● **Fix:** The password comes from ADMIN_PASSWORD or a hidden prompt; a failed username is recorded only when it names an account.
● **Guard:** tests/test_create_admin.py (a password on the command line is refused); tests/test_auth.py.
● **Lesson:** Take secrets from the environment or a hidden prompt, never argv, and avoid writing unmatched sign-in usernames to logs that cannot be redacted.
● **Evidence:** CHANGELOG.md: "the '--password' flag is gone, so a password never lands in shell history or the process list." Also: commit messages (git log).

### CQ-073 Remove real data from test fixtures and repository history

● **Rule:** none · **Raised by:** the author at import · **Severity:** not graded in the sources · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (fixed)
● **Applies to:** any repository importing code from elsewhere
● **Symptom:** An imported test held a trimmed copy of a real UDL record (a person's name, record ids, a dissemination marking, an external link); the uploaded zip, holding the NOTSO report and spreadsheet, sat in branch history.
● **Root cause:** Source delivered together with data products and real-record fixtures.
● **Fix:** Fixture values replaced with synthetic ones keeping the record's shape (0717c05); the upload commit removed from history and each later commit recreated with the same tree, author and date.
● **Guard:** none recorded
● **Lesson:** Before importing third-party code, strip data products and replace real records in fixtures with synthetic ones; rewrite history if they were ever committed.
● **Evidence:** commit messages (git log): "held a record its author described as a trimmed copy of a real UDL" Also: docs/AUDIT-LOG.md, V0.2 row.

### CQ-074 Cap a manual ingest's batch size, and keep security comments true to the code

● **Rule:** none · **Raised by:** security-reviewer (round 1 nit on the comment); the 10,000 cap is listed among the V0.2 fixes, its finder not named · **Severity:** nit · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (fixed)
● **Applies to:** any API that triggers upstream ingests
● **Symptom:** A manual UDL ingest could ask for any number of records; a max_results comment promised a cap that a request naming no limit did not get.
● **Root cause:** Unbounded max_results; a stale comment.
● **Fix:** At most 10,000 records in one pull (max_results bounded 1 to 10,000 in the elset and notification schemas); UDL's own default page size applies when none is named, marked TBC (e0d7f34).
● **Guard:** tests/test_udl_routes.py refuses max_results of 0 and 10,001.
● **Lesson:** Bound user-controlled batch sizes on every upstream call, and correct a comment that claims a limit the code does not enforce.
● **Evidence:** CHANGELOG.md: "A manual UDL ingest may ask for at most 10,000 records in one pull." Also: commit messages (git log).

### CQ-075 A development server must bind loopback, including its proxy

● **Rule:** `none (follow-on to SonarQube S8392)` · **Raised by:** security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised and fixed)
● **Applies to:** Vite and any dev setup with a proxy
● **Symptom:** Vite's dev server had host: true: with the API on 127.0.0.1, Vite still listened on every interface and proxied /api to it, so a machine on the LAN reached the API at :3000/api, while CHANGELOG and __main__.py claimed a development server is never reachable from the network.
● **Root cause:** Only the Python entry point was changed for S8392; the Vite dev proxy was missed.
● **Fix:** Vite binds 127.0.0.1 and proxies to http://127.0.0.1:8080; scripts/dev.sh and docs/developer/setup.md follow.
● **Guard:** none recorded
● **Lesson:** When restricting a server to loopback, check every process that can forward to it, such as a front-end dev proxy.
● **Evidence:** gate report as received: "The API binds 127.0.0.1, but Vite listens on every interface and proxies '/api' to it, so a machine on the LAN reaches the API at ':3000/api', along with Vite's own dev server."

### CQ-076 Validate the format of LLM-supplied fields at the server boundary, and render unparsed values as text

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised, client fixed, server deferred), V0.7 (server fixed)
● **Applies to:** any app storing or rendering LLM output
● **Symptom:** The assistant's deadline was any string up to 64 characters, so non-dates such as 'by end of shift' were stored and made the panel's formatter throw; in V0.7 the panel labelled any string the browser's Date reads, such as 'before shift 3', as a 2001 date.
● **Root cause:** The schema validated type and length, not meaning, and the client fed model output to a date parser.
● **Fix:** V0.6: the panel shows a non-date as written; the security gate accepted deferring the server check because the only reader shows it as escaped text. V0.7: the reply drops a deadline that is not an ISO 8601 timestamp, or a time without its UTC offset; the panel's label is limited to ISO-shaped values.
● **Guard:** Panel cases red without the guard; schema tests.
● **Lesson:** Treat every field of model output as untrusted input: parse it to the expected type on the server or drop it, and never pass free text to client parsers that guess.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "an assistant deadline that is not a date, such as "by end of shift", passed the schema and made the panel's formatter throw" Also: docs/AUDIT-LOG.md, V0.7 row; CHANGELOG.md.

### CQ-077 Secret-scan rules must follow a credential to its new transport form

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor, then nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised and fixed over three rounds)
● **Applies to:** any secret-scanning hook or CI scanner
● **Symptom:** Round 1: the pre-write hook blocked a JWT inside Authorization: Bearer (exit 2) but allowed X-Holly-Token: <jwt> (exit 0), so the hook and the upload content net, which shares its rules, no longer saw the app's token in its documented form. Round 2: the new JWT rule's leading word-boundary anchor missed a token glued to a word character, such as tok_eyJ...
● **Root cause:** The only rule covering the token keyed on the Bearer scheme; JWTs were an accepted blind spot; a word boundary needs a non-word character before eyJ.
● **Fix:** Two labelled rules in .claude/hooks/secret-scan.mjs, 'Holly token header' and 'JSON Web Token'; round 3 dropped the leading anchor. SECURITY.md's content-net row updated.
● **Guard:** Nets self-test cases "Holly's token in its own header", "a JSON Web Token" and "a JSON Web Token glued to a word", each split so the file's own source never matches; restoring the anchor turns the last red; the security gate scanned every blob in history (1,011) with old and new rules and found no false positive.
● **Lesson:** When a credential's carrier changes (header, cookie, file), update the secret-scan rules in the same change and plant a test token in each new form, including forms glued to other text.
● **Evidence:** gate report: Security gate on V0.9 round 1: "The new documented form, 'X-Holly-Token: <jwt>', passes the pre-write hook and therefore the upload content net (shown: exit 2 before, exit 0 now)." Also: gate report as received; gate report: Security gate on V0.9 round 3.

### CQ-078 Turn off CORS credentials mode when the app reads no cookie

● **Rule:** none · **Raised by:** security-reviewer (nit) · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised in rounds 1 and 2, fixed in round 3)
● **Applies to:** Starlette and FastAPI CORS; any CORS configuration
● **Symptom:** allow_credentials=True predated V0.9. With an origin listed it only let that origin's calls carry the platform's _appstore_app_session cookie to the gateway, and Starlette also sent access-control-allow-credentials: true to a disallowed origin.
● **Root cause:** A setting carried over that nothing in the app needed once the token became a script-set header.
● **Fix:** allow_credentials=False in the CORS middleware, with a comment; a preflight asking for credentials gets no credentials mode.
● **Guard:** The CORS test asserts no access-control-allow-credentials header; setting it back to True turns it red.
● **Lesson:** Enable CORS credentials only when the app itself authenticates by cookie; otherwise it only lets other cookies ride along.
● **Evidence:** gate report: Security gate on V0.9 round 1: "With an origin listed, it only lets that origin's calls carry the platform's '_appstore_app_session' cookie to the gateway." Also: tests/test_app.py at 83e9696.

### CQ-079 New identifiers must not pass for one another: restrict usernames and compare emails case-insensitively

● **Rule:** none · **Raised by:** security-reviewer (minor, look-alikes), engineering-reviewer (minor, email case) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised and fixed)
● **Applies to:** any app with user-chosen or admin-created account names
● **Symptom:** The security gate created a username with a Cyrillic a and one with a combining accent beside existing names; both were accepted and rendered identically on the Users page and in the audit view. The engineering gate found a case-sensitive email clash check.
● **Root cause:** The username validator allowed 1 to 50 printable characters, so any printable Unicode passed; email uniqueness compared case-sensitively.
● **Fix:** New usernames, after trimming and lowercasing, are restricted to a to z, 0 to 9 and . _ @ - (1 to 50); an email already in use in any case is refused.
● **Guard:** Schema tests and a killed look-alike-username mutant; the round 2 security gate's live probe refused Cyrillic, combining, zero-width, bidi, fullwidth, ligature and other look-alikes.
● **Lesson:** For identifiers shown to administrators or in audit trails, use a narrow ASCII alphabet (or full confusable checks) and compare case-insensitively where the identifier is.
● **Evidence:** gate report: Security gate on V0.10 round 1: "**Fix:** NFKC-normalise and refuse combining marks or mixed scripts, or restrict usernames to '[a-z0-9._-]'." Also: docs/AUDIT-LOG.md, V0.10 row; CHANGELOG.md.

### CQ-080 Every outcome of a security-relevant action must write its audit row

● **Rule:** none · **Raised by:** security-reviewer (nit) and engineering-reviewer (minor) in V0.10; engineering-reviewer (minor) in V0.12 · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (password change, raised and fixed), V0.12 (channel sweep, raised and fixed)
● **Applies to:** any app with an audit trail
● **Symptom:** V0.10: POST /auth/password refused a new password equal to the current one with no audit row, while every other outcome was audited and the operator manual said the action always carries success and any reason. V0.12: _changed ignored sweep.skipped, so a sweep that only skipped malformed records wrote no audit row, though the docs say skipped records are audited.
● **Root cause:** An early-return branch added without the audit call; the predicate deciding audit-worthiness omitted one outcome.
● **Fix:** V0.10 round 2 audits the refusal with reason same_password; V0.12 adds sweep.skipped to _changed (f6056cd).
● **Guard:** Same-password audit mutant killed; test_a_sweep_that_only_skipped_a_record_is_audited, whose mutation went red in round 2.
● **Lesson:** Test that each branch of an audited action, refusals and partial outcomes included, writes its row, rather than testing only the main path.
● **Evidence:** gate report: Security gate on V0.10 round 1: "refusal writes no audit row; every other outcome of the route does." Also: gate report: Engineering gate V0.12.

### CQ-081 Every token-accepting path must check the revocation version, logout included

● **Rule:** none · **Raised by:** security-reviewer (nit) · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised and fixed)
● **Applies to:** any JWT or session system with revocation
● **Symptom:** Logout answered 204 and audited success for a refresh token whose token version had moved on, a token that worked nowhere else.
● **Root cause:** Logout checked the refresh token's signature and revocation list but not the new token-version claim the other paths checked.
● **Fix:** Logout refuses a stale-version refresh token with 401, audited stale_token.
● **Guard:** A logout-stale-check mutant killed in round 2; the round 2 security gate's probe (logout of a valid token 204, again 401, stale token 401).
● **Lesson:** When a revocation mechanism is added, apply it to every endpoint that accepts the token, including logout, so the audit trail never records success for a dead session.
● **Evidence:** gate report: Security gate on V0.10 round 1: "**[NIT] Logout accepts a stale-version refresh token**" Also: gate report: Security gate on V0.10 round 2.

### CQ-082 Rolling back below a revocation mechanism resurrects revoked sessions

● **Rule:** none · **Raised by:** security-reviewer (minor), deploy-gate (same minor) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised), V0.12 (rollback texts fixed)
● **Applies to:** any app with versioned migrations and token revocation
● **Symptom:** Rolling back to V0.9 brings back every session V0.10 ended by raising the token version, until it expires (up to 7 days for a refresh token): 401 on V0.10, then 200 on V0.9. Rolling forward resets every version to 0 and every must_change_password to false, so V0.9 tokens keep working and pending temporary passwords become full passwords.
● **Root cause:** Session revocation lived in a column the downgrade drops, and the signing key, the only other revocation lever, was unchanged across the rollback.
● **Fix:** Interim handover steps rotate APP_SECRET_KEY with any rollback and again on roll-forward and re-issue pending temporary passwords; V0.12 writes this into the rollback texts.
● **Guard:** none recorded (the security gate showed it live; the deploy gate's rollback rehearsal on a used database reproduced it)
● **Lesson:** Rehearse rollbacks on a used database and ask what security state the downgrade discards; if revocation is lost, rotate the signing key as part of the rollback.
● **Evidence:** gate report: Security gate on V0.10 round 2: "Every session V0.10 had ended by raising the version comes back until it expires, up to 7 days for a refresh token, and works under V0.9. Proven: 401 on V0.10, then 200 on V0.9." Also: docs/AUDIT-LOG.md, V0.12 row.

### CQ-083 Make boolean request fields strict: Literal[True] also accepts 1

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the Comms work's first gate round, then labelled V0.11; fixed in 0a60d93)
● **Applies to:** Python with pydantic
● **Symptom:** PATCH /channels/{id} accepted {"reviewed": 1} and 1.0 with 200, while 'following' beside it was StrictBool.
● **Root cause:** In pydantic, Literal[True] matches 1 because 1 equals True in Python; the house rule is to reject bad input, never coerce it.
● **Fix:** A mode="before" field validator accepts only the JSON value true; 1, 1.0 and false are refused with 422 (0a60d93).
● **Guard:** 422 cases in tests/test_mattermost_routes.py; the V0.12 engineering gate killed the reviewed-only-true mutant.
● **Lesson:** In pydantic, use strict types or a before-validator for booleans and boolean literals, since numeric 1 compares equal to True.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "beside it is strict, and the rule is to reject bad input, never coerce it." Also: src/app/schemas/mattermost.py at 0a60d93.

### CQ-084 Bound collections an upstream listing drives, and pass id lists as one array parameter

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the Comms work's first gate round, then labelled V0.11; fixed in 0a60d93; residual accepted)
● **Applies to:** SQLAlchemy with asyncpg and PostgreSQL; any integration that mirrors an external listing
● **Symptom:** No cap on the channels a sweep records, and rows are never pruned: with 20,000 channels one cycle made 20,004 posts calls and outlasted a 120 s client timeout, GET /channels returned 8.7 MB to every open Comms tab each minute, and review-all put every name into one audit detail. At 33,009 rows the expanding IN exceeded asyncpg's 32,767-parameter limit, so the route answered 500 for every user. In V0.12 round 1 the caps were found to apply only after each listing is fetched and decoded.
● **Root cause:** The sweep trusted the upstream listing size; an IN list sized by data; listings read whole, not paged.
● **Fix:** A bot in more than 100 teams or 1,000 channels fails the sweep with Holly's own message and changes nothing; channel ids go to the database as one array (= ANY). SECURITY.md accepts that the caps bound what is stored, not one listing's size (ADR-015), since the Mattermost server is the team's own.
● **Guard:** test_more_teams_or_channels_than_the_caps_fail_the_sweep; both cap mutants killed in V0.12; SECURITY.md trip-wire to page the listings if the bot reaches a server outside the team's control.
● **Lesson:** Cap any stored collection whose size an upstream controls, fail the job when the cap is exceeded, and send variable-length id lists as a single array parameter rather than an expanding IN.
● **Evidence:** gate report: Security gate on V0.11 round 1: "At 33,009 rows, the expanding 'IN (...)' exceeds asyncpg's 32,767-parameter limit" Also: SECURITY.md.

### CQ-085 Apply the same printable-text cleaning to every display name from an external source

● **Rule:** none · **Raised by:** security-reviewer (coverage ledger) · **Severity:** not graded (a coverage-ledger note) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (noted, pre-existing, in the Comms work's first gate round, then labelled V0.11; fixed in 0a60d93)
● **Applies to:** any UI showing third-party names
● **Symptom:** Mattermost author nicknames (mattermost_ingest.py:59-63) were cut to length but not held printable, so a bidirectional control character in a nickname reached the page as text.
● **Root cause:** Channel names had a cleaning helper; author names used a separate, weaker path.
● **Fix:** _display_name uses the sweep's clean_name (renamed from _clean), so a nickname Holly cannot show gives way to the next key (0a60d93).
● **Guard:** test_a_nickname_or_channel_name_holly_cannot_show_gives_way_to_the_next.
● **Lesson:** Route every externally sourced display string through one cleaning function, so a second path cannot skip the printable check.
● **Evidence:** gate report: Security gate on V0.11 round 1: "Pre-existing, not changed by V0.11: author nicknames ('mattermost_ingest.py:59-63') are cut but not held printable" Also: CHANGELOG.md.

### CQ-086 Numeric checks on upstream values must not fail open on floats or NaN

● **Rule:** `none (the NaN-safe form was later judged likely to trip S1940, inference, and rewritten)` · **Raised by:** security-reviewer (float and NaN); engineering-reviewer (round 3, the likely S1940) · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.12 (rounds 1 to 3, raised and fixed)
● **Applies to:** Python and any language with IEEE NaN
● **Symptom:** Round 1: delete_at sent as a float such as 1.5e12 gave archived False, so an archived channel would keep being pulled. Round 2: delete_at = NaN read as not archived, though the comment said a number never fails towards open. Mattermost sends an int (inference), but Python's json accepts NaN.
● **Root cause:** isinstance(delete_at, int) excluded floats, and 'delete_at > 0' is False for NaN, with anything unmatched defaulting to open.
● **Fix:** Any int or float above 0 that is not a bool archives the channel (f6056cd); rewritten as 'not delete_at <= 0' so NaN archives (c2ac5cb); that inverted form was judged likely to draw S1940 in round 3 and became 'delete_at > 0 or math.isnan(delete_at)' (8aa5ecc).
● **Guard:** Parametrised delete_at cases including NaN in tests/test_mattermost_channels.py, proven in round 3 by reverting to 'delete_at > 0', and in round 4 by removing 'or math.isnan(delete_at)'.
● **Lesson:** Write fail-closed numeric checks so that anything not clearly safe (wrong type, NaN) takes the safe branch, and test float and NaN inputs explicitly.
● **Evidence:** gate report: Security gate V0.12: "'delete_at' sent as a float (for example '1.5e12') gives 'archived=False', so the archive check fails open." Also: gate report: Security gate V0.12 round 2; commit messages (git log).

### CQ-087 Switching a source off must remove its content from LLM context at once

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (round 1, raised and fixed)
● **Applies to:** any app feeding stored data into LLM prompts
● **Symptom:** _load_recent_chat did not filter by followed or open channels, so after a channel added by mistake was unfollowed or closed, its pulled messages kept going to Anthropic for the prompt window (6 hours by default); the docstring still said 'from the configured channels'. ADR-015 and SECURITY.md had documented and accepted this.
● **Root cause:** The prompt loader predated the follow list and closed state and was not updated when they were introduced.
● **Fix:** A correlated NOT EXISTS subquery leaves out messages from any channel switched off or closed; channels the table does not hold are kept; the docstring rewritten (f6056cd). Round 2 confirmed the columns are NOT NULL, so no NULL gap.
● **Guard:** tests/test_assistant_service.py pins the exact SQL; round 2 mutation of the filter went red.
● **Lesson:** When adding an off switch for a data source, update every consumer, especially prompt builders for external models, so the switch takes effect immediately rather than when data ages out.
● **Evidence:** gate report: Security gate V0.12: "'_load_recent_chat' does not filter by followed or open channels." Also: CHANGELOG.md.

### CQ-088 Upload nets do not refuse package-manager override files

● **Rule:** none · **Raised by:** V0.5 gates (open item below the blocking bar; the gate is not named) · **Severity:** below the blocking bar · **Status:** open · **Certainty:** mixed
● **Releases:** V0.5 (raised as open), still open at f8a00bd
● **Applies to:** Node packaging; any upload net
● **Symptom:** No upload net refuses a frontend/npm-shrinkwrap.json or frontend/.npmrc, either of which would change what the platform's npm ci installs.
● **Root cause:** A new install path (the root project handing npm ci to frontend/) was not added to the deny net.
● **Fix:** none yet; scripts/check-package.sh holds no such refusal in the current tree (a search finds neither name).
● **Guard:** none recorded
● **Lesson:** When the pipeline gains an install step, add the files that can redirect it (.npmrc, shrinkwrap, registry config) to the package deny net.
● **Evidence:** commit messages (git log): "refuses a frontend/npm-shrinkwrap.json or frontend/.npmrc."

### CQ-089 Two readers of the same environment flag must match names the same way

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer · **Severity:** minor (open below the blocking bar) · **Status:** open · **Certainty:** fact
● **Releases:** V0.8 (raised, round 1 fixed, round 2 left open)
● **Applies to:** Python with pydantic-settings; any app with a test-only start mode
● **Symptom:** The DAST start mode (APPSTORE_DAST_SCAN) fills in a throwaway key and temporary store. Round 1: with -e appstore_dast_scan=true, Holly served as the scan would but logged no dast_scan line and kept the background loops on, logging ERROR every cycle. Round 2: with APPSTORE_DAST_SCAN=false and appstore_dast_scan=true, the scan step read False and the settings True (and the reverse gave a live start on a throwaway key); Docker's environment order varied between runs; a lower-case app_secret_key or store name is replaced under the flag. Round 1 also noted SECURITY.md was silent on a key or store filled in under the flag with real settings.
● **Root cause:** pydantic-settings matches names in any case (lower-case fold, last wins) and reads .env; the scan step first read only the exact upper-case name, then took the first upper-cased match. The other five names it reads or writes are handled in upper case only.
● **Fix:** Round 2: the scan step reads the flag's name in any case, and SECURITY.md covers a key or store filled in under the flag (its relaxed start and single log line were recorded in round 1). Proposed and not done: refuse to start when two spellings disagree, read every name as pydantic-settings does, and drop other spellings before writing. The code at f8a00bd still takes the first match.
● **Guard:** A lower-case spelling test (the case-sensitive mutant killed in round 2); the last-spelling-wins mutant survived; the smoke rung runs the image with only the flag.
● **Lesson:** If two components read the same configuration, give them one shared reader, or test them together on case variants and duplicates; a security-relevant mode switch should refuse ambiguous input.
● **Evidence:** gate report: Security gate on V0.8 DAST: "pydantic-settings matches variable names case-insensitively, and also reads '.env'; 'scan_requested' reads only the exact upper-case name." Also: gate report: Security gate, V0.8 round 2; src/app/dast_scan.py at f8a00bd.

### CQ-090 A secret-strength check must count content, not raw length

● **Rule:** none · **Raised by:** engineering-reviewer (nit, outside the change), security-reviewer (nit) · **Severity:** nit (open below the blocking bar) · **Status:** open · **Certainty:** fact
● **Releases:** V0.8 (blank key raised and fixed; whitespace-padded key left open)
● **Applies to:** any app validating signing keys from configuration
● **Symptom:** Settings accepted an APP_SECRET_KEY of 40 spaces, and the scan step's handling of an empty or whitespace-only key under the flag was unpinned (mutants M15 and M37 survived). After the fix, a key of 31 spaces and one character is accepted, and so is one of 32 invisible non-space characters (U+200B, U+FEFF, U+3164).
● **Root cause:** _secret_problems checked only len(key) against the minimum of 32, and checks for blank only once the length passes.
● **Fix:** 'APP_SECRET_KEY must not be blank' added; the security gate confirmed all 29 Unicode whitespace code points at 32, 40 and 200 characters refused. Proposed and not done: test len(key.strip()) against the minimum; the code at f8a00bd still checks the raw length.
● **Guard:** test_a_blank_secret_key_is_refused in tests/test_config.py.
● **Lesson:** Measure a secret's length after stripping whitespace and invisible characters, or better, estimate its entropy, so padding cannot satisfy the minimum.
● **Evidence:** gate report: Engineering gate on V0.8 DAST: "outside the scan, 'Settings' accepts a 40-space 'APP_SECRET_KEY' (reproduced). That is for security-reviewer." Also: gate report: Security gate, V0.8 round 2; src/app/config.py at f8a00bd.

### CQ-091 Validate a server-supplied error code before logging it

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor (open below the blocking bar) · **Status:** open · **Certainty:** fact
● **Releases:** V0.8 (raised, left open)
● **Applies to:** any service logging database or upstream error metadata
● **Symptom:** A fake PostgreSQL server sent an error whose SQLSTATE field held 28P01, a newline and a forged audit JSON line, and the image printed it as its own log line; a 4,000-character SQLSTATE also passed. The docstrings claimed the logged parts held no value from the connection.
● **Root cause:** _refusal takes orig.sqlstate from the driver as-is and interpolates it into the refusal and log. It needs a hostile or impersonated database, outside the threat model.
● **Fix:** none yet; proposed: keep the SQLSTATE only if it matches [0-9A-Z]{5}, otherwise report 'invalid'.
● **Guard:** none recorded
● **Lesson:** Treat every field a remote peer sends, error codes included, as untrusted before it reaches a log; validate it against its expected shape to prevent log injection.
● **Evidence:** gate report: Security gate, V0.8 round 2: "a fake server sent an ErrorResponse whose 'C' field held '28P01' plus a newline and a forged audit JSON line. The image printed it as its own log line." Also: docs/AUDIT-LOG.md, V0.8 row.

### CQ-092 Unhandled connect errors can echo a malformed connection-string option in a traceback

● **Rule:** none · **Raised by:** security-reviewer (nit) · **Severity:** nit (open below the blocking bar) · **Status:** open · **Certainty:** fact
● **Releases:** V0.7 (pre-existing), V0.8 (raised, left open)
● **Applies to:** SQLAlchemy and asyncpg; any driver configured by URL
● **Symptom:** TypeError, UnicodeError and ValueError from bad query options or host labels escape wait_for_database as raw tracebacks; a ValueError echoes that query parameter's own value (the operator's value, never the password, user or host).
● **Root cause:** The wait handles SQLAlchemyError and OSError only, and query keys and values are not validated up front.
● **Fix:** none yet; proposed: check query keys and values in _database_problems.
● **Guard:** none recorded
● **Lesson:** Validate every component of a connection string at configuration time, so driver exceptions on connect never carry configuration values into logs.
● **Evidence:** gate report: Security gate, V0.8 round 2: "A malformed query parameter's own value reaches a traceback. It is the operator's value, never the password, user or host." Also: docs/AUDIT-LOG.md, V0.8 row.

### CQ-093 Trust forwarded client addresses only from known proxies, or per-client limits key on the proxy

● **Rule:** none · **Raised by:** V0.2 round 2 documentation fixes (the gate is not named, inference: security-reviewer); deploy-gate (V0.7) · **Severity:** minor (open) · **Status:** open · **Certainty:** mixed
● **Releases:** V0.2 (recorded), V0.7 (raised again by the deploy gate), still open
● **Applies to:** gunicorn and uvicorn behind an ingress; any proxied app
● **Symptom:** Behind the ingress every request may appear to come from one address, so all analysts share 600 requests a minute and the per-address sign-in limit, and anyone can spend the shared sign-in allowance; recorded client addresses are the ingress's.
● **Root cause:** gunicorn trusts forwarded addresses only from FORWARDED_ALLOW_IPS (loopback by default), and the platform's ingress addresses are unconfirmed; '*' would trust any forwarded header.
● **Fix:** Recorded in SECURITY.md, the security overview and the runbook; FORWARDED_ALLOW_IPS left TBC, never to be set to '*'. Still an open item in CLAUDE.md.
● **Guard:** SECURITY.md trip-wire: set FORWARDED_ALLOW_IPS to the ingress's addresses once confirmed.
● **Lesson:** Per-client rate limits behind a proxy need the proxy's addresses configured as trusted; until then, record that limits are shared and never trust forwarded headers from everyone.
● **Evidence:** gate report: Deploy-gate re-run on V0.7: "Until they are set, rate limits and recorded client addresses use the ingress address, so the sign-in limit is shared by all users." Also: SECURITY.md; commit messages (git log).

### CQ-094 Enforce an append-only audit table in a migration, and know what the database role can bypass

● **Rule:** none · **Raised by:** the author at the fusion (V0.2, ADR-005's unenforced rule); engineering-reviewer (V0.7 round 3 nit, the postgres role unrecorded); security-reviewer (V0.7 round 4 minor, the superuser's reach) · **Severity:** minor (open below the blocking bar) · **Status:** open · **Certainty:** fact
● **Releases:** V0.2 (trigger added), V0.7 (role recorded; superuser reach left open)
● **Applies to:** PostgreSQL-backed apps with audit trails
● **Symptom:** ADR-005's insert-only audit log was never enforced by a migration, and the app's database user can change any table. On the App Store the add-on connects as postgres. The V0.7 round 4 security gate showed a superuser can delete audit rows past the trigger (SET session_replication_role = replica) and run programs on the database host (COPY ... FROM PROGRAM) on PostgreSQL 16, while SECURITY.md names only a wider reach.
● **Root cause:** Migrations run with the application's own role, which needs schema rights; the platform's role privileges are unknown.
● **Fix:** Migration 0017 refuses UPDATE, DELETE and TRUNCATE on audit.audit_log with a statement-level trigger; python -m app.cli.verify_audit recomputes the chain; SECURITY.md records the postgres role. Proposed and not done: state the three consequences, link the unencrypted-connection row, and log rolsuper as a boolean at start.
● **Guard:** Smoke rung checks the audit log refuses an UPDATE; SECURITY.md trip-wire for a second, insert-only role.
● **Lesson:** Enforce append-only audit storage in the schema, then establish whether the runtime role can disable that enforcement, and log the role's privilege level at start.
● **Evidence:** CHANGELOG.md: "Migration 0017 refuses every UPDATE, DELETE and TRUNCATE on the audit log, the insert-only rule ADR-005 recorded but no migration enforced." Also: gate report: Security gate, V0.7 round 4; SECURITY.md; docs/AUDIT-LOG.md, V0.7 row.

### CQ-095 A single-page-app fallback answering 200 for every path can read as a scanner finding

● **Rule:** `none (ZAP active rule 90034 named as a possible false positive)` · **Raised by:** deploy-gate · **Severity:** minor (advisory) · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.8 (noted by the deploy gate; no change)
● **Applies to:** any server that serves a single-page app with a catch-all
● **Symptom:** With a browser Accept header, any unknown path returns 200 with index.html (508 bytes), including /latest/meta-data/ with Host 169.254.169.254, /.git/index and /WEB-INF/web.xml, so a ZAP-style scanner could report a false High (Cloud Metadata Potentially Exposed), and High findings block release.
● **Root cause:** The dashboard's catch-all route in factory.py's _mount_dashboard serves index.html for every path the API does not match.
● **Fix:** No change. The deploy gate advised uploading, reading the DAST report, and limiting the fallback to the dashboard's own routes if the finding fired; V0.8, V0.9 and V0.11 then passed all 11 stages, DAST included, so it did not fire (inference).
● **Guard:** none recorded
● **Lesson:** Limit an SPA's catch-all to the client's own route shapes, or at least know which scanner rules it can trip, before a scan gate blocks a release on a false positive.
● **Evidence:** gate report: Deploy-gate on V0.8: "with a browser 'Accept' header, any unknown path returns 200 with 'index.html' (508 bytes). That includes '/latest/meta-data/' with 'Host: 169.254.169.254', '/.git/index' and '/WEB-INF/web.xml'." Also: docs/AUDIT-LOG.md, V0.8 row.

### CQ-096 Moving a credential out of Authorization loses intermediaries' default protections

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.9 (raised and recorded)
● **Applies to:** any API carrying credentials in a custom header
● **Symptom:** ADR-013 and SECURITY.md did not say what leaving Authorization gives up: a shared cache does not store a response to a request carrying Authorization by default (RFC 9111 section 3.5), and proxies and log tools commonly redact that header; neither holds for a custom header. Whether the gateway logs X-Holly-Token cannot be checked from the app.
● **Root cause:** The trade-offs of a custom credential header were not analysed when the header moved.
● **Fix:** A SECURITY.md row and an ADR-013 consequence; Cache-Control: no-store on every response is the only shared-cache protection; ingress reliance item: pass X-Holly-Token through unchanged and do not log it (TBC, re-verify).
● **Guard:** no-store pinned by tests (removing it turns 15 tests red); SECURITY.md trip-wires: never relax no-store on an API response, and ask the platform team whether the gateway logs request headers before holding higher-classification data.
● **Lesson:** A credential in a custom header gets none of the cache and logging care given to Authorization; set no-store on authenticated responses and confirm intermediaries do not log the header.
● **Evidence:** gate report: Security gate on V0.9 round 1: "ADR-013 does not record what leaving 'Authorization' gives up." Also: SECURITY.md.

### CQ-097 Secret-scan regular expressions slow sharply on crafted input

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** not graded in the sources · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.9 (raised, accepted)
● **Applies to:** any regex-based secret scanner
● **Symptom:** The old rule took 9.6 s on 40,000 repetitions of -eyJ; the new JWT rule took 6.2 s on eyJ repeated and 10.4 s on -eyJ. On a 900 KB eyJ file the content net stopped with 'could not scan: ... ETIMEDOUT' and exit 1.
● **Root cause:** Backtracking in patterns with repeated character classes over adversarial input (inference).
● **Fix:** None: the content net fails closed on a timeout, so a slow input refuses the package. Whether Claude Code lets a write through when the pre-write hook times out was not checked.
● **Guard:** scan-package.mjs refuses on any failure to scan.
● **Lesson:** Test secret-scanning patterns against adversarial repetition, and make sure the scanner refuses, not passes, when it times out.
● **Evidence:** gate report: Security gate on V0.9 round 3: "On a 900 KB 'eyJ' file, 'scan-package.mjs' stopped with 'could not scan: ... ETIMEDOUT' and exit 1, so a slow input refuses the package rather than slipping past it."

### CQ-098 A bounded limiter's eviction can free a locked key

● **Rule:** none · **Raised by:** security-reviewer (round 3), engineering-reviewer (rounds 4 and 5) · **Severity:** nit (round 3), minor (rounds 4 and 5) · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.2 (raised in rounds 3 to 5; partly fixed, residual accepted)
● **Applies to:** any in-process rate limiter
● **Symptom:** Each limiter keeps 10,000 keys and drops the stalest, so checking 10,000 other usernames (about 13 minutes) frees a locked username for more guesses. Round 4: the limiter remembered keys it held no hits for, so sign-ins refused for want of a check slot pushed out a locked count in seconds. Round 5: the test never filled the limiter, so one guard went unpinned.
● **Root cause:** LRU eviction does not distinguish locked from unlocked keys, and wait_time kept a place for every key it was asked about.
● **Fix:** wait_time answers for an unknown key without remembering it and forgets a key whose hits have expired (46c48fc); the test fills the limiter with the locked key as its stalest (e55312b). The 13-minute flood is accepted, since evicting only unlocked keys would add a scan a flood could turn against the coarse limit.
● **Guard:** Tests red when either guard is removed; SECURITY.md trip-wire: evict only keys under their limit, with a bounded scan, before trusting forwarded addresses.
● **Lesson:** In a bounded in-memory rate limiter, only recorded hits should take a slot, and the eviction policy's effect on locked keys should be measured and recorded.
● **Evidence:** commit messages (git log): "pushed out a locked username's count in seconds rather than the 13" Also: SECURITY.md.

### CQ-099 Record what the app relies on the ingress for: TLS, host routing, request smuggling, slow clients

● **Rule:** none · **Raised by:** review testing at the scaffold gates (inference: security-reviewer; SECURITY.md says only 'in review testing') · **Severity:** minor · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.1 (recorded in c0a25dc), extended in V0.9
● **Applies to:** any app behind a managed ingress; uvicorn and h11 here
● **Symptom:** Review testing found the app server held idle and trickling connections for 20 seconds and longer, and h11 follows Transfer-Encoding and keeps a connection open when both Content-Length and Transfer-Encoding are sent.
● **Root cause:** Plain HTTP behind a platform ingress, with uvicorn and h11 defaults and no slow-client timeout of its own.
● **Fix:** SECURITY.md lists what is relied on from the ingress: TLS termination, host routing, Content-Length and Transfer-Encoding normalisation, slow-client timeouts and, from V0.9, X-Holly-Token pass-through; bodies are capped in size.
● **Guard:** SECURITY.md 'Relied on from the platform ingress' list.
● **Lesson:** Write down each protection delegated to the platform's edge, with the observed behaviour that makes it necessary, so a change of ingress is checked against the list.
● **Evidence:** SECURITY.md: "The app server held idle and trickling connections for 20 seconds and longer in review testing."

### CQ-100 A pattern-based secret scan has blind spots that must be recorded with trip-wires

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.1 (recorded), V0.10 (the scanner's header narrowed to a split or wrapped JWT)
● **Applies to:** any secret-scanning net
● **Symptom:** The upload content net cannot see a secret in a shape the hook has no rule for, a secret encoded inside text (base64, data: URI), or one inside an allowlisted binary; a binary from a Windows toolchain stores strings as UTF-16LE, which the run scan of allowlisted binaries would not read.
● **Root cause:** Detection is by regular expression over readable UTF-8 text.
● **Fix:** Blind spots recorded in SECURITY.md (85962f4); the UTF-16LE trip-wire added at the security gate's advice (6c84de5); any change to scripts/upload-binaries.txt treated as a security change. In V0.10 scripts/scan-package.mjs's header lists a split or wrapped JWT, not every JWT, among the shapes it cannot see.
● **Guard:** scripts/test-package-nets.sh pins every case the net covers; SECURITY.md trip-wires.
● **Lesson:** Document what a secret scanner cannot see and attach a trip-wire to each gap, such as scanning the UTF-16LE view before allowlisting a Windows binary.
● **Evidence:** SECURITY.md: "It cannot see a secret in a shape the hook has no rule for, such as an unquoted GitHub token" Also: docs/AUDIT-LOG.md, V0.10 row.

### CQ-101 Zip readers disagree on a member's name through the Unicode Path extra field

● **Rule:** none · **Raised by:** security-reviewer; engineering-reviewer (record correction) · **Severity:** minor · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.3 (raised, accepted; record corrected)
● **Applies to:** any zip inspection net
● **Symptom:** A member can carry a second name in a Unicode Path extra field (0x7075) that Info-ZIP and Python use and Java and Go ignore; the record first also named 0x6375, which engineering found is a comment field.
● **Root cause:** The name net judges names as Info-ZIP reads them.
● **Fix:** Accepted for zips built by git archive, which never writes the field; SECURITY.md names 0x7075 only (d429bff, 4827acb).
● **Guard:** SECURITY.md trip-wire: refuse members that carry a 0x7075 extra field before the net judges any zip it did not build.
● **Lesson:** A name check over archives is only as good as its agreement with the extractor that will be used; record which zip features it assumes absent.
● **Evidence:** SECURITY.md: "Refuse members that carry a 0x7075 extra field before the net judges any zip it did not build." Also: commit messages (git log).

### CQ-102 A baseline record accepts a dangling or unreachable commit

● **Rule:** none · **Raised by:** security-reviewer (nit) · **Severity:** nit · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.6 (raised, accepted and documented)
● **Applies to:** any git-based release gate
● **Symptom:** cat-file -e accepts a dangling or unreachable commit as the upload baseline.
● **Root cause:** The check tests the commit's existence, not its reachability from the branch.
● **Fix:** Accepted; the check's header and the SECURITY.md row both say a dangling commit counts.
● **Guard:** none recorded
● **Lesson:** When a gate keys on a recorded commit, decide whether it must be reachable and say so; existence alone admits orphaned objects.
● **Evidence:** gate report: Security gate on 97d90be: "'cat-file -e' accepts a dangling or unreachable commit as the baseline; I confirmed this in the clone." Also: docs/AUDIT-LOG.md, V0.6 row.

### CQ-103 An unencrypted database connection from a platform add-on is a recorded position

● **Rule:** none · **Raised by:** app-owner (console facts), security-reviewer (nit on the wording) · **Severity:** nit · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.7 (recorded; wording corrected by a gate nit)
● **Applies to:** apps using managed database add-ons
● **Symptom:** The POSTGRESQL add-on's DATABASE_URL carries sslmode=disable, so queries and results cross the platform network in clear; the first SECURITY.md wording overstated the password's exposure.
● **Root cause:** Platform add-on configuration; the authentication method is TBC.
● **Fix:** Holly honours the URL; the position is recorded with a trip-wire and the wording corrected.
● **Guard:** SECURITY.md trip-wire: revisit if the add-on offers TLS or data above the cleared markings is stored.
● **Lesson:** Record transport security you inherit from a platform, with what exactly is exposed, rather than assuming encryption.
● **Evidence:** SECURITY.md: "The POSTGRESQL add-on's 'DATABASE_URL' carries 'sslmode=disable' (the console, 19 October 2026)" Also: docs/AUDIT-LOG.md, V0.7 row.

### CQ-104 State what a stolen admin session can do

● **Rule:** none · **Raised by:** security-reviewer (minor) · **Severity:** minor · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.10 (raised and recorded)
● **Applies to:** any app with in-app user management
● **Symptom:** Any admin can reset another admin's password, create a lasting admin and demote every other admin; the record did not say so.
● **Root cause:** A flat admin trust model with in-app account management.
● **Fix:** SECURITY.md states the reach of an admin session; no account is ever deleted; new usernames restricted so no name passes for another.
● **Guard:** SECURITY.md trip-wires on one-time links, deletion and lower roles.
● **Lesson:** When adding account administration, write down the blast radius of a compromised admin session and the trip-wires that would narrow it.
● **Evidence:** docs/AUDIT-LOG.md, V0.10 row: "what a stolen admin session can do unstated" Also: SECURITY.md.

### CQ-105 An integration bot's memberships decide what every user can read

● **Rule:** none · **Raised by:** security-reviewer (minor); engineering-reviewer (doc drift: check the bot's memberships before the first deploy) · **Severity:** minor · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.12 (raised in the Comms work's first gate round, then labelled V0.11; recorded in 0a60d93)
● **Applies to:** any app ingesting from chat or collaboration tools through a bot
● **Symptom:** Holly follows every Mattermost channel its bot is in, at once; a private channel the bot is added to by mistake becomes readable to every signed-in user and reaches the assistant as context.
● **Root cause:** The app cannot tell a mistaken channel membership from an intended one.
● **Fix:** New channels are flagged until reviewed; any user can switch one off (audited, stopping the pull and the assistant use at once); the Mattermost admin removes the bot; the gap and remedy are recorded.
● **Guard:** SECURITY.md row with trip-wires; the operator manual asks for the bot's memberships to be checked before the first deploy.
● **Lesson:** When an integration account's access defines what the app ingests, treat its memberships as an access-control list: flag new sources, give a fast off switch, and record the residual risk.
● **Evidence:** session summaries: "a SECURITY.md row on the bot being added to a private channel by mistake (remedy or accepted gap);" Also: SECURITY.md; gate report: Security gate on V0.11 round 1.

### CQ-106 Write routes open to every signed-in user are a recorded risk with a trip-wire

● **Rule:** none · **Raised by:** recorded with the imported design (gate not named) · **Severity:** not graded in the sources · **Status:** accepted · **Certainty:** inference
● **Releases:** V0.2 (recorded at the fusion), V0.12 (extended to the shared channel follow list)
● **Applies to:** any internal tool with shared write access
● **Symptom:** Inherited from the imported dashboard: any analyst can run a UDL ingest, upload or delete a procedure, edit or delete any shift note or timer, and, from V0.12, change the shared channel follow list; only the audit log is role-gated.
● **Root cause:** Authorisation designed for one trusted operations team; ownership checks never built.
● **Fix:** Every such write is audited with user and address; the position and trip-wire recorded rather than left silent.
● **Guard:** SECURITY.md trip-wire: add role and ownership checks before anyone outside the operations team gets an account.
● **Lesson:** If authorisation is deliberately flat, record it explicitly with the condition that ends the assumption.
● **Evidence:** SECURITY.md: "Any analyst can run a UDL ingest, upload or delete a procedure, edit or delete any shift note or timer"

### CQ-107 Tokens in browser storage require a strict script policy

● **Rule:** none · **Raised by:** recorded with the imported design (gate not named) · **Severity:** not graded in the sources · **Status:** accepted · **Certainty:** inference
● **Releases:** V0.2 (recorded)
● **Applies to:** SPAs storing tokens client-side
● **Symptom:** Access and refresh tokens live in the browser's localStorage, readable by any script that runs in the page.
● **Root cause:** Bearer tokens held client-side rather than in an HttpOnly cookie.
● **Fix:** Dashboard CSP is script-src 'self' with no inline script or eval, React escapes rendered values, links only http and https, 30-minute access tokens and revocable refresh tokens.
● **Guard:** SECURITY.md trip-wire: move the refresh token to an HttpOnly, Secure, SameSite=Strict cookie before any third-party script or CSP loosening.
● **Lesson:** If tokens live in localStorage, hold the script policy strict and record the move to an HttpOnly cookie as the trigger for any loosening.
● **Evidence:** SECURITY.md: "Move the refresh token to an 'HttpOnly', 'Secure', 'SameSite=Strict' cookie before any third-party script is added or the policy is loosened in any way."

### CQ-108 A public status endpoint may reveal a secret's length, so only high-entropy secrets may appear there

● **Rule:** none · **Raised by:** security-reviewer (inference from the scaffold round's recorded positions) · **Severity:** not graded in the sources · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.1 (recorded)
● **Applies to:** any app with a public status page
● **Symptom:** /status and /api/v1/health/detailed are unauthenticated; /status reports each input in CONFIG_INPUTS as set or not and its length, and the detailed health read reports whether UDL credentials are configured.
● **Root cause:** Diagnosability without access leaks the length of each configured value.
● **Fix:** Never a value or a field derived from one; both sit behind the coarse rate limit; positions recorded at the scaffold gate round.
● **Guard:** SECURITY.md trip-wire on CONFIG_INPUTS.
● **Lesson:** Unauthenticated diagnostics should report presence, not size, of secrets; where length is shown, restrict it to high-entropy values.
● **Evidence:** SECURITY.md: "A secret joins 'CONFIG_INPUTS' only if it is high-entropy, because its length becomes public."

### CQ-109 An audit hash chain must hash exactly what it stores, and needs an anchor outside the database

● **Rule:** none · **Raised by:** security-reviewer (anchor, deferred in round 1); the author's review of imported code (hashing) · **Severity:** not graded in the sources · **Status:** deferred · **Certainty:** fact
● **Releases:** V0.2 (hashing fixed for new rows; anchor deferred)
● **Applies to:** any tamper-evident audit log
● **Symptom:** The imported dashboard hashed a timestamp it never stored, so its rows cannot be recomputed and a chain starting with them reports its first row as broken. Someone able to disable the append-only trigger and recompute every later hash could rewrite history undetected, since the newest entry_hash is never published outside the database.
● **Root cause:** Hash input differed from the persisted row; no external anchor.
● **Fix:** Every row Holly writes hashes the stored timestamp and stored detail, with a verifier (55ab9f1); earlier rows recorded as unverifiable; the anchor deferred with a trip-wire (ad5b332).
● **Guard:** python -m app.cli.verify_audit; SECURITY.md trip-wires: record the last pre-V0.2 hash out of band, and publish the newest entry_hash outside the database on a schedule before the log is relied on as evidence.
● **Lesson:** Hash the persisted bytes, not in-memory values, and anchor the chain's head somewhere the database owner cannot rewrite.
● **Evidence:** CHANGELOG.md: "Rows the Daily Operations Dashboard wrote hashed a timestamp it never stored and cannot be verified." Also: commit messages (git log).

### CQ-110 Reads and exports of sensitive records are not audited

● **Rule:** none · **Raised by:** security-reviewer (round 1, deferred) · **Severity:** not graded in the sources · **Status:** deferred · **Certainty:** fact
● **Releases:** V0.2 (deferred)
● **Applies to:** any app handling controlled data
● **Symptom:** Procedure downloads, shift-log exports, audit-log reads and who pressed Pull from UDL leave no audit row.
● **Root cause:** The audit chain records sign-ins, writes, ingests and assistant use only.
● **Fix:** Deferred with a trip-wire (ad5b332).
● **Guard:** SECURITY.md trip-wire: audit downloads and exports before any record is held under a classification that requires access records.
● **Lesson:** Decide early whether reads need audit records for the data's classification, and record the trigger if they are deferred.
● **Evidence:** commit messages (git log): "SECURITY.md records the deferred findings with their trip-wires: the" Also: SECURITY.md.

## 2.3 Server correctness and concurrency


### CQ-111 Read-modify-write on an unlocked row lets a concurrent request undo a revoking change

● **Rule:** none · **Raised by:** security-reviewer (MAJOR, round 1) and engineering-reviewer (MAJOR, round 1), each reproducing it on PostgreSQL · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 1 on 2a36aa1, fixed round 2 on 5627eb7, committed as af13871)
● **Applies to:** SQLAlchemy and PostgreSQL; any ORM doing read-modify-write
● **Symptom:** A session holder looping POST /auth/password while an admin reset the account survived the reset in 8 of 8 trials on PostgreSQL. The in-flight change wrote its own hash, the same raised token_version and a cleared must_change_password after the reset's, so the stolen session kept working and the admin's temporary password stopped signing in. Both gates failed round 1 on it.
● **Root cause:** The user row was read without a lock at the start of the request; token_version += 1 was computed in Python and written back as an absolute value after one or two bcrypt rounds, so two overlapping writers wrote the same version and the later one's columns won. The unit tests ran on a session fake (FakeSession) that cannot show a race.
● **Fix:** Round 2 added lock_users in src/app/services/accounts.py: SELECT ... ORDER BY id FOR NO KEY UPDATE with populate_existing, used by change_password (routes/auth.py) and by reset_password and update_user (through _locked_target in routes/users.py); create_admin takes the same FOR NO KEY UPDATE lock on its own row (with_for_update(key_share=True)). change_password re-reads the account under the lock and refuses with 401, audited stale_token or inactive_user, if its session ended while it ran. NO KEY UPDATE lets foreign-key KEY SHARE locks from note and timer inserts proceed; rows are locked in id order in one statement to avoid deadlock. SECURITY.md, the security overview and the operator manual were brought in line.
● **Guard:** A PostgreSQL race rung in scripts/smoke-container.sh races a looping own change against a reset three times; it failed on the round 1 code and passes on round 2's. Unit tests pin the lock clause, NO KEY UPDATE, populate_existing and id order (each mutant killed by the round 2 engineering gate). Round 2 security probe: the reset race 0 of 8 survived; in the round 2 engineering probe, with populate_existing removed, the same probe lost 6 of 6.
● **Lesson:** Any update that depends on a value read earlier in the request (a counter, version stamp or flag) must re-read the row under a row lock, or use compare-and-set or an in-SQL increment, before deciding. Prove it with a race test against the real database, because an in-memory session fake cannot show a lost update.
● **Evidence:** docs/AUDIT-LOG.md, V0.10 row: "security-reviewer FAIL on one MAJOR: a session holding the password, looping 'POST /auth/password' while an admin reset the account, survived the reset in 8 of 8 trials on PostgreSQL" Also: gate report: Security gate on V0.10 round 1; gate report: Engineering gate on V0.10 round 2; src/app/cli/create_admin.py at HEAD.

### CQ-112 Holding row locks across slow outbound network calls

● **Rule:** none · **Raised by:** engineering-reviewer (MAJOR, first Comms review, labelled V0.11 round 1 in the agent index) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review on c9e3acc, fixed in 0a60d93, confirmed by the V0.12 gates)
● **Applies to:** any stack with a relational database and outbound HTTP; SQLAlchemy and PostgreSQL
● **Symptom:** The Mattermost cycle's channel sweep wrote every channel row (a new last_seen_at) and held those row locks until the commit after the pull's HTTP calls. With 3 s per channel, PATCH /api/v1/mattermost/channels/{id} took 11.15 s of a 12.1 s cycle, waiting on Lock / transactionid behind a session idle in transaction. With Mattermost slow the wait grows to the channel count times the 30 s client timeout, each waiter holding a pool connection shared with the background loops.
● **Root cause:** One transaction spanned the sweep's database writes and the network-bound per-channel pull.
● **Fix:** The sweep is committed on its own before any post is requested, so no channel row stays locked during the pull; one mattermost.ingest audit row carrying the sweep's counts and the pull's follows in a second commit (src/app/services/mattermost_ingest.py). In the gate's probe copy a two-line commit before the pull took the PATCH to 0.065 s.
● **Guard:** tests/test_mattermost_channels.py test_a_cycle_sweeps_then_pulls_the_followed_open_channels_and_audits_both asserts two commits, the first before any posts request (assertion added in 0a60d93); the V0.12 engineering gate killed the commit-before-the-pull mutant.
● **Lesson:** Commit or roll back before any slow external call, so no row lock or open transaction is held while waiting on the network, and assert the commit order in a test.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "The cycle locks the channel rows for the whole pull, so follow switches hang" Also: CHANGELOG.md; src/app/services/mattermost_ingest.py at 0a60d93.

### CQ-113 Unchecked type of an upstream value crashes a background cycle while its status stays green

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer (MAJOR each, first Comms review) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review on c9e3acc, fixed in 0a60d93, confirmed by the V0.12 gates)
● **Applies to:** background jobs consuming third-party JSON; any stack
● **Symptom:** A Mattermost channel record whose type arrived as a JSON array or object raised TypeError: unhashable type at `kind not in PULLED_TYPES` (and at the direct or group message check). sweep_channels caught only MattermostClientError, so every cycle aborted: no sweep, no channel pulled, POST /sweep answered 500, while SWEEP_STATE.ok stayed true and the page showed a fresh, healthy sweep. Deeply nested JSON reached the same state through RecursionError.
● **Root cause:** Raw upstream values were used in hash lookups without a type check, the job boundary caught one exception class only, and the status time was set before the work. The module's stated promise to skip one malformed record had no test with a non-string type.
● **Fix:** isinstance(kind, str) before both lookups (_kind); a body nested too deep to decode is a client error (api_client.py catches ValueError and RecursionError); any other failure fails the sweep with a fixed message in Holly's words (UNEXPECTED), rolls back and logs the traceback (logger.exception).
● **Guard:** Tests for list and dict types and a sweep with one bad record among good ones; the V0.12 engineering gate killed the non-string type, RecursionError and rollback mutants, and the V0.12 security gate's rollback mutant (M5) turned a test red.
● **Lesson:** Check the type of every untrusted value before using it as a key, catch every failure at a background job's boundary, and set a health flag only from the job's outcome, so one bad record is skipped and a failed cycle never reads as healthy.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "One malformed channel record halts every Mattermost pull" Also: gate report: Security gate on V0.11 round 1.

### CQ-114 A start-up wait for the database must retry only transient failures

● **Rule:** none · **Raised by:** App Store DAST job log (advice, relayed by the app owner); engineering-reviewer (MAJOR, V0.8 round 1); security-reviewer (nit, V0.8 round 1) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (failed DAST with no_report; the scan's job log advises retrying the database for about a minute, and V0.7 had no wait), V0.8 (wait added; MAJOR raised round 1, fixed round 2; V0.8 then passed all 11 stages)
● **Applies to:** any service that waits for a database at start; Python, SQLAlchemy and asyncpg
● **Symptom:** V0.7's upload failed the DAST stage on no_report (nothing answered on 8080 within 300 seconds; Holly refused to start without APP_SECRET_KEY and database settings), and V0.7 made no attempt to wait for a database at start, where the scan's job log advises retrying it for about a minute. The wait V0.8 added then retried a wrong password (28P01), a missing database (3D000) or a missing role for about 62 s, about 30 failed logins, and stopped with 'the database did not answer within 60 seconds (last error: DBAPIError)', naming no cause where V0.7 had named the refusal; operator manual sections 04 and 10 sent operators to check reachability.
● **Root cause:** The retry set (OSError, SQLAlchemyError) included SQLAlchemy's DBAPIError, which wraps asyncpg's authentication and catalogue refusals; raising with `from None` and a message naming only the exception type dropped the real cause.
● **Fix:** migrate.wait_for_database runs at every start with a 5-second connect timeout and retries for about a minute only OSError, SQLSTATE 57P03 (starting up) and class 08 (connection exceptions). Any other refusal stops the start at once, naming its SQLSTATE and the driver's error class, never its text. The time-out message says 'within about 60 seconds' and the manual sections 'about a minute'.
● **Guard:** tests/test_migrations.py: a refusal such as 28P01 stops the start at once and names it, 57P03 is retried, each red with the filter removed. Live through gunicorn: a wrong password stopped in 1 second naming 28P01, an unresolvable host retried for 61 s, a database started 15 s late was waited for and migrated. The smoke rung starts with and without a database. Left unpinned and open in the V0.8 row: the 60-second deadline and the class-08 boundary.
● **Lesson:** Classify connection errors before retrying: retry only those that can clear (unreachable, starting, dropped) and fail fast, naming the cause, on authentication, permission or missing-object errors.
● **Evidence:** docs/AUDIT-LOG.md, V0.8 row: "advises generating a throwaway signing key under that flag and retrying the database for about a minute" Also: gate report: Engineering gate on V0.8 DAST.

### CQ-115 Decide whether a one-time bootstrap applies before validating its inputs

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer (shared MAJOR, round 2) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised round 2 on 8ff2c44, fixed round 3)
● **Applies to:** any stack with first-run or seed logic driven by environment variables
● **Symptom:** With the first admin already present, removing only ADMIN_PASSWORD as every document advised stopped every later start ('ADMIN_PASSWORD is not set: set ADMIN_USERNAME and ADMIN_PASSWORD together, or neither'); a bad ADMIN_EMAIL left set did the same. The docs said the variables were ignored once an account existed, and the error's first remedy was to put the secret back.
● **Root cause:** The bootstrap refused half a pair before counting accounts, so its input checks ran on every start rather than only when it could create an admin.
● **Fix:** Round 3: src/app/admin_bootstrap.py counts app_user rows first under its advisory lock; once any exists it checks and uses no value and only logs the names still set (variables_still_set). The docs say to remove all three variables together.
● **Guard:** Mutant M01 (credentials checked before the count) killed in the round 3 engineering gate; tests/test_admin_bootstrap.py test_an_existing_account_leaves_everything_alone_whatever_is_still_set; the smoke rung starts normally with the password removed after the admin exists.
● **Lesson:** Put a run-once step's 'is it needed?' check first and make its input validation conditional on it, so the documented clean-up of its inputs can never stop later starts.
● **Evidence:** docs/AUDIT-LOG.md, V0.7 row: "the documented step of removing 'ADMIN_PASSWORD' after the first start stopped every later start, since half a pair was refused before the accounts were counted" Also: gate report: Engineering gate, V0.7 round 2; gate report: Engineering gate, V0.7 round 3.

### CQ-116 A failed optional AI step must keep the last good output, stay pending and never block the user's own content

● **Rule:** none · **Raised by:** engineering-reviewer (MAJOR, V0.2 round 1); the fusion work on the imported Daily Operations Dashboard code · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (imported-code fixes at fusion in 55ab9f1; engineering MAJOR round 1, fixed in a520e68)
● **Applies to:** any stack calling an LLM or other unreliable service, especially from background jobs
● **Symptom:** A failed event narrative regeneration replaced the narrative with 'Event summary could not be generated.', marked every publication as seen and so was never retried; with the daily token cap, a spent budget or an Anthropic 429 would wipe one good narrative per hourly cycle. In the imported code a failed re-polish also discarded a shift note's polished text, an analyst's own edit included, and a spent assistant limit refused the shift note itself.
● **Root cause:** The failure path wrote a placeholder over the stored result and advanced the 'seen' marker as if it had succeeded; an optional enrichment sat on the critical path of saving the user's note.
● **Fix:** A failed regeneration writes nothing: the earlier narrative stays, unseen publications keep the event stale and the next cycle retries; a stored failure row from the old code counts as stale. A failed re-polish keeps the earlier text, and a note is saved as written and can be re-polished later.
● **Guard:** The sources name no test; in the repository, tests/test_event_summary.py test_an_assistant_failure_writes_nothing_and_is_not_raised and tests/test_shift_log.py test_a_failed_repolish_keeps_the_note_as_it_was_and_records_the_error and test_a_failed_polish_still_stores_the_raw_note.
● **Lesson:** Treat an LLM or other optional enrichment as best effort: on failure write nothing, keep the last good result, leave the work marked pending so it is retried, and never let it block saving the user's own input.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "MAJOR: a failed event narrative replaced and hid the last good one and was never retried" Also: commit messages (git log); CHANGELOG.md.

### CQ-117 CPU-bound password hashing on the event loop lets one client stall a single-worker server

● **Rule:** none · **Raised by:** security-reviewer (MAJOR, round 1) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised round 1, fixed in db957da)
● **Applies to:** Python asyncio (FastAPI, Starlette); any single-threaded event-loop server
● **Symptom:** bcrypt ran on the asyncio event loop, and the dummy check for unknown usernames made every attempt pay for it, so one client could stall and then restart the only gunicorn worker with sign-ins; a worker restart also resets every in-process limit.
● **Root cause:** Blocking CPU work inside async handlers, in a deployment with one worker that also runs the background loops and holds the in-memory limits.
● **Fix:** Sign-in counts every attempt per client address (30 a minute) before anything else, runs bcrypt on worker threads with at most 4 checks at once, and answers 503 with Retry-After instead of queueing beyond that.
● **Guard:** tests/test_auth.py TestSignInUnderLoad (test_an_unknown_username_still_costs_a_password_check, test_attempts_are_limited_per_address_before_anything_is_checked, test_a_sign_in_beyond_the_concurrent_checks_is_refused_at_once, test_password_checks_leave_the_event_loop_free); the commit says each was shown to fail with its protection removed.
● **Lesson:** Run CPU-heavy work such as password hashing off the event loop in a bounded pool, rate-limit before the expensive step, and shed load with a 503 rather than queueing.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "MAJOR: one client could stall and restart the only worker with sign-ins, as bcrypt ran on the event loop" Also: commit messages (git log); SECURITY.md.

### CQ-118 Re-raising a shared exception instance leaks memory through its traceback

● **Rule:** none · **Raised by:** engineering-reviewer (MAJOR, round 1) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised round 1, fixed in db957da)
● **Applies to:** Python
● **Symptom:** Shared 401 exceptions were module-level instances (src/app/dependencies.py, src/app/api/v1/routes/auth.py); raising one again appends each request's frames to its traceback, so memory grew with every refused request and every rejected request's traceback stayed alive.
● **Root cause:** Exception objects created once at import and re-raised per request.
● **Fix:** Each refusal builds a new exception.
● **Guard:** tests/test_auth.py test_each_refusal_is_a_new_exception_whose_traceback_does_not_grow and test_every_refusal_factory_builds_a_fresh_401; the commit says the fresh-refusal test was shown to fail with the protection removed.
● **Lesson:** Never raise a module-level exception instance; construct a new exception for each raise (a small factory function is fine), because each raise attaches its frames to the instance.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "shared 401 exceptions kept every rejected request's traceback alive" Also: commit messages (git log); CHANGELOG.md.

### CQ-119 Prove each lock with a test that fails without it, and keep lock keys distinct

● **Rule:** none · **Raised by:** engineering-reviewer (MAJOR in V0.2 round 1; nit in V0.7 round 1) · **Severity:** MAJOR (V0.2); nit (V0.7) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (migration lock unproven, MAJOR round 1, fixed in e0d7f34); V0.7 (bootstrap lock key distinctness unpinned, nit round 1, fixed round 2)
● **Applies to:** PostgreSQL advisory locks; any multi-process or distributed locking
● **Symptom:** V0.2: nothing would fail if the migration advisory lock were deleted, since the unit tests run migrations offline and one container starts the same with or without it. V0.7: the bootstrap's comment said its advisory lock key differs from the migrations' key, but setting it equal to MIGRATION_ADVISORY_LOCK_KEY survived as a mutant; one container's bootstrap would then wait on another's migration.
● **Root cause:** Concurrency controls were asserted in design notes and comments, not exercised by a test that a second session or process would show.
● **Fix:** V0.2: the smoke rung holds the packaged lock key from a psql session, starts Holly and requires it to report its migrations applied only after the session frees it; a variant image without the lock was shown to fail. V0.7: a test asserts the bootstrap, migration and audit-chain keys differ.
● **Guard:** scripts/smoke-container.sh migration-lock check; tests/test_admin_bootstrap.py test_the_bootstrap_lock_is_not_the_migrations_or_the_audit_chain_s (mutants R19 and N12 killed in the V0.7 round 2 engineering gate).
● **Lesson:** A lock that no test can see removed is not a control: hold the lock from outside in an integration test and require the code to wait, and assert that independent advisory lock keys never collide.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "nothing proved the migration advisory lock" Also: commit messages (git log); gate report: Engineering gate on V0.7.

### CQ-120 Check every external value for storability before a batch write, at every boundary

● **Rule:** none · **Raised by:** security-reviewer (V0.2 rounds 1 to 3, MINOR in rounds 2 and 3; V0.12 first Comms review, MINOR); engineering-reviewer (V0.2 round 4, minor) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (UDL records rounds 1 to 3, model reply round 3, request text round 4, all fixed); V0.12 (recurred in the Mattermost post ingest, fixed in 0a60d93)
● **Applies to:** PostgreSQL text and JSON columns; any batch ingest pipeline
● **Symptom:** One UDL record its table could not store (text over its column length, a wrong type, a NUL or lone surrogate, NaN or infinity in the raw JSON, Infinity for an integer, float overflow, a time leaving the calendar, a non-object element) failed the whole multi-row upsert every cycle while it stayed in the pull window. A model reply holding the JSON escape for NUL passed validation and failed the store after the call, stalling background evaluation at that notice; a shift note holding a NUL went to the assistant before its write failed with a 500. In V0.12 a Mattermost post holding NUL failed the batch insert and rolled back the whole cycle, sweep included; the high-water mark never moved, so every later cycle stalled at the same post while the page said ok.
● **Root cause:** No per-row check against column types and PostgreSQL's text rules before a multi-row write; once a rule existed it was applied one boundary at a time, so each new source (model output, request text, a new ingest) repeated the gap.
● **Fix:** Each mapped row is checked against its table's types and lengths and one shared rule (src/app/db/storable.py); a bad record is skipped, counted and logged by column, never by value. call_claude refuses a reply holding a NUL or lone surrogate and parse_evaluation refuses such decoded fields; StorableText refuses such request text with 422 before any query, call or write. V0.12 skips and counts posts, author names or channel names PostgreSQL cannot store, or whose raw body fails json_problem.
● **Guard:** tests/test_udl_ingest.py, tests/test_request_text.py and the assistant tests, each red when its check is mutated; the V0.12 gates killed the json_problem-on-posts mutant (security M6, engineering battery).
● **Lesson:** Validate every inbound value (upstream records, model output, request text) against what the database can store before a batch write, skip and count the bad row, and route every new ingest through the same shared rule so one poison record cannot stall a pipeline.
● **Evidence:** commit messages (git log): "The security gate found that one malformed UDL record failed the whole" Also: docs/AUDIT-LOG.md, V0.2 row; gate report: Security gate on V0.11 round 1.

### CQ-121 Fail closed on any failure once an irreversible external call may have been made

● **Rule:** none · **Raised by:** the documentation pass (1a59034); security-reviewer (MINOR, round 2) and engineering-reviewer (round 2, grade not recorded) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (a gap found by the documentation pass, fixed in 1a59034 before round 2; raised by both gates in round 2 on ad5b332, fixed in 62e5dc5)
● **Applies to:** background jobs calling external services; any stack
● **Symptom:** With a database that answers reads but refuses writes (a full disk or a standby), each background evaluation and event narrative failed when its result was stored, after the call to the assistant: the cycle logged, moved on and sent the next, up to 20 of each an hour, with no audit row. The documentation pass had already found that a narrative's publications reached Anthropic before its audit row, and a failed row or commit only rolled back and moved on to the next event.
● **Root cause:** The fail-closed claim held only when the audit write itself failed, not for every write after the external call.
● **Fix:** Any failure once the assistant may have been called stops the phase: storing or auditing an evaluation, and generating, auditing or committing a narrative; a narrative's history read, which comes before any call, still lets the next event run. Accepted in SECURITY.md: an on-demand evaluation that cannot be stored goes unaudited, with a trip-wire to commit an audit row before the call.
● **Guard:** The sources name no test for 62e5dc5 beyond the marking-order test; in the repository, tests/test_background_refresh.py test_each_is_evaluated_in_turn_and_audited_until_a_failure_stops_the_phase and test_a_failure_once_the_publications_may_have_been_sent_stops_the_cycle. The docs were restated to match the code (9df87b9).
● **Lesson:** After an irreversible external action (a disclosure, a payment, a billable call), treat any later failure to record it as a reason to stop the batch, not to carry on to the next item.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "with a database that refused writes, both background phases kept sending with no audit rows" Also: commit messages (git log); SECURITY.md.

### CQ-122 Reserve a shared budget before the call, and settle against the same period

● **Rule:** none · **Raised by:** security-reviewer (round 1, check-then-charge); the reviewer of the midnight defect is not named · **Severity:** minor (inference: not among round 1's named MAJORs) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (check-then-charge raised round 1, fixed in eae7e54; the midnight defect fixed in a4e8d55, in the round 2 fixes)
● **Applies to:** any stack metering LLM or API spend
● **Symptom:** The daily assistant token cap was checked before and charged after each call, so concurrent calls all passed the same check: with a 1,500-token cap, 10 concurrent calls spent 10,000. The first fix's reserve then read the clock a second time for the day it returned, so a call made across midnight UTC settled against the new day and could drive the count below zero.
● **Root cause:** A time-of-check to time-of-use race on a shared budget, then two clock reads for one logical operation.
● **Fix:** Each call holds its output allowance and a generous input estimate (three characters a token) before it is sent and settles to real use afterwards; a failed call gives its hold back; reserve returns the day it counted against.
● **Guard:** a4e8d55: tests pin the three-characters-a-token estimate and the midnight case, each mutation turning one red. In the repository: tests/test_claude.py test_calls_made_together_cannot_overrun_the_cap, test_the_hold_counts_the_prompt_at_three_characters_a_token and test_a_call_that_crosses_midnight_counts_only_its_use_on_the_new_day.
● **Lesson:** Enforce a spend cap by reserving the worst-case cost atomically before the call and reconciling afterwards, and carry the period key from reservation to settlement instead of reading the clock twice.
● **Evidence:** commit messages (git log): "passed the same check: with a 1,500-token cap, 10 concurrent calls"

### CQ-123 Count a rate-limited attempt before its check, with no suspension point in between

● **Rule:** none · **Raised by:** security-reviewer (round 2); engineering-reviewer (minor, round 3) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised round 2, fixed in 169d432; the unpinned ordering raised round 3, fixed in df9b394)
● **Applies to:** Python asyncio; any async rate limiter
● **Symptom:** A username's sign-in attempts were recorded only after a failed check, so concurrent guesses all passed the last place under the limit: the security gate saw 16 wrong guesses checked against a limit of 10. After the fix, an inserted await between the limit test and the count kept the suite green while four passwords were checked for one place.
● **Root cause:** Check-then-record with an await between them lets concurrent coroutines share the last place; no test held the ordering.
● **Fix:** Each attempt counts against its username once it holds a check slot and before the check starts, with no await between the test and the count; an attempt refused for want of a slot does not count; the check runs shielded so a cancelled request cannot leak a slot.
● **Guard:** A test sends five attempts together at the last place with the check held: one is checked and four refused; the inserted await turns it red (tests/test_auth.py test_attempts_sent_together_at_the_last_place_get_one_check_between_them, beside test_each_check_counts_before_it_runs_so_concurrent_guesses_stop_at_the_limit). The four limits and the key bound are pinned as literals.
● **Lesson:** In async code make the limit test and the increment one step with no await between them, and pin it with a concurrent test that holds the slow step open.
● **Evidence:** commit messages (git log): "security gate saw 16 wrong guesses checked against a limit of 10. Each" Also: docs/AUDIT-LOG.md, V0.2 row.

### CQ-124 Bound every parse of untrusted model output and map its failures to the domain error

● **Rule:** none · **Raised by:** security-reviewer (round 1, the RecursionError); the reviewer of the brace bound is not named · **Severity:** minor (inference: not among round 1's named MAJORs) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (RecursionError raised round 1, fixed in eae7e54; the brace bound fixed in a4e8d55, in the round 2 fixes)
● **Applies to:** any stack parsing LLM or other untrusted output
● **Symptom:** A reply nested beyond Python's recursion limit raised RecursionError, not AssistantError: the route answered 500 and the background loop re-billed the notice every cycle. The tolerant JSON parser retried from every opening brace, so a crafted reply full of them held the event loop for over a second.
● **Root cause:** Recursive, unbounded tolerant JSON extraction over untrusted text, raising an exception type the callers did not handle.
● **Fix:** Deep nesting is an assistant error raised at once; the parser tries at most the first 20 opening braces.
● **Guard:** Tests pin the 20-brace bound, each mutation turning one red; in the repository, tests/test_claude.py test_only_the_first_20_opening_braces_are_tried and test_nesting_too_deep_to_decode_is_an_error_not_a_crash.
● **Lesson:** Bound every parse of untrusted text in depth and in attempts, and convert every parser failure, RecursionError included, into the domain's error so it is handled once instead of crashing or being retried every cycle.
● **Evidence:** commit messages (git log): "● A reply nested beyond Python's recursion limit raised RecursionError,"

### CQ-125 Never infer removal from a listing that skipped records, and record what was skipped

● **Rule:** none · **Raised by:** engineering-reviewer (minor on skipped records, first Comms review; the unpinned JSON-array check within its test-completeness MAJOR; the skip-only audit minor, V0.12 round 1); security-reviewer (minor, surviving mutant M37 on the array check) · **Severity:** minor (the array check's test gap was part of a MAJOR) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review, fixed in 0a60d93; the skip-only audit gap raised in V0.12 round 1 on 519e561, fixed in f6056cd and confirmed by the round 2 gates)
● **Applies to:** any reconciliation or sync job against an external listing
● **Symptom:** The channel sweep's skipped count reached no log, audit row or response, and a known channel whose record turned malformed was marked lost and shown as 'Bot removed' with nothing to say why. Without the JSON-array check (present but untested), a 200 answer of {} for the teams list read as no channels and marked every known channel lost. A cycle that only skipped records wrote no audit row.
● **Root cause:** A completeness assumption (absent means gone) was applied even when records had been dropped as malformed or the listing was not the expected shape.
● **Fix:** record_sweep takes the skipped count; with any skipped record no channel is marked lost; the count is logged as a warning and added to the audit detail; a test holds that a teams or channels answer that is not an array fails the sweep and changes nothing; a sweep that only skipped a record is audited (sweep.skipped in _changed).
● **Guard:** test_a_sweep_that_skipped_a_record_marks_nothing_lost and test_a_sweep_that_skipped_records_says_so_in_the_log in tests/test_mattermost_channels.py; the V0.12 engineering gate killed the skipped-sweep, skipped-log, skipped-in-audit and JSON-array mutants, and the round 2 engineering gate the sweep.skipped-in-_changed mutant.
● **Lesson:** Mark items deleted only after a sweep you know was complete and well formed; when a sweep skips or fails anything, change nothing destructive and log and audit the count.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "Skipped records leave no trace, and a skipped known channel is marked lost" Also: CHANGELOG.md.

### CQ-126 Pin a single-flight guard with a concurrent test

● **Rule:** none · **Raised by:** engineering-reviewer (within a MAJOR on test completeness, first Comms review); security-reviewer (minor, surviving mutant M35) · **Severity:** MAJOR (as part of the test-completeness finding) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review, test added in 0a60d93)
● **Applies to:** background jobs and on-demand triggers; any stack
● **Symptom:** Replacing the single-flight wrapper on the Mattermost cycle (background_refresh.py:271) with a direct call left 255 tests green, yet without it two cycles running together on PostgreSQL failed with UniqueViolationError on uq_mattermost_channel_mm_channel_id, which the gate reproduced.
● **Root cause:** The guard that serialises the background cycle and on-demand sweeps had no test that ran two at once.
● **Fix:** A test that a sweep requested during a running cycle joins it: one ingest call and the same result.
● **Guard:** tests/test_background_refresh.py test_a_sweep_on_demand_during_a_running_cycle_joins_it; the V0.12 engineering gate killed the single-flight mutant.
● **Lesson:** Any guard that prevents two runs of a job from overlapping needs a test that starts the second run while the first is held open and asserts they share one execution.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "With a direct call instead, 255 tests stay green." Also: gate report: Security gate on V0.11 round 1.

### CQ-127 Decide an invariant on the locked rows, not on an earlier unlocked copy

● **Rule:** none · **Raised by:** security-reviewer (minor, round 1) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 1, fixed round 2)
● **Applies to:** SQLAlchemy and PostgreSQL; any invariant enforced in application code
● **Symptom:** The last-active-admin rule on PATCH /api/v1/users/{id} took its locked admin count only when an unlocked copy of the target said it was an active admin, so a target promoted or activated after that read could skip the count. Not reproduced; the gate described a contrived three-way interleaving that could leave no active admin.
● **Root cause:** _target loaded the target without a lock, and the decision whether to lock and count admins used that stale copy.
● **Fix:** _locked_target locks the target and the active admins together through lock_users, and _keep_an_admin decides on the locked rows; the split also brought update_user under the complexity limit.
● **Guard:** Round 2 mutants for the admins not locked with the target and for inactive admins counted were killed; live concurrent last-admin pairs left one active admin each time.
● **Lesson:** When a guard decides whether to take a lock, take the lock first and decide on what it returns, because a read made before the lock can be stale by the time the lock is held.
● **Evidence:** gate report: Security gate on V0.10 round 1: "**Cause:** '_target' loads the target without a lock, and the decision to take the locked admin count uses that copy." Also: docs/AUDIT-LOG.md, V0.10 row; session summaries.

### CQ-128 Cap what an external listing can store, and pass large id sets as one array parameter

● **Rule:** none · **Raised by:** security-reviewer (minor, first Comms review) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review, fixed in 0a60d93)
● **Applies to:** SQLAlchemy with asyncpg and PostgreSQL; any driver with a bind-parameter limit
● **Symptom:** No cap limited the channels a sweep records, and rows were never pruned. With 20,000 channels one cycle made 20,004 posts calls and outlasted a 120 s client timeout, and GET /channels returned 8.7 MB. At 33,009 rows the expanding IN (...) exceeds asyncpg's 32,767-parameter limit and GET /channels answers 500 for every user until rows are deleted by hand.
● **Root cause:** SQLAlchemy's in_() binds one parameter per id, and the sweep stored whatever the upstream listed.
● **Fix:** A bot in more than 100 teams or 1,000 channels fails the sweep rather than store an unbounded list; an _any_of helper sends channel_id = ANY(:ids) as one ARRAY(String) parameter in the queries that filtered by a list of channel ids. Accepted in SECURITY.md: the caps bound what is stored, not one listing's size.
● **Guard:** The V0.12 engineering gate killed the mutants of both caps; the V0.12 security gate read the = ANY(array) form at mattermost.py:60.
● **Lesson:** Cap what an upstream listing may add to your store, and pass large id sets as a single array parameter (= ANY) rather than an expanding IN list that can exceed the driver's bind-parameter limit.
● **Evidence:** gate report: Security gate on V0.11 round 1: "At 33,009 rows, the expanding 'IN (...)' exceeds asyncpg's 32,767-parameter limit" Also: src/app/api/v1/routes/mattermost.py at 0a60d93.

### CQ-129 A bounded limiter must only remember keys it has recorded a hit for

● **Rule:** none · **Raised by:** engineering-reviewer (minor, rounds 4 and 5) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised round 4, fixed in 46c48fc; the test gap raised round 5, fixed in e55312b); the residual flood accepted in SECURITY.md
● **Applies to:** in-memory rate limiters and caches; any stack
● **Symptom:** wait_time kept a place for every key it was asked about, so sign-ins refused for want of a check slot, which check no password, still took places among the 10,000 a limiter remembers: the gate pushed out a locked username's count in seconds rather than the 13 minutes the register gave. The test meant to pin the fix recorded one key under a bound of 2, so the limiter never reached capacity and removing the guard kept every test green.
● **Root cause:** A read path inserted into a bounded, evicting store, and the test never filled the store.
● **Fix:** wait_time answers for an unknown key without remembering it and forgets keys whose hits have all expired; the test fills the limiter with the locked key as its stalest before asking about other keys. Accepted: checking 10,000 other usernames, about 13 minutes, still drops a locked username's count, with a trip-wire to evict only keys under their limit before Holly trusts forwarded addresses.
● **Guard:** Limiter tests that turn red when either guard is removed (in the repository, tests/test_core.py test_asking_about_keys_never_pushes_out_one_over_its_limit).
● **Lesson:** In an evicting store that backs a security limit, never let a lookup insert an entry, and test eviction by actually filling the store to capacity.
● **Evidence:** commit messages (git log): "wait_time kept a place for every key it was asked about, so sign-ins" Also: SECURITY.md.

### CQ-130 Order a hash chain by write order, not by each writer's wall clock

● **Rule:** none · **Raised by:** engineering-reviewer (round 1, below MAJOR) · **Severity:** minor (inference: not among round 1's named MAJORs) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (raised round 1, fixed in aaf520f)
● **Applies to:** tamper-evident logs and event chains; any stack
● **Symptom:** The audit chain links each row to the newest by timestamp, and the timestamp came from the writing container's own clock: two containers overlapping during a deploy with clocks apart, or one clock stepping back, could link a row out of timestamp order, so the verifier, which walks the chain in that order, would report a break that is not there.
● **Root cause:** Ordering by wall-clock time taken independently by several writers.
● **Fix:** Each row's timestamp is the later of the clock and one microsecond after the newest row's, read under the same advisory lock, so timestamp order is always write order.
● **Guard:** tests/test_audit.py test_an_entry_is_timed_after_the_latest_even_when_this_clock_is_behind and test_a_clock_ahead_of_the_chain_keeps_its_own_time.
● **Lesson:** Never rely on timestamps from several writers' clocks to order a chain or log; derive a monotonic order under the same lock that serialises the writes.
● **Evidence:** commit messages (git log): "The engineering gate noted that the chain links each row to the newest" Also: CHANGELOG.md.

### CQ-131 Clean up partial files on every exit path, cancellation included

● **Rule:** none · **Raised by:** engineering-reviewer (round 1); both gates by mutation (round 2) · **Severity:** minor (inference: not among round 1's named MAJORs) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (raised round 1, fixed in 763194b; the test gap shown by mutation in round 2, fixed in 48c1a6e)
● **Applies to:** Python asyncio; any server writing uploads to disk
● **Symptom:** A procedure upload whose file write failed part-way, or whose request was cancelled, could leave an orphan file in the store, because the write ran outside the clean-up; the gates then showed the cancellation clean-up could be removed with every test green.
● **Root cause:** Clean-up covered only some failure paths; asyncio cancellation raises CancelledError, a BaseException, which the clean-up did not catch.
● **Fix:** The file write sits inside the clean-up, which runs on any exception, cancellation included (BaseException); a test drives the cancellation below the middleware.
● **Guard:** tests/test_procedures.py test_a_write_that_fails_part_way_leaves_no_file and test_a_cancelled_upload_leaves_no_file (the latter driven below the middleware since 48c1a6e).
● **Lesson:** Put file creation and the write inside one clean-up block that also runs on cancellation (finally, or BaseException), and test cancellation explicitly.
● **Evidence:** commit messages (git log): "route accepted 11 MiB. The engineering gate found that an upload whose" Also: CHANGELOG.md.

### CQ-132 Never derive a storage key from an id that has not been assigned yet

● **Rule:** none · **Raised by:** the V0.2 fusion work on the imported Daily Operations Dashboard code · **Severity:** not graded (fix to imported code) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (found in the imported code, fixed at fusion in 55ab9f1)
● **Applies to:** any server storing uploads beside database rows
● **Symptom:** Every uploaded procedure was stored in one file per extension, named after an id the row did not have yet, so a later upload replaced an earlier one's content and refusing a duplicate deleted the original's file.
● **Root cause:** The file name was computed from the row's id before the row existed.
● **Fix:** Each upload has its own file; an upload that fails for any reason removes its own file; a blank name is refused; a download whose file is missing answers 404.
● **Guard:** The sources name no test; in the repository, tests/test_procedures.py test_a_refused_duplicate_leaves_the_original_file_in_place.
● **Lesson:** Allocate a unique storage key (a random or content-derived name, or the id after insert) before writing a file, so uploads cannot overwrite each other and a refused duplicate cannot delete the original's file.
● **Evidence:** CHANGELOG.md: "Every uploaded procedure was stored in one file per extension, named after an id the row did not have yet, so a later upload replaced an earlier one's content and refusing a duplicate deleted the ..."

### CQ-133 Hash exactly what you store, and enforce append-only in the database

● **Rule:** none · **Raised by:** the V0.2 fusion work on the imported Daily Operations Dashboard code · **Severity:** not graded (fix to imported code) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (found in the imported code, fixed at fusion; pre-V0.2 rows accepted as unverifiable)
● **Applies to:** audit logs and tamper-evident records; PostgreSQL
● **Symptom:** The imported audit chain hashed a timestamp it never stored, so its rows cannot be recomputed or verified, and ADR-005's insert-only rule had no migration enforcing it.
● **Root cause:** The hash input differed from the persisted row, and a design rule never became a database control.
● **Fix:** Rows hash each row's stored timestamp and stored detail; python -m app.cli.verify_audit recomputes the chain and names the first break; migration 0017 refuses every UPDATE, DELETE and TRUNCATE on the audit log. Rows the Daily Operations Dashboard wrote stay unverifiable.
● **Guard:** tests/test_migrations.py test_the_audit_log_refuses_every_change_but_an_insert; the smoke rung checks the append-only audit log.
● **Lesson:** Compute an integrity hash only from the values exactly as persisted, and enforce append-only with a database trigger or permission rather than a convention.
● **Evidence:** CHANGELOG.md: "Rows the Daily Operations Dashboard wrote hashed a timestamp it never stored and cannot be verified."

### CQ-134 Drive incremental regeneration from unseen inputs, not from a moving window or timestamp ties

● **Rule:** none · **Raised by:** the V0.2 fusion work on the imported Daily Operations Dashboard code · **Severity:** not graded (fix to imported code) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (found in the imported code, fixed at fusion)
● **Applies to:** any incremental summarisation or materialised view; LLM pipelines
● **Symptom:** Event narratives were rebuilt from the current window only, so they shrank as older publications aged out, and a timestamp tie triggered a fresh narrative every hour. Inferred from the fix: older events were summarised first under the per-cycle cap, and a long-lived event cost more to summarise than a busy one.
● **Root cause:** Staleness was keyed on timestamps and the window's contents rather than on which publications a narrative had consumed (the tie behaviour implies a non-strict comparison: inference).
● **Fix:** A summary is refreshed only when the window holds a publication it has not seen, from the event's full history; a tie no longer triggers; the newest events are summarised first under the cap; at most 20 publications of one event, the first and the newest, are sent.
● **Guard:** The sources name no test; in the repository, tests/test_event_summary.py test_a_long_history_is_shown_as_its_first_and_newest_publications and test_on_a_timestamp_tie_the_id_decides_which_is_latest.
● **Lesson:** Track which inputs a derived result has consumed and regenerate only when a genuinely new input arrives, building from full history so the result never shrinks as a window slides.
● **Evidence:** CHANGELOG.md: "Event summaries: a summary is refreshed only when the window holds a publication it has not seen, and from the event's full history, so it never shrinks as older publications age out"

### CQ-135 Background loops must survive another caller's cancellation and re-raise their own

● **Rule:** none · **Raised by:** the V0.2 fusion work on the imported Daily Operations Dashboard code · **Severity:** not graded (fix to imported code) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (found in the imported code, fixed at fusion)
● **Applies to:** Python asyncio; any cooperative-cancellation runtime
● **Symptom:** The hourly background loop did not survive a cycle cancelled by another caller, and stopping the loops swallowed the caller's own cancellation.
● **Root cause:** CancelledError was handled without distinguishing a cancelled child cycle from the loop itself being cancelled (inference from the fix).
● **Fix:** The loop survives a cycle cancelled by another caller, and stopping the loops re-raises the caller's cancellation.
● **Guard:** The sources name no test; in the repository, tests/test_background_refresh.py test_a_cycle_cancelled_by_another_caller_does_not_end_the_loop and test_stopping_does_not_swallow_its_callers_own_cancellation.
● **Lesson:** Catch a cancellation only to clean up, and re-raise it unless it was aimed at a child task you own, so shutdowns and timeouts propagate and one cancelled cycle does not kill the loop.
● **Evidence:** CHANGELOG.md: "The hourly loop survives a cycle cancelled by another caller, and stopping the loops no longer swallows the caller's own cancellation."

### CQ-136 Validate LLM output fields to their declared format at the server boundary, time zone included

● **Rule:** none · **Raised by:** security-reviewer (minor, V0.6 round 2; record-only nit, V0.6 round 3; nit on the docstring, V0.7 round 1); engineering-reviewer (minor on the panel's label, V0.7 round 1; nit on the naive time, V0.7 round 3) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised round 2; display guarded in round 3, server check deferred), V0.7 (the server drops a non-ISO deadline, from V0.6's open items, before round 1; the panel labels only ISO-shaped values after round 1; a time of day without an offset dropped in round 4)
● **Applies to:** any stack storing LLM output; JavaScript Date consumers
● **Symptom:** An assistant deadline that is not a date, such as 'by end of shift', passed the schema and made the panel's formatter throw; once the panel was guarded it was still stored and shown as written. In V0.7 round 1 the panel labelled any string the browser's Date reads, such as 'before shift 3', as a 2001 date, and fromisoformat still kept naive timestamps: in a Europe/London browser a deadline of 2026-07-02T06:00 with no offset showed as 05:00:00 with no zone marked.
● **Root cause:** The schema accepted any string, then anything fromisoformat parses, including a time of day with no tzinfo, which the browser's Date reads as local time; the panel trusted V8's lenient Date parsing.
● **Fix:** V0.7 drops a deadline that is not an ISO 8601 timestamp when the reply is checked, the panel labels only ISO-shaped values (round 2), and round 4 also drops a time of day without an offset (src/app/schemas/assistant.py), so neither is stored.
● **Guard:** tests/test_assistant_service.py test_a_deadline_is_kept_only_as_a_timestamp; the naive-time mutants D01 to D05 were killed in the V0.7 round 4 engineering gate. Residual gaps are open in their own entries (the length heuristic, the prompt's wording).
● **Lesson:** Treat model output as untrusted input: parse each structured field to its declared type at the server, require an explicit offset for a time of day, and null out what fails rather than storing it for the client to interpret.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "an assistant deadline that is not a date, such as "by end of shift", passed the schema and made the panel's formatter throw" Also: gate report: Engineering gate, V0.7 round 3; docs/AUDIT-LOG.md, V0.7 row; gate report: Engineering gate on V0.7.

### CQ-137 Decide 'date only' with the parser, not a string-length proxy

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer (NIT each, V0.7 round 4) · **Severity:** nit · **Status:** open · **Certainty:** fact
● **Releases:** V0.7 (raised round 4, left open); unchanged at HEAD f8a00bd (V0.13)
● **Applies to:** Python datetime parsing; any format sniffing
● **Symptom:** The naive-time rule decides whether a deadline has a time by length (has_time = len(text) > len("2026-01-02")), so short ISO week and basic forms with a time but no offset, such as 2026W01T06, are kept; the security gate's fuzz of about 409,500 strings found five such shapes. The panel shows them as written, without 'By' and without converting zones.
● **Root cause:** A length heuristic stands in for asking the parser whether the text is a date alone.
● **Fix:** None yet. Both gates proposed treating the text as a date alone only when date.fromisoformat(text) accepts it, and otherwise requiring tzinfo; listed open in the V0.7 audit row.
● **Guard:** none recorded
● **Lesson:** Classify a value with the parser that defines the format, never with a length or shape proxy, and add the boundary forms the proxy misses to the tests.
● **Evidence:** gate report: Engineering gate, V0.7 round 4: "The 'has_time' length heuristic keeps a naive time 10 characters long." Also: gate report: Security gate, V0.7 round 4; src/app/schemas/assistant.py at f8a00bd.

### CQ-138 Align an LLM prompt's output instruction with the validator that checks it

● **Rule:** none · **Raised by:** engineering-reviewer (MINOR, V0.7 round 4) · **Severity:** minor · **Status:** open · **Certainty:** fact
● **Releases:** V0.7 (raised round 4, left open); unchanged at HEAD f8a00bd (V0.13)
● **Applies to:** any LLM integration with structured output
● **Symptom:** The validator now drops a time of day without an offset, but the prompt asks only for an 'ISO 8601 timestamp' and to use UTC, which 2026-01-02T06:00:00 satisfies, so a deadline given by the prompt's own rules disappears from the analyst's panel without a log.
● **Root cause:** The validator was tightened without updating the instruction that produces the value.
● **Fix:** None yet. The gate proposed asking for an ISO 8601 timestamp with its UTC offset, pinned by a test; listed open in the V0.7 audit row.
● **Guard:** none recorded
● **Lesson:** Change a model's output instructions in the same change as its validator, and test that an output following the prompt's own rules passes the validator.
● **Evidence:** gate report: Engineering gate, V0.7 round 4: "A deadline the model gave by the prompt's own rules now disappears from the analyst's panel without a log, although the prompt fixes its zone." Also: docs/AUDIT-LOG.md, V0.7 row; src/app/services/assistant.py at f8a00bd.

### CQ-139 Normalise a value the same way everywhere it is tested and used

● **Rule:** none · **Raised by:** security-reviewer (nit, round 3); engineering-reviewer (nit, round 3, the unpinned presence strip M03) · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised round 3, fixed round 4)
● **Applies to:** any stack reading configuration or credentials
● **Symptom:** The bootstrap's 'is it set' check stripped ADMIN_PASSWORD, so 12 spaces counted as unset there, but _credentials used it unstripped, and an admin was created live with a 12-space password. The engineering gate also found the presence strip unpinned (mutant M03).
● **Root cause:** Two code paths applied different normalisation to the same input.
● **Fix:** A password of spaces alone counts as unset in both the bootstrap and the create_admin CLI, so it is refused as half a pair.
● **Guard:** tests/test_create_admin.py test_a_password_of_spaces_is_no_password; the strip mutants in both paths (P01, C14) and M03 killed in the round 4 engineering gate; a live gunicorn probe on an empty database stopped the start with exit 1.
● **Lesson:** Normalise an input once, at the boundary, and pass the normalised value to every check and use, so a presence test and the code that consumes the value cannot disagree.
● **Evidence:** gate report: Security gate, V0.7 round 3: "but '_credentials' uses it unstripped, and an admin was created live with a 12-space password." Also: docs/AUDIT-LOG.md, V0.7 row; gate report: Security gate, V0.7 round 4.

### CQ-140 Report the same diagnostic fields on every status of a start-up log line

● **Rule:** none · **Raised by:** security-reviewer (nit, round 3) and engineering-reviewer (minor, round 3) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised round 3, fixed round 4)
● **Applies to:** structured logging; any stack
● **Symptom:** With only ADMIN_EMAIL left set after the first start, the bootstrap logged not_configured without naming it, though the docs said the log names any variable still set.
● **Root cause:** Only the accounts_exist path carried the list of variables still set.
● **Fix:** not_configured logs variables_still_set too.
● **Guard:** The not_configured names mutants (M09, M10) killed in the round 4 engineering gate; the round 4 security gate checked that no value appears in variables_still_set. Left open in the V0.7 row: the operator manual should say each status carries variables_still_set.
● **Lesson:** Give every outcome of a diagnostic log event the same fields, so the operator's documented check works whichever branch ran.
● **Evidence:** gate report: Security gate, V0.7 round 3: "The log says 'not_configured' and does not name it, although the docs say the log names any variable still set." Also: gate report: Engineering gate, V0.7 round 4.

### CQ-141 Treat an empty environment variable as unset in every reader

● **Rule:** none · **Raised by:** engineering-reviewer (minor, round 1) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.8 (raised round 1, fixed round 2; four of five names left unpinned)
● **Applies to:** environment-driven configuration; pydantic settings; any stack
● **Symptom:** Under the DAST scan flag, an empty DATABASE_URL was logged as no database, but Settings then read the empty string as set and refused it as a malformed URL; if the platform passed an empty variable, the DAST no_report failure would return.
● **Root cause:** The scan step and the settings judged 'set' differently: one stripped blanks, the other accepted an empty string as a value.
● **Fix:** A _blank_is_unset validator on database_url and the four postgres_* fields makes a blank value read as unset, in the scan and outside it.
● **Guard:** A test for a blank DATABASE_URL under the flag; the audit records that four of the five blank-as-unset names are unpinned.
● **Lesson:** Decide once, in one helper, what counts as 'set' for configuration (blank and whitespace as unset is usual), and use it in every reader of the same variables.
● **Evidence:** gate report: Engineering gate on V0.8 DAST: "How the scan delivers its database is 'TBC', so an empty variable from the platform would bring back 'no_report'." Also: docs/AUDIT-LOG.md, V0.8 row.

### CQ-142 Check a retry deadline before an attempt, or state the real bound

● **Rule:** none · **Raised by:** engineering-reviewer (nit, round 1; restated as a nit in round 2) · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.8 (raised round 1, closed round 2 by rewording)
● **Applies to:** retry loops; any stack
● **Symptom:** The start-up database wait could stop up to about 7 s past 60 (62 s seen), while the docs said 'up to 60 seconds'; round 2 put the worst case at about 65 s.
● **Root cause:** The deadline is checked only after a failed attempt, so a final 5 s connect and a 2 s sleep can run past it.
● **Fix:** The docs say 'about a minute' and the time-out message 'within about 60 seconds', which the round 2 gate accepted; the last attempt was not capped and the deadline is still checked after a failed attempt at HEAD.
● **Guard:** none recorded
● **Lesson:** Check the deadline before each attempt and cap the last attempt's timeout to the time left, or document the true worst case.
● **Evidence:** gate report: Engineering gate on V0.8 DAST: "The deadline is checked only after a failed attempt, so the stop can come up to about 7 s past 60 (one 5 s connect plus a 2 s sleep); I saw 62 s." Also: gate report: Engineering gate, V0.8 round 2.

### CQ-143 Compare a case-insensitive identifier case-insensitively when checking uniqueness

● **Rule:** none · **Raised by:** engineering-reviewer (graded MINOR (nit), round 1) · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 1, fixed round 2)
● **Applies to:** SQLAlchemy; any user store
● **Symptom:** The email clash check on account creation was case-sensitive, so Bob@x and bob@x could both be created.
● **Root cause:** The clash query compared the raw column to the submitted value.
● **Fix:** The check compares func.lower(User.email) with the lowercased submission, so an email in use in any case is refused with 409; a clash taken between the check and the insert also answers 409 through the IntegrityError path, which round 1 already covered.
● **Guard:** An email-case mutant killed in round 2; the security gate confirmed a case-only email clash answers 409.
● **Lesson:** Normalise case for identifiers that are case-insensitive in practice (emails, usernames) in both the stored and compared values, and back the check with a database constraint or handle the insert's integrity error.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "The email clash check is case-sensitive, so 'Bob@x' and 'bob@x' can both be created." Also: src/app/api/v1/routes/users.py at af13871; docs/AUDIT-LOG.md, V0.10 row.

### CQ-144 Do not flag items as needing action when no action is possible on them

● **Rule:** none · **Raised by:** engineering-reviewer (minor, first Comms review) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review, fixed in 0a60d93)
● **Applies to:** any sync job that flags new records for review
● **Symptom:** Channels found already closed counted as new and were listed in the banner 'found and followed ... Switch off any you do not want', though closed channels have no switch; the first sweep would list every archived channel the bot was ever in.
● **Root cause:** New-ness was set on first sight, independently of the closed check.
● **Fix:** A channel found closed on first sight arrives reviewed.
● **Guard:** The V0.12 engineering gate killed the closed-on-first-sight mutant.
● **Lesson:** Derive 'needs review' from whether a user can act on the item, so terminal-state records never land in an action queue.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "Channels found already closed count as new" Also: CHANGELOG.md; gate report: Engineering gate V0.12.

### CQ-145 Share one predicate where two code paths must agree, instead of copying the rule

● **Rule:** none · **Raised by:** engineering-reviewer (minor, first Comms review) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review, fixed in 0a60d93)
● **Applies to:** any stack
● **Symptom:** The route's pulled flag (routes/mattermost.py:150) copied the pull rule from channels_to_pull with no parity test; its `not row.closed` part could be deleted with no test failing.
● **Root cause:** Duplicated business logic with no test tying the copies together.
● **Fix:** One is_pulled(row) predicate in mattermost_channels.py, used by both the route and channels_to_pull.
● **Guard:** tests/test_mattermost_channels.py test_a_pulled_channel_is_followed_open_and_readable; the V0.12 engineering gate killed the is_pulled accessible mutant.
● **Lesson:** When a display flag and a job must apply the same rule, call one shared predicate from both and test it directly.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "'pulled' copies the pull rule from 'channels_to_pull' with no parity test" Also: src/app/services/mattermost_channels.py at 0a60d93.

### CQ-146 Keep a commit inside the block that writes the record it commits

● **Rule:** none · **Raised by:** engineering-reviewer (MINOR, V0.12 round 1) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised round 1 on 519e561, fixed in f6056cd)
● **Applies to:** any stack with explicit transactions
● **Symptom:** src/app/services/mattermost_ingest.py had two consecutive `if audited:` blocks, one writing the audit row and one committing, which split the transaction boundary across two conditionals.
● **Root cause:** The commit was separated from the audit write it belongs to.
● **Fix:** Merged into one block that commits inside it; the round 2 engineering gate found the merged block sound.
● **Guard:** none recorded
● **Lesson:** Keep a write and the commit that makes it durable under one condition, so a later edit cannot separate them.
● **Evidence:** gate report: Engineering gate V0.12: "'src/app/services/mattermost_ingest.py:283' and ':292' are two consecutive 'if audited:' blocks; merge them." Also: gate report: Engineering gate V0.12 round 2.

### CQ-147 Re-check the current selection after every await before applying an async answer

● **Rule:** none · **Raised by:** security-reviewer (out-of-scope note, V0.13 round 1); the reliability finder of the V0.13 SonarQube sweep · **Severity:** not graded (display integrity only, per the security gate) · **Status:** open · **Certainty:** inference
● **Releases:** V0.13 (noted in round 1 and by the SonarQube sweep's reliability finder; pre-existing since V0.12, not fixed)
● **Applies to:** React and TypeScript; any async UI
● **Symptom:** In frontend/src/components/comms/ChannelConversation.tsx, latest() awaits a page and then sets the messages without checking that the channel is still the one shown, so if the channel changes while the request is pending the old channel's page could briefly show under the new one. It was the same at f6951a6. Inference: the Comms page mounts the conversation with key={conversation.mm_channel_id}, so a channel switch remounts it and a late answer would land on the old, unmounted instance; the window is real only where the component is reused without that key.
● **Root cause:** The poll effect's cancelled guard covers the poll answer, but arrive awaits latest(), and latest() has no guard of its own after its await.
● **Fix:** None recorded; HEAD f8a00bd still has no check after the await in latest(), and the V0.13 audit row does not list it as open.
● **Guard:** none recorded
● **Lesson:** Every async load that writes UI state must confirm, after each await, that its request still matches the current selection (a request id or cancelled flag), not only at the outer poll.
● **Evidence:** gate report: Security gate V0.13 (fast): "its answer is not checked against the new channel, so the old channel's page could briefly show under the new one." Also: gate report: find:reliability; frontend/src/components/comms/ChannelConversation.tsx at f8a00bd; frontend/src/pages/Mattermost.tsx at f8a00bd.

### CQ-148 A grouping key for external events must include the source

● **Rule:** none · **Raised by:** a V0.2 round 1 review gate (which one is not recorded) · **Severity:** not recorded · **Status:** deferred · **Certainty:** mixed
● **Releases:** V0.2 (raised round 1, deferred with a trip-wire in ad5b332)
● **Applies to:** any multi-source ingest
● **Symptom:** Notices group on Event_Id, then the NOTSO number, then the UDL id, whatever their source; the background pull asks for source JCO only, but a manual ingest may name any source, and a record from another provider reusing a JCO Event_Id would join that event and its narrative.
● **Root cause:** The group key omits the data source.
● **Fix:** Deferred: the background pull asks for one source only.
● **Guard:** SECURITY.md trip-wire: add the source to the group key before a second source is ingested in normal use.
● **Lesson:** Namespace external identifiers by their source in any key that groups or deduplicates records, before a second source arrives.
● **Evidence:** SECURITY.md: "Notices group on 'Event_Id', then the NOTSO number, then the UDL id, whatever their source." Also: commit messages (git log).

### CQ-149 A long synchronous manual job can outlive the ingress timeout

● **Rule:** none · **Raised by:** a V0.2 round 1 review gate (which one is not recorded) · **Severity:** not recorded · **Status:** deferred · **Certainty:** mixed
● **Releases:** V0.2 (raised round 1, deferred with a trip-wire in ad5b332)
● **Applies to:** any web app behind an ingress or proxy
● **Symptom:** Pull from UDL answers only when the whole cycle ends (the UDL pull, up to 20 evaluations and up to 20 narratives); an ingress timeout shorter than that ends the request while the cycle may be cut part-way.
● **Root cause:** The manual trigger runs the full cycle inside the request.
● **Fix:** Deferred: the hourly cycle picks up what is left. The ingress timeout is TBC, re-verify.
● **Guard:** SECURITY.md trip-wire: if the ingress timeout proves shorter than a cycle, run the manual pull in the background and have the page poll for its end.
● **Lesson:** Run any job that can exceed a proxy timeout in the background and let the client poll for its result, rather than holding the request open.
● **Evidence:** SECURITY.md: "**Pull from UDL** answers when the whole cycle ends: the UDL pull, up to 20 evaluations and up to 20 narratives."

### CQ-150 Read only the bytes a preview needs

● **Rule:** none · **Raised by:** security-reviewer (round 1); both gates by mutation (round 2) · **Severity:** minor (inference: not among round 1's named MAJORs) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (raised round 1, fixed in c9cd2f8; the test gap shown by mutation in round 2, fixed in 48c1a6e)
● **Applies to:** any stack; Python asyncio
● **Symptom:** Each evaluation read every previewable procedure file whole, up to 10 MB, on the event loop, to keep its first 64 KiB.
● **Root cause:** Read-then-truncate instead of a bounded read.
● **Fix:** The preview reads 64 KiB and one byte, enough to tell whether the file goes on; a later test counts the bytes at the read itself.
● **Guard:** Boundary tests at exactly 64 KiB, one byte over and 10 MiB, and a test counting the read (in the repository, tests/test_procedures.py test_the_preview_reads_64_kib_and_one_byte_never_the_whole_file and test_the_preview_stops_at_64_kib).
● **Lesson:** Bound file and network reads to what the caller needs (plus one byte to detect truncation), especially on an event loop.
● **Evidence:** commit messages (git log): "The security gate noted that each evaluation read every previewable"

### CQ-151 Accept external ids in every JSON type the upstream sends

● **Rule:** none · **Raised by:** the V0.2 fusion work on the imported Daily Operations Dashboard code · **Severity:** not graded (fix to imported code) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (found in the imported code, fixed at fusion)
● **Applies to:** any third-party JSON ingest
● **Symptom:** Satellite ids that UDL sends as numbers crashed evaluations and event summaries.
● **Root cause:** The code assumed string ids.
● **Fix:** Numeric ids are handled.
● **Guard:** The sources name no test; in the repository, tests/test_assistant_service.py test_satellite_ids_stored_as_numbers_still_reach_the_prompt.
● **Lesson:** Normalise upstream identifiers to one type at the ingest boundary, and test both the string and numeric forms an API is known to send.
● **Evidence:** CHANGELOG.md: "Satellite ids that UDL sends as numbers no longer crash evaluations and event summaries." Also: commit messages (git log).

### CQ-152 Bound client-supplied schedule and ingest inputs, and anchor recurrences

● **Rule:** none · **Raised by:** the V0.2 fusion work on the imported Daily Operations Dashboard code (CHANGELOG V0.2 Fixed; no gate named) · **Severity:** not graded (fix to imported code) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (found in the imported code, fixed at fusion; migration 0016)
● **Applies to:** any scheduling or timer feature; any ingest API
● **Symptom:** Event timers took whitespace-only labels and unbounded targets, looped on an unknown recurrence value, pre-alerted at a fixed 5 minutes, and a monthly timer set for the 31st drifted after a shorter month; a manual UDL ingest had no cap on the records one pull may ask for (inference from the new cap), and the element-set ingest's audit entry did not record the data mode it asked for.
● **Root cause:** No boundary validation, and (inference from migration 0016's recurrence anchor) the next occurrence was computed from the last fire date rather than an anchor.
● **Fix:** Blank labels refused; targets bounded to the years 2000 to 2099; an unknown recurrence dismissed once; pre-alerts use the timer's own lead time; migration 0016 adds a recurrence anchor; at most 10,000 records a pull; the element-set ingest's audit entry records the data mode.
● **Guard:** The sources name no test; in the repository, tests/test_event_timers.py test_a_blank_label_is_refused, test_a_monthly_timer_keeps_its_day_of_the_month_after_a_short_month and test_an_unknown_recurrence_is_dismissed_once_and_never_loops.
● **Lesson:** Validate and bound every client-supplied scheduling or quantity field at the boundary, and compute recurrences from a stored anchor so month-end dates do not drift.
● **Evidence:** CHANGELOG.md: "Event timers: a whitespace-only label is refused, targets are bounded to the years 2000 to 2099, and an unknown recurrence value is dismissed once instead of looping."

### CQ-153 Translate driver-specific connection options when switching database drivers

● **Rule:** none · **Raised by:** engineering-reviewer (minor, round 1) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised round 1, fixed in de816cc; reworked in 4676e45 to rename sslmode on SQLAlchemy's own parse of the URL)
● **Applies to:** SQLAlchemy with asyncpg; any async database driver
● **Symptom:** A DATABASE_URL ending ?sslmode=require passed the boot check and failed on first connection.
● **Root cause:** SQLAlchemy hands every query parameter of the URL to asyncpg, which has no sslmode.
● **Fix:** libpq's sslmode is renamed to asyncpg's ssl, which takes the same values.
● **Guard:** tests/test_config.py test_libpq_sslmode_becomes_asyncpg_ssl (from the repository; the commit names no test).
● **Lesson:** When a connection URL written for one driver reaches another, translate or refuse its options at boot, and test the platform's actual URL form.
● **Evidence:** commit messages (git log): "asyncpg, which has no sslmode, so a URL ending ?sslmode=require" Also: src/app/config.py at f8a00bd.

### CQ-154 Host validation must accept container service names with underscores

● **Rule:** none · **Raised by:** engineering-reviewer (nit, round 4) · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised round 4, fixed in 71fc76b)
● **Applies to:** container platforms; any configuration validator
● **Symptom:** A database host such as holly_db was refused with a message that blamed the scheme.
● **Root cause:** The host check followed strict DNS hostname rules.
● **Fix:** The DATABASE_URL host and POSTGRES_HOST accept underscores; the check still refuses anything else a misread password could leave behind.
● **Guard:** tests/test_config.py test_a_service_name_with_an_underscore_is_a_host and the host cases that include holly_db (from the repository; the commit names no test).
● **Lesson:** Validate hosts against what the deployment platform actually produces (container service names often contain underscores), and make a refusal name the real fault.
● **Evidence:** commit messages (git log): "Container platforms name services with underscores, as in holly_db," Also: docs/AUDIT-LOG.md, V0.2 row.

### CQ-155 Disable framework trailing-slash redirects so routes answer as declared

● **Rule:** none · **Raised by:** engineering-reviewer or security-reviewer (both failed round 1; which raised this is not recorded) · **Severity:** not recorded · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (raised round 1 on 9616c41, fixed in c0a25dc)
● **Applies to:** FastAPI and Starlette; any router with slash redirects
● **Symptom:** A path with a trailing slash was redirected by the framework rather than answered as declared. Inference from the test added with the fix, which sends Host: evil.example and asserts no Location header: the redirect could carry a location built from the request's Host header.
● **Root cause:** FastAPI's default redirect_slashes behaviour (inference from the fix).
● **Fix:** The app factory sets redirect_slashes=False, so trailing slashes are not redirected.
● **Guard:** tests/test_app.py test_a_trailing_slash_is_not_redirected (present since c0a25dc): /healthz/ answers 404 with no Location header.
● **Lesson:** Turn off automatic slash redirects so each path, probes included, answers exactly as declared and a redirect cannot point at a host taken from the request.
● **Evidence:** commit messages (git log): "trailing slashes are not redirected, and PORT must be canonical." Also: src/app/factory.py at f8a00bd; tests/test_app.py at f8a00bd.

### CQ-156 Remove error messages for conditions that cannot occur

● **Rule:** none · **Raised by:** engineering-reviewer (nit, round 3) · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised round 3, fixed round 4)
● **Applies to:** any CLI or validator
● **Symptom:** The create_admin CLI could print 'The admin password is too long', though there is no length limit and bcrypt input is cut at 72 bytes.
● **Root cause:** A shared message covered every field, including one with no length limit.
● **Fix:** The CLI names each field's problem with field-specific messages.
● **Guard:** none recorded
● **Lesson:** Keep error messages field-specific and reachable; an impossible message misleads operators and hides which check really failed.
● **Evidence:** gate report: Engineering gate, V0.7 round 3: "cannot happen: there is no length limit, and bcrypt input is cut at 72 bytes (security.py:26)." Also: gate report: Engineering gate, V0.7 round 4.

### CQ-157 A cancelled request must not cancel the work that alone releases a shared slot

● **Rule:** none · **Raised by:** not recorded (inference: arose while fixing the security gate's round 2 finding on the sign-in limit, fixed in the same commit) · **Severity:** not recorded · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (fixed in 169d432, among the round 2 gate fixes 62e5dc5 to 9df87b9)
● **Applies to:** Python asyncio; any async runtime with cooperative cancellation
● **Symptom:** In Holly's sign-in route, a request cancelled while its password check still waited for a worker thread also cancelled that check, which was the only code that gave its bounded check slot back, so cancelled sign-ins could keep slots. File: src/app/api/v1/routes/auth.py.
● **Root cause:** The slot-holding check ran in the request's own task, so the request's cancellation propagated into it before the release path ran.
● **Fix:** 169d432 runs the check under asyncio.shield(asyncio.to_thread(...)), so cancelling the request no longer cancels the check that returns the slot.
● **Guard:** tests/test_auth.py test_a_check_cancelled_before_it_reaches_a_thread_still_gives_its_slot_back queues a check behind a busy one-thread executor, cancels it and asserts the slot comes back (169d432)
● **Lesson:** When work holds a resource that only that work releases, shield it from the caller's cancellation or release it in a path cancellation cannot skip, and test the cancel-while-queued case directly.
● **Evidence:** commit messages (git log): "The check runs shielded, so a request cancelled while its check still" Also: src/app/api/v1/routes/auth.py at f8a00bd; tests/test_auth.py at f8a00bd; docs/AUDIT-LOG.md, V0.2 row.

## 2.4 Frontend, React and accessibility


### CQ-158 Incremental polling that fetches one capped page silently skips items when more arrive than the page holds

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR (gate FAIL) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised round 1 at 519e561), V0.12 (fixed round 1 in f6056cd)
● **Applies to:** any client that polls a paged API for new items (React and TypeScript here)
● **Symptom:** The Comms feed and a channel's conversation polled for newer messages with `posted_at_gte` and `limit: 50`. Proven with a throwaway test: 1 message shown, 61 newer on the server; after "Show 50 new messages" the feed read "51 of 51 messages", messages in the gap (the probe's `new 55` among them) were never shown and "Load older" was disabled (`CommsFeed.tsx:97` and `:109`, `ChannelConversation.tsx:128` and `:142`).
● **Root cause:** Each poll took only the newest page and prepended it, adding the page size to a client-side total, while "Load older" paged by offset from the newest, so anything between the newest page and what was already shown fell between the two and was never fetched.
● **Fix:** When the server's total exceeds the items on the page, the feed and the conversation reload the latest page instead of prepending, and take the total from the server (f6056cd). The off-by-one this fix introduced in the count is a separate entry.
● **Guard:** views.test.tsx: "reloads the latest page when more arrived than one poll holds, so none is skipped" (feed) and "reloads the latest page when more arrived than one poll holds, at the bottom or below" (conversation); the reload's own stale-answer guard in `showWaiting` was given a test in round 2 (6c712cc).
● **Lesson:** An incremental poll must notice when more items arrived than one response holds (compare the server's total with the page length) and reload or page back, never prepend a capped page and patch a client-side count. Test it with more items waiting than one page holds.
● **Evidence:** gate report: Engineering gate V0.12: "**[MAJOR] The feed and conversation lose messages when more than 50 build up between polls.**" Also: CHANGELOG.md.

### CQ-159 An inclusive range bound counts the boundary item twice, and a test fixture built from the same formula enshrines the wrong figure

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR (gate FAIL) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised round 2 at f6056cd), V0.12 (fixed in 6c712cc, confirmed by round 3 mutants at ccbc7b8)
● **Applies to:** any stack; clients counting "new since" items against a range query
● **Symptom:** After the page-skip fix, the new-message count was one too high whenever more than one page had arrived: 60 new messages showed as "Show 61 new messages" (`CommsFeed.tsx:105`, `ChannelConversation.tsx:147`). The test at `views.test.tsx:251` fixed the wrong figure in place (its fake returned total 61 with 50 items), and the conversation test at `:449` used the same formula.
● **Root cause:** The poll asks `posted_at_gte: newest` and the route filters with `ge`, so the server's total also counts the newest message already shown; `page.total - (page.items.length - fresh.length)` kept that boundary message whenever it was not on the returned page. The fixtures were derived from the code's own formula rather than from what the server returns.
● **Fix:** A helper `alsoAsked` in `utils/comms.ts` counts the shown messages the poll also matched (posted at or after the newest) and subtracts them, in the feed and the conversation; the tests use the server's true total (6c712cc). Round 3 mutants (each view back to the old formula, `>=` turned to `>`, `alsoAsked` always 0) each went red.
● **Guard:** views.test.tsx assertions on the server's true total in the feed and the conversation; the round 3 engineering gate's mutation table.
● **Lesson:** When a query's lower bound is inclusive, subtract every already-shown item the bound also matches, or use an exclusive bound. Build test fixtures from the server's real semantics, never from the formula under test, or the test will pin the bug.
● **Evidence:** gate report: Engineering gate V0.12 round 2: "The new-message count is too high by at least 1 whenever more than one page has arrived." Also: gate report: Engineering gate V0.12 round 3.

### CQ-160 When swapping an element to satisfy an analyser rule, match the old element's computed styles, not browser defaults

● **Rule:** `none (arose fixing SonarQube S6819)` · **Raised by:** engineering-reviewer · **Severity:** MAJOR (gate FAIL) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.11 (raised round 1 at 777ffe8), V0.11 (fixed round 2 at 91ffed8, committed unchanged as c8af9ad)
● **Applies to:** any web UI; HTML and CSS
● **Symptom:** V0.10's upload failed Code Quality on two S6819 smells (`role="status"` at `Users.tsx:255` and `ChangePassword.tsx:101`). The hotfix made each confirmation line an `<output>` with a new `.status-line { margin: 1em 0; }`, which gave 15px above and below (15px body font), where the replaced `<p>` took the project's global `p { margin: 0 0 var(--space-3); }` (0 above, 12px below). Gaps on the Users page moved by about 3 pixels, so the CHANGELOG's "looks as before" and the audit row's "margins the paragraph had" were untrue.
● **Root cause:** The new rule used the browser's default paragraph margin (`1em 0`) rather than the project's own base `p` rule; the gate had no headless browser (no Chromium or Playwright installed) to compare renders and worked the difference out from the cascade.
● **Fix:** `.status-line { display: block; margin: 0 0 var(--space-3); }` (91ffed8), matching the old paragraph exactly, with the comment reworded.
● **Guard:** None recorded for the layout; the gate settled it by working the cascade out from source. The role-based test assertions were shown load-bearing by mutation.
● **Lesson:** Replacing one element with another (for an accessibility or lint rule) is a visual change until proven otherwise: copy the old element's effective styles from the project's own base rules, and check before and after renders rather than claiming "looks as before".
● **Evidence:** gate report: Engineering gate on V0.11 hotfix: "The new '.status-line { margin: 1em 0; }' gives 15px on top and 15px below, because the body font size is 15px" Also: docs/AUDIT-LOG.md, V0.11 row; gate report: Engineering gate on hotfix round 2.

### CQ-161 Check responsive layout at every width down to 320 CSS pixels with populated data, not at one viewport with empty lists

● **Rule:** `WCAG 2.2 1.4.10 (Reflow)` · **Raised by:** engineering-reviewer (round 1); engineering-reviewer and security-reviewer (round 2) · **Severity:** blocking (found by round 1's engineering gate; both gates FAIL in round 2) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.4 (raised round 1, both gates FAIL round 2), V0.4 (fixed in rounds 3 and 4, committed together in 05bd528)
● **Applies to:** any web UI; CSS layout
● **Symptom:** The theme commit said the header held together on a narrow screen, but it had been checked only at 1,024 pixels: below 578 pixels every signed-in page scrolled sideways. Round 2 failed both gates: at 600 pixels wide or less, and at 320 by 256 (1,280 by 1,024 at 400% zoom), the fixed-height shell left page content out of reach and a banner could cover Sign out; with populated lists a note's buttons, a message's header and a timer's buttons reached past the panel; the 760-pixel media block sat above the rules it overrides, so three of its values never applied. Round 3's engineering gate asked for the pager's and the narrative heading's wraps back, for a seven-digit total and the button's "Composing..."; round 4 also made a long word in a timer's label break rather than widen every page.
● **Root cause:** Layout verified at a single desktop viewport with empty data (8 widths, 7 of the 8 pages, width alone); a fixed-height application shell; a media-query block placed before the rules it was meant to override.
● **Fix:** Rounds 3 and 4 (05bd528): on a window 600 pixels wide or 480 tall, or smaller, the whole page scrolls; the header wraps where its brand and controls do not share a line and never shrinks under banners; the navigation becomes a row of links at 600 and below; a note's buttons, a message's header, the pager and the narrative's heading wrap, and a long word in a timer's label breaks; the 760-pixel block follows the rules it overrides. Checked in Chromium on round 4's build, on all 8 signed-in pages every 4 pixels from 320 to 1,024, with populated data, 17- and 50-character usernames and a seven-digit total.
● **Guard:** Each of the 19 reflow rules removed alone turned a reflow, reach, header, slack or sign-in check red (the browser checks ran in Chromium outside the repository, so nothing in the loop holds them).
● **Lesson:** Test reflow at every width from 320 pixels up, and at short heights, with realistic long content on every page; put media-query overrides after the rules they override, and avoid fixed-height shells that cannot scroll.
● **Evidence:** docs/AUDIT-LOG.md, V0.4 row: "Its message says the header holds together on a narrow screen, but that was looked at only at 1,024 pixels: the engineering gate's first round found that below 578 pixels every signed-in page ..." Also: commit messages (git log).

### CQ-162 Guard every async answer and poll against a newer request, and prove each guard with a test that fails without it

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor for each defect; MAJOR for the untested guards (V0.5 round 1, Comms round 1, V0.12 rounds 1 and 2) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (guard tests, raised round 1, fixed round 2); V0.11 round 1 of the Comms work at c9e3acc (raised), V0.12 (fixed in 0a60d93 and f6056cd; guard tests completed in 6c712cc)
● **Applies to:** React and TypeScript; any UI framework with async effects
● **Symptom:** Comms: a feed poll in flight across a scope or search change could offer messages from the old scope (`CommsFeed.tsx:85-97`); `loadOlder` and the page's `refresh` had no guard, so an answer for an earlier scope or `since` could land after a newer one; the first-load `cancelled` checks, the reload guard in `showWaiting` and the conversation poll's guard could each be deleted with every test green; removing the polls' interval clean-up also stayed green ("Each channel switch would leak a poller"). In V0.5, four tests named for a stale-response guard still passed with the guard removed.
● **Root cause:** Effects and handlers set state from whichever response arrived last, with no cancelled flag or request identity; tests resolved requests in order, so the guards were never exercised.
● **Fix:** A cancelled flag on the feed poll (0a60d93), a read counter in `refresh` and scope checks in `loadOlder` and `showWaiting` (f6056cd), and tests for each guard and for the interval clean-ups, each failing without its guard (an older answer held open while a newer one lands, or an unmount followed by a clock advance; 6c712cc completed the last two). In V0.5 a battery neutralising each `!cancelled` alone went from 2 of 17 guards killed to 17 of 17.
● **Guard:** views.test.tsx ("drops a poll answered after the scope changed, and stops polling once closed", "drops older messages answered after the scope changed", "drops a reload of the latest page answered after the scope changed", "stops polling once closed, and drops an answer that lands after") and Mattermost.test.tsx ("keeps the latest read of the channels when an earlier one answers late"); the gates' mutation runs.
● **Lesson:** Any effect or handler that awaits and then sets state needs a cancellation or request-identity check, and pollers need clean-up on unmount. Prove each guard with a test that resolves an older request after a newer one and fails when the guard is removed.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "A feed poll still in flight across a scope or search change can offer messages from the old scope" Also: gate report: Engineering gate V0.12 round 2; docs/AUDIT-LOG.md, V0.5 row.

### CQ-163 Older pages still fetch without stale-response guards and keep stale state after a failed load

● **Rule:** none · **Raised by:** verification loop (found while writing V0.5's dashboard tests) · **Severity:** not graded (recorded below the blocking bar) · **Status:** deferred · **Certainty:** mixed
● **Releases:** V0.5 (found and deferred), V0.6 (carried open), still open for the shift log and procedures at V0.13
● **Applies to:** React and TypeScript; any data-fetching UI
● **Symptom:** Writing V0.5's tests found no stale-response guard in `ShiftLog.tsx` (an older shift's entries can replace the shift picked, and a new entry is then listed under the wrong shift), `Mattermost.tsx` (paging and filters) or `Procedures.tsx` (opening one, and the list after deletes). Also: a failed shift load keeps the previous shift's entries; an entry's error stays after a retry succeeds; the shift log, Procedures, the audit log and Comms show an empty-list message beside a load error (the audit log tells an analyst without the role that it holds no entries); `Maneuvers.tsx:81` keeps its "must be numeric" message until the next load.
● **Root cause:** Pages imported from the Daily Operations Dashboard fetch in effects without cancellation and do not reset data or error state when a new load starts or fails.
● **Fix:** None. V0.5 removed the test assertions that held the defects as correct and listed them; V0.6 carried "the eleven defects" as open. At f8a00bd, `ShiftLog.tsx` and `Procedures.tsx` still hold no `cancelled` guard (fact, from a code search). The Comms page was rewritten in V0.12 with guards, so its V0.5 defects are superseded (inference).
● **Guard:** none recorded; no test holds the defects in place
● **Lesson:** When writing tests exposes a defect, record it rather than assert it, and schedule the fix; on any page that loads by selection, reset data and error state at the start of each load and guard against late answers.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "no stale-response guard in 'ShiftLog.tsx' (an older shift's entries can replace the shift picked, and a new entry is then listed under the wrong shift)" Also: docs/AUDIT-LOG.md, V0.6 row.

### CQ-164 Surface the server's error message whatever shape the body takes, not the HTTP client's generic status text

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor (V0.2); part of a MAJOR (V0.10 round 1); minor for the missing page tests (V0.10 round 2) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (Blob error bodies, raised and fixed in de816cc); V0.10 (422 list detail, raised round 1, fixed round 2), V0.12 (page tests added)
● **Applies to:** any web client; axios with FastAPI or pydantic validation errors
● **Symptom:** V0.2: downloads and exports had been plain links that could not carry the analyst's token, so they became authenticated fetches returning a Blob; a failed download's JSON error then also arrived as a Blob and analysts saw "Request failed with status code 404" instead of the server's message about a missing procedure file. V0.10: a 422's `detail` is a list, so the Users and Password pages showed "Request failed with status code 422"; on the Users page that was the only way an admin learned why a username was refused, since the rule is checked only on the server.
● **Root cause:** `responseType: "blob"` applies to error responses too, and the shared error extractor fell back to axios's own message whenever `detail` was not a string.
● **Fix:** V0.2: the dashboard reads an error Blob back as JSON first (de816cc; `withJsonErrorBody` in `utils/errors.ts`). V0.10: `validationMessage` in `frontend/src/utils/errors.ts` shows a 422's first problem as text, wired into the Users and ChangePassword pages; V0.12 added page tests of that wiring, which round 2's mutants F24 and F25 had shown untested.
● **Guard:** `frontend/src/utils/download.test.ts` and `errors.test.ts`; V0.12 page tests of a 422's message on the Users and Password pages.
● **Lesson:** Normalise every error body (JSON string, JSON list, Blob) into the server's own message in one helper, test each shape and each page's wiring, and never let the HTTP library's "Request failed with status code N" reach users.
● **Evidence:** commit messages (git log): "Two minor findings from the engineering gate:" Also: gate report: Engineering gate on V0.10 round 1; gate report: Engineering gate on V0.10 round 2; frontend/src/utils/errors.ts at af13871.

### CQ-165 Never present an unobserved value as observed: mark data the system does not collect

● **Rule:** none · **Raised by:** design-critic (advisory) · **Severity:** HIGH (advisory review) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.11 Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any dashboard or data UI
● **Symptom:** On the Comms switchboard, activity and last-message fields count only messages Holly holds, so an unfollowed channel or one the bot had left showed a flat trace and "No messages yet", and a recently unfollowed channel's trace fell to zero and read as "went quiet".
● **Root cause:** The switchboard rendered the same trace whether or not the channel was pulled, although the channel type already carried `pulled`.
● **Fix:** A channel Holly does not pull shows "Not pulled" in place of the trace.
● **Guard:** parts.test.tsx "says a channel Holly does not pull is not pulled, rather than drawing it quiet".
● **Lesson:** Distinguish "zero" from "not measured" in every display: when the system does not collect a value for an item, say so instead of drawing an empty or flat reading.
● **Evidence:** gate report: Design critique of the Comms console: "That shows an unobserved value as observed, which breaks the integrity floor." Also: CHANGELOG.md; frontend/src/components/comms/ChannelSwitchboard.tsx at f8a00bd.

### CQ-166 Exempt only the exact session endpoints from refresh-and-retry; a substring match also caught the page-load session check

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** not graded (raised as outside the change); the untested `/auth/login` entry was round 2's MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised round 1 as older than the change), V0.9 (fixed round 2, its `/auth/login` entry pinned by a test in round 3; committed as 83e9696)
● **Applies to:** any single-page app with token refresh interceptors (axios here)
● **Symptom:** A page reloaded after the 30-minute access token expired returned to the sign-in page even with a valid refresh token, the same visible symptom as the gateway fault V0.9 was fixing.
● **Root cause:** The axios response interceptor skipped refresh for any URL containing `/auth/` (a substring test), which also matched `/auth/me`, the first call `AuthContext` makes when the page loads.
● **Fix:** An exact set, `SESSION_CALLS`, of `/auth/login`, `/auth/refresh` and `/auth/logout` replaced the substring test; every other call, `/auth/me` included, refreshes once and retries, bounded by the `_retry` flag and the shared refresh promise. Round 2 left the `/auth/login` entry untested (removing it kept every test green); round 3 added a test with a refresh token held.
● **Guard:** Vitest: "refreshes a refused /auth/me, so a reload after the access token expires stays signed in", "never tries to refresh a refused refresh" and "never tries to refresh a failed sign-in, even with a refresh token held"; mutants reverting to `includes("/auth/")`, adding `/auth/me` to the set, or dropping `/auth/refresh` or `/auth/logout` were killed in round 2, and dropping `/auth/login` in round 3.
● **Lesson:** Exempt endpoints from an interceptor by exact path, never by substring, test every entry of the exemption list, and test the page-reload path with an expired access token and a valid refresh token.
● **Evidence:** gate report: Engineering gate on V0.9 round 1: "**Outside this change:** 'client.ts:75-80' never refreshes after a 401 on any '/auth/' path, and that includes '/auth/me', which 'AuthContext' calls when the page loads." Also: gate report: Engineering gate on V0.9 round 2; gate report: Engineering gate on V0.9 round 3; frontend/src/api/client.ts at 0fcd6d1; frontend/src/api/client.ts at 83e9696.

### CQ-167 Never call a throwing formatter on untrusted text during render

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised round 2), V0.6 (fixed round 3, committed 691f25b); server-side check added in V0.7
● **Applies to:** React and TypeScript; any UI rendering LLM output
● **Symptom:** A model-made deadline such as "by end of shift" passed the 64-character string field; the assistant panel's `new Date(...).toISOString()` threw a RangeError and, with no error boundary, the stored evaluation blanked the page each time it rendered.
● **Root cause:** The Large Language Model (LLM) deadline was trusted to be a date: the schema took any string up to 64 characters, nothing checked for an invalid date before `toISOString()`, and no error boundary surrounded the panel.
● **Fix:** The formatter returns the raw string when it is not a date (React escapes it), with a test red without the guard; from V0.7 the server also drops a deadline that is not an ISO 8601 timestamp.
● **Guard:** AssistantPanel.test.tsx case with the non-date deadline, red without the guard.
● **Lesson:** Treat model and user output as untrusted at render time: validate before calling anything that can throw (date formatting, JSON parsing), fall back to showing the value as text, and consider an error boundary so one bad record cannot blank the page.
● **Evidence:** gate report as received: "'new Date(...).toISOString()' then throws a RangeError, and with no error boundary the stored evaluation blanks the page each time it renders." Also: docs/AUDIT-LOG.md, V0.6 row.

### CQ-168 Decide whether a string is a timestamp by a strict shape, not by a lenient date parser

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit (V0.6); minor (V0.7) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 ("By by" nit, round 3; fixed in V0.7), V0.7 (lenient parser raised round 1, fixed round 2)
● **Applies to:** JavaScript and TypeScript; any UI formatting dates from untrusted strings
● **Symptom:** After the V0.6 fallback, a deadline that was not a date showed as "By by end of shift". V0.7 showed non-ISO deadlines as written, but `deadlineLabel` still labelled any string V8's `Date` accepts: a stored "before shift 3" rendered as "By 2001-03-01 00:00:00", a date the assistant never gave, contradicting the CHANGELOG and the audit row.
● **Root cause:** `new Date(string)` in V8 parses many free-text forms, so a not-NaN check does not prove a value is ISO 8601; the "By " prefix was kept when the raw text was shown.
● **Fix:** V0.7 round 2: only values matching an anchored ISO shape that also give a valid Date are labelled "By"; any other value shows as written, without "By".
● **Guard:** AssistantPanel.test.tsx "labels only an ISO 8601 deadline with By, and shows any other as written"; frontend mutant F1 (the ISO-shape guard) killed in round 2.
● **Lesson:** Gate date formatting on a strict, anchored pattern for the format you expect, then parse; never use a permissive parser's success as proof of format, and do not prefix fallback text with wording meant for the parsed form.
● **Evidence:** gate report as received: "A deadline that is not a date shows as "By by end of shift"" Also: gate report: Engineering gate on V0.7; gate report: Engineering gate, V0.7 round 2.

### CQ-169 Keep the display rule for timestamps in step with the server's rule, including for rows stored earlier

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** nit · **Status:** deferred · **Certainty:** fact
● **Releases:** V0.7 (raised round 3 as a nit, again round 4 by both gates, listed open for a follow-up), unchanged at V0.13
● **Applies to:** any client displaying stored timestamps
● **Symptom:** The server now drops a time of day without an offset, but the panel's `ISO_TIMESTAMP` still labels an already-stored naive time "By" and reads it in the browser's zone: a stored 2026-07-02T06:00 shows as 10:00 in New York and 21:00 the day before in Tokyo. Mutant F10 (`|$` to `|`) survives, as V8 accepts "2026-01-02 (Zulu)" and "2026-01-02 6:00". Only a local database could hold such a row, since no upload had deployed.
● **Root cause:** The regex's time branch does not require `Z` or a UTC offset, so the client's rule is looser than the server's.
● **Fix:** None. The gates proposed requiring `Z` or an offset after a time, otherwise showing the value as written, with those two strings added to the test; listed open in the V0.7 audit row, and the regex is unchanged at f8a00bd.
● **Guard:** none recorded
● **Lesson:** When the server tightens a format rule, tighten the client's display rule to match and decide what happens to records stored under the old rule; a time without a zone should never be silently read in the viewer's local zone.
● **Evidence:** gate report: Engineering gate, V0.7 round 3: "A deadline without a UTC offset is kept and the browser reads it as local time" Also: gate report: Security gate, V0.7 round 4; gate report: Engineering gate, V0.7 round 4; docs/AUDIT-LOG.md, V0.7 row; frontend/src/components/AssistantPanel.tsx at f8a00bd.

### CQ-170 Content-derived React keys need collision handling against every key already issued

● **Rule:** `S6479 (index keys replaced); S1994 on the follow-up loop` · **Raised by:** engineering-reviewer (minor) and security-reviewer (nit); SonarQube on the platform (S1994, as relayed by the app owner) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised round 1, fixed round 2); V0.7 upload (S1994 on the loop), V0.8 (rewritten in 117346c)
● **Applies to:** React and TypeScript; any keyed list rendering
● **Symptom:** To clear SonarQube S6479, the assistant panel keyed its lists by content, a repeat taking an occurrence suffix; `withContentKeys(["a","a","a#2"])` returned `["a","a#2","a#2"]`, duplicate keys from assistant (LLM) output, which is untrusted. The test name "so no two keys match" overstated what it proved. The fix's loop, `for (let n = 2; issued.has(key); n++)`, was then flagged as S1994 on V0.7's upload.
● **Root cause:** The suffix came from an occurrence count without checking the keys already issued, so content shaped like a suffixed key collided.
● **Fix:** Track every key issued and bump the suffix until it is free, with the colliding input as a test case (V0.6). V0.8 rewrote the loop as a `while` that tests the key and moves the occurrence number with it, the keys unchanged.
● **Guard:** `frontend/src/utils/keys.test.ts` "never issues a key twice, even where content looks like a suffixed key".
● **Lesson:** When keys are derived from content, de-duplicate against the set of keys already issued, not a count, and test with input that mimics your suffix format; untrusted content will eventually contain it. Keep a loop's condition and its update on the same variable.
● **Evidence:** gate report: Engineering gate on V0.6 tree: "the suffixed key can collide with real content. 'withContentKeys(["a","a","a#2"])' returns '["a","a#2","a#2"]', two keys the same." Also: docs/AUDIT-LOG.md, V0.6 row; the app owner's message.

### CQ-171 Keep client requests within the server's validated limits; ask by criterion instead of sending an unbounded id list

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms round 1 at c9e3acc (followed list, raised), V0.12 (fixed in 0a60d93); V0.12 round 1 (picked channels, raised), V0.12 (fixed in f6056cd)
● **Applies to:** any client of a validated API
● **Symptom:** With more than 200 followed open channels, the Feed's default request expanded the follow list into `channel_id` values beyond the route's cap of 200, got a 422 and showed "Failed to load messages." Later, picking more than 200 channels by hand sent a request the server refuses, shown as a raw error.
● **Root cause:** The client turned "the followed channels" into an explicit id list bounded by a server cap, and did not mirror the cap for hand-picked selections.
● **Fix:** The messages route takes `followed=true` and selects the followed open channels on the server, so the feed asks by the follow list (0a60d93); `MAX_PICKED = 200` in `scope.ts` ignores a pick past the cap (f6056cd).
● **Guard:** tests/test_mattermost_routes.py "test_the_followed_channels_are_asked_for_by_the_follow_list_not_by_id"; parts.test.tsx "takes at most the 200 channels the server reads in one ask, and still takes one out"; the gates' mutants of `followed: true` and `MAX_PICKED` went red.
● **Lesson:** When the server validates a list size, let the server resolve sets by criterion and mirror any remaining cap in the client; never let a growing data set push a default request past a validation limit.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "Over 200 followed open channels breaks the Feed" Also: gate report: Engineering gate V0.12; frontend/src/components/comms/scope.ts at f6056cd.

### CQ-172 A detail view that loads once goes stale while summary counts elsewhere keep polling

● **Rule:** none · **Raised by:** engineering-reviewer (minor) and design-critic (MEDIUM) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms round 1 at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** React and TypeScript; any polling UI
● **Symptom:** The Channels layout's conversation (`ChannelConversation.tsx:37-55`) loaded only when the channel changed, so its header count, fed by the 60-second channel poll, rose while the message list did not.
● **Root cause:** Only the feed had a poll; the conversation was written as a one-shot load.
● **Fix:** The conversation checks for new messages every 30 seconds, appends them when the reader is at the bottom and otherwise offers them below, and opens at the last-visit marker.
● **Guard:** views.test.tsx ("adds a message that arrives at the bottom for a reader already there", "holds a message that arrives below a reader who has scrolled up, until asked"); the V0.12 engineering gate killed the conversation update path mutant.
● **Lesson:** If any part of a screen refreshes, every view showing the same data must refresh on the same trigger, or the screen will contradict itself.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "It loads only when the channel changes. The header count (from the 60 s channel poll) goes up while the message list does not." Also: gate report: Design critique of the Comms console; gate report: Engineering gate V0.12.

### CQ-173 Clear a polled view's error state when a later request succeeds

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms round 1 at c9e3acc (raised), V0.12 (fixed in 0a60d93)
● **Applies to:** React and TypeScript; any polling UI
● **Symptom:** On the Comms page (`Mattermost.tsx:42-50`) a failed poll's error stayed on screen after later polls succeeded.
● **Root cause:** The error state was set on failure but never reset on success.
● **Fix:** The error clears on a successful read of the channel list.
● **Guard:** Mattermost.test.tsx "clears a failed read of the channels once a later one succeeds"; the V0.12 engineering gate killed the loadError-cleared mutant.
● **Lesson:** Every success path of a retrying or polling request must reset the error it can set; test failure followed by success.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "A failed poll's error stays up after later polls succeed" Also: CHANGELOG.md.

### CQ-174 A deliberate policy refusal must not render as an error

● **Rule:** none · **Raised by:** app owner · **Severity:** not graded (owner question) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised by the app owner, fixed in 1e29a06, gated in rounds 1 to 7)
● **Applies to:** any UI fronting a policy or disclosure control
● **Symptom:** The app owner sent a screenshot of the assistant panel asking "why is this here?": a notice withheld by the disclosure control (its classification marking not in `ASSISTANT_CLEARED_MARKINGS`) showed in red as "Assistant could not produce a structured evaluation".
● **Root cause:** The evaluation reported the disclosure control's refusal through the same error path as a genuine failure, so the UI could not tell them apart.
● **Fix:** The evaluation carries a computed `withheld` flag; the panel shows a calm fixed note (not sent, content stayed in Holly, which markings the assistant may see is the data owner's decision) and offers no re-run.
● **Guard:** AssistantPanel.test.tsx "shows a notice kept from the assistant as a calm note, not an error, with no re-run" and tests/test_assistant_service.py cases; the V0.12 engineering gate killed the withheld panel mutant.
● **Lesson:** Model intended outcomes (policy refusals, withheld content) as their own state from the API to the UI, with neutral wording and no retry, so users do not read a control working as designed as a fault.
● **Evidence:** session summaries: ""why is this here?" about the assistant panel showing "Assistant could not produce a structured evaluation: Not sent to the assistant: this notice's classification marking is not cleared for it ..." Also: CHANGELOG.md.

### CQ-175 Report a committed change as done even when a follow-up read fails

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 1), V0.10 (fixed round 2)
● **Applies to:** any client; React context actions here
● **Symptom:** If `/auth/me` failed after the server had accepted a password change (the new tokens already stored), the page said the password could not be changed; a retry with the old password then answered "not correct" and counted against the rate limit.
● **Root cause:** The change and the user re-read shared one try block, so a failure of the second was reported as a failure of the first.
● **Fix:** Round 2 catches the re-read separately: the user is forgotten rather than shown as still due, the access token is still set so the effect reads the user again, and the change resolves.
● **Guard:** Mutants F17 and F18 (the catch and `setUser(null)`) killed in round 2.
● **Lesson:** Separate a state-changing call from the reads that follow it; once the server has committed, report success and recover the follow-up read on its own.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "If '/auth/me' fails after the server has accepted the change (the new tokens are already stored), the page says the password could not be changed." Also: gate report: Engineering gate on V0.10 round 2.

### CQ-176 Derive every colour from theme tokens and measure every text pair, visual effects included

● **Rule:** `WCAG 2.2 AA contrast (1.4.3, 1.4.11)` · **Raised by:** the V0.4 theme work's own measurements (raiser of the procedure-text and file-button defects not recorded); design-critic (scrollbar, dismissed timer, native controls) · **Severity:** not graded · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.4 (raised and fixed in 0e66528, 63f0ddd and b94e742; the check extended through round 7, committed in 05bd528)
● **Applies to:** any web UI; CSS custom properties
● **Symptom:** A procedure's text had been drawn in the light text colour on a near-white panel since the V0.2 fusion; 26 hard-coded tints remained; the native file-picker button kept the browser's light default; the design's scanlines over body text pulled the fainter labels below 4.5:1 even at 12%, and at the document's 40% the rust and green counts fell to 2.9:1; a dismissed timer faded below 4.5:1; the scrollbar thumb was under 3:1; native controls and autofill were light.
● **Root cause:** Colours set outside the token system, browser-drawn controls left unstyled, and decorative overlays and opacity fades never measured.
● **Fix:** Every tint became a token (25 as `color-mix`); scanlines confined to headings and counts at 35%; the file button themed; a dismissed timer dims by colour; a 3:1 thumb; dark native controls. `scripts/contrast-check.mjs`, a new loop step, measures every text and field-edge pair the tokens make (218 at V0.4, 247 by V0.12) and refuses a colour outside the tokens and an accent closer than 0.2 in OKLab to a status colour.
● **Guard:** `scripts/contrast-check.mjs` and its self-test in `scripts/verify.sh`; `scripts/mutation-battery.mjs` in CI proves the checker's controls.
● **Lesson:** Put every colour behind a token and run a contrast check on every token pair in the loop, including overlays, animation peaks, fades and browser-drawn controls; a theme that only looks right on one panel is not measured.
● **Evidence:** CHANGELOG.md: "**A procedure's text was unreadable.** It was drawn in the light text colour on a near-white panel; it now sits on the screen colour in the code face." Also: docs/AUDIT-LOG.md, V0.4 row; commit messages (git log).

### CQ-177 A focus style aimed at text fields must not remove the focus ring from other controls

● **Rule:** `WCAG 2.2 2.4.7 (Focus Visible)` · **Raised by:** design-critic (advisory) · **Severity:** not graded · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.4 (raised by the design review, fixed in b94e742)
● **Applies to:** any web UI; CSS
● **Symptom:** Focus was invisible on the checked Scanlines toggle: the text-field focus rule removed the ring from checkboxes too.
● **Root cause:** An over-broad focus selector reset the outline on every input type.
● **Fix:** The rule applies to text fields only, so every checkbox keeps the 2px phosphor ring; later V0.4 rounds hold the focus ring to the text contrast floor in the contrast check.
● **Guard:** `scripts/contrast-check.mjs` measures the focus ring's colour; no test that the ring is drawn on every control is recorded.
● **Lesson:** Scope focus-style overrides to the exact controls they are meant for, and check keyboard focus on every control type, checked and unchecked.
● **Evidence:** commit messages (git log): "Focus was invisible on the checked Scanlines toggle: the text-field focus" Also: docs/AUDIT-LOG.md, V0.4 row.

### CQ-178 Do not use colour as the only cue for links, pressed states or matches

● **Rule:** `WCAG 2.2 1.4.1 (Use of Color)` · **Raised by:** design-critic (advisory) · **Severity:** MEDIUM (pressed segments); LOW (search matches); not graded (V0.4 links) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.4 (links, fixed in b94e742); Comms design review at c9e3acc (pressed segments and search matches), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any web UI
● **Symptom:** V0.4: links relied on colour. V0.12: colour alone marked the pressed segment of the Feed/Channels and Followed/All toggles (pressed accent text against muted text measured 1.9:1 and the tinted fill against the panel 1.4:1, under the 3:1 needed), and search matches were marked by a background tint only.
● **Root cause:** State and emphasis styled by colour changes alone.
● **Fix:** Links underlined; pressed segments gain `font-weight: 600` and an inset accent underline (`box-shadow: inset 0 -2px 0 var(--color-accent)`), token-only so the contrast check still passes; matches underlined.
● **Guard:** `scripts/contrast-check.mjs` keeps every token pair at WCAG AA; no check for a non-colour cue is recorded.
● **Lesson:** Give every state and emphasis a second cue (weight, underline, shape or text) and check it by viewing the screen without colour.
● **Evidence:** CHANGELOG.md: "Links are underlined, so colour is never their only cue." Also: gate report: Design critique of the Comms console; frontend/src/styles/tokens.css at 62ba4aa.

### CQ-179 Keep keyboard focus when a control becomes busy or removes itself

● **Rule:** `WCAG 2.2 2.4.3 (Focus Order)` · **Raised by:** design-critic (advisory) · **Severity:** MEDIUM · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** React and TypeScript; any web UI
● **Symptom:** A focused button that becomes `disabled` drops focus to the page body in Chromium (the follow switch, "Find channels now"), and "Mark reviewed" removed its own banner on success, so keyboard users restarted from the top of the page each time.
● **Root cause:** Busy state used the `disabled` attribute, and nothing received focus after the banner went.
● **Fix:** Busy controls use `aria-disabled="true"` and ignore clicks; after "Mark reviewed", focus moves to the always-rendered `<output>` notice (`tabIndex={-1}`).
● **Guard:** parts.test.tsx "keeps its focus while its change saves, and ignores presses meanwhile"; the V0.12 engineering gate killed the review and follow busy-guard mutants.
● **Lesson:** Do not disable a focused control while it works; mark it `aria-disabled` and ignore clicks, and when an action removes its own container, move focus to a stable element that reports the outcome.
● **Evidence:** gate report: Design critique of the Comms console: "A focused button that becomes 'disabled' drops focus to the page body in Chromium." Also: docs/AUDIT-LOG.md, V0.12 row; frontend/src/pages/Mattermost.tsx at 62ba4aa.

### CQ-180 Derive a selection's highlight and ARIA state from the filter it applies, and show that it can be clicked

● **Rule:** none · **Raised by:** design-critic (advisory) · **Severity:** MEDIUM · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** React and TypeScript; any web UI
● **Symptom:** The Feed's selection highlight went stale: clicking a narrowed channel again widened the feed but left the row highlighted with `aria-current`, and a channel picked in Channels view stayed highlighted in Feed view; the test at `Mattermost.test.tsx:131` did not assert the highlight. In Feed view nothing showed that a channel name could be clicked to narrow the feed.
● **Root cause:** Two sources of truth (a `selected` variable and the feed's scope) and `aria-current` used for what is a toggle.
● **Fix:** In Feed view the switchboard's `selectedIds` come from the feed's scope (in Channels view, the open conversation); names use `aria-pressed` in Feed view and `aria-current` in Channels view, show an underline on hover and focus, and picked channels show as removable chips.
● **Guard:** Mattermost.test.tsx "narrows the feed to the channels picked on the switchboard, and back again"; parts.test.tsx "in the feed, presses the names picked and picks another".
● **Lesson:** Compute highlight and ARIA state from the state that actually filters the view, not a parallel selection variable; use `aria-pressed` for toggles and `aria-current` for the current item, and give filters a visible affordance.
● **Evidence:** gate report: Design critique of the Comms console: "The Feed's selection highlight goes stale." Also: session summaries; frontend/src/pages/Mattermost.tsx at 62ba4aa; CHANGELOG.md.

### CQ-181 Put ARIA state and descriptions on the element that owns them

● **Rule:** `S6811 (V0.6); WAI-ARIA 1.2` · **Raised by:** design-critic (V0.4 current page); verification (V0.5 tests, aria-sort); SonarQube on the platform (S6811 on V0.5's upload); raiser of the toggle note not recorded · **Severity:** not graded; S6811 was one of V0.5's 68 Code Quality findings · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.4 (current page fixed in b94e742; toggle note fixed in round 5, committed in 05bd528); V0.5 (aria-sort found), V0.6 (fixed under S6811)
● **Applies to:** React and TypeScript; any web UI
● **Symptom:** `SortableHeader.tsx` put `aria-sort` on its button, where WAI-ARIA 1.2 supports it only on a column or row header, so screen readers missed the sort. In V0.4 the side navigation did not mark the current page for screen readers, and the flicker toggle's reduced-motion note sat inside its label rather than serving as its description.
● **Root cause:** ARIA attributes and descriptive text attached to convenient elements rather than the ones the specification reads them from.
● **Fix:** V0.6: `aria-sort` moves to the column header, set only on the sorted column. V0.4: the navigation marks the current page; the reduced-motion note moves out of the label and becomes the toggle's description.
● **Guard:** Under reduced motion Chromium's accessibility tree names the toggle "CRT flicker" and describes it (a check run outside the repository); none recorded for the header.
● **Lesson:** Check each ARIA attribute against the roles that support it, and give a control one name and one description; an automated rule (SonarQube S6811, jsx-a11y) catches some of these, the accessibility tree catches the rest.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "'SortableHeader.tsx' puts 'aria-sort' on its button, where WAI-ARIA 1.2 supports it only on a column or row header, so screen readers miss the sort" Also: docs/AUDIT-LOG.md, V0.6 row; docs/AUDIT-LOG.md, V0.4 row.

### CQ-182 Presentation styles must not alter how a stored value reads

● **Rule:** none · **Raised by:** design-critic (advisory) · **Severity:** not graded (V0.4); LOW (V0.12) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.4 (fixed in b94e742); Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any web UI; CSS
● **Symptom:** V0.4: the code face's ligatures changed how records' characters showed, and headings upper-cased record values (inferred from the fix). V0.12: the global `h2` style turned a channel name into "#CONJUNCTION DESK", changing a record's own value on screen.
● **Root cause:** Decorative `text-transform` and font ligatures applied to elements that display data.
● **Fix:** Ligatures off in the code face; headings that show a record keep its case; the conversation heading carries the existing `record-value` class.
● **Guard:** views.test.tsx asserts the conversation heading's class is `record-value`.
● **Lesson:** Exempt data from decorative typography: a class for record values that turns off text transforms and ligatures, applied wherever a heading or label shows stored content.
● **Evidence:** CHANGELOG.md: "Code and records show their characters as stored, with the code face's ligatures off, and headings that show a record's value keep its case." Also: gate report: Design critique of the Comms console; frontend/src/components/comms/views.test.tsx at 62ba4aa.

### CQ-183 Avoid nested scroll regions that hide the latest item below the fold

● **Rule:** none · **Raised by:** design-critic (advisory) · **Severity:** MEDIUM · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any web UI; CSS layout
● **Symptom:** The 70vh conversation box started about 400px down inside the scrolling content, so opening a channel scrolled the inner box to the latest message while that row sat below the fold; the sticky switchboard's `calc(100vh - 32px)` exceeded the screen area and cut off its Closed section with about 12 or more channels.
● **Root cause:** Fixed viewport-relative heights nested inside another scroll container.
● **Fix:** Above 760 by 640 pixels the channel list and the stage each scroll on their own in a fill layout, and a conversation opens at the last-visit marker.
● **Guard:** None recorded.
● **Lesson:** Give each scrolling pane a flex or grid track that fills the remaining space (`min-height: 0`) instead of viewport-relative heights inside a scrolling parent, and check where "scroll to latest" lands on a real screen.
● **Evidence:** gate report: Design critique of the Comms console: "Nested scroll hides the latest message." Also: docs/AUDIT-LOG.md, V0.12 row.

### CQ-184 On narrow screens, bring the result of a selection into view

● **Rule:** none · **Raised by:** design-critic (advisory) · **Severity:** MEDIUM · **Status:** resolved · **Certainty:** mixed
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any responsive web UI
● **Symptom:** At 390px wide the whole channel list stacked above the stage, no message showed on the first screen, and tapping a channel changed nothing visible because its conversation renders far below.
● **Root cause:** The desktop two-column layout simply stacked on phones.
● **Fix:** After a pick on a narrow screen (760 pixels or less) the stage is scrolled into view, at once under reduced motion. The suggested drawer or chip row for the list was not taken (inference from the change).
● **Guard:** Mattermost.test.tsx "brings the stage into view after a pick on a narrow screen, at once if asked for less motion".
● **Lesson:** On stacked mobile layouts, every selection must produce a visible result: scroll it into view (respecting reduced motion) or collapse the list.
● **Evidence:** gate report: Design critique of the Comms console: "At 390px wide the whole channel list stacks above the stage." Also: frontend/src/pages/Mattermost.tsx at 62ba4aa.

### CQ-185 Draw comparable small charts on one shared scale and print the total

● **Rule:** none · **Raised by:** design-critic (advisory) · **Severity:** MEDIUM · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any data visualisation
● **Symptom:** Each channel's 24-hour activity trace was scaled to its own busiest hour, so one message looked as tall as another channel's busiest hour, and sighted users got no count or units (the total existed only in `aria-label`).
● **Root cause:** Per-row normalisation.
● **Fix:** Every trace is scaled to one peak across the open pulled channels, with its total printed (for example "12 in 24 h").
● **Guard:** parts.test.tsx "draws every pulled channel's day on one scale, with its total in words".
● **Lesson:** Sparklines meant for comparison share one scale, and the number they summarise is printed for everyone, not only in assistive text.
● **Evidence:** gate report: Design critique of the Comms console: "Each trace is scaled to its own busiest hour" Also: frontend/src/components/comms/ChannelSwitchboard.tsx at 62ba4aa; frontend/src/components/comms/parts.test.tsx at f8a00bd.

### CQ-186 Keep a live region rendered and change only its text

● **Rule:** `none (the critic's suggested form would have raised SonarQube S6819)` · **Raised by:** design-critic (advisory) · **Severity:** LOW · **Status:** resolved · **Certainty:** mixed
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** React and TypeScript; any web UI
● **Symptom:** The `role="status"` notice was added to the page already holding its text, which screen readers often skip.
● **Root cause:** The live region was mounted conditionally with its message.
● **Fix:** The notice is an always-rendered `<output>` whose text changes, and `<output>` replaced every `role="status"`. The critic's suggested `<p role="status">` would have reintroduced the S6819 smell that failed V0.10's upload, which is taken to be why the native element was used (inference).
● **Guard:** None recorded.
● **Lesson:** Mount live regions once and update their text; prefer the native element (`<output>`) to a role on a generic element, which SonarQube also flags.
● **Evidence:** gate report: Design critique of the Comms console: "notice is added to the page already holding its text, which screen readers often skip." Also: session summaries.

### CQ-187 Report one failure once, and let the words carry it as well as the colour

● **Rule:** none · **Raised by:** design-critic (advisory) · **Severity:** LOW · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any web UI
● **Symptom:** A failed manual sweep showed 2 identical rust alerts, while the sweep strip still read "Channels swept 3 min ago" beside a rust lamp.
● **Root cause:** Both the page error and the strip reported the same failure, and the strip's text did not change with its lamp.
● **Fix:** The failure is shown once; the strip says "The last channel sweep, X, failed."
● **Guard:** Mattermost.test.tsx "shows a failed sweep once, in the strip and the warning under it"; parts.test.tsx "says in words when the last sweep failed, and names no bot it never learned"; the V0.12 engineering gate killed the no-notice-on-failed-sweep mutant.
● **Lesson:** Route each failure to one place on screen, and make its text state the failure rather than relying on an indicator colour.
● **Evidence:** gate report: Design critique of the Comms console: "A failed manual sweep shows 2 rust alerts that say the same thing." Also: session summaries.

### CQ-188 Tell users when a control changes shared state for everyone, and offer undo

● **Rule:** none · **Raised by:** design-critic (advisory) · **Severity:** MEDIUM · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any multi-user UI
● **Symptom:** The follow list is shared by every user, but nothing told the user a switch changed it for everyone, including what the assistant reads.
● **Root cause:** Per-user styling and wording on a global setting.
● **Fix:** Notices say the change is for everyone, with an Undo button, and a hint under the switchboard explains that the switches are shared.
● **Guard:** Mattermost.test.tsx "follows and unfollows a channel for everyone, says so, and can undo it".
● **Lesson:** A control whose effect reaches other users or downstream systems must say so at the point of use and offer an immediate undo.
● **Evidence:** gate report: Design critique of the Comms console: "nothing tells the user a switch changes it for everyone, including what the assistant reads." Also: CHANGELOG.md.

### CQ-189 Explain state that a hidden rule decides

● **Rule:** none · **Raised by:** design-critic (advisory) · **Severity:** MEDIUM · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any UI
● **Symptom:** The rule that the word CLOSED in a name closes a channel was invisible, so a channel such as "Closed-Loop Tests" would land in Closed with no reason given.
● **Root cause:** The UI showed the rule's outcome but not the rule.
● **Fix:** Closed channels are tagged "Archived" or "Closed by name", and the conversation's note says the name carries CLOSED and that taking the word out of the name in Mattermost reopens the channel at the next sweep.
● **Guard:** views.test.tsx asserts the closed-by-name note text and the "Closed by name" tag; parts.test.tsx asserts the tag on the switchboard.
● **Lesson:** When the system classifies an item by a rule, show which rule fired and how the user can change the outcome.
● **Evidence:** gate report: Design critique of the Comms console: "would land in Closed with no reason given." Also: docs/AUDIT-LOG.md, V0.12 row.

### CQ-190 Keep a new-content prompt visible while the user scrolls

● **Rule:** none · **Raised by:** design-critic (advisory) · **Severity:** MEDIUM · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any feed UI; CSS
● **Symptom:** The "Show N new messages" pill scrolled away with the list, so a reader further down never saw it.
● **Root cause:** The prompt sat in the scrolling flow.
● **Fix:** The feed's status line is `position: sticky; top: 0`, and the conversation's sticks to the bottom.
● **Guard:** None recorded.
● **Lesson:** Prompts about newly arrived content belong in a sticky position, or they reach only users who are already at the top.
● **Evidence:** gate report: Design critique of the Comms console: "pill scrolls away with the list, so a reader further down never sees it." Also: frontend/src/styles/tokens.css at f8a00bd.

### CQ-191 Empty and unconfigured states must speak to the user's situation, not the developer's

● **Rule:** none · **Raised by:** found in the V0.2 fusion of the imported code (raiser not recorded); verification (V0.5 tests); engineering-reviewer (Comms round 1, doc drift) · **Severity:** not graded (V0.2, V0.5); minor (Comms round 1) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (fixed in 55ab9f1); V0.5 (found, deferred); Comms round 1 at c9e3acc (raised), V0.12 (fixed in 0a60d93)
● **Applies to:** any UI fronting an optional integration
● **Symptom:** The empty Comms page told analysts to edit a local `.env` file (V0.2); Comms showed its set-up advice when a channel filter matched nothing (V0.5); later the page said Holly keeps pulling the channels it already knows even when Mattermost was not configured and nothing was pulled.
● **Root cause:** Developer copy carried into user-facing text, and no signal from the server that the integration was unconfigured, so the page guessed.
● **Fix:** The `.env` advice removed (V0.2); the sweep state the API returns gains `configured`, and the page says Holly pulls nothing while Mattermost is not configured (0a60d93). The V0.12 rewrite of the page replaced the empty-filter message (inference).
● **Guard:** Mattermost.test.tsx "says Holly pulls nothing while Mattermost is not configured"; the backend not-configured mutant killed by the V0.12 engineering gate.
● **Lesson:** Distinguish "not configured", "nothing matches" and "nothing yet" with a server-provided signal, and word each for the person looking at it; setup steps belong in the operator docs.
● **Evidence:** CHANGELOG.md: "The empty Comms page no longer tells analysts to edit a local '.env' file." Also: gate report: Engineering gate on V0.11 round 1; src/app/schemas/mattermost.py at 0a60d93.

### CQ-192 Read UI copy in every context it appears, for grammar, units and wording

● **Rule:** none · **Raised by:** engineering-reviewer (V0.10 nit); design-critic (V0.12, LOW) · **Severity:** nit (V0.10); LOW (V0.12) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (busy wording, raised round 1, fixed round 2); Comms design review at c9e3acc (copy, raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any UI
● **Symptom:** V0.10: the shared password-check helper's 503 read "Sign-in is busy" when it appeared on the password page. V0.12: "is closed since", "No message holds", an interval shown as "every 300 seconds", and "#" only before the first name when several channels were chosen.
● **Root cause:** Copy written for one caller of a shared helper, and copy written alongside code without a read-through.
● **Fix:** The helper takes a `busy` parameter and the change route passes "Password checks are busy."; "has been closed since", "No message contains", and an `everyLabel` helper that states the interval in minutes. Picked channels are now shown as chips (inference that this retired the "#" wording).
● **Guard:** A "change route's busy wording" mutant killed in V0.10 round 2; views.test.tsx asserts "No message contains"; parts.test.tsx "says how often in minutes, or in seconds when it is not whole minutes".
● **Lesson:** Parameterise user-facing text in shared helpers, state durations in human units, and review copy as a deliverable, not a by-product of code.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "The 503 message reads "Sign-in is busy" when it appears on the password page." Also: gate report: Design critique of the Comms console; src/app/api/v1/routes/auth.py at af13871.

### CQ-193 Give small touch targets a 24 pixel minimum

● **Rule:** `WCAG 2.2 2.5.8 (Target Size, Minimum)` · **Raised by:** design-critic (advisory) · **Severity:** LOW · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any web UI; CSS
● **Symptom:** The follow switch was about 20px tall; spacing probably saved it under WCAG 2.5.8, but it was tight for touch.
● **Root cause:** Compact control sizing.
● **Fix:** `min-height: 24px` on the follow switch.
● **Guard:** None recorded.
● **Lesson:** Set a 24 pixel minimum on compact controls rather than relying on spacing exceptions.
● **Evidence:** gate report: Design critique of the Comms console: "The follow switch is about 20px tall." Also: frontend/src/styles/tokens.css at 62ba4aa.

### CQ-194 Keep a heading hierarchy: a run of h3 headings needs its own h2

● **Rule:** `WCAG 2.2 1.3.1 (Info and Relationships)` · **Raised by:** design-critic (advisory) · **Severity:** LOW · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (fixed, ported in 62ba4aa)
● **Applies to:** any web UI
● **Symptom:** The feed had no h2, so its day headings (h3) read as sections of "Channels".
● **Root cause:** Visual layout built without an outline check.
● **Fix:** A visually hidden h2, "Messages", heads the feed.
● **Guard:** views.test.tsx asserts a heading named "Messages".
● **Lesson:** Check the heading outline of each view; a visually obvious region still needs a heading for screen reader navigation.
● **Evidence:** gate report: Design critique of the Comms console: "The feed has no h2, so its day headings (h3) read as sections of" Also: session summaries; frontend/src/components/comms/views.test.tsx at f8a00bd.

### CQ-195 Use spacing tokens instead of raw pixel values that already exist as tokens

● **Rule:** none · **Raised by:** design-critic (advisory) · **Severity:** LOW · **Status:** resolved · **Certainty:** mixed
● **Releases:** Comms design review at c9e3acc (raised), V0.12 (ported in 62ba4aa)
● **Applies to:** any web UI; CSS custom properties
● **Symptom:** Several Comms spacings were raw pixel values (32px, 4px, 16px, 8px) that exist as `--space-6`, `--space-1`, `--space-4` and `--space-2`, for example `max-height: calc(100vh - 32px)` and `margin-top: 4px` in c9e3acc.
● **Root cause:** Hand-typed values while building the console.
● **Fix:** At 62ba4aa the switchboard's `calc(100vh - 32px)` reads `var(--space-6)`, `.switchboard-meta` uses `--space-1` and `--space-4`, and the follow switch's 8px padding is `--space-2` (its 6px gap became `--space-1`; its 2px and 3px paddings stay raw) (fact, from git). `.segmented button`, also cited by the critic, keeps `padding: 6px 14px` at f8a00bd. That the change answered the finding is inference.
● **Guard:** None; `scripts/contrast-check.mjs` checks colour tokens only.
● **Lesson:** If spacing has tokens, lint for raw lengths that equal a token value, as is already done for colours.
● **Evidence:** gate report: Design critique of the Comms console: "Some spacings are raw pixel values that already exist as tokens: 32px, 4px, 16px, 8px." Also: frontend/src/styles/tokens.css at c9e3acc; frontend/src/styles/tokens.css at 62ba4aa; frontend/src/styles/tokens.css at f8a00bd.

### CQ-196 Case-insensitive match offsets shift when lower-casing changes a string's length

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor (cosmetic) · **Status:** resolved · **Certainty:** fact
● **Releases:** Comms round 1 at c9e3acc (raised), V0.12 (fixed in 0a60d93); V0.13 (offsets unchanged by the S4138 and S7723 rewrites of `lowered`, checked by the security gate)
● **Applies to:** JavaScript and TypeScript; any text search highlighting
● **Symptom:** Search highlights could land in the wrong place: `matchParts` found matches in a lower-cased copy, so a character whose lower case is longer, such as "İ" (U+0130), shifted every highlight after it.
● **Root cause:** Indexes found in the lower-cased string were applied to the original.
● **Fix:** `matchParts` maps each lowered unit back to its source character's start and end (the `lowered` helper), so each highlight stays on its own letters. In V0.13 the security gate compared the old and new offset code over every code point from U+0000 to U+2FFFF (round 1) and over 200,000 random inputs (round 2), with 0 differences.
● **Guard:** comms.test.ts "keeps each highlight on its own letters after one that lowers to two"; the V0.12 gate killed the fix's mutant.
● **Lesson:** Never reuse offsets from a case-folded or normalised copy on the original string; map them back per character, and test with characters whose case mapping changes length.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "'matchParts' finds matches in a lower-cased copy, so a character whose lower case is longer (such as "İ") shifts the highlight. Cosmetic." Also: CHANGELOG.md; gate report: Security gate V0.13 (fast); gate report: Security gate V0.13 round 2.

### CQ-197 Alert banners in a fixed-height shell can crowd out the page

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.3 (present), V0.4 (raised rounds 3 and 4, accepted with a trip-wire in SECURITY.md)
● **Applies to:** any web UI with stacked alerts; CSS layout
● **Symptom:** With several event timers firing at once, the banners fill the fixed-height layout and the page's content and navigation go out of reach: from 4 timers with short labels on a 601 by 481 window, and from 2 with labels of 100 characters or more. V0.3 lost the page within one timer of the same counts.
● **Root cause:** Above 600 by 480 pixels the header, the firing banners and the page share a fixed height, and each banner grows with its label (up to 200 characters).
● **Fix:** The header never shrinks under banners, so Sign out stays whole, and every Dismiss button can be scrolled to; the gate's tested fix (cap the banner area at 40% of the window and let it scroll) was left to the owner as a design call, since it would hide alerts behind a scroll. Recorded in SECURITY.md with measured counts by label length and window size.
● **Guard:** SECURITY.md trip-wire: two or more 100-character timers or four or more of any length firing in use, any change to the header, banners, shell height rules or label limit, or a report that the page vanished under banners.
● **Lesson:** Bound the space alerts can take (a capped, scrollable banner area) or let the page scroll; growable banners in a fixed-height shell will eventually hide the content they warn about.
● **Evidence:** docs/AUDIT-LOG.md, V0.4 row: "the header never shrinks under firing banners, so Sign out stays whole where it had shrunk to a 10-pixel strip" Also: SECURITY.md.

### CQ-198 Protected pages render before the current user is known

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.10 (raised round 1 as a nit, accepted round 2)
● **Applies to:** React Router; any single-page app with client-side route guards
● **Symptom:** `ProtectedRoute` rendered protected pages while the user was still unknown, the source of two one-off 403s after sign-in when a password change was due.
● **Root cause:** The route guard treats "token held, user not yet loaded" as signed in.
● **Fix:** Left as it was: rendering nothing would blank the page on a failed `/auth/me`, and the two 403s are harmless; the round 2 engineering gate accepted the reasoning.
● **Guard:** none recorded
● **Lesson:** Decide explicitly what a route guard renders while identity is loading, weighing early requests that will be refused against a blank page when the identity call fails.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "Protected pages render while the user is still unknown, which is where the 2 one-off 403s after sign-in come from." Also: docs/AUDIT-LOG.md, V0.10 row; gate report: Engineering gate on V0.10 round 2.

### CQ-199 Form fields without accessible names, and repeated button names

● **Rule:** `WCAG 2.2 4.1.2 (Name, Role, Value) and 2.4.6 (Headings and Labels)` · **Raised by:** verification loop (found while writing V0.5's dashboard tests) · **Severity:** not graded · **Status:** deferred · **Certainty:** fact
● **Releases:** V0.5 (found, deferred), V0.6 (carried open), still open at V0.13
● **Applies to:** React and TypeScript; any web UI
● **Symptom:** The shift log's text boxes have no accessible name (a placeholder only) and its entry buttons repeat the same names, so a screen reader cannot tell one note's controls from another's.
● **Root cause:** Imported page built with placeholders and repeated visible labels.
● **Fix:** None; recorded in V0.5 and carried open in V0.6. At f8a00bd the new-entry textarea still has a placeholder and no label, and the edit textarea has neither (fact, from the code).
● **Guard:** none recorded
● **Lesson:** Every input needs a programmatic label (a placeholder is not one), and repeated controls need names that include their item; querying by role and name in component tests exposes both.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "the shift log's text boxes have no accessible name and its entry buttons repeat the same names" Also: frontend/src/pages/ShiftLog.tsx at f8a00bd.

### CQ-200 A contrast checker's simplifications leave blind spots that must be listed and tracked

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer (minors below the blocking bar) · **Severity:** minor · **Status:** deferred · **Certainty:** fact
● **Releases:** V0.4 (raised round 7, deferred)
● **Applies to:** any custom CSS or accessibility checker
● **Symptom:** Open after round 7: the check measures a colour a `@keyframes` block animates only at its steps, where Chromium passes through colours between them (a swap of text and background reaching 1.02:1); it takes the scanlines to be black without reading their colour; it reads a token from `--name:` anywhere in the first `:root` block, so a declaration CSS drops (such as `x--color-text`) or a conditional `:root` can feed it; it passes a background in `currentColor`. Also open: a tint's token name has no case, the easing case uses one that cannot overshoot, and (for the licence plugin) a hand-written `data:` URI stops the build only in the double-quoted form.
● **Root cause:** Static analysis of CSS simplifies what the browser computes.
● **Fix:** None. Holly's own sheet animates only the pulse's tint, paints its scanlines black and holds none of those forms (fact, from the audit row).
● **Guard:** none recorded
● **Lesson:** When a home-grown checker cannot see a form, list the limit in its header and record a trip-wire, or refuse the form outright, as Holly's check does for many others.
● **Evidence:** docs/AUDIT-LOG.md, V0.4 row: "the check measures a colour a @keyframes block animates only at its steps, where Chromium passes through colours between them, a swap of text and background reaching 1.02:1"

### CQ-201 Imported front-end code that never passed a type-checked build

● **Rule:** none · **Raised by:** found in the V0.2 fusion of the imported Daily Operations Dashboard (raiser not recorded) · **Severity:** not graded · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (found and fixed in 55ab9f1)
● **Applies to:** TypeScript front ends
● **Symptom:** The dashboard did not compile as uploaded: `SortDirection` was imported in three files and defined in none.
● **Root cause:** The imported code had evidently never been through a type-checked build (inference from the defect).
● **Fix:** `SortDirection` defined; the dashboard's ESLint, Prettier, build and Vitest run in `scripts/verify.sh`.
● **Guard:** The dashboard steps in `scripts/verify.sh` (install from the lockfile, lint, format, types and build, unit tests).
● **Lesson:** Before building on imported front-end code, run its type check and production build; a project that has never compiled cannot be trusted to have run.
● **Evidence:** CHANGELOG.md: "The dashboard did not compile as uploaded: 'SortDirection' was imported in three files and defined in none." Also: commit messages (git log); docs/AUDIT-LOG.md, V0.2 row.

### CQ-202 An inserted helper separated a function from its doc comment

● **Rule:** `none (the SonarQube sweep found no rule that fires on comment placement)` · **Raised by:** engineering-reviewer; also security-reviewer and the SonarQube sweep's maintainability and reliability finders · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.13 (raised round 1 at 559a9d0, fixed in 6085a53)
● **Applies to:** any stack
● **Symptom:** The new `unseen` helper in `utils/comms.ts` went in between `alsoAsked`'s two-line comment (207-208) and `alsoAsked` itself, so the comment headed `unseen` and `alsoAsked` at :215 had none.
● **Root cause:** The new block was inserted between a declaration and its leading comment.
● **Fix:** 6085a53 moved `alsoAsked`'s comment back above `export function alsoAsked`.
● **Guard:** none recorded
● **Lesson:** Insert new declarations above a function's leading comment, not between the two, and read the diff for comments that now describe the wrong code.
● **Evidence:** gate report: Engineering gate V0.13 (fast): "'alsoAsked''s doc comment (207-208) now sits above 'unseen''s comment and function, so 'alsoAsked' at ':215' has no comment." Also: gate report: find:maintainability; commit messages (git log).

### CQ-203 User-facing text hard-coded a value the logic reads from the record

● **Rule:** none · **Raised by:** found in the imported Daily Operations Dashboard during the fusion (who found it is not recorded) · **Severity:** not recorded · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (found in the imported code, fixed at the fusion in 55ab9f1)
● **Applies to:** any UI; React and TypeScript
● **Symptom:** In the imported dashboard, an event timer's pre-alert window started at the timer's own pre_alert_minutes, but its badge read '5-min alert' and its browser notification 'Event in 5 minutes', whatever lead time the timer held. Files: frontend/src/components/EventTimersPanel.tsx, frontend/src/context/EventTimersContext.tsx.
● **Root cause:** The alert window was computed from the stored field while the badge and notification text carried a literal.
● **Fix:** 55ab9f1 renders the badge and notification from pre_alert_minutes (`{timer.pre_alert_minutes}-min alert`, `Event in ${t.pre_alert_minutes} min`).
● **Guard:** none recorded
● **Lesson:** Build user-facing text from the same value the behaviour uses; a literal in a message beside a configurable setting drifts from it the first time the setting changes.
● **Evidence:** CHANGELOG.md: "The pre-alert badge and browser notification give the timer's own lead time, not a fixed 5 minutes." Also: frontend/src/context/EventTimersContext.tsx at 0717c05; git show 55ab9f1 -- frontend/src/components/EventTimersPanel.tsx.

### CQ-204 A responsive override block placed before the rules it overrides never applies

● **Rule:** `none (arose in the WCAG 2.2 1.4.10 Reflow work)` · **Raised by:** engineering-reviewer and security-reviewer, both FAIL in round 2 (which gate named this item is not recorded) · **Severity:** not recorded (both gates failed the round) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.4 (raised in round 2, fixed in round 3, committed in 05bd528)
● **Applies to:** CSS in any web front end
● **Symptom:** In round 2 of Holly's theme work, the 760-pixel media block in frontend/src/styles/tokens.css sat above the rules it overrides, so three of its values never applied.
● **Root cause:** A media query adds no specificity, so an override placed earlier in the sheet loses to a later base rule of equal specificity (inference: standard CSS cascade).
● **Fix:** Round 3 moves the 760-pixel block after the rules it overrides (committed in 05bd528).
● **Guard:** in the gate evidence, each of the 19 reflow rules was removed alone and its browser check went red against a green baseline; no loop check recorded
● **Lesson:** Place each media-query override after the base rules it changes, and prove every responsive rule with a check that goes red when that rule alone is removed.
● **Evidence:** docs/AUDIT-LOG.md, V0.4 row: "The second round wrapped the header below 760 pixels and stacked the navigation below 600, and both gates failed it" Also: commit messages (git log).

### CQ-205 Declare the colour scheme so browser-drawn controls follow a custom dark theme

● **Rule:** none · **Raised by:** design-critic (advisory) for b94e742; who raised the file picker's button is not recorded · **Severity:** not recorded · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.4 (the file picker's button fixed in 63f0ddd; native controls, date pickers and autofill fixed in b94e742 after the design review)
● **Applies to:** CSS theming in any web front end
● **Symptom:** Under Holly's V0.4 dark theme, the native button beside a file field kept the browser's light default, the one unthemed control on the procedures page; native controls, date pickers and autofill also had to be brought onto the dark theme. File: frontend/src/styles/tokens.css.
● **Root cause:** The browser draws native controls and their pseudo-elements in its own colours unless the page declares a colour scheme or styles them, and the token-based contrast check cannot see the browser's own colours where no rule sets one.
● **Fix:** 63f0ddd styles the file selector button as the theme's plate, with its pair measured by the contrast check; b94e742 adds color-scheme: dark to the theme tokens so native controls, autofill and pickers follow the dark theme.
● **Guard:** scripts/contrast-check.mjs measures the file button's pair and lists the browser's own colours among what it cannot see
● **Lesson:** With a custom dark theme, declare color-scheme and style native pseudo-elements explicitly, then inspect every native control (file, date, select, autofill, scrollbars) in a browser, since a token-based contrast checker cannot see colours the browser chooses.
● **Evidence:** commit messages (git log): "The native button beside a file field kept the browser's light default," Also: docs/AUDIT-LOG.md, V0.4 row; frontend/src/styles/tokens.css at f8a00bd.

### CQ-206 A client-side validation message outlives the input it complained about

● **Rule:** none · **Raised by:** found while writing the V0.5 dashboard tests (recorded in the V0.5 row) · **Severity:** not recorded · **Status:** open · **Certainty:** fact
● **Releases:** V0.5 (recorded as a defect while writing tests), V0.6 (carried open among the 11 recorded defects), open at V0.13 (HEAD f8a00bd)
● **Applies to:** any form UI; React and TypeScript
● **Symptom:** On Holly's Maneuvers page, a satellite number that does not parse sets 'Satellite number must be numeric.' and returns; the message stays until the next load, reachable only where the type="number" field lets free text through. File: frontend/src/pages/Maneuvers.tsx.
● **Root cause:** The submit handler sets the page-level error and returns; only the load effect clears it, so the message is not tied to the field's current value.
● **Fix:** none; recorded in V0.5's row and carried in V0.6's open items; the code is unchanged at HEAD
● **Guard:** none (the V0.5 row records that no test holds the defects in place)
● **Lesson:** Tie a validation message to the field's current value: clear it when the input changes or validates, not on an unrelated reload.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "'Maneuvers.tsx:81' keeps its "must be numeric" message until the next load, reachable only where the number field takes free text" Also: docs/AUDIT-LOG.md, V0.6 row; frontend/src/pages/Maneuvers.tsx at f8a00bd.

### CQ-207 The language library target limits which modern APIs code and analyser-suggested fixes may use

● **Rule:** `typescript:S7755 and unicorn/no-array-reverse suggest APIs above the ES2020 lib (neither reported by the platform)` · **Raised by:** found while writing the V0.12 Comms code (how it was caught is not recorded); noted again by the V0.13 SonarQube sweep's finder and a verifier · **Severity:** not recorded · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.12 (hit while writing the Comms code), V0.13 (noted by the SonarQube sweep)
● **Applies to:** TypeScript (tsconfig lib and target); any analyser-driven refactoring
● **Symptom:** Holly's dashboard tsconfig targets lib ES2020, so Array.prototype.at was unavailable while writing the Comms code and a latest() helper took its place. In the V0.13 sweep, the finder explained S7755 (prefer .at) as not applying because lib ES2020 lacks .at, and a verifier advised against changing `[...page.items].reverse()` to toReversed, which is ES2023. Files: frontend/tsconfig.json, frontend/src/components/comms/ChannelConversation.tsx, frontend/src/components/comms/views.test.tsx.
● **Root cause:** Analyser rules recommend built-ins newer than the project's library target, so applying a rule's suggested fix can break the type-checked build.
● **Fix:** A helper in place of Array.at; `[...page.items].reverse()` left as it is, since SonarQube did not report it.
● **Guard:** tsc in the dashboard's build script (tsc && vite build) refuses APIs outside the lib
● **Lesson:** Before applying an analyser's 'use the newer API' suggestion, check it against the project's language and library target; raise the target deliberately or keep the older form, and do not chase rules the platform does not report.
● **Evidence:** session summaries: "The lib is ES2020: no 'Array.at'. Use a 'latest()' helper." Also: frontend/src/components/comms/views.test.tsx at f8a00bd; gate report: find:security-and-config; gate report: verify:unicorn/no-array-reverse@ChannelConversation.tsx:160#7.

## 2.5 Testing


### CQ-208 No local test rung modelled the platform's ingress gateway, so an auth failure seen only in production passed every check

● **Rule:** none · **Raised by:** app owner, from the deployed App Store app; engineering-reviewer (V0.9 round 1 minor: the real gap is that no local rung has a gateway) · **Severity:** platform failure (sign-in unusable in production) · **Status:** open · **Certainty:** mixed
● **Releases:** V0.8 (failed in production), V0.9 (worked around; no gateway rung added)
● **Applies to:** any containerised web app deployed behind a platform gateway or ingress
● **Symptom:** V0.8 passed the verification loop, the pipeline simulation, the container smoke rung and all 11 App Store stages and went Active, yet signing in returned the admin to the sign-in page at once: the gateway in front of the app answered 401 to Holly's own bearer token in Authorization. Reproducing it needed an ad hoc proxy stand-in and a headless browser outside the repository. scripts/smoke-container.sh now proves only Holly's side (a token in X-Holly-Token answers 200, one in Authorization 401).
● **Root cause:** Every local rung calls the container directly; the gateway exists only on the platform, and nothing in the repository imitates it. That the gateway refuses before the app sees the request is inference in the record, from the missing headers and the wording.
● **Fix:** V0.9 moved the token to X-Holly-Token (ADR-013), made the shared Vitest adapter answer 401 to any request carrying Authorization, extended the smoke rung, and used a gateway stand-in outside the repository to show V0.8 bouncing and V0.9 staying signed in. The stand-in was not committed.
● **Guard:** Smoke step and the gateway-like Vitest adapter (the app's side only); no gateway rung in the repository.
● **Lesson:** When the platform puts a gateway or proxy in front of the app, add a rung that imitates its refusals and run the real browser journey through it; a green suite against the bare container proves nothing about what the gateway does.
● **Evidence:** docs/AUDIT-LOG.md, V0.9 row: "V0.8 (0ebea48) went Active with all 11 stages passed; signing in as the admin showed the dashboard and returned to the sign-in page at once" Also: gate report: Engineering gate on V0.9 round 1.

### CQ-209 A second language's code was barely tested against a platform coverage floor that scores it

● **Rule:** `none (the App Store Code Quality gate's 80% coverage floor)` · **Raised by:** author, against the platform's Code Quality floor; engineering-reviewer (nit on the lcov check) · **Severity:** blocking risk at the platform's Code Quality gate (caught before upload) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.5 (raised and fixed)
● **Applies to:** polyglot repositories scored by SonarQube or a similar coverage gate
● **Symptom:** 117 of the dashboard's 1,002 TypeScript lines (11.67%) and 75 of its 708 branches were tested, against the 80% the App Store's Code Quality gate holds an upload to; only the Python suite had been measured. The first lcov report named a test setup file that Vitest leaves out of every report, and the loop at first checked only that coverage/lcov.info existed.
● **Root cause:** The imported dashboard had only a few logic unit tests and coverage was measured for Python alone. That the platform scores a file missing from the report at 0% is recorded as inference, not confirmed by the platform team.
● **Fix:** Vitest renders every page, component and context in jsdom with Testing Library (273 tests, 99.8% of lines), with an 80% floor on lines, branches, functions and statements, and writes coverage/lcov.info at the repository root with paths from there; test globals replaced the setup file.
● **Guard:** Vitest thresholds in frontend/vite.config.ts; scripts/check-lcov.sh, run by the loop and the pipeline simulation, refuses a report that does not name exactly the non-test files under frontend/src.
● **Lesson:** Measure coverage for every language the quality gate scores from the first commit, and check that the report names every source file by the path the gate resolves, since a file left out can count as 0%.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "117 of the dashboard's 1,002 lines (11.67%) and 75 of its 708 branches were tested, against the 80% the platform's Code Quality gate holds an upload to"

### CQ-210 A concurrency control that only matters with two starters had no test that fails without it

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (raised gate round 1, fixed in e0d7f34 before round 2)
● **Applies to:** any stack with start-up migrations or shared locks (PostgreSQL advisory locks especially)
● **Symptom:** Nothing failed if the migration advisory lock in src/app/migrate.py were deleted: the unit tests ran migrations offline, and one container starts the same with or without the lock.
● **Root cause:** The lock changes behaviour only when two processes start at once, and no test arranged that.
● **Fix:** The container smoke rung holds the packaged lock key from a psql session, starts Holly and requires it to report migrations applied only after the session frees it; a variant image without the lock was shown to fail the check.
● **Guard:** Migration-lock check in scripts/smoke-container.sh, run before every upload.
● **Lesson:** For a lock or other concurrency control, write a test that holds the contended resource from outside and asserts the second party waits, and prove it against a build without the control.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "nothing proved the migration advisory lock" Also: commit messages (git log).

### CQ-211 A load-bearing security line added as a fix had no test, so removing it left the suite green

● **Rule:** none · **Raised by:** engineering-reviewer (MAJOR) and security-reviewer (minor) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (suggested as a security nit in gate round 1, added in round 2's fixes, raised as unpinned in gate round 2, pinned in round 3)
● **Applies to:** any stack; shell and git tooling especially
● **Symptom:** `unset GIT_CONFIG_PARAMETERS` in scripts/check-baseline.sh and scripts/check-reviews.sh, added in round 2's fixes after a round 1 security nit that the variable could turn git's commit-graph back on, was untested: with either line deleted the upload nets stayed green, and the engineering gate showed a forged commit-graph then passed both checks.
● **Root cause:** The fix was added without a matching case in scripts/test-package-nets.sh.
● **Fix:** Each forged-commit-graph case runs again with GIT_CONFIG_PARAMETERS turning the graph on, red with either unset removed (200 cases).
● **Guard:** Nets cases for verdicts before the bump and for an upload changed under the baseline's version, each behind a forged commit-graph and GIT_CONFIG_PARAMETERS.
● **Lesson:** Every line added to close a security finding needs its own case that fails when that line alone is removed; delete the line and run the suite before calling the fix done.
● **Evidence:** gate report: Engineering gate, V0.6 round 2: "The suite does not test 'unset GIT_CONFIG_PARAMETERS', which is a load-bearing control." Also: docs/AUDIT-LOG.md, V0.6 row.

### CQ-212 A skip-list entry was untested because the test lacked the precondition that makes the entry matter

● **Rule:** none · **Raised by:** engineering-reviewer (MAJOR) and security-reviewer (minor) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised round 2, fixed round 3)
● **Applies to:** HTTP clients with refresh-and-retry interceptors; any guard test
● **Symptom:** Removing /auth/login from the new SESSION_CALLS set in frontend/src/api/client.ts left all 284 Vitest tests green. With a refresh token held, a wrong password would then trigger a refresh, resend the password, spend the refresh token, count twice against the sign-in limit and write two audit rows.
● **Root cause:** The test that a failed sign-in never refreshes held no refresh token, so the refresh attempt threw before any request whether or not the entry existed.
● **Fix:** The test stores a refresh token, spies on the refresh call and counts sign-in posts, asserting no refresh, exactly one sign-in and no redirect.
● **Guard:** Vitest case 'never tries to refresh a failed sign-in, even with a refresh token held'; mutant F9 killed in round 3.
● **Lesson:** Set up the state in which a guard would change the outcome (here, a refresh token held) before asserting the guard's effect, or the test passes for an unrelated reason.
● **Evidence:** gate report: Engineering gate on V0.9 round 2: "the '/auth/login' entry in 'SESSION_CALLS' is new in round 2, and no test holds it." Also: gate report: Security gate on V0.9 round 2; gate report: Engineering gate on V0.9 round 3.

### CQ-213 A test double did not refuse what the real upstream refuses, so the retry path could reintroduce a production fault

● **Rule:** none · **Raised by:** engineering-reviewer (MAJOR); security-reviewer (nit) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised round 1, fixed round 2)
● **Applies to:** any client tested against a fake transport or mock server
● **Symptom:** Mutants making the refresh-and-retry path in frontend/src/api/client.ts send Authorization instead of, or beside, X-Holly-Token kept all 282 Vitest tests green; behind the gateway that would bring back the sign-in bounce about 30 minutes into a session.
● **Root cause:** The retry passes back through the request interceptor, and the tests asserted only that X-Holly-Token was present, never that Authorization was absent; the test adapter accepted any header.
● **Fix:** The shared Vitest adapter answers 401 to any request carrying Authorization, whatever the handler says, as the gateway did, so no call, first or retried, may send it; a test asserts Authorization is absent on an ordinary call.
● **Guard:** The gateway-like adapter in frontend/src/api/client.test.ts; in round 2 the 'retry sends Authorization' and 'retry adds Authorization too' mutants each turned 3 tests red.
● **Lesson:** Make a shared fake enforce the real upstream's refusals for every request, so every path, retries included, is checked for what it must not send as well as what it must.
● **Evidence:** gate report: Engineering gate on V0.9 round 1: "Nothing checks that the refresh-and-retry path never sends 'Authorization'." Also: 83e9696.

### CQ-214 A wire-contract name defined separately in server and client had no parity test

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised round 1, fixed round 2)
● **Applies to:** client and server pairs in different languages
● **Symptom:** TOKEN_HEADER was declared in src/app/dependencies.py and in frontend/src/api/client.ts. A typo in the client kept all 282 Vitest tests green, and one in the server kept the 200 tests of three server suites green; only the smoke rung's literal would catch the server side, so a drift would ship the sign-in loop again with every check green.
● **Root cause:** Each suite imported its own copy of the constant, so each stayed self-consistent while the two could disagree.
● **Fix:** tests/test_token_header.py reads client.ts, extracts the exported TOKEN_HEADER literal with an anchored regex, asserts exactly one definition equal to the server's constant, and pins the server literal.
● **Guard:** tests/test_token_header.py; in round 2 a server typo, a client typo, 'as const', a lower-case name and a second definition each turned it red.
● **Lesson:** Any constant shared across runtimes (header names, limits, enumerations) needs a parity test that reads both definitions from source, holds them equal and pins the literal.
● **Evidence:** gate report: Engineering gate on V0.9 round 1: "The header name is defined separately in the server and the dashboard, with no parity test." Also: 83e9696; docs/AUDIT-LOG.md, V0.9 row.

### CQ-215 A validation rule written twice in two languages had no parity test, and the copies disagreed at the edges

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 1, fixed round 2)
● **Applies to:** JavaScript or TypeScript clients with Python or other servers
● **Symptom:** The password rule (12 to 1,024 characters, not spaces alone) lived in frontend/src/utils/passwords.ts and src/app/schemas/auth.py. JavaScript counted UTF-16 code units and pydantic counts code points, so 6 astral emoji passed the client and failed the server, and 12 U+FEFF characters failed the client as spaces but passed the server. This came one release after the same class of finding on the token header.
● **Root cause:** Different string semantics (UTF-16 length, JavaScript trim against Python str.isspace) and nothing holding the copies equal; a comment claimed the server held the same rule.
● **Fix:** The client counts code points ([...password].length) and uses an explicit PYTHON_SPACES set equal to Python's str.isspace(); tests/test_password_rule.py reads the TypeScript constants and holds the lengths and the spaces set equal to the server's.
● **Guard:** tests/test_password_rule.py, which catches dropping U+001C, adding U+FEFF, or changing either bound in the TypeScript file.
● **Lesson:** When a rule must hold on both sides, either validate on the server alone and show its message, or add a parity test; exercise the copies with astral and Unicode-space input where the languages count and trim differently.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "**The password rule is written on both sides with no parity test, and the two sides already disagree.**" Also: gate report: Engineering gate on V0.10 round 2.

### CQ-216 The client half of a multi-step journey had no test with its real providers mounted, so removing key steps passed the suite

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 1, fixed round 2)
● **Applies to:** React or other single-page apps with auth contexts and route guards
● **Symptom:** Three dashboard mutants passed all of Vitest: F01 deleted the user re-read after a forced password change (the user landed back on an empty /password form), and F15 and F16 let a 403 or a 400 trigger a token refresh like a 401 (a wrong current password sent and counted twice, then sign-out; the change-due 403 signing the user out). The first journey test written to fix it still missed the re-read mutant.
● **Root cause:** ChangePassword was tested without ProtectedRoute and AuthProvider, the client's refresh-only-on-401 rule was reasoned but never pinned, and the first journey test's mock answered before the missing step could matter.
● **Fix:** A journey test mounts AuthProvider, ProtectedRoute and ChangePassword together and asserts '/' after a due change, with a delayed re-read mock; client tests assert a 400 and a 403 reach the caller with no refresh and both tokens kept.
● **Guard:** Mutants F01, F01b, F15, F16, F17 and F18 killed in round 2.
● **Lesson:** Test a multi-step flow with its real providers and route guards mounted together, and make mocks answer late enough that a missing step changes the outcome.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "**No test protects the dashboard's half of the forced-change journey: 3 mutants pass the whole Vitest suite.**" Also: gate report: Engineering gate on V0.10 round 2; session summaries.

### CQ-217 A single-flight guard on a background job had no test that starts a second run during the first

● **Rule:** none · **Raised by:** engineering-reviewer (MAJOR) and security-reviewer (mutant M35) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review, run as 'V0.11 round 1'; fixed in 0a60d93)
● **Applies to:** any stack with background jobs that can also be triggered on demand
● **Symptom:** Replacing the single-flight call at src/app/services/background_refresh.py:271 with a direct call left 255 tests green; without it, two Mattermost cycles running together on PostgreSQL failed with UniqueViolationError on uq_mattermost_channel_mm_channel_id (reproduced by the gate).
● **Root cause:** No test started a second run_mattermost_now while one was running.
● **Fix:** test_a_sweep_on_demand_during_a_running_cycle_joins_it asserts that an on-demand sweep during a running cycle joins it: one ingest call, the same result.
● **Guard:** That test; the V0.12 round 1 engineering gate killed the single-flight mutant.
● **Lesson:** For a single-flight or de-duplication wrapper, hold the first call open, start a second, and assert one underlying call and a shared result.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "With a direct call instead, 255 tests stay green." Also: gate report: Security gate on V0.11 round 1; 0a60d93.

### CQ-218 Only well-shaped fakes were used, so the check that an upstream answer has the expected shape was untested

● **Rule:** none · **Raised by:** engineering-reviewer (MAJOR) and security-reviewer (mutant M37) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review; fixed in 0a60d93)
● **Applies to:** any service that consumes a third-party API
● **Symptom:** The JSON-array check at src/app/services/mattermost_client.py:94-96 was uncovered and could be deleted with the suite green. Without it, a 200 answer of {} for the teams list reads as no channels and marks every known channel lost.
● **Root cause:** Every fake Mattermost answer in the tests was well shaped.
● **Fix:** test_a_listing_that_is_not_a_json_array_is_a_client_error: a listing that is not a JSON array is a client error that fails the sweep and changes nothing.
● **Guard:** That test; the V0.12 round 1 engineering gate killed the JSON-array mutant.
● **Lesson:** Feed integration clients successful but wrongly shaped answers (an object where a list is expected, a wrapped list) and assert the job fails closed without changing stored state.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "These lines are uncovered, and deleting the check stays green." Also: gate report: Security gate on V0.11 round 1; 0a60d93.

### CQ-219 The commit and audit path of a job run that changes only metadata was untested

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR (first Comms review); minor (the skip-only case, V0.12 round 1) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review, fixed in 0a60d93; skip-only case raised round 1, fixed in f6056cd)
● **Applies to:** any stack with scheduled sync jobs and an audit trail
● **Symptom:** `_changed` (src/app/services/mattermost_ingest.py:273) and `or tally.sweep is not None` (:285) could each be deleted with the suite green, though the audit overview promises a mattermost.ingest row when a cycle only finds channels new, closed, reopened or lost. V0.12 round 1 then found a cycle that only skipped records wrote no audit row.
● **Root cause:** Tests covered cycles that pulled messages, not cycles whose only effect was on the channel list.
● **Fix:** Tests that a sweep which changed nothing and pulled nothing is committed but not audited, and that a sweep which only lost a channel is audited; f6056cd audits a skip-only sweep.
● **Guard:** test_a_sweep_that_changed_nothing_and_pulled_nothing_is_committed_not_audited and test_a_sweep_that_only_lost_a_channel_is_audited; the V0.12 round 1 engineering gate killed the _changed mutant, and round 2 killed the mutant dropping sweep.skipped from _changed.
● **Lesson:** List each kind of run outcome (data pulled, metadata only, records skipped only, nothing) and test what each commits and audits.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "Each can be deleted with the suite staying green." Also: gate report: Engineering gate V0.12; 0a60d93; commit messages (git log).

### CQ-220 Fixtures used only past timestamps, so the bound on an index derived from an external time was dead code to the suite

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review; fixed in 0a60d93)
● **Applies to:** any stack bucketing external timestamps
● **Symptom:** No test sent a Mattermost message dated in the future. Without the upper bound on the activity index at src/app/api/v1/routes/mattermost.py:133, a post an hour ahead raises IndexError and GET /channels answers 500.
● **Root cause:** Fixtures used only past timestamps.
● **Fix:** The channel list test includes an activity row at the current hour plus 1, which must not be drawn.
● **Guard:** The future-hour row in tests/test_mattermost_routes.py; the V0.12 round 1 engineering gate killed the future-hour mutant.
● **Lesson:** Put future, far-past and clock-skewed timestamps from external systems in fixtures, and bound every index computed from them.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "Without the bound, a post an hour ahead raises IndexError and the channel list answers 500" Also: 0a60d93; gate report: Engineering gate V0.12.

### CQ-221 A stale-response guard on first load stayed untested after an earlier review had asked for its test

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (asked for in the first Comms review; raised again round 1; fixed in f6056cd)
● **Applies to:** React and TypeScript with Vitest; any async UI
● **Symptom:** Deleting the first-load `if (cancelled) return;` in frontend/src/components/comms/CommsFeed.tsx:67 left the suite green, so a slow search or scope answer could overwrite a newer one; the same guard in ChannelConversation.tsx:69 also survived. The first Comms review had asked for this CommsFeed test; the fix round that followed added a stale-poll test instead.
● **Root cause:** No test resolved an older first-load request after a newer one; the requested test was not checked off by mutating the guard it named.
● **Fix:** Tests let answers resolve out of order and assert the newer result stays ('shows the answer to the latest ask, whatever order the answers come in' in views.test.tsx), in f6056cd.
● **Guard:** frontend/src/components/comms/views.test.tsx; the f6056cd message says each guard was proven by removing it (the author's own run; no later gate report names a mutation of this guard).
● **Lesson:** For each async effect guard, resolve requests out of order in a test, and close a reviewer's request for a test by mutating the exact guard named.
● **Evidence:** gate report: Engineering gate V0.12: "the first-load 'if (cancelled) return;' survived. A slow search or scope response can overwrite a newer one." Also: gate report: Engineering gate on V0.11 round 1; commit messages (git log).

### CQ-222 Polling clean-up and late-answer guards were untested after unmount

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR (round 1); minor (round 2) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (feed poll raised in the first Comms review, fixed in 0a60d93; conversation poll raised rounds 1 and 2, fixed in f6056cd and 6c712cc)
● **Applies to:** React and TypeScript with Vitest fake timers; any component that polls
● **Symptom:** Removing the CommsFeed poll's clean-up stayed green in the first Comms review, although Dashboard.test.tsx already tested this for the Dashboard. In V0.12 round 1, deleting the interval clean-up in ChannelConversation.tsx:133 left the suite green, so each channel switch would leak a poller; in round 2, deleting that poll's `if (cancelled) return` (:132) kept every test green.
● **Root cause:** Tests covered that a poll runs, not that it stops and ignores answers once the component is gone.
● **Fix:** Tests unmount, advance fake timers by the poll interval and expect no further call ('drops a poll answered after the scope changed, and stops polling once closed' in 0a60d93; 'stops polling once closed, and drops an answer that lands after' in f6056cd); a test drops a multi-page poll answered for a channel no longer shown (6c712cc).
● **Guard:** frontend/src/components/comms/views.test.tsx; round 3 mutation of each guard went red.
● **Lesson:** For every interval or subscription, test unmount: advance the clock and expect no further calls, and resolve an in-flight answer after unmount and expect no state change.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "Removing the clean-up stays green, although 'Dashboard.test.tsx:235-237' already tests this for the Dashboard." Also: gate report: Engineering gate V0.12; gate report: Engineering gate V0.12 round 2.

### CQ-223 A fix introduced a new guard without its own test

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised round 2, fixed in 6c712cc)
● **Applies to:** any stack
● **Symptom:** Deleting `if (asked.current !== scoped) return;` in showWaiting (frontend/src/components/comms/CommsFeed.tsx:130), which stops a slow reload of the latest page overwriting a scope or search the user has since changed, left all 56 Comms tests green. The guard was added by the round 1 fix itself.
● **Root cause:** The round 1 fix added a reload path and its guard without a race test for it.
● **Fix:** A test holds the reload's answer, changes the scope, releases the answer and asserts the new scope stays; round 3 mutation went red.
● **Guard:** views.test.tsx case 'drops a reload of the latest page answered after the scope changed'.
● **Lesson:** Treat each fix's diff as new code: every guard it adds needs a test that fails when that guard is removed, checked in the same round.
● **Evidence:** gate report: Engineering gate V0.12 round 2: "Deleting 'if (asked.current !== scoped) return;' leaves all 56 comms tests green." Also: gate report: Engineering gate V0.12 round 3; commit messages (git log).

### CQ-224 A new renderer shipped with most of its branches never rendered, hidden by a high whole-suite figure

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised round 1, fixed in f6056cd)
● **Applies to:** any UI component that renders several kinds of content
● **Symptom:** frontend/src/components/Markdown.tsx, the reader for the in-app manuals, was at 69% lines while all files stood at 98.92%: inline code, bold, italic, h4, tables, steps, quote callouts and code blocks were uncovered, and making Table, Quote or inline code render null survived all 421 tests.
● **Root cause:** The renderer came with parser tests (utils/markdown.test.ts) but no component test rendering each block kind.
● **Fix:** A new Markdown.test.tsx renders each heading level, inline code, bold and italic, bullets, steps, a table with column headers, a callout and code.
● **Guard:** frontend/src/components/Markdown.test.tsx.
● **Lesson:** Read per-file coverage, not the total; a renderer or a switch over kinds needs one test per kind asserting the element produced.
● **Evidence:** gate report: Engineering gate V0.12: "'frontend/src/components/Markdown.tsx' is at 69% lines." Also: f6056cd.

### CQ-225 Test cases overlapped two layers of a fail-closed filter, so neither layer was proven alone

● **Rule:** none · **Raised by:** engineering-reviewer (MAJOR) and security-reviewer (minor) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised round 3, fixed in c00e3d2 and 8aa5ecc)
● **Applies to:** any stack with Unicode-aware filtering or layered validation
● **Symptom:** Removing Mn, or Me, from the Unicode categories dropped before reading CLOSED in a Mattermost channel name left all 76 tests green, because every Mn test character was also in the explicit _INVISIBLE list and nothing tested Me; CLO with a combining underline or an enclosing circle would then read as open.
● **Root cause:** Each test character was caught by two layers of the same control, so deleting either layer changed nothing observable.
● **Fix:** c00e3d2 adds close-cases with Mn characters outside _INVISIBLE (C followed by U+0308, and U+16FE4); 8aa5ecc adds an underline (U+0332, Mn) and an enclosing circle (U+20DD, Me) inside the word, each proven by removing its category.
● **Guard:** Parametrised closed cases in tests/test_mattermost_channels.py; mutation by the gates.
● **Lesson:** Where a control has layers (an explicit list and a category rule), give each layer a case that only it catches, and mutate each layer separately.
● **Evidence:** gate report: Engineering gate V0.12 round 3: "dropping combining ('Mn') and enclosing ('Me') marks is a load-bearing fail-closed control." Also: gate report: Security gate V0.12 round 3; commit messages (git log).

### CQ-226 Tests named for a race guard passed with the guard removed

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised round 1, fixed round 2)
● **Applies to:** React and TypeScript; any async UI
● **Symptom:** Four Vitest tests named for a stale-response (`!cancelled`) guard still passed with it removed; a battery neutralising each of the 17 guards in six components alone at first killed only 2 of 17. After the fix, the V0.5 row's claim that each test releases the older request after the newer one answers held for 11 of the 17.
● **Root cause:** The tests did not hold an older request open while a newer one answered, so the guard never decided the outcome.
● **Fix:** The tests were rewritten so the guard decides the outcome; the battery that neutralises each `!cancelled` alone went from 2 of 17 guards killed to 17 of 17, each by the test named for it. The row's description of every test as releasing the older request after the newer one answers holds for 11 of the 17, recorded open below the gates' bar.
● **Guard:** Vitest suite; the guard battery was run for the round.
● **Lesson:** A test named for a guard must fail when that guard alone is neutralised; for races, control the order in which promises resolve.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "four tests named for a stale-response guard still passed with it removed" Also: commit messages (git log).

### CQ-227 Tests written against current behaviour asserted known defects as correct

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised round 1, fixed round 2)
● **Applies to:** any stack
● **Symptom:** While bringing the dashboard to the coverage floor, tests asserted recorded defects as correct behaviour, which would hold the defects in place.
● **Root cause:** Characterisation tests written to reach coverage without judging the behaviour they pinned.
● **Fix:** The assertions holding defects were removed and the defects (missing stale-response guards in ShiftLog, Mattermost and Procedures, a failed shift load keeping the previous entries, aria-sort on the sort button, and others) listed in the V0.5 row for a later release.
● **Guard:** Practice: a test asserts intended behaviour; known defects are recorded, not asserted.
● **Lesson:** Never let a characterisation test lock in behaviour you know is wrong; record the defect and leave it unasserted, or assert the intended behaviour as an expected failure.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "tests asserted recorded defects as correct"

### CQ-228 A release-gating script's self-test was not mutation-checked guard by guard, so the record claimed every guard pinned when it was not

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised in record rounds 1 to 3; fixed in e40e12b, 153c91e and 8c70dbd)
● **Applies to:** any stack with custom release or packaging scripts
● **Symptom:** On 7eedb7b four guards of the review record check and packager (the hex check on a commit id, the packager and .gitattributes in the tool list, the nets on the upload path) could be deleted with the self-test green, though the commit message said removing any guard turns the cases red. Round 2: the replace-ref guard was unpinned and a replace ref then forged the record. Round 3: a mutant reading the working copy's record instead of the committed one left every case green.
● **Root cause:** Cases were written for intended behaviour, not checked by removing each guard alone; overlapping guards masked one another.
● **Fix:** Cases added until each single-guard mutation turned the self-test red: 48 mutations on 153c91e, then 34 on 8c70dbd, plus the engineering gate's port of 38 more.
● **Guard:** scripts/test-package-nets.sh, with single-guard mutation runs by the author and both gates each round.
● **Lesson:** Before claiming a self-test pins every guard, delete each guard alone and run it; a claim not backed by that run is itself a defect in the record.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "MAJOR: four guards could be deleted with the self-test green"

### CQ-229 Custom build-time checks shipped without committed self-tests, then with tests that missed list entries and misjudged equivalent mutants

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.4 (raised rounds 3, 4, 5 and 6; passed round 7)
● **Applies to:** any stack with custom lint, licence or accessibility checks
● **Symptom:** Round 3: the refusals of the licence plugin (frontend/bundled-licences.mjs) and the contrast checker (scripts/contrast-check.mjs) had no committed test, so deleting any left the loop green. Round 4: 57 single entries of the check's lists, each removed alone, left the self-test green. Round 5: three of the check's controls (a text fill that is not a token, a background-color read as a rule's background, a background image under text with no background colour) could each be deleted with the self-test green. Round 6: a mutant the sweep called equivalent was not, since CSS reads 1px#333333 as two tokens. Round 7's sweep also met 51 mutants that ran the check past the ten seconds a run is given, which the self-test fails.
● **Root cause:** Cases were written per feature rather than per control and list entry, and equivalence was judged by reasoning rather than by inputs aimed at telling the mutant apart.
● **Fix:** Committed self-tests run by the loop; scripts/mutation-battery.mjs removes or moves each control and list entry and fails unless the named case goes red (484 mutants killed, 13 declared equivalent), run by CI; each survivor compared with the original on witness sheets before being classed equivalent; a run past ten seconds fails.
● **Guard:** scripts/test-contrast-check.mjs, scripts/test-bundled-licences.mjs and node scripts/mutation-battery.mjs in CI.
● **Lesson:** A check that guards the build is code and needs its own tests and a mutation battery; class a mutant as equivalent only after running it on inputs built to tell it apart, with a time limit per run.
● **Evidence:** docs/AUDIT-LOG.md, V0.4 row: "The third round's engineering gate failed it on one MAJOR: the plugin's and the checker's refusals had no committed test, so deleting any of them left the loop green."

### CQ-230 A hand-written analyser read its input differently from the real engine until it was held against that engine as an oracle

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.4 (raised round 4, further forms in rounds 4 to 6, browser oracle in round 7)
● **Applies to:** custom analysers of CSS, HTML, SQL or configuration
● **Symptom:** The contrast check (scripts/contrast-check.mjs) read a rule's first text colour and background where CSS paints the last, and missed a background image painted over them, so two all-token edits made text 1:1 with every loop step green. Later rounds found an escaped property name, url( after a name character, a no-break space, @property and two keyframes name forms read otherwise than CSS reads them. Held against Chromium 141, round 6's check passed 126,372 of 803,361 generated forms, and of 47,953 of those, 3,291 painted a plain element otherwise than it claims.
● **Root cause:** A parser modelling CSS instead of refusing anything that needs CSS's own rules to read.
● **Fix:** The check refuses forms CSS would read otherwise (duplicates, escapes, url(, non-ASCII, brackets holding delimiters, @import, @property); held against Chromium 141 over 803,418 generated forms, it passes 66,414, of which 5 paint otherwise, each a limit it names.
● **Guard:** Contrast self-test and the mutation battery in the repository; the browser oracle ran outside it.
● **Lesson:** When a check reimplements another engine's parsing, accept only a narrow subset, refuse the rest, and run a differential test against the real engine; name every residual difference.
● **Evidence:** docs/AUDIT-LOG.md, V0.4 row: "the check read a rule's first text colour and background where CSS paints the last, and missed a background image painted over them, so two all-token edits made text 1:1 with every loop step green"

### CQ-231 Loop-breaking guards in an HTTP retry interceptor were untested

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised round 2, fixed round 3)
● **Applies to:** HTTP clients with interceptors (axios and similar)
● **Symptom:** Removing `config._retry = true` or the isAuthEndpoint test in frontend/src/api/client.ts left 9 of 9 client tests green. The _retry guard is all that stops an endless refresh loop when a retried request still gets 401, and each refresh writes an audit row. The lines predated V0.6.
● **Root cause:** Imported code whose loop-breaking guards had never been tested.
● **Fix:** Tests that a refused retry refreshes once only and then signs out, and that a refused auth call never refreshes even with a refresh token held; each red under its mutant, none hung.
● **Guard:** frontend/src/api/client.test.ts.
● **Lesson:** Test the termination of every retry or refresh loop: a retried request that fails again must stop after one attempt, and auth endpoints must never trigger a refresh.
● **Evidence:** gate report: Security gate, V0.6 round 2: "Removing 'config._retry = true', or the 'isAuthEndpoint' test, leaves 9/9 green." Also: docs/AUDIT-LOG.md, V0.6 row.

### CQ-232 Mechanical rewrites made to clear static-analysis findings changed lines no test would notice breaking

● **Rule:** `S7746, S7744 (the SonarQube rules the rewrite cleared)` · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised round 1, fixed round 2)
● **Applies to:** any stack fixing SonarQube or lint findings
● **Symptom:** Clearing V0.5's failed Code Quality findings, frontend/src/api/client.ts was changed to throw in place of Promise.reject and to spread its headers plainly. Two changed lines could then be broken with the suite green: deleting `...config.headers,` (a retried request loses the caller's headers, Content-Type included) and replacing the no-refresh-token throw with `return ""`.
● **Root cause:** Lint-driven refactors on code with thin tests were treated as behaviour-neutral.
● **Fix:** Tests that a retried 401 keeps a caller's custom header and replaces Authorization, and that with no refresh token the original error rejects and no retry is sent; each red under its mutant.
● **Guard:** frontend/src/api/client.test.ts.
● **Lesson:** A refactor to satisfy a linter or SonarQube rule can still change behaviour; mutate each rewritten line and add a test wherever the suite stays green.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "'client.ts' throws in place of 'Promise.reject' and spreads its headers plainly (S7746, S7744)" Also: gate report as received.

### CQ-233 A documented security position was pinned on one path only, so the record claimed more than the tests held

● **Rule:** `none (follows the SonarQube S8414 middleware-order change)` · **Raised by:** engineering-reviewer (minor, then nit); security-reviewer (nit) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised rounds 2 and 3), V0.7 (closed)
● **Applies to:** any web stack with middleware ordering (CORS, security headers)
● **Symptom:** SECURITY.md said a CORS preflight leaves before the security headers and reflects nothing, but only the missing x-request-id was asserted: moving CORS between the security headers and the request id left all 64 tests green, and preflights then carried the CSP and nosniff; no test pinned the fixed body or that no request header was echoed. After round 3 only the allowed-origin preflight test asserted no CSP, while the audit log said the preflight tests did.
● **Root cause:** Tests were written for the change's main effect, not for every clause of the record, and a property was asserted on one branch only.
● **Fix:** Round 3: the allowed-origin preflight test asserts no CSP and the fixed OK body, and the refused one a Disallowed CORS body with no requested header echoed. V0.7: the refused-preflight test asserts the CSP's absence too.
● **Guard:** Preflight assertions in tests/test_app.py; mutants (allow_headers set to a wildcard, security headers outside CORS) each go red.
● **Lesson:** For each clause of a documented security position, assert it on every branch it covers (allowed and refused), and word the record from the assertions that exist.
● **Evidence:** gate report: Engineering gate, V0.6 round 2: "Moving CORS between the security headers and the request id leaves all 64 tests green, and the preflight then carries the CSP and 'nosniff'." Also: gate report: Engineering gate, V0.6 round 3; docs/AUDIT-LOG.md, V0.7 row.

### CQ-234 A release note claimed a behaviour change that already existed, and the change that did happen had no test

● **Rule:** `none (arose from the SonarQube S8414 fix)` · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised round 1, fixed round 2)
● **Applies to:** any stack
● **Symptom:** The audit row and CHANGELOG said a 413 or 429 to an allowed origin gains CORS headers once CORS is outermost; probing both trees showed a 413 already carried them on V0.5. No test pinned the 429: the outermost-CORS test went red under the old order only through the preflight's x-request-id assertion.
● **Root cause:** The claim was written from the intent of the change, not from probing the old and new builds.
● **Fix:** The wording names the 429 alone; a test asserts a coarse-limit 429 to an allowed origin carries access-control-allow-origin, red under the old order.
● **Guard:** test_a_429_to_an_allowed_origin_carries_the_cors_headers in tests/test_app.py.
● **Lesson:** Probe the old and new builds before writing what a change does, and give each claimed difference a test that is red on the old build.
● **Evidence:** gate report as received: "On V0.5 a 413 to an allowed origin already carried 'access-control-allow-origin', because the body cap sat inside CORS (probe output). Only the 429 changed." Also: docs/AUDIT-LOG.md, V0.6 row.

### CQ-235 A changed security allow-list entry was not pinned by any test

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised round 1, fixed round 2)
● **Applies to:** any web stack with CORS or other allow-lists
● **Symptom:** Mutants re-admitting Authorization to the CORS allow_headers in src/app/factory.py, or dropping X-Holly-Token, survived the whole suite.
● **Root cause:** The CORS tests checked the allowed origin and the middleware order, not the allowed request headers.
● **Fix:** test_an_allowed_origin_may_send_holly_s_token_header_and_never_authorization: a preflight asking for x-holly-token gets 200 with the header listed, and one asking for authorization gets 400 Disallowed CORS headers.
● **Guard:** That test; round 2 mutants M3, M4 and M6 killed.
● **Lesson:** When a diff changes an allow-list, add a test for the entry added and the entry removed.
● **Evidence:** gate report: Engineering gate on V0.9 round 1: "Nothing asserts the 'allow_headers' change; both CORS mutants survive." Also: gate report: Security gate on V0.9 round 1.

### CQ-236 Defence-in-depth security guards were never reached by a test, so mutation removed them with the suite green

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** open · **Certainty:** mixed
● **Releases:** V0.12 (raised in the first Comms review, run as 'V0.11 round 1'; three of four fixed in 0a60d93; the channel audit address still unpinned at HEAD f8a00bd)
● **Applies to:** any stack
● **Symptom:** Removing each of these left all 1,290 tests green: `_checked(team_id)` in the Mattermost client (M08, whose first layer M07 was killed), the seed id filter (M13), ip_address on channel audit rows (M23, routes/mattermost.py) and the per-user rate-limiter key (M27).
● **Root cause:** Guards were written defensively, but tests exercised only the first layer of each.
● **Fix:** 0a60d93: the malformed-id test covers get_my_team_channels (M08); a seed entry that is not an id is ignored (M13); the sweep limit is each user's own (M27); the sweep route test patches client_ip and asserts the address passed on to the cycle, whose audit row carries it. No route test at HEAD asserts ip_address on the channel follow or review audit rows, the line M23 named, so that guard looks still unpinned (inference from reading the tests; no mutation was run).
● **Guard:** test_a_malformed_id_never_reaches_a_request_path, test_a_seed_entry_is_trimmed_and_one_that_is_not_an_id_is_ignored, test_the_limit_is_each_users_own; the V0.12 round 1 security gate reported the round 1 fixes present and tested.
● **Lesson:** Run mutation over every security guard, including second layers behind an earlier check, and add a case that reaches each layer directly; assert audit fields such as the client address, not only that a row was written.
● **Evidence:** gate report: Security gate on V0.11 round 1: "Security guards a mutation removes with all 1,290 tests still green" Also: 0a60d93; tests/test_mattermost_routes.py@HEAD; gate report: Security gate V0.12.

### CQ-237 Controls that held could still be removed with every test green

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (rounds 2, 3 and 5; fixed in 48c1a6e, df9b394 and e55312b)
● **Applies to:** FastAPI and pytest; any stack
● **Symptom:** Round 2: by mutation, a cancelled upload's clean-up, the one-file-two-fields form rule, the 64 KiB preview read and the generic error path before the request id could each be removed with the suite green. Round 3: nothing pinned that no await comes between the sign-in limit test and the count. Round 5: the limiter test never filled the limiter.
● **Root cause:** Tests exercised the happy path and never reached the guard, or never drove the limiter to capacity.
● **Fix:** 48c1a6e: a test for each round 2 control, driven where the control acts (below the middleware for cancellation, at the read for the preview); each new test shown to fail with its fix reverted. df9b394: five sign-ins arrive together at the last place under the limit, one is checked and four refused, and an inserted await turns the test red. e55312b fills the limiter.
● **Guard:** Mutation by both gates in every round.
● **Lesson:** Show every new test failing with its fix reverted before recording the fix, and drive limiters and caps to capacity in tests.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "several of them controls a mutation could remove with the suite still green" Also: commit messages (git log).

### CQ-238 A test double stood in for a library object, and the code reached a third-party attribute through a silent fallback

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised round 3, fixed round 4)
● **Applies to:** Python with gunicorn; any code relying on library internals
● **Symptom:** src/app/gunicorn_conf.py reached cfg.env_orig through getattr(..., {}), which would do nothing, silently, if a gunicorn upgrade renamed the attribute, and tests/test_gunicorn_conf.py passed a SimpleNamespace in place of gunicorn's Config, so the test would not notice. The control removes ADMIN_PASSWORD from the environment a re-executed master inherits.
● **Root cause:** A defensive fallback turned a failing security control into a no-op, and the test double did not model the dependency.
● **Fix:** on_starting pops server.cfg.env_orig directly, so a rename fails closed with AttributeError; the test builds gunicorn's real Config.
● **Guard:** tests/test_gunicorn_conf.py with gunicorn.config.Config; the smoke start runs the real arbiter.
● **Lesson:** Test against the library's real object where it is cheap to build, and never wrap a third-party attribute a security control depends on in a silent default.
● **Evidence:** gate report: Security gate, V0.7 round 3: "the 'getattr(..., {})' fallback does nothing, silently, if a future gunicorn renames 'env_orig', and the test uses a 'SimpleNamespace' in place of gunicorn's 'Config', so it would not notice." Also: gate report: Engineering gate, V0.7 round 3; gate report: Engineering gate, V0.7 round 4.

### CQ-239 A fake recorded that it was called, not the state it was called in, so an ordering bug survived the unit tests

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised round 2, fixed round 3)
● **Applies to:** any stack using fakes or mocks
● **Symptom:** The fake bootstrap in tests/test_gunicorn_conf.py did not record whether ADMIN_PASSWORD was present when it was called, so popping the password before the bootstrap (mutant N11) survived the unit tests; only the container smoke rung caught it.
● **Root cause:** The fake asserted the call, not the environment at call time.
● **Fix:** The fake records the password's presence at call time.
● **Guard:** Mutant N11 killed in round 3.
● **Lesson:** When order matters, make fakes capture the state they see at call time (environment, flags, locks held) and assert it.
● **Evidence:** gate report: Engineering gate, V0.7 round 2: "the fake bootstrap does not record whether the password was present when it was called, so N11 (popping before the bootstrap) survives the unit tests. The smoke catches it." Also: gate report: Engineering gate, V0.7 round 3.

### CQ-240 A length limit was checked before case folding, and no test used characters that grow when lowered

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised round 3, fixed round 4)
● **Applies to:** any stack storing case-folded text in bounded columns
● **Symptom:** Checking username instead of username.lower() in src/app/cli/create_admin.py left the suite green; the capital dotted I lowers to two code points, so 30 or 50 of them exceed the 50-character column once lowered.
● **Root cause:** No test used a character whose lower-case form is longer than the original.
● **Fix:** A case of repeated capital dotted I in tests/test_create_admin.py.
● **Guard:** Mutant C13 killed in round 4.
● **Lesson:** Check limits on the value as stored after normalisation, and test with characters whose case-folded or normalised form is longer.
● **Evidence:** gate report: Security gate, V0.7 round 3: "Attack: check 'username' instead of 'username.lower()'. The suite stays green." Also: gate report: Engineering gate, V0.7 round 4.

### CQ-241 A new guard had no case that only it catches, and the record claimed every guard was proven

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer · **Severity:** minor (engineering); nit (security) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised round 2, fixed round 3)
● **Applies to:** any stack
● **Symptom:** No case gave ADMIN_EMAIL a storable but unprintable character, so deleting `or not email.isprintable()` in src/app/admin_bootstrap.py (mutant N07) left all 1,081 tests green, and the AUDIT-LOG's round 2 note that each new guard turned a test red did not hold for it.
● **Root cause:** The printable check was added with the username's tests in mind; the record's claim was not checked guard by guard.
● **Fix:** A printable-email case (the gate suggested an escape character and U+202E) in tests/test_admin_bootstrap.py.
● **Guard:** The gates re-run their mutants each round.
● **Lesson:** Prove each new guard with its own failing mutant before the record says so; one field's tests do not cover a sibling field's guard.
● **Evidence:** gate report: Engineering gate, V0.7 round 2: "so N07 (deleting 'or not email.isprintable()' at :64) stays green across all 1,081 tests." Also: gate report: Security gate, V0.7 round 2.

### CQ-242 Tests asserted the refusal but not that the checked value is the one passed on

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised round 3, fixed round 4)
● **Applies to:** any stack
● **Symptom:** The create_admin CLI checked the stripped email, but no test asserted it passed that checked value to upsert_admin; mutants C11 (unstripped) and C12 (args.email passed raw) stayed green, so a padded 256-character email would pass the check and reach the database.
● **Root cause:** Tests covered the refusal path only, not what the accepted path forwards.
● **Fix:** A CLI case with a padded email asserts upsert_admin receives the stripped value.
● **Guard:** test_a_padded_email_is_checked_and_stored_stripped in tests/test_create_admin.py; C11 and C12 killed.
● **Lesson:** Assert that the value forwarded or stored is the validated, normalised one, not just that bad input is refused.
● **Evidence:** gate report: Engineering gate, V0.7 round 3: "The CLI checks the stripped email, but no test asserts it passes that checked value on: mutants C11 (unstripped) and C12 (args.email passed raw) stay green, so a padded 256-character email would pass ..." Also: gate report: Engineering gate, V0.7 round 4.

### CQ-243 Test inputs already in normal form, so removing the normalisation changed nothing observable

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised round 1, fixed round 2)
● **Applies to:** any stack
● **Symptom:** The email-strip mutant in the first-admin bootstrap survived because the create test used an unpadded ADMIN_EMAIL.
● **Root cause:** Fixtures were already stripped and lower-case.
● **Fix:** The create test uses a padded email and asserts it is stored stripped.
● **Guard:** Stripped-email mutants killed in round 2.
● **Lesson:** Feed padded, mixed-case or otherwise unnormalised input to every path that normalises, and assert the stored form.
● **Evidence:** gate report: Engineering gate on V0.7: "The email-strip mutant survives ('ADMIN_EMAIL' unstripped still passes)."

### CQ-244 Limits were tested only beyond the boundary, never at it

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised round 2, fixed round 3)
● **Applies to:** any stack
● **Symptom:** No test accepted a username of exactly 50 or an email of exactly 255 characters, so changing > to >= in src/app/admin_bootstrap.py survived (mutants N13, N14).
● **Root cause:** Tests covered only values over the limit.
● **Fix:** Acceptance cases at 50 and 255 characters (the security gate stored both, using 4-byte characters).
● **Guard:** test_the_longest_username_and_email_holly_stores_are_accepted in tests/test_admin_bootstrap.py.
● **Lesson:** For every limit, test the largest accepted value and the smallest refused one.
● **Evidence:** gate report: Engineering gate, V0.7 round 2: "there is no test accepting exactly 50 or 255 characters, so changing '>' to '>=' survives (N13, N14)." Also: gate report: Security gate, V0.7 round 3.

### CQ-245 Branches of a parsing guard survived mutation because cases covered only the headline inputs

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised rounds 2 and 3, fixed rounds 3 and 4)
● **Applies to:** any stack parsing dates or other free text
● **Symptom:** In the assistant panel's deadline parser (frontend/src/components/AssistantPanel.tsx), the NaN guard, the regular expression's ^ anchor and its bare-date branch survived mutation (F2, F4, F5) in round 2; the space separator in [T ] (F9) survived in round 3.
● **Root cause:** Tests covered typical well-formed values, not each branch.
● **Fix:** A case for each branch (the gate suggested 2026-13-45 and 2026-01-02), then one for the space separator.
● **Guard:** AssistantPanel.test.tsx; F2, F4 and F5 killed in round 3, F9 in round 4.
● **Lesson:** Give each branch, anchor and alternative of a parser or regular expression its own case, including an impossible date and each accepted separator.
● **Evidence:** gate report: Engineering gate, V0.7 round 2: "the NaN guard, the '^' anchor and the bare-date branch all survive (F2, F4, F5)." Also: gate report: Engineering gate, V0.7 round 4.

### CQ-246 A multi-part refusal was documented but only partly pinned

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.8 (raised round 1, fixed round 2)
● **Applies to:** Python and pydantic settings; any configuration validation
● **Symptom:** SECURITY.md and the audit row say half a set of database settings is still refused under the DAST scan flag, but dropping postgres_password, postgres_user or postgres_host from the no-database tuple in src/app/config.py kept every test green (mutants M7, M8, M9).
● **Root cause:** Only POSTGRES_DB alone, and host, database and user together, were tested.
● **Fix:** The scan case is parametrised over each of POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER and POSTGRES_PASSWORD set alone, each refused.
● **Guard:** Parametrised test in tests/test_config.py; round 2 mutation killed each part.
● **Lesson:** When a rule names several fields, parametrise the test over each field alone.
● **Evidence:** gate report: Engineering gate on V0.8 DAST: "Dropping 'postgres_password', 'postgres_user' or 'postgres_host' from the no-database tuple keeps every test green (M7, M8, M9)." Also: gate report: Engineering gate, V0.8 round 2.

### CQ-247 A temporary directory's privacy and unpredictability were correct but not pinned

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.8 (raised round 1, fixed round 2)
● **Applies to:** any stack creating temporary files
● **Symptom:** Replacing mkdtemp in src/app/dast_scan.py with a fixed /tmp/holly-dast created with mode 0777 survived all 233 relevant tests. The code was correct (0700, random suffix, owned by the app user), but nothing held it.
● **Root cause:** The tests checked that a store was created, not its mode or randomness.
● **Fix:** Tests assert mode 0700 and that two calls give different paths.
● **Guard:** tests/test_dast_scan.py; round 2 mutants 'store world-readable' and 'store predictable' killed.
● **Lesson:** Pin security properties of files and directories (mode, owner, unpredictable name) with assertions, not just their existence.
● **Evidence:** gate report: Security gate on V0.8 DAST: "replacing 'mkdtemp' at 'dast_scan.py:55' with a fixed '/tmp/holly-dast' created 0777 survives all 233 relevant tests." Also: gate report: Security gate, V0.8 round 2.

### CQ-248 Exception-chaining suppression was not pinned, so a refactor could chain a driver's error text into a traceback

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.8 (raised round 1, fixed round 2)
● **Applies to:** Python
● **Symptom:** A mutant changing `from None` to `from exc` in src/app/migrate.py survived, so nothing stopped a later change chaining the database driver's exception, and possibly its text, into a traceback. There was no leak at the time.
● **Root cause:** Tests asserted the message but not __cause__ or __suppress_context__.
● **Fix:** Tests assert the raised error's __cause__ is None and __suppress_context__ is set.
● **Guard:** tests/test_migrations.py; both from-None mutants killed in round 2.
● **Lesson:** Where an error is re-raised to hide sensitive detail, assert the chain is cut (no cause, context suppressed).
● **Evidence:** gate report: Security gate on V0.8 DAST: "the 'from exc' mutant survives, so 'from None' is unpinned." Also: gate report: Security gate, V0.8 round 2.

### CQ-249 Mutants survived on edge inputs of a new start-up step

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.8 (raised round 1, fixed round 2)
● **Applies to:** any stack reading environment configuration
● **Symptom:** Mutants survived on an empty or whitespace-only APP_SECRET_KEY under the DAST scan flag (M15, M37) and on POSTGRES_HOST setting the logged database field (M18) in src/app/dast_scan.py.
● **Root cause:** Tests covered an absent key and DATABASE_URL, not blank keys or the second database variable.
● **Fix:** Cases for a blank key under the flag and for POSTGRES_HOST in the log field.
● **Guard:** tests/test_dast_scan.py; round 2 killed the POSTGRES_HOST and .strip() log-field mutants.
● **Lesson:** Test absent, empty and whitespace-only values separately, and each alternative source of a value.
● **Evidence:** gate report: Engineering gate on V0.8 DAST: "an empty or whitespace-only 'APP_SECRET_KEY' under the flag (M15, M37);" Also: gate report: Engineering gate, V0.8 round 2.

### CQ-250 A documented equivalence of a security helper had no test

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 1, fixed round 2)
● **Applies to:** any stack using bcrypt or similar truncating hashes
● **Symptom:** The docstring of same_password in src/app/core/security.py claimed bcrypt's 72-byte equivalence, but replacing the function with `first == second` survived all 1,204 tests (mutant B14).
● **Root cause:** Only plain equal and unequal passwords were tested.
● **Fix:** A test of two passwords equal in their first 72 UTF-8 bytes and different after, and a route case refused with 400.
● **Guard:** Mutant B14 killed in round 2; the security gate saw the 72-byte case refused live.
● **Lesson:** Every edge behaviour a docstring claims for a security helper needs a test at that edge.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "The 72-byte equivalence the docstring claims is untested: replacing it with 'first == second' survives all 1,204 tests (B14)." Also: gate report: Security gate on V0.10 round 2.

### CQ-251 A fixture started in the expected end state, so the assertion could not fail

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 1, fixed round 2)
● **Applies to:** any stack
● **Symptom:** The create_admin test for an existing user built that user with must_change_password already False, so deleting the line that clears the flag (src/app/cli/create_admin.py:70) survived (mutant B28).
● **Root cause:** The fixture's starting state matched the asserted outcome.
● **Fix:** The test builds the user with make_user(..., must_change_password=True).
● **Guard:** Mutant B28 killed in round 2.
● **Lesson:** Start fixtures in the opposite state to the one the code should produce, so the assertion proves a change happened.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "The existing user already has 'must_change_password' False, so deleting create_admin.py:70 survives (B28)."

### CQ-252 The boundary case of a locking condition was untested

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 1, fixed round 2)
● **Applies to:** any stack with invariants such as 'at least one active admin'
● **Symptom:** No test changed an inactive admin, so widening the last-admin lock condition in src/app/api/v1/routes/users.py to any admin survived (mutant B27); that mutant would refuse demoting an inactive admin while only one admin is active.
● **Root cause:** Tests covered active admins only.
● **Fix:** A case changing an inactive admin: 200, with no FOR UPDATE issued.
● **Guard:** Mutant B27 killed in round 2.
● **Lesson:** For a condition that decides when to lock or refuse, test the records just outside it as well as inside.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "No test changes an inactive admin. Widening the lock condition to any admin survives (B27)"

### CQ-253 A container smoke step skipped a new route and accepted any refusal body

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 1, fixed round 2)
● **Applies to:** any containerised service with a smoke test
● **Symptom:** The Users step in scripts/smoke-container.sh never ran the password reset route on PostgreSQL, and accepted any 403 whatever its body.
● **Root cause:** The step was written for the happy path and matched status codes only.
● **Fix:** The step resets an account, matches the 403 body to the change-due text, and races reset against the user's own change three times.
● **Guard:** scripts/smoke-container.sh, run before every upload.
● **Lesson:** Smoke steps against the real database should exercise every new route and match refusal bodies, not just status codes.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "The reset route never runs on PostgreSQL, and any 403 is accepted whatever its body." Also: docs/AUDIT-LOG.md, V0.10 row.

### CQ-254 Error-message wiring on a page was untested though the helper had unit tests

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 2), V0.12 (fixed)
● **Applies to:** React and TypeScript; any UI
● **Symptom:** Removing the `validationMessage(err) ??` wiring on the Users and Password pages (mutants F24, F25) survived every page test; without it a 422 shows axios's generic text, the only way an admin learns why a username was refused.
● **Root cause:** validationMessage had unit tests, but no page test rejected with a 422 detail list.
● **Fix:** Page tests of a 422's message on the Users and Password pages.
● **Guard:** frontend/src/pages/Users.test.tsx and ChangePassword.test.tsx.
● **Lesson:** Unit-testing a helper does not test that a page uses it; add a page-level test that drives the server error through to the visible message.
● **Evidence:** gate report: Engineering gate on V0.10 round 2: "Removing the 'validationMessage(err) ??' wiring (mutants F24 and F25) survives every page test." Also: docs/AUDIT-LOG.md, V0.12 row.

### CQ-255 A test replaced a module attribute directly and never restored it

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised round 2), V0.12 (fixed)
● **Applies to:** Python and pytest; any test framework with global state
● **Symptom:** tests/test_users_routes.py set `users.write_audit = AsyncMock()`, so every later test in the run that reached the real audit write through that module would silently test the mock. It had been there since round 1 and was missed then.
● **Root cause:** Direct module attribute assignment instead of a scoped patch.
● **Fix:** The Users route test no longer leaves users.write_audit patched (monkeypatch.setattr or the audit_calls fixture was the gate's suggestion).
● **Guard:** none recorded
● **Lesson:** Patch with a scoped tool (monkeypatch, a context manager or a fixture) so every replacement is undone after the test.
● **Evidence:** gate report: Engineering gate on V0.10 round 2: "'users.write_audit = AsyncMock()' replaces the module attribute directly and nothing restores it." Also: docs/AUDIT-LOG.md, V0.12 row.

### CQ-256 No test told a hidden-character marker apart from an ordinary separator

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised round 6, fixed in 6f7dcd0)
● **Applies to:** any stack using marker characters in text processing
● **Symptom:** With the hidden-character mark in src/app/services/mattermost_channels.py changed to a space, all 98 tests still passed, although names such as 'CLO SED' and 'C L O S E D' would then wrongly close a channel.
● **Root cause:** The open-case list had no name with an ordinary separator inside the word.
● **Fix:** Open cases for a space and a tab inside the word, so the mark can never be a separator.
● **Guard:** Open cases in tests/test_mattermost_channels.py.
● **Lesson:** When a sentinel value must differ from ordinary input, test that ordinary input never behaves like the sentinel.
● **Evidence:** gate report: Engineering gate V0.12 round 6: "Nothing tests that the mark differs from a separator." Also: gate report as received; commit messages (git log).

### CQ-257 A property sweep whose reference was the code under test proved nothing

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** unranked (coverage note) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.12 (raised round 6)
● **Applies to:** any stack using property-based or differential testing
● **Symptom:** Round 5's sweep script for the CLOSED reading (sweep5.py) had a reference that had become the code itself, so its agreement with the code was no evidence. Who wrote that script is not recorded: both round 5 gate reports are empty.
● **Root cause:** The sweep's oracle had come to match the implementation being judged instead of standing as an independent statement of the rule (how it came to match is not recorded).
● **Fix:** Round 6 wrote an independent sweep whose reference tries every nothing-or-space reading of each hidden character against the original plain pattern; the engineering gate built its own separate sweep, and round 7 re-ran against the refactor.
● **Guard:** Practice: an independent oracle for property sweeps.
● **Lesson:** A property or differential test needs an oracle written independently of the implementation; if the oracle imports or copies the code, it can only agree.
● **Evidence:** gate report: Security gate V0.12 round 6: "that script's reference is now the code itself, so it proves nothing"

### CQ-258 A test with a single arrival could not pin the order of several

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.13 (raised round 1, fixed in 6085a53)
● **Applies to:** any stack
● **Symptom:** The append-at-bottom test in frontend/src/components/comms/views.test.tsx had one new message, so dropping `.reverse()` at ChannelConversation.tsx:160 would leave it passing. The gap predated the SonarQube refactor that moved the line verbatim; round 1 could not run the mutation, as the permission system refused a scratch copy of frontend/.
● **Root cause:** One element cannot tell one order from another.
● **Fix:** A test 'adds several messages that arrive at the bottom oldest first'; in round 2, with `.reverse()` removed it fails (1 failed, 29 passed).
● **Guard:** The Vitest case, proven by mutation in round 2.
● **Lesson:** Ordering logic needs at least two items, in an order that differs from the input, before a test can pin it; a refactor that moves such a line is a good moment to add the test.
● **Evidence:** gate report: Engineering gate V0.13 (fast): "no test fixes the reversed order when several messages are appended at the bottom" Also: gate report: Engineering gate V0.13 round 2.

### CQ-259 A timing-dependent test failed under load

● **Rule:** none · **Raised by:** engineering-reviewer (from its own verification run) · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.12 (raised round 2, fixed in 6c712cc)
● **Applies to:** Vitest or Jest fake timers
● **Symptom:** The gate's first verify run failed on Mattermost.test.tsx 'reads the channels again every minute' (expected 3 to be 2 at line 409) while eslint, jscpd and npm ci loaded the machine; a second run with no other load passed. The test was new in V0.12.
● **Root cause:** Inference from the gate: `shouldAdvanceTime: true`, with the extra read the lastSeen change triggers, let the baseline call count be sampled before that read landed.
● **Fix:** The minute-poll test waits for the first reads to settle before sampling.
● **Guard:** none recorded beyond the test itself
● **Lesson:** With fake timers that also advance real time, wait for every start-up request to settle before taking a baseline count, and rerun new timer tests under load.
● **Evidence:** gate report: Engineering gate V0.12 round 2: "'Mattermost.test.tsx > the Comms console > reads the channels again every minute': 'expected 3 to be 2' at line 409." Also: commit messages (git log).

### CQ-260 Async UI tests read state before it settled and updated it outside act

● **Rule:** none · **Raised by:** pipeline simulation (the unloaded panel, round 1); the node job's run inside node:24-alpine (the 11 act() warnings, closed in round 2); who first raised the warnings is not recorded · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.5 (raised and fixed in rounds 1 and 2)
● **Applies to:** React Testing Library with Vitest or Jest
● **Symptom:** The pipeline simulation first failed because a test read the assistant panel before it had loaded; three frame tests printed 11 act() warnings inside node:24-alpine, the platform's node job image.
● **Root cause:** Missing waits, and providers resolving outside act.
● **Fix:** Tests wait for load; the three frame tests let their providers answer inside act; no act() warning remains.
● **Guard:** scripts/simulate-pipeline.sh runs the node job's commands, with this machine's node standing in for node:24-alpine (its header says so); the run inside node:24-alpine was a separate check in the round's evidence.
● **Lesson:** Wait for asynchronous loads before asserting, treat act() warnings as failures, and run the suite in the platform's own image.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "a test read the assistant panel before it had loaded" Also: scripts/simulate-pipeline.sh@HEAD.

### CQ-261 A timer-driven test waited in real time and could not observe the poll

● **Rule:** none · **Raised by:** not recorded (listed in the session summary among surviving mutants that were fixed; inference: the author's own mutation run) · **Severity:** unranked · **Status:** resolved · **Certainty:** inference
● **Releases:** V0.10 (inference: the Layout timer work; found before the gates)
● **Applies to:** Vitest or Jest
● **Symptom:** The Layout's timer-poll test did not kill its mutant until it used fake timers.
● **Root cause:** The test waited on real time, so it never reached the poll.
● **Fix:** Layout.test.tsx uses vi.useFakeTimers and advances 11 seconds.
● **Guard:** The Layout timer test.
● **Lesson:** Drive interval behaviour with fake timers and explicit advances, and confirm the test kills a mutant of the poll.
● **Evidence:** session summaries: "the timer-poll test needed fake timers"

### CQ-262 Tests hung once start-up gained a real blocking wait

● **Rule:** none · **Raised by:** the author's own test runs while building (the summary records the hang, not which run found it) · **Severity:** unranked · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.8 (found and fixed while building)
● **Applies to:** Python with gunicorn hooks; any start-up code
● **Symptom:** The on_starting tests in tests/test_config.py hung once wait_for_database existed.
● **Root cause:** The tests called the real gunicorn on_starting hook, which now waits up to a minute for a database the test environment does not have.
● **Fix:** wait_for_database is stubbed in those tests.
● **Guard:** none recorded
● **Lesson:** When a start-up hook gains a network wait, stub it in every unit test that calls the hook, and give waits an injectable deadline.
● **Evidence:** session summaries: "**Hanging config test.** 'test_config''s on_starting tests hung once 'wait_for_database' existed; I stubbed it in those tests."

### CQ-263 Tests left temporary directories behind on the host

● **Rule:** none · **Raised by:** security-reviewer (nit in rounds 1 and 2) and engineering-reviewer (minor in round 2) · **Severity:** minor · **Status:** open · **Certainty:** fact
● **Releases:** V0.8 (raised rounds 1 and 2; partly fixed)
● **Applies to:** Python and pytest
● **Symptom:** Each run left an empty 0700 holly-dast-* directory in the system temp. Round 2 redirected tempfile in tests/test_dast_scan.py, but tests/test_gunicorn_conf.py still runs the real prepare_scan_environment without redirecting it, and the V0.8 row records that its closure overstated this.
● **Root cause:** The redirect was added per file, not in the shared autouse fixture in tests/conftest.py.
● **Fix:** Partly: test_dast_scan.py sets tempfile.tempdir to tmp_path. Neither conftest.py nor test_gunicorn_conf.py sets it at HEAD f8a00bd.
● **Guard:** none recorded
● **Lesson:** Isolate temporary paths in one shared autouse fixture so every test that reaches real code writes under the test's own directory.
● **Evidence:** gate report: Security gate on V0.8 DAST: "each run leaves one empty 0700 'holly-dast-*' directory in the host '/tmp'." Also: gate report: Engineering gate, V0.8 round 2.

### CQ-264 Tests computed their expectations instead of stating literals

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** unknown (the round 1 reports are not available) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (raised round 1, fixed in c0a25dc)
● **Applies to:** any stack
● **Symptom:** The scaffold's tests were rewritten so every expectation is a literal, and the reviewers' mutants were then all killed; that the earlier tests derived expectations from the code under test, letting a mutated control stay green, is inference from the fix.
● **Root cause:** Inference: expectations built from the same source as the implementation.
● **Fix:** Every expectation is a literal, a reviewed route inventory acts as the trip-wire for authentication, and all 14 mutants the reviewers used or the new controls imply are killed.
● **Guard:** Route inventory in tests/test_app.py; mutation by the gates each round.
● **Lesson:** Write expected values as literals in tests; an expectation computed from the code under test moves with any bug in it.
● **Evidence:** commit messages (git log): "Tests: every expectation is a literal, a reviewed route inventory acts"

### CQ-265 A configuration-module test would not notice a misspelt setting or hook

● **Rule:** none · **Raised by:** a review gate on c0a25dc (b56e04c closes the minor items both gates left; which gate raised this one is not recorded) · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (fixed in b56e04c, extended to server hooks in 85962f4)
● **Applies to:** Python configuration modules (gunicorn and similar)
● **Symptom:** A misspelt gunicorn setting or server hook in src/app/gunicorn_conf.py would be ignored silently by gunicorn and by the test.
● **Root cause:** The test checked a hand-written list of names.
● **Fix:** The settings test derives the names from the module, so a misspelt extra setting fails (b56e04c), and counts functions too, so a misspelt server hook fails (85962f4).
● **Guard:** tests/test_gunicorn_conf.py.
● **Lesson:** For configuration read by name, test that every name defined is one the consumer recognises, so a typo fails instead of being ignored.
● **Evidence:** commit messages (git log): "Both gates passed c0a25dc and left minor items; this commit closes them."

### CQ-266 An allowlist parser took duplicates silently and its read-from-commit rule was unpinned

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.1 (raised on ac0c5bc, fixed in fab9044)
● **Applies to:** any stack with allowlist files read by tooling
● **Symptom:** A path listed twice in scripts/upload-binaries.txt silently took its last entry, and no case pinned the rule that only a committed allowlist entry counts: a mutant reading the working tree's list kept the self-test green.
● **Root cause:** Last-wins parsing and an untested read-from-HEAD rule.
● **Fix:** scripts/scan-package.mjs refuses a second entry; scripts/test-package-nets.sh commits a binary in a throwaway clone and requires a refusal while its entry is uncommitted and a pass once committed.
● **Guard:** scripts/test-package-nets.sh.
● **Lesson:** Make security allowlists refuse duplicates, and test the source of truth (the committed copy, not the working tree) with a case that differs between the two.
● **Evidence:** commit messages (git log): "A path listed twice in scripts/upload-binaries.txt silently took its"

### CQ-267 A configuration fix was unpinned, then pinned by a text check that comments and fallbacks could bypass

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised gate rounds 1 to 3; fixed in a6ee4df, 02a4317 and 3b54e4e)
● **Applies to:** shell-based verification of configuration files
● **Symptom:** Nothing pinned the TCP form of the local PostgreSQL health check in infra/docker-compose.yml, and the version test missed the dashboard's manifest and lockfile. The new loop step then let through a socket check with -h 127.0.0.1 in a trailing comment, and a wait followed by a fallback or sent to the background, and did not say what it cannot see, so the CHANGELOG claimed more than it checked.
● **Root cause:** A configuration fix without a regression check, then grep patterns that matched anywhere on a line.
● **Fix:** The step's patterns stop at a # and the wait line must end at db; it fails on 5 broken variants and gives the same results under dash and bash on the security reviewer's 26 cases (48 by round 4); it prints its blind spots; the version test fails with each of its four fields changed.
● **Guard:** The verify.sh 'Local database' step; tests/test_version.py.
● **Lesson:** Pin each configuration fix with a check, prefer parsing to line greps, test the check against bypass variants under every shell it runs in, and have it print what it cannot see.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "nothing in the repository pinned the TCP form of the check" Also: scripts/verify.sh.

### CQ-268 Smoke-rung checks failed open and their refusals had no near-miss case

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (smoke rounds 2 and 3; fixed in e13a3d3 and e0156ce)
● **Applies to:** shell test harnesses and container smoke tests
● **Symptom:** The PostgreSQL 16 smoke logged a blank server version and carried on when the read failed; the loop step tried the smoke's image refusal only on an image with no digest, so a refusal widened to any digest would pass.
● **Root cause:** An unchecked command substitution, and a negative case far from the boundary.
● **Fix:** The smoke stops if the version read fails or comes back empty; the loop runs the refusal on an image with no digest and on one with a well-formed digest that is not the pinned one, with a stand-in docker.
● **Guard:** verify.sh step 'Database images: both pin PostgreSQL by digest, and the smoke rung refuses any other image and waits over TCP'.
● **Lesson:** Make every probe in a test rung fail closed on an empty or failed read, and test each refusal with a near miss (a valid-looking but wrong value), not only an obviously bad one.
● **Evidence:** commit messages (git log): "The smoke reads the server version into a variable and stops if the" Also: scripts/verify.sh.

### CQ-269 A self-test that uses a stand-in binary can pass where the stand-in cannot run

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** minor · **Status:** deferred · **Certainty:** fact
● **Releases:** V0.3 (raised smoke round 3, mitigated in e0156ce, residual deferred at round 4)
● **Applies to:** shell test harnesses using PATH stubs
● **Symptom:** If the shell cannot run the stand-in docker (a noexec TMPDIR), the real client would run. After the mitigation, where TMPDIR is mounted noexec, a refusal rewritten to print its message and carry on would still pass the loop step, though Docker is never reached.
● **Root cause:** PATH-based stubbing depends on the stub being executable from the temporary directory.
● **Fix:** Each run sets DOCKER_HOST to a socket that does not exist and KEEP_SMOKE=0, so the real client reaches no daemon. The remaining case was deferred to the backlog.
● **Guard:** The verify.sh 'Database images' step (partial).
● **Lesson:** When a test stubs a tool through PATH, assert the stub actually ran (for example a marker file) rather than inferring it from the outcome.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "Both minors are one open case: where TMPDIR is mounted noexec, a refusal rewritten to print its message and carry on would pass the step, though Docker is still never reached." Also: commit messages (git log).

### CQ-270 Layered refusals masked one another under mutation, so some guards turned red only through the refusal's wording

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.3 (14 recorded at record round 4), V0.6 (5 raised by the gates on 97d90be and recorded; 2 more raised in round 1 and recorded in round 2)
● **Applies to:** any fail-closed validation chain
● **Symptom:** Many single-guard mutations of the packaging checks were killed only because another refusal fired with different wording: 14 in the review record check at V0.3; at V0.6 five baseline-check guards (the baseline commit exists, the record is committed, the version pattern, the empty record, the awk exit status), then the review check's single-line rule and the baseline check's equal-version refusal, which the record had not listed. Earlier, SECURITY.md's claim that the row names each such guard did not hold.
● **Root cause:** Delete one guard of a fail-closed chain and a later one still refuses; only a case matched on wording notices.
● **Fix:** Each such guard is named in the audit row with what refuses in its place, as SECURITY.md requires.
● **Guard:** SECURITY.md commits the audit log to listing them; the gates mutation-test every new guard and compare the refusal's wording.
● **Lesson:** Match test cases on the specific refusal message, and record every guard that only wording distinguishes, with what refuses in its place, so a later change cannot remove two guards at once unnoticed.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "14 guards turn their cases red only through the refusal's wording" Also: docs/AUDIT-LOG.md, V0.6 row; gate report: Engineering gate on V0.6 tree; SECURITY.md.

### CQ-271 A test clone inherited the developer's global git configuration

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised record round 4), V0.4 (fixed in 3a99acb)
● **Applies to:** tests that drive git
● **Symptom:** The nets self-test's record clone gained an upstream under branch.autoSetupMerge=always, changing what the packaging checks saw.
● **Root cause:** The self-test ran git with the developer's global configuration.
● **Fix:** The self-test clears any upstream git sets on its record clone.
● **Guard:** scripts/test-package-nets.sh.
● **Lesson:** Isolate test repositories from user and system git configuration (or reset what it can set) so tests behave the same on every machine.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "the record clone gaining an upstream under 'branch.autoSetupMerge=always'" Also: docs/AUDIT-LOG.md, V0.4 row.

### CQ-272 Self-tests failed where the temporary directory sits behind a symlink

● **Rule:** none · **Raised by:** engineering-reviewer (V0.3 record round 3); who found the V0.4 licence self-test case is not recorded · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.3 (raised record round 3, nets case fixed in 8c70dbd), V0.4 (licence self-test fixed in round 5)
● **Applies to:** tests on macOS or any system with a symlinked temp directory
● **Symptom:** The nets' relative-path case failed where TMPDIR sits behind a symlink, and the licence self-test failed behind a symlinked TMPDIR, as on macOS.
● **Root cause:** Tests compared logical paths with physical ones.
● **Fix:** 8c70dbd: the relative-path case expects the physical path. V0.4 round 5: the licence self-test takes its temporary folder's real path.
● **Guard:** scripts/test-bundled-licences.mjs and scripts/test-package-nets.sh.
● **Lesson:** Resolve temporary paths to their real path before comparing them, and run self-tests on a symlinked TMPDIR at least once.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "the relative-path case failed where TMPDIR sits behind a symlink" Also: commit messages (git log); docs/AUDIT-LOG.md, V0.4 row.

### CQ-273 A test of a security-sensitive file checked named fields only

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised round 1, fixed round 2)
● **Applies to:** Node projects with install scripts; any small security-relevant config
● **Symptom:** tests/test_root_node_project.py checked named fields of the root package.json and package-lock.json (which run a postinstall), so a widening edit elsewhere could pass; in the same round the image's build context took the dashboard's tests.
● **Root cause:** Field-level assertions on a file whose every field matters, and a broad build-context allowlist.
● **Fix:** A whole-file test, shown to refuse 6 widening edits; the dashboard's tests are excluded from the image's build context.
● **Guard:** tests/test_root_node_project.py.
● **Lesson:** For small files with security weight (install hooks, CI configuration), assert the whole file, not selected fields.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "the root project test checked named fields only; the image's build context"

### CQ-274 A test literal tripped the upload's secret scan

● **Rule:** none · **Raised by:** pipeline simulation (the upload content net) · **Severity:** unranked · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.6 (round 2)
● **Applies to:** repositories whose tests are packaged and scanned
● **Symptom:** The pipeline simulation's first try in round 2 was refused by the upload content net for a new test naming a field token.
● **Root cause:** The content net runs the secret-scan hook's rules over every shipped text file, tests included, so a credential-shaped literal in a test is refused like one in source.
● **Fix:** The test was changed and the simulation then scanned 242 text files clean (how the test was changed is not recorded). The session's standing notes, under SonarQube, keep PASSWORD, TOKEN and SECRET names off string literals; the same hook's rules later blocked credential-shaped test fixtures at write time, which were rebuilt from parts or renamed.
● **Guard:** Upload content net in packaging and the simulation.
● **Lesson:** Tests ship and are scanned too: build credential-shaped fixtures from parts or neutral names so secret scanners stay strict.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "round 2's first try had been refused by the content net for a new test naming a field 'token'" Also: session summaries.

### CQ-275 Strict TypeScript rejected property access on a possibly undefined test value

● **Rule:** none · **Raised by:** verification loop (inference: the commit names only the type) · **Severity:** unranked (a type error, no gate finding) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.12 (fixed in ccbc7b8)
● **Applies to:** TypeScript
● **Symptom:** After the round 2 fixes (6c712cc), a new test in views.test.tsx filtered recorded queries with query.channel_id where a recorded query may be undefined.
● **Root cause:** The helper's return type allowed undefined entries and the new test did not narrow them.
● **Fix:** Optional chaining, query?.channel_id.
● **Guard:** The type check in the verification loop.
● **Lesson:** Type-check test files as strictly as source and run the type check before committing test changes.
● **Evidence:** commit messages (git log): "Fix a test's type: a query recorded may be undefined" Also: ccbc7b8.

### CQ-276 A test's name claimed more than it proved

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised round 1, fixed round 2); V0.12 (raised round 3, fixed in 8aa5ecc)
● **Applies to:** any stack
● **Symptom:** V0.6: frontend/src/utils/keys.test.ts was named 'so no two keys match', though withContentKeys could still return two equal keys. V0.12: test_any_number_above_nothing_in_delete_at_archives_it covered NaN after round 2, which is not above nothing.
● **Root cause:** Names written for the intent, or not updated when a parametrised case was added.
● **Fix:** V0.6: keys skip any key already issued, with the colliding input as a case, so the unchanged name now holds. V0.12: renamed test_any_number_but_zero_or_below_in_delete_at_archives_it.
● **Guard:** none recorded
● **Lesson:** A test's name is a claim: check it against the cases each time a case is added, and do not name a property the cases do not prove.
● **Evidence:** gate report: Engineering gate on V0.6 tree: "overstates what it proves" Also: frontend/src/utils/keys.test.ts@HEAD; gate report: Engineering gate V0.12 round 3.

### CQ-277 A redundant whitespace strip on a credential header was unpinned

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised round 1, resolved round 2)
● **Applies to:** Python ASGI servers (h11, uvicorn); any stack
● **Symptom:** No test sent a padded token, so the returned .strip() in src/app/dependencies.py was unpinned; the strip in the empty check was redundant, as decode_token already refuses an empty string, and in production h11 trims the header's surrounding spaces before the app sees it.
● **Root cause:** Defensive code for input the HTTP server already normalises.
● **Fix:** Simplified to decode the token only when present, with a comment that the HTTP server trims surrounding spaces and decode_token refuses anything else.
● **Guard:** The remaining 'if token else None' mutant was shown equivalent in rounds 2 and 3; no new test.
● **Lesson:** When code cannot be pinned because the layer below already normalises the input, simplify it and document why rather than keeping untestable branches.
● **Evidence:** gate report: Engineering gate on V0.9 round 1: "No test sends a token with spaces around it, so the return '.strip()' is unpinned." Also: 83e9696.

### CQ-278 No negative test proves an error message omits the database driver's text

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** minor · **Status:** open · **Certainty:** fact
● **Releases:** V0.8 (raised round 2; open)
● **Applies to:** any stack wrapping database or third-party errors
● **Symptom:** A mutant appending `{exc}` to the migrations refusal message in src/app/migrate.py survived all 184 relevant tests, so a regression that leaks the driver's message, which names the user and database, would pass.
● **Root cause:** The fake driver error carried no sensitive value, and the refusal test did not assert that the error text was absent.
● **Fix:** None yet. Proposed: put the URL's user and password into the fake error's text and assert neither appears in the message or the captured output.
● **Guard:** none recorded
● **Lesson:** For every error path that hides upstream detail, plant a recognisable secret in the fake upstream error and assert it never reaches the message, the log or the response.
● **Evidence:** gate report: Security gate, V0.8 round 2: "a mutant that appends '{exc}' to the refusal message survived all 184 tests." Also: docs/AUDIT-LOG.md, V0.8 row.

### CQ-279 A validator covering several fields was pinned for one, and the record overstated the closure

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** open · **Certainty:** fact
● **Releases:** V0.8 (raised round 2; open)
● **Applies to:** Python and pydantic settings validators
● **Symptom:** Removing postgres_host, postgres_db, postgres_user or postgres_password from `_blank_is_unset` in src/app/config.py left all 1,141 tests green, though the audit row first claimed the tests pinned each case. The change also refuses a blank POSTGRES_PASSWORD with the other parts set, where V0.7 accepted it, and no test covers that.
● **Root cause:** The test was written for the triggering case (DATABASE_URL); the validator's field list grew without matching parametrisation.
● **Fix:** None; the audit row was corrected to say four of the five names are unpinned. No parametrised test at HEAD.
● **Guard:** none recorded
● **Lesson:** Parametrise validator tests over every field in the validator's list, and check the record's claims with the same mutation run.
● **Evidence:** gate report: Engineering gate, V0.8 round 2: "Removing 'postgres_host', 'postgres_db', 'postgres_user' or 'postgres_password' leaves all 1141 tests green" Also: docs/AUDIT-LOG.md, V0.8 row.

### CQ-280 A page's interval poll still has no unmount test

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** MAJOR (as part of the review's test-completeness finding) · **Status:** open · **Certainty:** inference
● **Releases:** V0.12 (raised in the first Comms review; open)
● **Applies to:** React and TypeScript; any polling page
● **Symptom:** Removing the clean-up of the Comms page's 60-second channel poll in frontend/src/pages/Mattermost.tsx stayed green. The review asked for unmount tests of both polls; the feed's poll gained one, but HEAD's Mattermost.test.tsx tests that the channels are read every minute and never unmounts.
● **Root cause:** The page test covered that the poll runs, not that it stops.
● **Fix:** None found for the page poll.
● **Guard:** none recorded
● **Lesson:** Close every item of a multi-part test request, and check each by mutating its own guard.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "Needed: unmount, advance the clock, and expect no further calls, for both polls." Also: frontend/src/pages/Mattermost.test.tsx@HEAD.

### CQ-281 A fixture's incidental order matched the order under test

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** open · **Certainty:** inference
● **Releases:** V0.12 (raised in the first Comms review; open)
● **Applies to:** any stack
● **Symptom:** The first-seen hue order in frontend/src/utils/comms.ts could be deleted without a test failing, because the fixture's first-seen dates run in the same order as its ids (alpha to golf), so the id tie-break alone gives the same result.
● **Root cause:** Fixture ids were alphabetical in the same order as their first-seen dates.
● **Fix:** None found: the hue test at HEAD lists the same channels in the same date order.
● **Guard:** none recorded
● **Lesson:** Choose fixtures where the ordering under test differs from every incidental ordering (ids, insertion, alphabetical).
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "The fixture's first-seen order matches its id order." Also: frontend/src/utils/comms.test.ts@HEAD.

### CQ-282 An assertion held whether or not the code under test ran

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** open · **Certainty:** inference
● **Releases:** V0.12 (raised in the first Comms review; open)
● **Applies to:** any stack
● **Symptom:** The check that a pulled channel's name came from the sweep (tests/test_mattermost_channels.py:353 and :375) proved nothing: the posts page was empty, so no name lookup happened either way, and removing the name prefill (src/app/services/mattermost_ingest.py:266) stayed green.
● **Root cause:** The fixture gave the channel no post, so the path under test was never reached.
● **Fix:** None found: at HEAD the test still serves chan-1 an empty posts page.
● **Guard:** none recorded
● **Lesson:** Before trusting an assertion, confirm the fixture drives execution through the code it is meant to check; a mutation of that code is the quickest proof.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "The posts page is empty, so no name lookup happens either way" Also: tests/test_mattermost_channels.py@HEAD.

### CQ-283 Retry deadline and error-class boundary constants were not pinned

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** open · **Certainty:** fact
● **Releases:** V0.8 (raised round 2; open)
● **Applies to:** any stack with retry loops or error classification
● **Symptom:** Raising DATABASE_WAIT_SECONDS in src/app/migrate.py from 60 to 600 stayed green, though the manual quotes about 60 seconds and the wait must stay well inside the DAST scan's 300-second window; widening the connection-class SQLSTATE prefix '08' to '0' also survived.
● **Root cause:** Tests inject the deadline and use a few SQLSTATEs, so the default and the class boundary are never asserted.
● **Fix:** None yet. Proposed: a test that the default deadline is 60, with its reason, and a refusal test for another class-0 code such as 0P000.
● **Guard:** none recorded
● **Lesson:** When tests inject a constant for speed, add one test that pins the production default and the boundary of any prefix or class match.
● **Evidence:** gate report: Engineering gate, V0.8 round 2: "raising 'DATABASE_WAIT_SECONDS' to 600 stays green." Also: docs/AUDIT-LOG.md, V0.8 row.

### CQ-284 A blank-value test used only one kind of whitespace

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** nit · **Status:** open · **Certainty:** inference
● **Releases:** V0.8 (raised round 2; open)
● **Applies to:** any stack validating secrets or required text
● **Symptom:** The blank APP_SECRET_KEY test in tests/test_config.py builds the key from ASCII spaces only, so a mutant that strips spaces but not tabs, newlines or Unicode spaces survived.
● **Root cause:** A single example where the property covers a class of inputs.
● **Fix:** None recorded. Proposed: parametrise over tab, newline, U+00A0 and U+3000. At HEAD the test still uses spaces only.
● **Guard:** none recorded
● **Lesson:** Parametrise blank-value tests over the whitespace classes the language recognises, including Unicode spaces.
● **Evidence:** gate report: Security gate, V0.8 round 2: "Fix: parametrise over tab, newline, U+00A0 and U+3000." Also: tests/test_config.py at f8a00bd.

### CQ-285 The blank optional argument was not tested separately from the padded one

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** open · **Certainty:** fact
● **Releases:** V0.7 (raised round 4; open)
● **Applies to:** any CLI or API with optional fields
● **Symptom:** No create_admin CLI test passes an email of only spaces, which should mean no email rather than a refused empty one; mutant C16 survives.
● **Root cause:** The padded-email test covered surrounding spaces only.
● **Fix:** None yet; listed open in the V0.7 row, and tests/test_create_admin.py at HEAD has no such case.
● **Guard:** none recorded
● **Lesson:** For optional inputs, test absent, blank and padded values as three separate cases.
● **Evidence:** gate report: Engineering gate, V0.7 round 4: "which should mean no email rather than a refused empty one." Also: docs/AUDIT-LOG.md, V0.7 row.

### CQ-286 An integration was verified only against stand-ins for the upstream API

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** unranked (coverage note) · **Status:** open · **Certainty:** fact
● **Releases:** V0.12 (raised in the first Comms review; open)
● **Applies to:** any service integrating a third-party API
● **Symptom:** The Mattermost API shapes Holly relies on (archived channels under include_deleted, direct and group messages in the per-team listing, no paging) and whether a non-member can read a public channel's posts were tested only against stand-ins.
● **Root cause:** No real Mattermost instance was available to the gates.
● **Fix:** None recorded.
● **Guard:** none recorded
● **Lesson:** Record which upstream behaviours the fakes assume, and confirm them once against the real service (a contract test or a recorded session) before relying on them.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "Real Mattermost: not verified."

### CQ-287 Database-specific SQL was pinned only as compiled text against a fake session

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** unranked (coverage note) · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.12 (rounds 1 and 2; accepted)
● **Applies to:** SQLAlchemy and PostgreSQL; any ORM with a fake session
● **Symptom:** PostgreSQL-specific SQL (ANY(ARRAY), EXTRACT(epoch) buckets, ILIKE with ESCAPE, the followed subquery, the NOT EXISTS prompt filter, migration 0019) is checked in pytest only as compiled SQL text on the session fake in tests/fakes.py, not executed on PostgreSQL.
● **Root cause:** The unit suite uses a session fake; real-database behaviour is left to the container smoke rung.
● **Fix:** No change recorded. The round 1 gate called the SQL sound by inference from the compiled-SQL assertions and the smoke PASS on cf5a234; later rounds passed with the gap still in their ledgers, so the acceptance is implicit.
● **Guard:** scripts/smoke-container.sh on PostgreSQL 16 (partial; not these queries specifically).
● **Lesson:** Run dialect-specific queries against the real database engine in at least one test tier; compiled-SQL assertions pin text, not results.
● **Evidence:** gate report: Engineering gate V0.12: "pytest uses the fake session and checks compiled SQL text only" Also: gate report: Engineering gate V0.12 round 2.

### CQ-288 A defensive nullish fallback branch is never taken

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** open · **Certainty:** fact
● **Releases:** V0.9 (raised round 2, carried open in round 3), still open at V0.10
● **Applies to:** TypeScript
● **Symptom:** The `?? ""` fallback on the request URL in frontend/src/api/client.ts (line 80 at HEAD) is never taken, holding the file's branch coverage below 100%.
● **Root cause:** A defensive default for a value axios sets in practice.
● **Fix:** None: the gate judged it harmless and the author chose not to take it; the V0.10 row lists it as still open.
● **Guard:** none recorded
● **Lesson:** Either cover a defensive branch with a test or remove it with a reason; an untaken branch is noise in coverage reports.
● **Evidence:** gate report: Engineering gate on V0.9 round 2: "It is defensive and harmless." Also: gate report: Engineering gate on V0.9 round 3; docs/AUDIT-LOG.md, V0.10 row.

### CQ-289 Shell checks were not linted and their portability was proven on one awk and one git

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer (coverage notes) · **Severity:** unranked · **Status:** open · **Certainty:** fact
● **Releases:** V0.6 row (the upload-baseline commit 97d90be; open)
● **Applies to:** shell tooling
● **Symptom:** shellcheck was not installed, so the new shell scripts (scripts/check-baseline.sh, scripts/check-reviews.sh) were not linted; awk behaviour was proven under mawk only, and only git 2.43.0 was tested.
● **Root cause:** Toolchain gap in the sandbox and the loop.
● **Fix:** None recorded: dash -n syntax checks and the passing nets stood in. The current loop has no shellcheck step.
● **Guard:** none recorded
● **Lesson:** Lint shell scripts in the loop and test them under each awk, shell and git the pipeline or developers may use.
● **Evidence:** gate report: Engineering gate on 97d90be: "shellcheck is not installed, so no lint was run on the shell scripts." Also: gate report: Security gate on 97d90be.

### CQ-290 Some refusals in a check have no case, because an earlier check refuses first

● **Rule:** none · **Raised by:** author (declared in the commit), confirmed by engineering-reviewer · **Severity:** unranked · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.6 row (the upload-baseline commit 97d90be; accepted)
● **Applies to:** any fail-closed script chain
● **Symptom:** scripts/check-baseline.sh shipped with three refusals without a case: a commit to package that does not resolve and a missing version there (the review check refuses both first), and a git error comparing the trees.
● **Root cause:** Upstream checks make the conditions unreachable in the nets harness.
● **Fix:** Declared in the commit message and accepted; the engineering gate confirmed the list accurate.
● **Guard:** none recorded
● **Lesson:** When a defensive refusal cannot be reached through the harness, list it explicitly with the reason, or test the script in isolation where it can be reached.
● **Evidence:** commit messages (git log): "Three refusals have no case: a commit to package" Also: gate report: Engineering gate on 97d90be.

### CQ-291 Edge cases in quick check-script parsers were left open

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** minor and nits · **Status:** open · **Certainty:** mixed
● **Releases:** V0.5 (open below the blocking bar)
● **Applies to:** custom verification scripts
● **Symptom:** The loop's lock-parity step keys a lock's entries by name, so a package uv lists twice for a marker split would not be compared; scripts/check-lcov.sh could pass with frontend/src missing, prints no reason for a file named twice, and calls a named test file missing; no upload net refuses a frontend/npm-shrinkwrap.json or frontend/.npmrc.
● **Root cause:** Checks built for today's files, without edge cases.
● **Fix:** None recorded; the lock step and check-lcov.sh at HEAD f8a00bd have the same shape.
● **Guard:** none recorded
● **Lesson:** Give each check script cases for missing inputs, duplicates and the less common forms its input format allows, so the check itself fails closed.
● **Evidence:** commit messages (git log): "Open below the gates' blocking bar, for a follow-up: the lock step's"

### CQ-292 A test-only timeout cap is not pinned

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** deferred · **Certainty:** fact
● **Releases:** V0.1 (raised on fab9044; deferred)
● **Applies to:** any stack
● **Symptom:** No test pins the 30-second cap on the secret-scan hook's timeout override used by the package content net.
● **Root cause:** A test-only setting judged low risk.
● **Fix:** Deferred; HOOK_TIMEOUT_CEILING_MS is still 30000 in scripts/scan-package.mjs at HEAD.
● **Guard:** none recorded
● **Lesson:** Even test-only limits deserve one case at the cap, or a recorded reason for leaving it unpinned.
● **Evidence:** docs/AUDIT-LOG.md, V0.1 row: "one engineering NIT is deferred: no test pins the 30-second cap on the hook timeout override, a test-only setting."

### CQ-293 A static contrast checker's known limits were left open

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** minor · **Status:** open · **Certainty:** fact
● **Releases:** V0.4 (open after round 7)
● **Applies to:** static accessibility or style checkers
● **Symptom:** The check measures a colour an @keyframes block animates only at its steps, where Chromium passes through colours between them (a swap of text and background reaching 1.02:1); it takes the scanlines to be black without reading their colour; further limits on conditional :root tokens and currentColor backgrounds, and the licence plugin does not guard a worker's own build.
● **Root cause:** Known limits of a static checker against a dynamic renderer.
● **Fix:** Recorded for a follow-up; Holly's own sheet and build hold none of them.
● **Guard:** none recorded
● **Lesson:** Publish a static checker's known blind spots with the check, so a later change that enters one is caught in review.
● **Evidence:** docs/AUDIT-LOG.md, V0.4 row: "the check measures a colour a @keyframes block animates only at its steps" Also: commit messages (git log).

### CQ-294 A test script's message misdescribed the test environment

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.8 (raised round 1, fixed round 2)
● **Applies to:** container smoke tests
● **Symptom:** The smoke rung's DAST step in scripts/smoke-container.sh said 'no network', but the container runs on Docker's default bridge.
● **Root cause:** Imprecise wording: what was meant was not on the database's network.
● **Fix:** Reworded to say the container is not on the database's network.
● **Guard:** none recorded
● **Lesson:** Test output is evidence others rely on; state the environment a test sets up precisely.
● **Evidence:** gate report: Engineering gate on V0.8 DAST: "is inaccurate: the container runs on Docker's default bridge."

### CQ-295 A version-consistency test must cover every file that carries the version

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.3 (raised in gate round 1 on 65be203, fixed in a6ee4df)
● **Applies to:** any stack with the version in several manifests
● **Symptom:** Holly's tests/test_version.py did not check the dashboard's package.json and package-lock.json, so a bump could leave them at the old version with the suite green.
● **Root cause:** The test listed the version's homes when it was written and was not extended when the dashboard's manifest and lockfile, which also carry the version, joined the upload (inference on timing).
● **Fix:** a6ee4df extends the test to the dashboard's manifest and both lockfile root fields, shown failing with each of the three fields at 0.2.0.
● **Guard:** tests/test_version.py; CLAUDE.md names the files it holds equal to __version__
● **Lesson:** Whenever a new file starts carrying the release version, add it to the consistency test in the same change, and show the test fails with each field changed alone.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "two nits (developer setup did not say how '--wait' fails; the version test did not cover the dashboard)"

### CQ-296 A test of a retry loop must end on its own when the loop's guard is removed

● **Rule:** none · **Raised by:** found while mutation-testing the fix (session summary); confirmed closed by security-reviewer round 3 · **Severity:** not recorded · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.6 (hit while adding the round 2 tests for the client's refresh guards; confirmed by the round 3 security gate, committed in 691f25b)
● **Applies to:** any test suite; Vitest and HTTP client interceptors
● **Symptom:** While pinning Holly's HTTP client refresh guards, a mutant that removed the `_retry` guard made Vitest loop forever and hang the run. Files: frontend/src/api/client.ts, frontend/src/api/client.test.ts.
● **Root cause:** The test's fake answered every refresh, so with the guard gone the interceptor retried without end and the test could neither pass nor fail (inference from the fix).
● **Fix:** The test refuses a second refresh, so the mutant fails fast; the round 3 security gate ran each client mutant under a 180-second timeout and none hung.
● **Guard:** frontend/src/api/client.test.ts case 'refreshes once only, then signs out, when the retry is refused too'
● **Lesson:** When a test covers a loop guard, make its fakes stop answering after the expected number of calls, so removing the guard turns the test red quickly instead of hanging, and run mutants under a timeout.
● **Evidence:** session summaries: "A '_retry' mutant made Vitest loop forever. I killed it, restored 'client.ts', and made the test refuse a second refresh so the mutant fails fast." Also: gate report: Security gate, V0.6 round 3.

## 2.6 Build, packaging, pipeline and container


### CQ-297 The platform's test job installs the default requirements file, so a runtime-only lock leaves out the test runner

● **Rule:** none · **Raised by:** App Store pipeline (python test job) · **Severity:** platform-fail · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.4 (raised by the platform), V0.5 (fixed)
● **Applies to:** any stack whose platform generates its own test job; Python with hash-pinned pip lockfiles
● **Symptom:** V0.4's upload (dccfbdc, zip ff5d3658, merge request 2) failed at the test stage. The App Store's python job, on python:3.12-slim, runs `pip install -r requirements.txt` then `pytest --cov --cov-report=xml:coverage.xml`; requirements.txt held only the image's runtime set, so pytest was not installed and the job stopped with exit 127 (`sh: 1: pytest: not found` when V0.5's simulation reproduced it on dccfbdc).
● **Root cause:** One lockfile served two consumers: the image's runtime install and the platform's test job, which installs requirements.txt by name and expects the test tools in it. The local pipeline simulation did not yet run each platform job with the commands its log shows (inference: V0.5 added exactly that).
● **Fix:** The runtime set moved to requirements-runtime.in and requirements-runtime.txt, which the Dockerfile installs; requirements.in and requirements.txt now hold it with pytest, pytest-cov and pytest-asyncio, and requirements-dev.in builds on them. No pinned version moved, and the image installs only the runtime lock. Packaging refuses an upload without requirements-runtime.txt.
● **Guard:** A verify.sh step refuses a package one lock pins unless the lock that extends it pins the same version, marker and hashes; pip-audit covers all three locks; scripts/simulate-pipeline.sh runs both platform test jobs, each on a fresh checkout of the upload, with the logged commands. Reproduced first: the new simulation on dccfbdc failed both jobs exactly as the platform did.
● **Lesson:** Find out exactly which file and command the platform's test stage runs, and give the test job its own lock layered over the runtime lock, with a check that the layers pin alike. Rehearse every platform job on a fresh checkout of the upload before handing it over.
● **Evidence:** scripts/upload-baseline.txt: "0.4.0 failed # V0.4, zip ff5d3658, merge request 2: both test jobs failed at the test stage" Also: docs/AUDIT-LOG.md, V0.5 row; scripts/verify.sh.

### CQ-298 A platform job that runs the package manager at the upload root fails when the front end's manifest lives in a subfolder

● **Rule:** none · **Raised by:** App Store pipeline (node test job); security-reviewer (nit on the fix, V0.5 round 1) · **Severity:** platform-fail · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.4 (raised by the platform), V0.5 (fixed)
● **Applies to:** monorepos or server apps with a nested JavaScript front end on a platform that detects a Node stack
● **Symptom:** In the same V0.4 upload the node job, on node:24-alpine, ran `npm ci` at the upload's root, which held no package, and failed with `npm error code EUSAGE` (exit 1). The console detects Holly's stack as node-react; that this detection is what puts a node job at the root is inference, as CLAUDE.md records.
● **Root cause:** The React dashboard's package.json and lockfile lived only under frontend/, while the platform's node job runs at the upload's root.
● **Fix:** A root package.json and package-lock.json holding no packages run `npm ci --prefix frontend --ignore-scripts` as their postinstall and hand `test` and `build` to the dashboard. The upload's required members gain both root files. SECURITY.md records the postinstall as an accepted position (no package install script runs; the root holds no packages). The security gate's nit that the first test checked named fields only led to a test that holds both root files whole.
● **Guard:** tests/test_root_node_project.py holds the root project's scripts exactly and refuses any package there (a change to either is a security change); packaging refuses an upload missing either root file; scripts/simulate-pipeline.sh runs the node job on a fresh checkout.
● **Lesson:** Mirror the layout the platform's detected stack expects at the upload root, delegating to the real project with install scripts off, and pin the delegating manifest whole in a test so it cannot quietly widen.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "The node job, on node:24-alpine, runs 'npm ci' at the upload's root, which held no package (EUSAGE, exit 1)." Also: SECURITY.md; CLAUDE.md@f8a00bd.

### CQ-299 A fail-closed start never serves when the platform's DAST scan runs the image with no settings

● **Rule:** none · **Raised by:** App Store pipeline (DAST stage) · **Severity:** platform-fail · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised by the platform), V0.8 (fixed; all 11 stages passed)
● **Applies to:** any containerised web app on a platform with a DAST stage that runs the image without its configuration
● **Symptom:** V0.7's upload (452e3c7, merge request 3) failed DAST on `no_report`: the scanner got no answer from http://dast-target:8080 within 300 seconds. The scan runs the image with APPSTORE_DAST_SCAN=true and none of the app's variables or secrets, and retrying the same image fails the same way. Run locally with the flag only, the V0.7 image exits 1 with `Holly cannot start: APP_SECRET_KEY: Field required`.
● **Root cause:** Boot refusals that are right for production (no signing key, no database) met a stage that gives the container nothing. The smoke rung always supplied settings, so it never ran the image as the scan does. The platform's log advises generating a throwaway signing key under the flag.
● **Fix:** src/app/dast_scan.py, called first in the gunicorn master, acts under the flag alone: a throwaway APP_SECRET_KEY from `secrets` when none is set (never logged), a temporary procedure store when none is configured, background pulls off, one `dast_scan` log line of what it set. Settings allow no database under the flag alone (half a set is still refused); `sqlalchemy_url` raises DatabaseNotConfiguredError, answered as a plain 503, and the master skips the migrations and admin bootstrap. Gate round 1 minors closed in round 2: the flag's name read in any letter case, blank database variables read as unset, a blank APP_SECRET_KEY refused. SECURITY.md records the relaxed start, with the trip-wire never to set the flag by hand; the operator manual says a live start never carries the flag and to remove it if the `dast_scan` line appears outside a scan.
● **Guard:** scripts/smoke-container.sh step 3d runs the built image with nothing but APPSTORE_DAST_SCAN=true, requires 200 on 8080 within 120 seconds, 503 on a route that needs the database and the `dast_scan` log line, then repeats with the flag and a database. The deploy-gate probes the scan start (V0.8: 8080 answered in 2.8 seconds; 4,124 requests, none answering 500). The baseline skills appstore-gate-compliance and app-store-deployment gained the DAST stage.
● **Lesson:** Read each scan stage's contract and start the image exactly as that stage does, with no settings, in the local smoke test. Keep fail-closed refusals for production, but give the scan, and only the scan, a safe degraded start that still listens on the port.
● **Evidence:** the app owner's message: "no_report: the scanner got no answer from http://dast-target:8080 within 300 seconds, so nothing was scanned." Also: gate report: Engineering gate on V0.8 DAST; scripts/smoke-container.sh@f8a00bd; SECURITY.md; docs/runbook/operator-manual.md@f8a00bd.

### CQ-300 Confirm the platform's mounted volume is writable by the image's non-root user before the first deploy

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** BLOCKER · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the deploy-gate), V0.7 (BLOCKER, then cleared on the platform team's confirmation), V0.10 (recorded as settled)
● **Applies to:** any non-root container that writes to a platform-mounted volume
● **Symptom:** The V0.5 deploy-gate failed partly on no fsGroup 10001 request for FILE_STORAGE. The V0.7 deploy-gate on 452e3c7 failed with a BLOCKER: nobody had confirmed that /data (the S3-backed FILE_STORAGE add-on) accepts mkdir, create, write and delete by user 10001. Its probe with a root-owned /data showed Holly stopping at boot (`storage_writable` false, errno 13, exit 3).
● **Root cause:** A platform permission outside the code: the container cannot grant its own user write access to a mounted volume, and the boot-time storage probe fails closed, so an unconfirmed volume means a failed start.
● **Fix:** No code change. The app owner relayed the platform team's confirmation that Holly's user can write to /data (19 October 2026); the deploy-gate re-run passed with the item resting on that confirmation. V0.8 and V0.9 started on the platform, and V0.10 recorded /data as writable by user 10001 in the operator manual and CLAUDE.md.
● **Guard:** src/app/services/procedure_storage.py writes and deletes a probe file at boot and src/app/factory.py logs storage_writable=false with the errno and stops, so a wrong confirmation shows at once; the smoke rung refuses a read-only store at boot (exit 3 in the V0.7 deploy-gate re-run).
● **Lesson:** Treat volume ownership as a deploy precondition: request the group or mount options the non-root user needs, record the platform's answer, and have the app probe the mount at start and stop with a clear log line if it cannot write.
● **Evidence:** gate report: Deploy-gate on V0.7: "[BLOCKER] Storage permission (FILE_STORAGE) | Nobody has confirmed that '/data' accepts mkdir, create, write and delete by user 10001" Also: the app owner's message; docs/AUDIT-LOG.md, V0.10 row; gate report: Deploy-gate re-run on V0.7.

### CQ-301 Retry only transient database failures at start, and stop at once on a refusal

● **Rule:** none · **Raised by:** App Store DAST job log (advice); engineering-reviewer (MAJOR, V0.8 round 1) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (advised by the platform's DAST log), V0.8 (fixed after an engineering MAJOR in round 1)
● **Applies to:** any service that connects to a managed database at container start
● **Symptom:** The V0.7 DAST job log advises retrying the database for about a minute; Holly stopped at its first failed connection. V0.8's first wait then retried everything: a wrong password, a missing database or a missing role was retried for about 62 seconds and then reported as the database not answering, where V0.7 had named the refusal.
● **Root cause:** First no retry at start, then a retry that did not tell a database not yet reachable from one that answers and refuses.
● **Fix:** `wait_for_database` in src/app/migrate.py, run at every start, retries an unreachable host, SQLSTATE 57P03 (starting) and class 08 (dropped connection) for about 60 seconds with a 5-second connect timeout, and stops at once on any other refusal, naming its SQLSTATE and the driver's error class, never an error's text.
● **Guard:** tests/test_migrations.py TestWaitForDatabase; mutants of the refusal filter and the starting-up and connection-class branches each turned a test red; the engineering gate confirmed it live through gunicorn (a wrong password stopped in 1 second naming 28P01; an unresolvable host retried for 61 seconds). Left open below the blocking bar: the 60-second deadline and the class-08 boundary are unpinned, and no test proves a refusal never repeats the driver's text.
● **Lesson:** A start-up wait should retry only what time can cure (unreachable, starting, connection dropped) and fail fast, with an error code and no secret, on authentication or missing-object errors.
● **Evidence:** docs/AUDIT-LOG.md, V0.8 row: "advises generating a throwaway signing key under that flag and retrying the database for about a minute" Also: CHANGELOG.md.

### CQ-302 Record every upload handed to the platform, so the changed-code window is known and a version bump is enforced

● **Rule:** none · **Raised by:** deploy-gate (MAJOR) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the deploy-gate; 97d90be added the record), V0.6 (hardened after both review gates failed 97d90be)
● **Applies to:** any app shipped to a platform that scores changed code per upload
● **Symptom:** The deploy-gate failed V0.5 with, among others, a MAJOR for no upload baseline record. The platform scores new code against the previous upload, passed or failed, and that boundary was recorded nowhere in the repository (V0.4's upload, ff5d3658 from dccfbdc, merge request 2, had failed at the test stage).
● **Root cause:** Uploads were handed over by hand, with no committed record of which commit each zip came from or how the platform judged it.
● **Fix:** scripts/upload-baseline.txt records each upload (full commit id, version, outcome, the zip's SHA-256 prefix, merge request, failing stage), one appended line per handover, never edited. scripts/check-baseline.sh, run by packaging for upload after the review check, refuses when the record is missing, unreadable or disagrees with its commit, and prints the files that differ (V0.5's window: 42 files); at 97d90be it refused an upload changed under the baseline's version, and from V0.6 it requires a higher version. Rehearsals skip it. Each recorded zip prefix was reproduced as the SHA-256 of a rehearsal of its commit. Both gates then failed 97d90be on a commit-graph bypass, closed in V0.6 (see the entry on git-history checks).
● **Guard:** check-baseline.sh in package-appstore.sh and among the packaging tools the review check compares by content; 17 new upload-net cases (191 in all at 97d90be); SECURITY.md row 'The upload baseline proves the record, not the handover'.
● **Lesson:** When a platform measures new code against the previous upload, keep a committed, append-only ledger of uploads and have the packager refuse without it, print the window, and require a higher version for any changed upload.
● **Evidence:** the app owner's message: "no upload baseline record (V0.4's upload, ff5d3658 from dccfbdc, merge request 2, failed at the test stage)" Also: scripts/upload-baseline.txt; commit messages (git log); docs/AUDIT-LOG.md, V0.6 row.

### CQ-303 Packaging checks that read git history must switch off replace refs, grafts, the commit-graph and config overrides

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised and fixed in the review-record check), V0.6 (raised again in the baseline check and fixed)
● **Applies to:** any release or packaging script that decides from git history
● **Symptom:** V0.3: in the review-record check, the guard against replace refs could be deleted with the self-test green, and a replace ref then forged the record. V0.6: both gates failed 97d90be on one shared MAJOR: check-baseline.sh set the replace-ref and graft overrides but not core.commitGraph=false, and a forged commit-graph made an upload changed under the baseline's version read as unchanged (exit 0). Round 1 on the V0.6 tree added (a security nit) that GIT_CONFIG_PARAMETERS could turn the commit-graph back on, and round 2 (engineering MAJOR) that nothing pinned its unset.
● **Root cause:** Git reads parents and trees from local caches and honours local configuration, so a check that trusts `git diff` or `git log` in a writable clone can be steered by anyone who can write to .git/ or the environment. Each new script copied only some of the overrides.
● **Fix:** 153c91e, 8c70dbd and 691f25b: every packaging script ignores replace refs; the packager, the review check and the baseline check ignore grafts; the review and baseline checks also turn the commit-graph off (core.commitGraph=false through GIT_CONFIG_*) and unset GIT_CONFIG_PARAMETERS; the review check's bump search also ignores a local textconv and signature display. The packager's upstream comparison still reads the commit-graph file, a limit SECURITY.md states (see the entry on residual limits).
● **Guard:** Forged-commit-graph cases in scripts/test-package-nets.sh, run again with GIT_CONFIG_PARAMETERS turning the graph on and red with either unset removed, alongside replace-ref and graft cases; SECURITY.md states that both checks ignore replace refs, grafts and the commit-graph file.
● **Lesson:** Give every history-reading release check the same set of anti-forgery overrides, and back each override with a planted forgery case that goes red without it.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "MAJOR: the guard against replace refs could be deleted with the self-test green, and a replace ref then forged the record" Also: gate report: Engineering gate on 97d90be; docs/AUDIT-LOG.md, V0.6 row; scripts/check-baseline.sh@f8a00bd.

### CQ-304 An upload content scan must decide positively what it can read and refuse everything else

● **Rule:** none · **Raised by:** security-reviewer and engineering-reviewer · **Severity:** gate FAIL (security, four rounds running) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.1 (raised and fixed over five gate rounds)
● **Applies to:** any packaging step that scans an upload or image for secrets
● **Symptom:** Packaging scans each file in the upload with the secret-scan hook's rules. Both gates failed b56e04c: the net passed member names back to unzip, which reads brackets as a wildcard and lists control characters escaped, so those members were never read and the empty input passed (a key in src/app/[leak].py packaged with exit 0). Security then failed 85962f4 (compressed content under an upper-case or unlisted name), 774173a (a list of format signatures still let zlib, raw deflate, LZMA-alone and a zipapp through) and 28de168 (ASCII behind a stray UTF-16 byte-order mark decoded into characters the rules could not read).
● **Root cause:** Each version enumerated what to refuse (names, then format signatures, then encodings), so anything outside the list passed as clean, and a read the scanner could not perform looked like an empty, clean file.
● **Fix:** scripts/check-package.sh extracts the zip once and scripts/scan-package.mjs walks every file; a missing hook, any other status, a read error or a file count that differs from the archive's reads as 'could not scan' and refuses. From ac0c5bc only strict UTF-8 without control characters counts as text; every other file is refused unless scripts/upload-binaries.txt, read from HEAD, pins it by SHA-256 with a reason; a duplicate allowlist path is refused (fab9044).
● **Guard:** scripts/test-package-nets.sh (58 cases at fab9044, each bypass the gates found among them), run by verify.sh; SECURITY.md treats an allowlist change as a security change and carries a UTF-16LE trip-wire.
● **Lesson:** A secret scanner on a release artefact should accept only what it can provably read and fail closed on everything else, with an explicit, hash-pinned allowlist for binaries; a failed read must never look like a clean one.
● **Evidence:** docs/AUDIT-LOG.md, V0.1 row: "both FAIL on b56e04c, because its new package content net reported files clean that it could not read (bracketed and control-character names)" Also: commit messages (git log).

### CQ-305 Upload name checks must judge each member name byte for byte as it will be extracted

● **Rule:** none · **Raised by:** security-reviewer (MAJOR), engineering-reviewer (minors) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised and fixed)
● **Applies to:** any upload or artefact check that refuses files by name
● **Symptom:** Security failed the V0.3 gate round covering 6d03e18 (which refuses the agent configuration in the upload by name) on a defect older than that change: a member name holding a DEL or a byte above 0x7E passed every name check, and extraction dropped or changed the byte, so `prod.en<DEL>v` landed as `prod.env` and `CLAUDE<DEL>.md` as `CLAUDE.md`. Round 2 found that a backslash passed (both gates) and, from security, that Info-ZIP strips a VMS version suffix, so `CLAUDE.md;1` had landed as `CLAUDE.md` at 0c67540, which 96136cf's round trip already refused.
● **Root cause:** The name net matched names as stored in the archive, while the extractor normalises them, so a banned name could arrive in disguise.
● **Fix:** 96136cf refuses names outside printable ASCII and any file that does not land under its listed name, and refuses on a grep error; 37c1756 refuses a backslash and pins the locale with an executable named with a raw byte; d429bff pins the VMS route and records the Unicode Path extra field in SECURITY.md with its trip-wire.
● **Guard:** test-package-nets.sh cases for each route (78 upload-net cases at 4827acb), every guard shown to turn the self-test red when removed.
● **Lesson:** Check archive member names as the consumer will see them: restrict the allowed byte set, extract once, compare what landed with what was listed, and refuse any mismatch.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "a member name holding a DEL or a byte above 0x7E passed every name check and extraction dropped or changed the byte, so 'prod.en<DEL>v' landed as 'prod.env'"

### CQ-306 A packaging gate that reads a review record must fail closed, and each of its guards needs a case that fails without it

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised and fixed over four rounds)
● **Applies to:** any scripted release gate that reads approvals or records from the repository
● **Symptom:** 7eedb7b made packaging for upload refuse unless both reviews passed, read from scripts/upload-record.txt. The gates failed it three rounds running: a FAIL filed under another version label was dropped, so the packager wrote the upload with a FAIL last; four guards could be deleted with the self-test green; a rehearsal path through a symlink and .., or a symlinked dist/, reached the upload path; the upstream check failed open through a file named like its range, a missing upstream, a graft or no upstream at all; and a mutant reading the working copy's record left every case green.
● **Root cause:** The record check trusted its inputs (labels, paths, upstream state) and read an error as a pass, and the self-test proved behaviour without proving that each guard was needed.
● **Fix:** e40e12b, 153c91e and 8c70dbd: the last line from each reviewer decides whatever commit it names; HEAD is resolved once and the run refuses if it moves; each packaging tool is compared by content; a zip is refused unless it is exactly the committed files; rehearsals are written outside dist/, resolved physically and compared with dist/ by inode; an upload comes only from the tip of a local branch not behind its upstream, refusing an upstream that does not resolve; the committed record is read, never the working copy.
● **Guard:** On 153c91e, 48 single-guard mutations each turned the clone cases red; on 8c70dbd, 34 more did, and so did the engineering gate's port of round 3's other 38. Guards killed only through a refusal's wording are named in the V0.3 audit row with what refuses in their place.
● **Lesson:** For any release gate, list the ways it can fail open (stale labels, symlinks, missing upstreams, working-copy reads) and prove each guard by deleting it and watching a case go red.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "MAJOR: a FAIL filed under another version label was dropped, so the packager wrote the upload with a FAIL last"

### CQ-307 Start the server in exec form through the app's validated port parser, never by shell-expanding PORT

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer (both FAIL on 9616c41) · **Severity:** gate FAIL (finding rank not recorded) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.1 (raised and fixed)
● **Applies to:** any container that reads its port from the environment
● **Symptom:** The scaffold's template CMD started gunicorn through `sh -c` with `-b 0.0.0.0:${PORT:-8080}`. Both gates failed 9616c41; the fix commit names a silent misbind on PORT=0, flag injection through an unquoted PORT, and a false Errno 13 boot error from gunicorn's control socket.
● **Root cause:** The shell expanded an untrusted variable straight into the command line, bypassing the validated parser the dev server used, and gunicorn's control socket, on by default, produced a false boot error in the hardened container.
● **Fix:** c0a25dc: gunicorn starts in exec form with `--config python:app.gunicorn_conf`, which binds 0.0.0.0 through the same validated PORT parser as the dev server and disables the control socket; PORT must be canonical.
● **Guard:** tests/test_gunicorn_conf.py (b56e04c derives the setting names from the module, so a misspelt setting fails); the smoke rung refuses a malformed PORT and checks PORT unset and PORT=9090.
● **Lesson:** Resolve and validate the listen port once, in code every entry point shares, start the server in exec form with that configuration, and switch off server defaults that need a writable filesystem.
● **Evidence:** Dockerfile@9616c41: "CMD ["sh","-c","exec gunicorn --chdir /app --pythonpath /app/src app.main:app -k uvicorn_worker.UvicornWorker -b 0.0.0.0:${PORT:-8080}"]" Also: commit messages (git log).

### CQ-308 Make image hardening steps self-checking so a skipped step fails the build

● **Rule:** `none (V0.6 follow-ups: SonarQube S8541, S8431)` · **Raised by:** engineering-reviewer and security-reviewer (both FAIL on 9616c41); SonarQube on V0.5's upload for the V0.6 follow-ups · **Severity:** gate FAIL (finding rank not recorded) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.1 (raised and fixed); V0.6 (related SonarQube fixes to the same Dockerfile)
● **Applies to:** any hardened container build
● **Symptom:** The scaffold Dockerfile ran `apt-get update && ... upgrade`, so a failed index fetch passed as 0 upgraded; `COPY . /app` took the whole build context; the user was created without a matching group or an explicit no-home flag; nothing removed group or world write from the code; the setuid sweep and pip removal were never verified; `# syntax=docker/dockerfile:1` pulled a floating frontend image on every build.
● **Root cause:** The template Dockerfile hardened by intent but asserted nothing, so a silent failure in any step still produced an image.
● **Fix:** c0a25dc: `apt-get update --error-on=any`; `COPY src /app/src`; `groupadd -g 10001` and `useradd -u 10001 -g 10001 -M`; `chmod -R go-w /app`, so code is writable by root alone; read-only checks after the setuid/setgid sweep fail the build if a setuid bit or pip survives; the syntax directive removed; the HEALTHCHECK omission recorded in the Dockerfile header (Kubernetes ignores it and probes the health paths). In V0.6, after SonarQube findings on V0.5's upload, pip installs wheels only (`--only-binary :all:`, S8541) and the bases are named by digest alone (S8431).
● **Guard:** The build fails if a setuid bit or pip survives; every deploy-gate checks the built image for one layer, uid 10001, no setuid bits and no pip.
● **Lesson:** Make each hardening step in an image build verify its own result, copy only what the runtime needs, and pin build front ends and base images by digest.
● **Evidence:** Dockerfile@c0a25dc: "# --error-on=any makes a failed index fetch reach the warning instead of passing as "0 upgraded"." Also: commit messages (git log); docs/AUDIT-LOG.md, V0.6 row.

### CQ-309 Rehearse every documented operator command inside the built image, not in the development tree

● **Rule:** none · **Raised by:** engineering-reviewer (MAJOR, V0.10 round 1) · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised and fixed)
● **Applies to:** any containerised app with documented migration, rollback or admin commands
● **Symptom:** The only documented rollback across migration 0018 was `alembic downgrade 0017_audit_append_only`. In the V0.10 container it fails with `FAILED: No 'script_location' key found in configuration.` (exit 255), because the image ships no alembic.ini (the Dockerfile copies only src/).
● **Root cause:** The command was written against the repository, where alembic.ini sits at the root, and was never run in the image the operator would use.
● **Fix:** The docs (ADR-014 and the operator manual) give a form the engineering gate rehearsed on PostgreSQL with V0.10 and V0.9 images: a `python -c` call of Alembic's `command.downgrade` with `app.migrate.alembic_config()`, run in the V0.10 container immediately before V0.9 is deployed.
● **Guard:** The deploy-gate rehearses the rollback live on later releases (V0.12: V0.11 refuses a database at 0019, the manual's downgrade to 0018 succeeds, V0.11 then starts). Still open: the command needs a shell in the container, and whether the platform offers one is TBC, re-verify.
● **Lesson:** Any command a runbook tells an operator to run in production must be executed in the shipped image during review; configuration files that exist only in the repository are a common reason it fails.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "In the V0.10 container, 'alembic downgrade 0017_audit_append_only' fails with 'FAILED: No 'script_location' key found in configuration.' (exit 255). The image ships no alembic.ini." Also: docs/AUDIT-LOG.md, V0.10 row; docs/AUDIT-LOG.md, V0.12 row; gate report: Deploy gate V0.12.

### CQ-310 Write the coverage report where the platform's job runs, with paths from that root, and check it names every source file

● **Rule:** none · **Raised by:** pipeline simulation; engineering-reviewer (nits, V0.5 round 1) · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.5 (raised and fixed)
● **Applies to:** any project whose coverage report is read by a platform quality gate, especially with nested front ends
● **Symptom:** The node job runs at the upload root, so lcov paths had to resolve from there. The first V0.5 simulation found the lcov naming the test setup file, which Vitest leaves out of every report; the engineering gate noted the loop only checked that the lcov existed and that the test helpers counted as source. The dashboard had been 11.67% covered against the 80% Code Quality holds an upload to.
● **Root cause:** Coverage tools name files relative to their own root, and a report can exist yet miss or misname files, which a report check that scores a missing file at 0% would punish (inference, from the baseline skill).
● **Fix:** Vitest writes coverage/lcov.info at the repository's root, naming each file from there (frontend/src/...), with an 80% floor; `test.globals` replaced the setup file; scripts/check-lcov.sh refuses a report that does not name exactly the non-test files under frontend/src (it refused 4 broken reports and accepted a good one).
● **Guard:** scripts/check-lcov.sh, run by verify.sh and by simulate-pipeline.sh on the node job's checkout. Left open below the blocking bar at V0.5: it could pass with frontend/src missing, prints no reason for a file named twice, and calls a named test file missing.
● **Lesson:** Generate each coverage report from the directory the platform's job runs in, and check that the report names exactly the source files the analyser will score, not merely that it exists.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "writes 'coverage/lcov.info' at the repository's root, naming each file from there ('frontend/src/...'), as the node job runs at the root" Also: commit messages (git log).

### CQ-311 Version checks on an upload must read exactly one version and compare numerically

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer (minors and a nit) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised and fixed)
● **Applies to:** any release script that enforces version bumps
● **Symptom:** Gates on check-baseline.sh (97d90be) and the V0.6 tree found: the bump rule only checked that the version differed, so 0.4.0 after a 0.5.0 baseline passed; a version set in two lines read as neither; an annotated second `__version__` passed both the review and baseline checks; and 0.6 against 0.6.0 was refused as below the baseline's, which misleads though it fails closed.
● **Root cause:** Line-based version extraction without a uniqueness rule, inequality used where ordering was meant, and text equality mixed with numeric ordering.
● **Fix:** Both checks refuse more than one line starting `__version__`, or one not in the strict form; a changed upload needs a strictly higher version, comparing dotted numbers; versions equal as numbers refuse with the baseline's bump-the-version message.
● **Guard:** tests/test_version.py holds the source to one plain assignment and the other copies equal; upload-net cases for a lower version, an annotated second line and equal-as-numbers versions (the last killed only through wording, as recorded).
● **Lesson:** Read the version from one canonical declaration, refuse ambiguity, and compare versions as number sequences, with cases for lower, equal-but-written-differently and duplicated declarations.
● **Evidence:** gate report: Engineering gate on 97d90be: "The bump rule only checks that the version differs from the baseline's, so a changed upload with a lower version (for example 0.4.0 after a 0.5.0 baseline) passes." Also: docs/AUDIT-LOG.md, V0.6 row; gate report as received.

### CQ-312 Build and probe the container from the upload artefact, and extend the probe with each new runtime dependency

● **Rule:** none · **Raised by:** review gates on the scaffold (inference: the fix commit addresses both gates' findings); engineering-reviewer (minor, V0.12 round 1) · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (raised and fixed), V0.12 (raised again for newly packaged files and fixed)
● **Applies to:** any containerised app
● **Symptom:** At the scaffold nothing exercised the deploy contract (port, health paths, boot refusals) on an image built from what is actually uploaded. In V0.12 the two manuals were newly copied into the image and served at /api/v1/manuals/{slug}, but scripts/smoke-container.sh never checked that the image carries them or that the route answers 200; it rested on inference from the Dockerfile COPY lines.
● **Root cause:** The loop proved the source tree, not the artefact the platform builds, and new runtime dependencies on files in the image were added without a matching probe.
● **Fix:** c0a25dc: scripts/smoke-container.sh builds the image from the upload artefact, probes the contract and refuses a malformed PORT. It grew with the releases: PostgreSQL with the FILE_STORAGE writable mount and migrations under the advisory lock (V0.2), the admin bootstrap and sign-in (V0.7), the DAST start (V0.8), /api/v1/auth/me with the token in each header (V0.9), the Users flow (V0.10). f6056cd fetches each manual from the running image and checks it answers 200 with the manual's own opening text.
● **Guard:** CLAUDE.md requires the smoke rung before every upload; each deploy-gate builds from the upload and runs it.
● **Lesson:** Make the last pre-upload rung build the image from the packaged artefact and probe the platform contract end to end, and add a probe whenever a release makes the runtime depend on a new file or route.
● **Evidence:** commit messages (git log): "Tooling: a container smoke rung builds from the upload artefact, probes" Also: gate report: Engineering gate V0.12; scripts/smoke-container.sh@f6056cd; docs/AUDIT-LOG.md, V0.7 row; docs/AUDIT-LOG.md, V0.9 row.

### CQ-313 A pipeline simulation must run with only the tools the platform's job has

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer (minors left on c0a25dc) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.1 (raised and fixed)
● **Applies to:** any local simulation of a CI or platform job
● **Symptom:** The local simulation of the platform's test job ran on an allowlisted PATH at c0a25dc that still included /usr/bin and /bin, so git, curl, tar or bash on the host could stand in for tools the platform's job lacks; neither rung exited cleanly on Ctrl-C, and the smoke rung left its build context behind.
● **Root cause:** The simulation's PATH allowlist took whole system directories, and the rungs had no signal traps or smoke cleanup.
● **Fix:** b56e04c: PATH holds only the venv and sh, with a premise check that git, curl, tar and bash are unreachable; both rungs exit cleanly on Ctrl-C; the smoke rung removes its build context unless KEEP_SMOKE=1 (c0a25dc had already made the simulation clean up unless KEEP_SIM=1 and added INSTALL_CMD and TEST_CMD overrides for the platform's test command once confirmed).
● **Guard:** The premise check inside scripts/simulate-pipeline.sh.
● **Lesson:** A local rehearsal of a platform job should start from an allowlisted environment and assert that host tools the platform lacks are unreachable, or it will pass where the platform fails.
● **Evidence:** commit messages (git log): "Simulation: PATH now holds only the venv and sh, with a premise check" Also: scripts/simulate-pipeline.sh@c0a25dc.

### CQ-314 Packaging and its self-test must never leave a stale, unchecked or rewritten upload artefact

● **Rule:** none · **Raised by:** not recorded for the V0.1 changes (found during the net rounds); security-reviewer (minors, V0.3) · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (fixed), V0.3 (stale zip and rehearsal placement fixed)
● **Applies to:** any packaging script with a fixed output path
● **Symptom:** In V0.1 the nets' self-test packaged in the working repository, rewriting dist/appstore.zip, and the upload zip's mode drifted from 0644 during the rework. In V0.3 security noted that the rehearsal zip in dist/ was the upload without the check, and that a stale upload zip outlived later runs.
● **Root cause:** Tests and rehearsals ran the real packager against the real output path, and a failed run could leave an earlier artefact in place.
● **Fix:** 85962f4: package-appstore.sh builds under a temporary name and moves the zip to dist/appstore.zip only when every net passes; a failure removes it and any stale upload zip. 774173a restores mode 0644. ac0c5bc: the self-test packages HEAD in a throwaway clone. e40e12b removes the last upload zip on every run and writes rehearsals outside dist/.
● **Guard:** scripts/test-package-nets.sh, including a case for the real package from HEAD at mode 0644.
● **Lesson:** Write release artefacts atomically, only after every check passes, remove stale ones on failure, and keep tests and rehearsals away from the real output path.
● **Evidence:** commit messages (git log): "package-appstore.sh builds under a temporary name and moves the zip to" Also: docs/AUDIT-LOG.md, V0.3 row.

### CQ-315 Tests that need full git history break on CI's default shallow checkout

● **Rule:** none · **Raised by:** GitHub CI (the verify workflow) · **Severity:** CI red · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.4 (raised and fixed)
● **Applies to:** any CI that runs history-dependent tests
● **Symptom:** CI went red on 9d8c8d0: actions/checkout fetches one commit, git writes no commit-graph in a shallow clone, and the upload-net self-test's forged commit-graph case (added in 8c70dbd) failed at its chmod.
● **Root cause:** CI's checkout depth differed from the local clones the self-test was written against.
● **Fix:** 3a99acb: CI checks out the full history (fetch-depth 0), and the self-test refuses a shallow clone by name.
● **Guard:** The self-test's shallow-clone refusal, which later stopped a scratch clone the same way until `git fetch --unshallow`.
● **Lesson:** Tests that depend on git history should detect a shallow clone and refuse with a clear message, and the CI checkout should fetch the depth they need.
● **Evidence:** commit messages (git log): "CI went red on 9d8c8d0: actions/checkout fetches one commit, git" Also: docs/AUDIT-LOG.md, V0.4 row; session summaries.

### CQ-316 A compose wait returns before the database listens on TCP unless its health check asks over TCP

● **Rule:** none · **Raised by:** the first run of scripts/dev.sh; engineering-reviewer and security-reviewer (minors and nits on the fix) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised and fixed)
● **Applies to:** local development stacks with Docker Compose and PostgreSQL
● **Symptom:** scripts/dev.sh's first run had its migrations' first connection reset: infra/docker-compose.yml had no health check, so `docker compose up --wait` returned as soon as the container started, while on a fresh volume PostgreSQL runs initdb and a temporary server on its Unix socket alone.
● **Root cause:** No health check, and a socket-based pg_isready would also pass during the temporary first-start server.
● **Fix:** A pg_isready health check over TCP (`-h 127.0.0.1`) holds `--wait` until the published port takes connections; dev.sh runs `up -d --wait db` before the migrations.
● **Guard:** A verify.sh step checks, as text, that the health check asks over TCP and that dev.sh waits for it before migrating; it failed on 5 broken variants and, after gate rounds, on the security reviewer's bypasses.
● **Lesson:** Health checks used for readiness must test the same path the client will use (TCP on the published port), or they pass during a database's first-start phase.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "Without it, '--wait' returned as soon as the container started; on a fresh volume nothing listens on TCP until the image has initialised the database" Also: scripts/verify.sh.

### CQ-317 Run the container smoke test against the platform's database major version

● **Rule:** none · **Raised by:** app owner · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised and fixed)
● **Applies to:** any app tested against a managed database add-on
● **Symptom:** The App Store's upload page lists the POSTGRESQL add-on as PostgreSQL 16, while the smoke rung ran 15.19; the smoke also waited on the Unix socket, which ended inside the image's first-start server.
● **Root cause:** The test database was chosen before the platform's version was known.
● **Fix:** 3a48c8f: the smoke runs PostgreSQL 16.15 pinned by digest, refuses another image, waits over TCP and logs the server version it tested. The local database stays on 15.19, since a volume made by 15 will not start under 16; the add-on's minor version stays TBC, re-verify.
● **Guard:** The verify.sh 'Database images' step checks both images are pinned by digest and runs the smoke's refusal of another image.
● **Lesson:** Pin integration-test dependencies to the platform's versions by digest, and log the version actually tested.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "At the requester's request, 3a48c8f moves the container smoke rung to PostgreSQL 16.15, pinned by digest, because the App Store's upload page lists the POSTGRESQL add-on as PostgreSQL 16" Also: commit messages (git log).

### CQ-318 Smoke-test checks must fail closed, and a refusal path must be executed, not grepped

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer (minors, rounds 2 and 3 on the PostgreSQL 16 change) · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.3 (raised and fixed; one case deferred)
● **Applies to:** shell-based smoke and verification scripts
● **Symptom:** The smoke logged a blank server version and carried on. The loop's check of the smoke's image-pin refusal did not run it at first (inference from e13a3d3 making it run 'for real'), then ran it only on an image with no digest, so a refusal widened to any digest would pass.
● **Root cause:** An unchecked command substitution, and a refusal path that no test ever ran.
● **Fix:** e13a3d3 stops the smoke on an unreadable or empty version and has the loop run the smoke's refusal with a stand-in docker; e0156ce runs it on a wrong digest too, points DOCKER_HOST at a socket that does not exist and matches the whole wait line. Deferred: on a noexec TMPDIR a refusal rewritten to print and carry on would pass the step, though Docker is never reached.
● **Guard:** The verify.sh 'Database images' step, which fails on each of 9 mutants at its own check.
● **Lesson:** Treat an empty or unreadable value in a test rung as a failure, and prove a refusal by running it against a stand-in with both a missing and a wrong input.
● **Evidence:** commit messages (git log): "● The smoke reads the server version into a variable and stops if the" Also: docs/AUDIT-LOG.md, V0.3 row.

### CQ-319 Unfixable High CVEs in the base image's OS packages: accept with evidence, rebuild when fixes ship

● **Rule:** none · **Raised by:** deploy-gate (Trivy); App Store Container Scan · **Severity:** minor · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.7 (raised by the deploy-gate; the platform's Container Scan passed), V0.10 (same 44 found); base digests unchanged through V0.13, which later gates did not rescan
● **Applies to:** any container on a Debian or other distribution base image
● **Symptom:** The deploy-gate's Trivy scan of the V0.7 image found 0 Critical and 44 High, all in Debian 13.7 base packages with no fix (36 in the util-linux family, then ncurses, systemd, acl and perl-base; none in apt or dpkg), before the platform's policy on unfixable Highs was known. The platform's Container Scan then passed V0.7 with the base image's 44 unfixable High findings; V0.10's deploy-gate found the same 44.
● **Root cause:** The python:3.12-slim (Debian trixie) base ships OS packages with High CVEs that have no released fix.
● **Fix:** No code change; accepted while no fix exists. The prep stage upgrades OS packages at build. The deploy-gate advised rebuilding when Debian ships fixes, and purging the util-linux family or moving to a distroless base if the scan ever stops on them.
● **Guard:** Each deploy-gate that scans checks for 0 Critical; the platform's Container Scan is binding and passed V0.7 to V0.11 with the same base digests.
● **Lesson:** Scan the image locally before the first upload and ask the platform how it treats unfixable findings; keep a rebuild-when-fixed note and a fallback plan (purge or distroless) ready.
● **Evidence:** gate report: Deploy-gate on V0.7: "Container-scan risk | 44 unfixable High in the Debian base. The platform's scan stage has never been reached, and its policy on unfixable Highs is unknown." Also: gate report: Deploy-gate re-run on V0.7; docs/AUDIT-LOG.md, V0.8 row.

### CQ-320 OS package manager left in a non-root runtime image: accepted deviation with a trip-wire

● **Rule:** none · **Raised by:** deploy-gate (each release from V0.7); position recorded at the V0.1 scaffold · **Severity:** minor · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.1 (accepted in SECURITY.md), V0.7 to V0.13 (raised by each release's deploy-gate)
● **Applies to:** any hardened container built from a distribution base image
● **Symptom:** Each release's deploy-gate from V0.7 to V0.13 found apt, apt-get and dpkg in the runtime image, against the deploy contract's line that the image ships no package manager. pip is removed; Trivy found no High or Critical in apt or dpkg.
● **Root cause:** The base image keeps its OS package manager and the prep stage removes pip but not apt or dpkg; the platform's reference recipe keeps them too.
● **Fix:** None. Accepted in SECURITY.md since the scaffold (c0a25dc): they need root and the image runs as uid 10001. The platform's Container Scan passed V0.7 to V0.11 with them in the image (V0.12's other stages TBC, re-verify; V0.13's outcome not recorded in the sources); the V0.12 gate suggested removing them in the prep stage at a convenient release.
● **Guard:** SECURITY.md trip-wire: remove them if the image policy scan flags them; each deploy-gate re-checks and lists it as an accepted deviation.
● **Lesson:** When a platform contract forbids a package manager but its own base keeps one, either purge it in the build or record the deviation once, with a reason and a trip-wire, so each release gate checks the same position rather than re-arguing it.
● **Evidence:** gate report: Deploy gate V0.13 (fast): "'/usr/bin/apt', '/usr/bin/apt-get' and '/usr/bin/dpkg' are still in the image" Also: SECURITY.md; gate report: Deploy-gate on V0.7; gate report: Deploy gate V0.12; scripts/upload-baseline.txt.

### CQ-321 Confirm what the platform's generated test jobs run and how its quality gate reads each coverage report

● **Rule:** none · **Raised by:** engineering-reviewer (minor, V0.5 round 1); V0.5 round 2 open items (gate not named); deploy-gate (minor, V0.7) · **Severity:** minor · **Status:** open · **Certainty:** fact
● **Releases:** V0.5 (raised), V0.7 (raised again), open at V0.13
● **Applies to:** any app on a platform whose pipeline is generated and hidden
● **Symptom:** Only the node job's `npm ci` is confirmed by a job log; the simulation's later node commands follow the platform's node template. V0.5's engineering gate found the node job's later commands stated as fact, and V0.5's round 2 open items add that comments in vite.config.ts, verify.sh and package-appstore.sh still said the node job runs the tests and that Code Quality reads coverage/lcov.info. How Code Quality combines coverage.xml with coverage/lcov.info under node-react is also unconfirmed.
● **Root cause:** The platform's generated pipeline is not visible from the repository; only failed jobs' logs revealed commands.
● **Fix:** Partial. The changelog says the later commands follow the platform's node template until confirmed, CLAUDE.md's adoption note marks both questions TBC, re-verify, and each coverage report is held to 80% on its own meanwhile. The three code comments still state the node job's test run and the gate's reading of coverage/lcov.info as fact at HEAD (f8a00bd).
● **Guard:** scripts/simulate-pipeline.sh runs both jobs before every upload; check-lcov.sh checks the lcov paths.
● **Lesson:** Mark platform behaviour you have not seen in a log as unconfirmed everywhere it is stated, code comments included, satisfy every plausible reading meanwhile (here, each report at the floor on its own), and ask the platform team rather than infer.
● **Evidence:** CHANGELOG.md: "The node job's commands after 'npm ci' follow the platform's node template until they are confirmed." Also: gate report: Deploy-gate on V0.7; docs/AUDIT-LOG.md, V0.5 row; commit messages (git log); frontend/vite.config.ts@f8a00bd.

### CQ-322 SonarQube scope keys left from a scaffold template no longer describe the analysed code

● **Rule:** none · **Raised by:** SonarQube sweep (V0.13 find agents) · **Severity:** unrecorded · **Status:** open · **Certainty:** mixed
● **Releases:** V0.13 (raised by the SonarQube sweep), open
● **Applies to:** any project with a sonar-project.properties or similar analyser scope file
● **Symptom:** sonar-project.properties sets sonar.sources=src and sonar.tests=tests, Python paths that would exclude frontend/ entirely, and declares only the Python coverage report (sonar.python.coverage.reportPaths=coverage.xml). Yet V0.12's platform report named frontend files, so the platform evidently analyses the upload archive and does not scope by these keys.
● **Root cause:** The file came from the Python scaffold template and was last changed at c0a25dc, before the dashboard was fused in at V0.2; the platform's real analysis surface is the uploaded archive.
● **Fix:** None recorded. The sweep treated the archive as the analysed surface.
● **Guard:** None recorded.
● **Lesson:** Re-check analysis configuration after every structural change to the repository, and verify against a real platform report which keys the platform actually honours.
● **Evidence:** gate report: find:security-and-config: "sonar.sources: it is 'src', which would exclude frontend/ entirely. But V0.12's report named frontend files, so the platform does not scope by it (fact)." Also: sonar-project.properties@f8a00bd.

### CQ-323 Record the scan's start conditions you have not seen, and handle each only when a scan log shows it

● **Rule:** none · **Raised by:** deploy-gate (minor, V0.8) · **Severity:** minor · **Status:** deferred · **Certainty:** fact
● **Releases:** V0.8 (raised; deferred)
● **Applies to:** apps with a scan-only degraded start mode
● **Symptom:** How the DAST scan supplies its database is TBC, re-verify. Three conditions would still fail Holly's scan start: a partial POSTGRES_* set is refused, a database unreachable for about 60 seconds stops the start, and a read-only root with no writable /tmp fails. The scan command as documented uses none of them.
● **Root cause:** The platform documents the scan only through its job log, which mentions an empty scan database without saying how the container reaches it.
● **Fix:** Deferred: handle each case under the flag if a scan log shows one. V0.8 to V0.11's DAST stages passed.
● **Guard:** Smoke rung step 3d covers the documented command (flag only, and flag with a database).
● **Lesson:** Test the scan's documented start exactly and keep a written list of undocumented variants, rather than widening the relaxed start speculatively.
● **Evidence:** gate report: Deploy-gate on V0.8: "How the scan supplies its database is 'TBC, re-verify'. A partial 'POSTGRES_*' set is refused, a database unreachable for about 60 s stops the start, and a read-only root with no writable '/tmp' ..."

### CQ-324 A single-page app fallback that answers 200 for every path can read as a DAST finding

● **Rule:** none · **Raised by:** deploy-gate (minor, V0.8) · **Severity:** minor · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.8 (raised by the deploy-gate; DAST then passed)
● **Applies to:** server-hosted single-page apps scanned by DAST
● **Symptom:** Unknown paths with an HTML Accept header return 200 with index.html (src/app/factory.py `_mount_dashboard`), which may trip a ZAP-style cloud-metadata High; a false High would block release.
● **Root cause:** The dashboard's client-side routing needs a catch-all fallback, which answers 200 for paths a scanner probes.
● **Fix:** No change: the gate advised uploading and reading the DAST report, and limiting the fallback to the dashboard's own routes if it fired. V0.8's upload passed all 11 stages, DAST included.
● **Guard:** The platform's DAST stage on each upload.
● **Lesson:** Know how your catch-all route answers scanner probes; be ready to scope it to real client routes or refuse paths with file extensions and metadata prefixes if a scan flags it.
● **Evidence:** gate report: Deploy-gate on V0.8: "Unknown paths with an HTML 'Accept' header return 200 'index.html', which may trip a ZAP-style cloud-metadata High." Also: docs/AUDIT-LOG.md, V0.8 row; scripts/upload-baseline.txt.

### CQ-325 Record the residual limits of git-based packaging checks, each with a trip-wire

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer · **Severity:** minor · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.3 (accepted), V0.4 (restated)
● **Applies to:** any repository-hosted release gate
● **Symptom:** Accepted at V0.3: `git log -G` runs without `-m` (a version change carried by a skipped merge is still refused by the content diff); a local filter's or textconv's command runs after the packaging tools were compared; the upstream comparison reads the commit-graph file, so a forged graph in .git/ hides the lag, which needs write access to .git/.
● **Root cause:** Git runs local programs and reads local caches during packaging, and some of them cannot be switched off without losing the comparison.
● **Fix:** Stated in SECURITY.md ('The review record proves the record, not the review') with trip-wires; V0.4 states the filter limit plainly.
● **Guard:** SECURITY.md rows for the review record and the upload baseline.
● **Lesson:** Where a release check cannot close a route, write down what it cannot see and who could exploit it, with a trip-wire for when that changes.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "Both accepted the reasoning for leaving 'git log -G' without '-m': the content diff refuses any version change a skipped merge carries"

### CQ-326 CI actions pinned by tag rather than commit SHA

● **Rule:** none · **Raised by:** review gates on the scaffold (inference: security-reviewer; b56e04c closes both gates' minors) · **Severity:** minor · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.1 (accepted)
● **Applies to:** GitHub Actions workflows
● **Symptom:** The CI workflow references actions by tag (for example actions/checkout@v4).
● **Root cause:** Tags are mutable; accepted because the workflow holds a read-only token and no secrets and never deploys.
● **Fix:** Accepted in SECURITY.md; b56e04c asks for SHA pins to be confirmed against release pages when adopted.
● **Guard:** SECURITY.md trip-wire: pin full commit SHAs, each confirmed against the action's release page, before the workflow gains any secret or write permission.
● **Lesson:** Tag pins are tolerable only for a workflow with no secrets and no write access; record the condition that forces SHA pinning.
● **Evidence:** SECURITY.md: "Pin full commit SHAs, each confirmed against the action's GitHub release page, before the workflow gains any secret or any write permission." Also: .github/workflows/verify.yml@f8a00bd.

### CQ-327 An upload secret scan also covers shipped tests, so fixtures must avoid credential-shaped names

● **Rule:** none · **Raised by:** pipeline simulation (upload content net) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised and fixed)
● **Applies to:** any upload that carries its tests and is secret-scanned
● **Symptom:** Round 2's first V0.6 pipeline simulation was refused by the content net (the secret-scan hook's rules applied to every text file in the upload) because a new test named a field `token`.
● **Root cause:** The tests ship in the upload, and the content scan matches credential-shaped names in any shipped text.
● **Fix:** The test field was renamed to `auth`; the simulation on the tree after round 3's fixes scanned 242 text files clean.
● **Guard:** scripts/check-package.sh content net, run by simulate-pipeline.sh and the packager before every upload.
● **Lesson:** When tests ship inside the artefact, write fixtures that the secret scanner reads as clean, and run the scan in the local rehearsal so a false positive costs a rename, not an upload.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "round 2's first try had been refused by the content net for a new test naming a field 'token'" Also: session summaries.

### CQ-328 A lockfile drift check that compares with the git index needs relocked files staged first

● **Rule:** none · **Raised by:** verification loop · **Severity:** verification-loop stop · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.3 (loop stop, recorded in the audit row); twice more during the V0.6 to V0.10 work (session summaries; the exact releases are not recorded)
● **Applies to:** any loop that checks `npm ci` or similar leaves the lockfile untouched
● **Symptom:** The loop's dashboard step runs `npm ci` and then checks the lockfile is unchanged against git's index; after a version bump or relock left unstaged (once after a `git reset` emptied the index), the loop stopped there.
● **Root cause:** The check compares the working tree with the index by design, so a legitimate relock reads as drift until it is staged.
● **Fix:** The relocked or restamped lockfiles were staged with `git add` and the loop re-run; the cause is noted in the session summaries.
● **Guard:** scripts/verify.sh lockfile check after `npm ci`.
● **Lesson:** A drift check against the index catches an install that rewrites the lockfile, but the workflow must stage intended lockfile changes before running it.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "A first run, with the change not yet staged, stopped at the check that 'npm ci' leaves the lockfile as the index holds it, since the index still held 0.2.0." Also: session summaries.

### CQ-329 Upload nets should refuse package-manager configuration files that change how the platform installs

● **Rule:** none · **Raised by:** review gates, V0.5 (open item below the blocking bar; which gate is not recorded) · **Severity:** minor · **Status:** open · **Certainty:** mixed
● **Releases:** V0.5 (raised below the blocking bar), open at V0.13 (inference)
● **Applies to:** any upload installed by a platform's package manager
● **Symptom:** V0.5's record commit lists among open items that no upload net refuses a frontend/npm-shrinkwrap.json or frontend/.npmrc, either of which could change what the platform's node job installs. No later record closes it, and a search of the repository at HEAD (f8a00bd) finds neither name.
● **Root cause:** The name net was built around secrets, caches and archives, not files that steer the package manager.
● **Fix:** None recorded.
● **Guard:** None recorded.
● **Lesson:** Treat package-manager configuration (registry, shrinkwrap, install-script settings) in the upload as a supply-chain input and refuse or pin it explicitly.
● **Evidence:** commit messages (git log): "refuses a frontend/npm-shrinkwrap.json or frontend/.npmrc."

### CQ-330 A type-aware lint rule must be scoped to the files its TypeScript project covers

● **Rule:** `none (lint guard for SonarQube S6557)` · **Raised by:** engineering-reviewer (minor, V0.13 round 1) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.13 (raised and fixed)
● **Applies to:** TypeScript projects using ESLint flat config with typed rules
● **Symptom:** 559a9d0 enabled the type-aware prefer-string-starts-ends-with (the guard for S6557) for every .ts and .tsx file, but projectService was set only for src/**, so linting vite.config.ts or running `eslint .` would throw. It was latent because `npm run lint` is `eslint src`; the config's header comment also did not mention the new rules.
● **Root cause:** The rule was added to the general block while the parser setting it needs was scoped to a narrower block.
● **Fix:** 6085a53 moved the rule into the src/** block next to projectService, with a comment saying why, and the header now mentions the SonarQube rules. Security round 2 ran `npx eslint .` with exit 0.
● **Guard:** The scoped block in frontend/eslint.config.js; no dedicated check recorded.
● **Lesson:** Put type-aware lint rules in the same configuration block as the parser options that give them type information, and run the linter over the whole tree once to prove it.
● **Evidence:** gate report: Engineering gate V0.13 (fast): "the type-aware 'prefer-string-starts-ends-with' applies to '**/*.{ts,tsx}', but 'projectService' is only set for 'src/**'. Linting 'vite.config.ts' or running 'eslint .' would throw." Also: frontend/eslint.config.js; gate report: Security gate V0.13 round 2.

### CQ-331 A local lint guard that approximates a SonarQube rule covers only part of it

● **Rule:** `typescript:S7723` · **Raised by:** engineering-reviewer (minor, V0.13 round 2) · **Severity:** minor · **Status:** deferred · **Certainty:** fact
● **Releases:** V0.13 (raised; deferred to the next release)
● **Applies to:** projects mirroring SonarQube rules in ESLint
● **Symptom:** The no-restricted-syntax selector added for S7723 catches a missing `new` on its listed constructors only, not `Object()` without arguments, `Float16Array()`, or `new` on String, Number, Boolean, Symbol or BigInt, which the rule SonarJS decorates also reports.
● **Root cause:** A hand-written selector approximates the analyser's rule instead of running the rule itself.
● **Fix:** Deferred to the next release; none of these patterns is in the code.
● **Guard:** None recorded.
● **Lesson:** Where possible run the same rule the platform's analyser uses (here unicorn new-for-builtins) rather than a hand-written approximation, and test the guard against the rule's full set of examples.
● **Evidence:** gate report: Engineering gate V0.13 round 2: "The S7723 guard covers only the call side of its list. It misses 'Object()' with no arguments, 'Float16Array()', and the other half of S7723, 'new String/Number/Boolean/Symbol/BigInt'." Also: docs/AUDIT-LOG.md, V0.13 row.

### CQ-332 A server default that writes under the home directory fails in a non-root image that has no home

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer, both FAIL on 9616c41 (which gate named this item is not recorded) · **Severity:** not recorded (c0a25dc addressed every MAJOR and the minor findings in scope) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (raised at the first gate round on 9616c41, fixed in c0a25dc)
● **Applies to:** any non-root container; Python and gunicorn
● **Symptom:** Holly's scaffold image, whose non-root user has no home directory, logged a false Errno 13 boot error from gunicorn: gunicorn 25.1 and later open an admin control socket under $HOME by default (Holly locks gunicorn 26.2.0). Files: Dockerfile, src/app/gunicorn_conf.py.
● **Root cause:** A server feature that is on by default assumed a writable home directory, which the hardened image deliberately lacks, and the scaffold's shell-form CMD started gunicorn with no configuration module that could turn it off.
● **Fix:** c0a25dc starts gunicorn in exec form with src/app/gunicorn_conf.py, which sets control_socket_disable = True with a comment giving the reason.
● **Guard:** none specific; the container smoke rung added in c0a25dc boots the built image (inference that it would show the error again)
● **Lesson:** When an image runs as a non-root user without a home directory, audit the server's defaults for anything that writes under $HOME (control sockets, caches, history files) and turn off what the app does not need in a committed configuration file, with the reason beside it.
● **Evidence:** commit messages (git log): "and disables gunicorn's control socket. That removes the false Errno 13" Also: docs/AUDIT-LOG.md, V0.1 row; src/app/gunicorn_conf.py at f8a00bd.

### CQ-333 A floating build-frontend directive is an unpinned input in an otherwise pinned image build

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer, both FAIL on 9616c41 (inference: removed in the commit fixing their findings; which gate named it is not recorded) · **Severity:** not recorded · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (in the scaffold at 9616c41, removed in the gate-fix commit c0a25dc)
● **Applies to:** any Docker or BuildKit image build
● **Symptom:** The scaffold Dockerfile, copied from the template, opened with `# syntax=docker/dockerfile:1` while its base images were pinned by digest, so each build could pull a different BuildKit frontend image. File: Dockerfile.
● **Root cause:** The template's syntax directive named a moving tag, an unpinned supply-chain input that nothing in the build needed.
● **Fix:** c0a25dc removes the directive; the Dockerfile header records why there is none.
● **Guard:** none recorded beyond the header comment
● **Lesson:** Pin or remove every image a build pulls, a Dockerfile syntax directive's frontend included; a digest-pinned base does not make the build reproducible while another input floats.
● **Evidence:** Dockerfile at 9616c41: "# syntax=docker/dockerfile:1" Also: commit messages (git log); Dockerfile at f8a00bd.

### CQ-334 Record why a container image ships without a HEALTHCHECK instruction

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer, both FAIL on 9616c41 (inference: recorded in the commit fixing their findings; which gate named it is not recorded) · **Severity:** not recorded · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.1 (recorded in the gate-fix commit c0a25dc); unchanged at V0.13
● **Applies to:** container images deployed to Kubernetes-based platforms
● **Symptom:** Holly's image has no HEALTHCHECK instruction, an omission Dockerfile linters and reviewers commonly flag; the scaffold's gate round led to the omission being recorded rather than an instruction added. File: Dockerfile.
● **Root cause:** The platform runs the container on Kubernetes, which ignores Docker's HEALTHCHECK and probes the app's health paths itself, so the instruction would change nothing at runtime.
● **Fix:** c0a25dc records the omission and its reason in the Dockerfile header.
● **Guard:** none in the repository; the platform's Dockerfile Lint stage passed V0.7's upload with the omission in place
● **Lesson:** When a linter-favoured instruction does nothing on the target orchestrator, leave it out deliberately and write the reason beside the build file, so the next reviewer or analyser finding meets a recorded decision rather than a gap.
● **Evidence:** commit messages (git log): "directive is gone; the HEALTHCHECK omission is recorded." Also: Dockerfile at f8a00bd; docs/AUDIT-LOG.md, V0.8 row.

### CQ-335 A deliberately fail-open patch step must announce when it was skipped

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer on 9616c41 (which gate named it is not recorded); deploy-gate at V0.7 and V0.9 for the cache visibility · **Severity:** not recorded · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.1 (fixed in c0a25dc); V0.7 and V0.9 (deploy gates could not tell from a cached build whether it ran)
● **Applies to:** Debian-based container builds; any CI step allowed to fail
● **Symptom:** Holly's image patches OS packages fail-open by design so an offline runner can still build, but a failed package-index fetch passed as '0 upgraded', hiding a skipped patch. Later deploy gates found the step served from the build cache, so its log could not show whether it ran. File: Dockerfile.
● **Root cause:** apt-get update's default exit status let a failed index fetch through, so the tolerated branch hid a skipped patch; layer caching replays no output on later builds.
● **Fix:** c0a25dc runs `apt-get update --error-on=any` in its own RUN and echoes `WARNING: OS package upgrade skipped` on any failure, so a skip is visible and cannot swallow a mandatory step. This is the one tolerated step, unlike the read-only hardening checks that fail the build.
● **Guard:** none in the loop; deploy gates rescan with Trivy where available and otherwise rely on the platform's Container Scan
● **Lesson:** If a build step may fail, make it fail loudly: force the tool to report every error, print a warning on the tolerated path and keep it in its own step so it cannot mask a mandatory one; a cached layer replays no log, so rebuild without the cache when you need to know it ran.
● **Evidence:** commit messages (git log): "an unquoted PORT. apt-get update uses --error-on=any so a skipped patch" Also: Dockerfile at f8a00bd; gate report: Deploy-gate on V0.7; gate report: Deploy-gate on Holly V0.9.

### CQ-336 Local check scripts must clean up their scratch state on every exit, interrupt included

● **Rule:** none · **Raised by:** engineering-reviewer and security-reviewer, both PASS on c0a25dc with minor items that b56e04c closes (which gate named this item is not recorded) · **Severity:** minor (inference: among the minor items b56e04c closes) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (raised on c0a25dc, fixed in b56e04c)
● **Applies to:** POSIX shell scripts (sh, dash); any local verification script
● **Symptom:** Holly's pipeline simulation and container smoke rung did not exit cleanly on Ctrl-C, and the smoke rung kept its build context, so interrupted runs left scratch clones and contexts behind. Files: scripts/simulate-pipeline.sh, scripts/smoke-container.sh.
● **Root cause:** Both rungs had only an EXIT trap, and dash runs an EXIT trap on a normal exit or a set -e failure but not on a signal; the smoke rung also kept its context by default.
● **Fix:** b56e04c traps INT and TERM to exit 130 and 143, so the EXIT trap removes the scratch directories; the simulation keeps them only with KEEP_SIM=1 (from c0a25dc) and the smoke rung only with KEEP_SMOKE=1.
● **Guard:** none recorded
● **Lesson:** In POSIX sh, pair an EXIT clean-up trap with INT and TERM traps that call exit, and make keeping scratch state an explicit opt-in, so an interrupted check leaves nothing behind.
● **Evidence:** commit messages (git log): "Both gates passed c0a25dc and left minor items; this commit closes them." Also: scripts/smoke-container.sh at f8a00bd.

### CQ-337 Writing a release artefact through a private temporary file changes its permissions

● **Rule:** none · **Raised by:** not recorded (fixed in the commit answering the security gate's FAIL on 85962f4) · **Severity:** not recorded · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (introduced by 85962f4, fixed in 774173a, pinned in 28de168)
● **Applies to:** any build or packaging script using mktemp or a write-then-rename pattern
● **Symptom:** After packaging moved to writing Holly's upload zip under a temporary name and moving it into dist/ only when every net passed (85962f4), the zip lost its ordinary readable mode; 774173a made it 0644 again. File: scripts/package-appstore.sh.
● **Root cause:** mktemp creates its file readable by the owner only, and moving the file into place keeps that mode.
● **Fix:** scripts/package-appstore.sh runs chmod 644 on the temporary zip before moving it into place (774173a).
● **Guard:** scripts/test-package-nets.sh checks the real package from HEAD at mode 0644 (from 28de168), and a rehearsal zip too
● **Lesson:** When an artefact is written to a temporary file and renamed into place, set its final permissions explicitly before the rename and pin them in a test, because secure temporary files are created owner-only.
● **Evidence:** commit messages (git log): "package-appstore.sh builds under a temporary name and moves the zip to" Also: scripts/package-appstore.sh at f8a00bd; scripts/test-package-nets.sh at f8a00bd.

### CQ-338 Keep tests and files the runtime never needs out of the container build context

● **Rule:** none · **Raised by:** V0.1: engineering-reviewer and security-reviewer on 9616c41 (which gate not recorded); V0.5: security-reviewer · **Severity:** V0.1 not recorded; V0.5 nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.1 (the scaffold's COPY . /app, narrowed to src/ in c0a25dc); V0.5 (the dashboard's tests in the build context, raised in gate round 1 on 9602d0d, fixed in 6f12b3a)
● **Applies to:** any Docker image build
● **Symptom:** The scaffold's prep stage ran `COPY . /app`, relying on .dockerignore alone; at V0.5 the allowlist .dockerignore re-admitted the whole frontend/ subtree for the dashboard build, so the dashboard's newly added tests entered the image's build context. Files: Dockerfile, .dockerignore.
● **Root cause:** A broad COPY and a whole-subtree re-admission in an allowlist ignore file took files in by default, and adding a test suite did not prompt a change to the exclusions.
● **Fix:** c0a25dc copies only src/; 6f12b3a excludes the dashboard's *.test.ts, *.test.tsx and test helpers from the build context, with a comment that the image builds the dashboard and never tests it.
● **Guard:** deploy gates inspect the built image for .env, tests and .git; no loop check recorded
● **Lesson:** Copy named paths into an image rather than the whole context, and when an allowlist ignore file re-admits a whole directory, exclude tests, fixtures and local outputs inside it again; revisit the ignore file whenever a new kind of file joins a re-admitted tree.
● **Evidence:** Dockerfile at 9616c41: "COPY . /app" Also: commit messages (git log); docs/AUDIT-LOG.md, V0.5 row; .dockerignore at f8a00bd; gate report: Deploy-gate on V0.7.

### CQ-339 A required first-run step must not depend on a container shell the platform may not offer

● **Rule:** none · **Raised by:** review gates at V0.2 (a deferred finding); deploy-gate at V0.5 · **Severity:** MAJOR (V0.5 deploy-gate) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (account creation deferred to SECURITY.md), V0.5 (deploy-gate MAJOR), V0.7 (first admin from App Store variables; deploy gate PASS on re-run), V0.10 (admin Users page)
● **Applies to:** any app deployed to a managed container platform
● **Symptom:** Holly's accounts could be created only with `python -m app.cli.create_admin`, which needs a shell in the container, unconfirmed on the App Store. The V0.5 deploy gate raised that there was no confirmed way to create the first admin; at V0.10 the owner asked how to add users and Holly had no route or page for it.
● **Root cause:** Account creation was left to a CLI inherited from the imported dashboard and recorded as deferred, while whether the platform offers a container shell stayed TBC, re-verify.
● **Fix:** V0.7: src/app/admin_bootstrap.py, run by the gunicorn master after the migrations, creates one admin from ADMIN_USERNAME, ADMIN_PASSWORD and ADMIN_EMAIL only while app_user is empty (the owner's choice of three designs). V0.10: an admin Users page and a password change for every user, at the owner's request. The CLI remains for where a shell exists.
● **Guard:** the container smoke rung creates the admin on PostgreSQL (V0.7) and runs the Users flow (V0.10)
● **Lesson:** List every operator step a first deploy needs and check each against what the platform actually offers; a step that needs a shell, console or manual job the platform has not confirmed needs a path through configuration or the app itself before the first upload.
● **Evidence:** commit messages (git log): "audit chain's missing anchor, account creation, unaudited reads, event" Also: the app owner's message; docs/AUDIT-LOG.md, V0.7 row; docs/AUDIT-LOG.md, V0.10 row; SECURITY.md.

### CQ-340 Treat a search tool's error exit as a failure, never as no match

● **Rule:** none · **Raised by:** security-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised on 092cf83..0c67540, fixed in 96136cf)
● **Applies to:** POSIX shell; grep and similar tools in any security or packaging check
● **Symptom:** In Holly's upload member-name checks, an `if ... | grep -q` test read grep's error status as no match, so a name net that could not search passed the package. File: scripts/check-package.sh.
● **Root cause:** grep exits 1 for no match and 2 or more for an error, and an if-test takes any non-zero status as false.
● **Fix:** 96136cf routes the name checks through a helper that refuses with 'could not check the member names (grep exited N)' on any status above 1, as the project's rule on unverifiable controls asks.
● **Guard:** scripts/test-package-nets.sh runs check-package.sh with a stand-in grep that fails and expects a refusal (96136cf)
● **Lesson:** In shell checks, tell 'no match' from 'could not run': capture the exit status and fail closed on anything other than the tool's documented no-match code.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "nits: a 'grep' error read as no match, '.mcp.json')" Also: commit messages (git log); scripts/check-package.sh at f8a00bd.

### CQ-341 Refuse archive members that are not regular files before hashing or reading them

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised in round 2 on 4827acb..e40e12b, fixed in 153c91e)
● **Applies to:** any packaging or upload scanner
● **Symptom:** Holly's upload nets hashed a symlink member through its target, so the check judged the file the link pointed at rather than the member itself. File: scripts/check-package.sh.
● **Root cause:** The nets read extracted members by path, which follows links, and never checked a member's type.
● **Fix:** 153c91e refuses any member that is not a regular file before hashing it.
● **Guard:** scripts/test-package-nets.sh cases 'a symlink member' and 'a committed symlink'; under mutation, removing the guard turned the case red only through another refusal, the zip's byte-for-byte comparison, as the V0.3 row records
● **Lesson:** In any check over an archive or directory, refuse links, devices and other non-regular entries explicitly before reading, so the check never follows a link to content outside what it was asked to judge.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "nits: symlink members hashed through their targets, rehearsal path edge cases" Also: commit messages (git log); scripts/test-package-nets.sh at f8a00bd.

### CQ-342 List the files to check with the same pathspec and quoting rules as the tool that packages them

● **Rule:** none · **Raised by:** engineering-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised in round 2 on 4827acb..e40e12b, fixed in 153c91e)
● **Applies to:** git-based packaging; any check that compares an artefact with its source tree
● **Symptom:** Holly's nets listed a commit's files with git ls-tree, which refused an exclude pathspec and quoted unusual names, so the list compared with the zip could differ from what git archive packages. File: scripts/check-package.sh.
● **Root cause:** Two git commands with different pathspec handling and name quoting were used for the same set of files.
● **Fix:** 153c91e lists the commit's files with git diff-tree -r -z from the empty tree, which reads pathspecs as git archive does and leaves names unquoted.
● **Guard:** none specific recorded; the byte-for-byte comparison of the zip with the commit's files runs on every package
● **Lesson:** When a check re-derives an artefact's contents, use a listing that interprets paths exactly as the packaging command does, with NUL-separated output, or the check and the artefact can disagree on unusual names.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "minors: ls-tree refused an exclude pathspec and quoted names, a NUL passed the record check" Also: commit messages (git log); scripts/check-package.sh at f8a00bd.

### CQ-343 Shell path handling must keep trailing newlines and ignore CDPATH

● **Rule:** none · **Raised by:** security-reviewer (the trailing newline; the CDPATH half is fixed in the same commit, its raiser not recorded) · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.3 (raised in round 3 on 4827acb..153c91e, fixed in 8c70dbd)
● **Applies to:** POSIX shell scripts
● **Symptom:** In Holly's packaging scripts, command substitution dropped a trailing newline from a directory's name and an exported CDPATH sent a relative cd elsewhere, so a rehearsal could reach dist/ and the review check and the nets could read a sibling clone. Files: scripts/package-appstore.sh, scripts/check-reviews.sh, scripts/check-package.sh, scripts/check-baseline.sh.
● **Root cause:** $(...) strips trailing newlines from its output, and cd consults CDPATH for a relative path.
● **Fix:** 8c70dbd splits and resolves paths without losing a final newline and unsets CDPATH in each script.
● **Guard:** scripts/test-package-nets.sh twin clones, one named with a final newline, pin each script's root, with a case that runs packaging with CDPATH naming the twin
● **Lesson:** In shell scripts that compute paths, never let command substitution silently trim a path, and unset CDPATH before any relative cd; test with a directory whose name ends in a newline.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "command substitution dropped a trailing newline from a path, so a rehearsal reached dist/ and the checks read a sibling clone" Also: commit messages (git log); scripts/check-package.sh at f8a00bd.

## 2.7 Dependencies and supply chain


### CQ-344 A pipeline test job's lockfile must carry the test tools, and layered lockfiles must agree on version, marker and hashes

● **Rule:** `none (platform python test job: `pytest: not found`, exit 127; gate nit on the lock-comparison step)` · **Raised by:** platform (python test job on V0.4's upload); security-reviewer (nit, V0.5 round 1) · **Severity:** blocking (platform test stage failed); the version-only comparison was a nit · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.4 (upload failed the platform's test stage), V0.5 (fixed; the comparison tightened after a round 1 nit)
● **Applies to:** Python with uv or pip-tools hash-pinned lockfiles; any stack whose CI installs a different manifest from the image
● **Symptom:** V0.4's upload failed the App Store's python test job, which runs `pip install -r requirements.txt` then `pytest --cov --cov-report=xml:coverage.xml`: requirements.txt held only the runtime set, so pytest was not installed (exit 127). After the split into requirements-runtime.txt (the image), requirements.txt (the test job) and requirements-dev.txt (tooling), the new loop step that holds the locks together compared versions only.
● **Root cause:** One lockfile served two consumers with different needs (the image and the platform's test job). The first consistency check ignored environment markers and hashes; inference: two locks could then pin the same version and still install different artefacts.
● **Fix:** In 6f12b3a (V0.5): the runtime set moved to requirements-runtime.in and .txt, which the Dockerfile installs; requirements.txt holds it with pytest, pytest-cov and pytest-asyncio; requirements-dev.in builds on that; no pinned version moved. In round 2 the loop step was tightened to refuse a package one lock pins unless the lock that extends it pins it at the same version, under the same marker and with the same hashes; it refused 5 planted drifts and accepted 2 clean cases. pip-audit covers all three locks.
● **Guard:** scripts/verify.sh 'Locks' step; pip-audit --strict --require-hashes on all three locks; scripts/simulate-pipeline.sh runs the python job's own install and test commands on a fresh checkout.
● **Lesson:** Find out exactly which manifest each pipeline job installs and make sure it holds what that job runs. When one lockfile extends another, check every shared package matches on version, environment marker and hashes, not version alone.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "'requirements.txt' held only the runtime set, so pytest was not installed (exit 127)" Also: scripts/upload-baseline.txt; scripts/verify.sh@HEAD.

### CQ-345 New advisories against pinned packages appear between releases: audit every lock, tooling included, on every run

● **Rule:** `npm audit (every severity) and pip-audit --strict: GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw, GHSA-587h-7wmj-h5pm (vite); GHSA-q3jh-wrc6-jgq8, GHSA-8r9p-f939-6h3c (follow-redirects); PYSEC-2026-4320 (certifi)` · **Raised by:** verification loop · **Severity:** blocking for the verification loop (its audits fail on any advisory) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.12 (raised and fixed, 21 October 2026)
● **Applies to:** Any stack; shown with npm audit and pip-audit
● **Symptom:** On 21 October 2026, with no dependency change since V0.11 (git shows none between V0.11's upload commit 049e162 and 62ba4aa's parent), npm audit and pip-audit in scripts/verify.sh found advisories in vite 7.3.6 (its development server's launch-editor), follow-redirects 1.16.0 under axios, and certifi 2026.7.22 in the development lock only.
● **Root cause:** Advisories published after V0.11 against exactly pinned versions. Exact pins hold a version still, so a lock that was clean goes red with no code change.
● **Fix:** In 62ba4aa: vite pinned to 7.3.7, follow-redirects relocked to 1.16.1 and certifi to 2026.10.19. Each fixed version was past the 15-day cooldown except certifi, released 19 October 2026 and taken as the only fixed version. The loop then passed. Recorded as inference in the changelog: none reaches the running image.
● **Guard:** scripts/verify.sh: npm audit fails on any severity, info included, and fails closed when the advisory service returns no report; pip-audit --strict --require-hashes runs on the runtime, test-job and tooling locks.
● **Lesson:** Run the dependency audit on every loop run, not only when dependencies change, and include build and test tooling locks; fail closed when the audit cannot reach its advisory source. Record whether each advisory reaches the shipped artefact so its urgency is clear.
● **Evidence:** docs/AUDIT-LOG.md, V0.12 row: "npm audit and pip-audit found advisories published since V0.11 in vite 7.3.6, follow-redirects 1.16.0 and certifi 2026.7.22 (development lock only)" Also: CHANGELOG.md; commit messages (git log); scripts/verify.sh@HEAD.

### CQ-346 When an advisory's only fix is younger than the dependency cooldown, take it, record the waiver and review the relock entry by entry

● **Rule:** `npm audit: GHSA-qxg6-89mg-rqv8 and GHSA-xp26-3454-mjgp (@vitest/mocker); the project's 15-day cooldown` · **Raised by:** verification loop (during the V0.12 gates); checked by security-reviewer and engineering-reviewer in round 7 · **Severity:** blocking for the verification loop; test tooling only, never in the image · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.12 (raised during the gate rounds, fixed at d266102, confirmed in round 7)
● **Applies to:** Any stack with a dependency cooldown; shown with npm and Vitest
● **Symptom:** Mid-review on 21 October 2026, npm audit found two advisories in @vitest/mocker 4.1.11, a package of the dashboard's test runner. The only fixed 4.x release, 4.1.12, was published 15 October 2026, inside the 15-day cooldown; after it the registry held only 5.x.
● **Root cause:** Fresh advisories against pinned test tooling, where the cooldown and a clean audit could not both be met (inference). Engineering round 7 noted that CLAUDE.md's cooldown rule is worded for a new package, while this was a bump of an existing tooling package.
● **Fix:** d266102 pinned vitest and @vitest/coverage-v8 to 4.1.12 (chai 6.3.0 and tinyrainbow 3.2.0 moved with them), with the cooldown waiver and its reason (the only fixed version) in the commit message and the AUDIT-LOG row; the CHANGELOG's security entry records the bump. Security round 7 compared the locks as JSON: exactly 11 entries changed version, every resolved URL on registry.npmjs.org, each integrity matching `npm view`, no install scripts in the changed packages, and 0 vulnerabilities on the new lock.
● **Guard:** npm audit in scripts/verify.sh; the gates check publish dates, resolved URLs and integrities of every changed lock entry; any cooldown deviation is written into the release's audit row.
● **Lesson:** A cooldown is a default, not an absolute: when the only fixed version is younger than it, take that version, record the waiver and its reason, and review the relock entry by entry (registry, integrity, install scripts, what else moved).
● **Evidence:** docs/AUDIT-LOG.md, V0.12 row: "npm audit found GHSA-qxg6-89mg-rqv8 and GHSA-xp26-3454-mjgp in @vitest/mocker 4.1.11, the test runner's, never in the image" Also: gate report: Security gate V0.12 round 7; gate report: Engineering gate V0.12 round 7.

### CQ-347 A relock can crash in one package-manager version: relock with another and prove the lock installs unchanged under every version that consumes it

● **Rule:** `none (npm resolver error `Cannot read properties of null (reading 'edgesOut')`)` · **Raised by:** the relock itself under the local npm 10.9.4, recorded in the V0.12 audit row; verified by engineering-reviewer round 7 · **Severity:** blocking for the dependency fix until worked around · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.12 (raised and worked around at d266102); V0.4 (an earlier npm 10.9.4 relock churned the lock)
● **Applies to:** Node and npm lockfiles; any package manager whose version differs between machines
● **Symptom:** Relocking frontend/package-lock.json for the vitest 4.1.12 bump with the local npm 10.9.4 failed in the resolver on the optional peers of vite 8. The verification loop and the pipeline simulation install with that same local npm on node v22.22.0, which stands in for the platform's node:24-alpine job (that image ran npm 11.19.1 when checked in V0.5).
● **Root cause:** A resolver failure in npm 10.9.4 on optional peer dependencies (as recorded; the records show no further investigation). npm versions also write the lock differently: in V0.4 npm 10.9.4's relock dropped 15 `"peer": true` flags with no package change.
● **Fix:** Relocked with npm 11.20.0 through `npm install --package-lock-only`, as the project's rule requires, with the npm version and the crash message recorded in the AUDIT-LOG row. Engineering round 7 confirmed lockfileVersion stayed 3, `npm ci --prefix frontend --ignore-scripts` under npm 10.9.4 installed the new lock, and the loop's 'lockfile must not change' step passed. Inference: no V0.12 or V0.13 gate report records installing the new lock inside node:24-alpine itself, although the engineering report headed its local npm 10.9.4 check as the platform's npm.
● **Guard:** scripts/verify.sh runs `npm ci` then fails if frontend/package-lock.json changed; scripts/simulate-pipeline.sh runs the node job's `npm ci` on a fresh checkout, with this machine's node standing in for the job's image.
● **Lesson:** If one package-manager version cannot relock, relock with another that keeps the lockfile format, then prove a clean install that leaves the lock unchanged under every version that will consume it: local, CI and the platform image. Record the tool version used, since lock churn differs between versions.
● **Evidence:** docs/AUDIT-LOG.md, V0.12 row: "relocked with npm 11.20.0 because npm 10.9.4's resolver failed on the optional peers of vite 8 ('Cannot read properties of null (reading 'edgesOut')')" Also: gate report: Engineering gate V0.12 round 7; docs/AUDIT-LOG.md, V0.4 row; docs/AUDIT-LOG.md, V0.5 row; scripts/simulate-pipeline.sh@HEAD.

### CQ-348 Lock newly added packages behind a supply-chain cooldown

● **Rule:** `15-day dependency cooldown (CLAUDE.md: lock a new dashboard package with `--before`)` · **Raised by:** security-reviewer · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised round 1, fixed round 2)
● **Applies to:** npm (`--before`) and any package manager that can resolve as of a past date
● **Symptom:** Adding jsdom and Testing Library for the dashboard's coverage brought 48 packages into frontend/package-lock.json; seven of them had been published less than 15 days earlier.
● **Root cause:** `npm install` resolves the newest matching releases, so freshly published versions land in the lock by default (inference from the fix).
● **Fix:** Relocked with `npm install --before=2026-10-04T23:59:59Z`, so none of the 48 added packages was younger than 15 days; the relock moved exactly those seven to older releases and changed no V0.4 entry. The test packages are test-only and pinned exactly. The V0.5 commit (6f12b3a) also added the rule to CLAUDE.md.
● **Guard:** CLAUDE.md rule, checked by the security gate (it read publish dates with `npm view` in V0.12 round 7). Inference: the loop has no publish-date check, as none appears in scripts/verify.sh.
● **Lesson:** Resolve new dependencies against a registry view some days old (npm `--before` or your package manager's equivalent) so a freshly published malicious release cannot land in the lock, and confirm the cooldown relock moved only the intended packages.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "security-reviewer PASS with one minor (seven of the new test packages were younger than 15 days)" Also: CLAUDE.md@HEAD; 6f12b3a.

### CQ-349 Replace a dependency whose transitive advisory has no fixed release

● **Rule:** `dependency advisory with no fixed release (ecdsa, through python-jose)` · **Raised by:** not recorded (the V0.2 fusion work on the imported Daily Operations Dashboard; gate reports before V0.6 are not available) · **Severity:** not recorded · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (fixed when the imported dashboard was fused into Holly, commit 55ab9f1)
● **Applies to:** Python and FastAPI token sign-in; any stack
● **Symptom:** The imported Daily Operations Dashboard signed sign-in tokens with python-jose, whose ecdsa dependency carries an advisory with no fixed release, so no upgrade could clear it.
● **Root cause:** A JSON Web Token library pulling a transitive dependency with an unfixed advisory. Holly's tokens are HS256 (per the comment beside the pin); inference: it needed none of the ECDSA code.
● **Fix:** Sign-in tokens use PyJWT (pinned at 2.15.1 today); decoding accepts the configured algorithm only and requires every claim. The reason is a comment beside the pin in requirements-runtime.in.
● **Guard:** pip-audit --strict on every lock in scripts/verify.sh; the reason recorded beside the pin.
● **Lesson:** When an advisory sits in a transitive dependency with no fix, replace the direct dependency rather than wait, and use the swap to tighten its use (one algorithm, required claims). Record the reason beside the pin so nobody brings it back.
● **Evidence:** CHANGELOG.md: "in place of python-jose, whose ecdsa dependency carries an advisory with no fixed release. Decoding accepts the configured algorithm only and requires every claim." Also: requirements-runtime.in@HEAD; docs/AUDIT-LOG.md, V0.2 row; commit messages (git log).

### CQ-350 Unfixable base-image vulnerabilities: learn the platform scan's policy before spending an upload, and rescan when the base or feeds move

● **Rule:** `Container Scan (Trivy): 0 Critical, 44 High with no fix in Debian 13.7 packages` · **Raised by:** deploy-gate · **Severity:** minor · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.7 (raised by deploy-gate), V0.8 (the platform's Container Scan passed V0.7's upload; carried as accepted), V0.8 and V0.9 (deploy-gates had no local scanner and relied on the platform scans), V0.10 (deploy-gate reran Trivy: the same 44 unfixable High), V0.12 and V0.13 (deploy-gates left the policy scan to the platform)
● **Applies to:** Container images on a Debian base; any platform with a container scan stage
● **Symptom:** The V0.7 deploy-gate's Trivy scan found 0 Critical and 0 High in Python packages but 44 High in Debian 13.7 base packages, none with a fix (36 in the util-linux family, then ncurses, systemd, acl and perl-base). The platform's scan stage had never been reached and its policy on unfixable Highs was unknown. The V0.8 and V0.9 deploy-gates had no trivy, grype or scout in the sandbox; the V0.10 deploy-gate ran Trivy again and found the same 44 High and 0 Critical, none fixable.
● **Root cause:** The pinned Debian base carries High CVEs with no upstream fix, so no package upgrade can close them.
● **Fix:** Carried as a minor for the V0.7 upload, with a fallback ready (purge the util-linux family in the prep stage, or move to a distroless base, if the scan stopped on them). Fact from the console, recorded in the V0.8 row: V0.7's Container Scan passed with the 44 unfixable High findings. Later deploy-gates leaned on that result while the base digests and Dockerfile were unchanged, with the platform's scan as the binding check. No SECURITY.md position records it.
● **Guard:** Base images pinned by digest; the platform's Container Scan stage. Local Trivy runs in the V0.7 and V0.10 deploy-gates only; the V0.8, V0.9, V0.12 and V0.13 deploy-gates did not rescan locally.
● **Lesson:** Before the first upload, find out whether the platform's container scan fails on High findings with no fix, and keep a fallback ready (purge the affected packages or use a distroless base). A known scan result holds only while the base digest and the OS package and CVE feeds are unchanged, so rescan locally whenever you can.
● **Evidence:** gate report: Deploy-gate on V0.7: "44 unfixable High in the Debian base. The platform's scan stage has never been reached, and its policy on unfixable Highs is unknown." Also: docs/AUDIT-LOG.md, V0.8 row; gate report: Deploy-gate on V0.8; gate report: Deploy-gate on Holly V0.9; gate report: Deploy gate for V0.10; gate report: Deploy gate V0.12.

### CQ-351 Ship the licence of every bundled third-party package, and trace files the bundler inlines

● **Rule:** `none (licence obligations of bundled packages, by the app owner's decision)` · **Raised by:** app owner (decision to ship licences); engineering-reviewer and security-reviewer (tracing gaps, rounds 3 to 6) · **Severity:** minor (each tracing gap was a gate minor; round 3's engineering MAJOR was that the plugin's refusals had no committed test) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.4 (raised and fixed across 7 gate rounds; residual gaps left open after round 7)
● **Applies to:** React and Vite builds; any bundler that ships third-party code
● **Symptom:** The V0.4 theme bundled three Fontsource fonts (OFL-1.1), eight more MIT packages and Vite's own helper code into the dashboard, and at the owner's decision the build had to ship each licence. The gates found tracing gaps round by round: one package from two folders and a font a stylesheet's url() brings in (round 3), a file small enough for Vite to inline shipping as a data: URI that names no package (round 4), a file inlined on request (`?inline`), a stylesheet an @import brings in and a worker's packages (round 5), and ?inline files written to the output unrecorded (round 6).
● **Root cause:** Vite does not record every file it writes: a file named with ?inline reaches the output as a data: URI without a recorded read, and small files are inlined unless inlining is turned off.
● **Fix:** frontend/bundled-licences.mjs, a Vite plugin, copies the licence of every package with a module in the graph or a file the build records reading to licences/, served with an index. It stops the build on a package without a licence file, one package name from two folders, a module or file outside every package and the dashboard's own source, or a data: URI in the built page or a script's new URL(). Vite's inlining of small files is off. Left open after round 7: the worker gap (next entry) and a hand-written data: URI stopping the build only in the double-quoted form.
● **Guard:** scripts/verify.sh checks each runtime dependency's licence is in the output (7 at V0.4) and runs scripts/test-bundled-licences.mjs (23 small projects at V0.4); scripts/mutation-battery.mjs, run in CI, proves the self-test.
● **Lesson:** Build licence notices from what the bundler actually emitted, not from the package manifest, and fail the build on any output file you cannot trace to a package; turn off asset inlining or trace inlined assets explicitly.
● **Evidence:** docs/AUDIT-LOG.md, V0.4 row: "At the requester's decision the build ships, under 'licences/' beside the dashboard"

### CQ-352 Bundler worker builds run their own plugin pipeline, so build-time dependency checks can miss them

● **Rule:** none · **Raised by:** the V0.4 round 7 gates (which gate is not recorded); security-reviewer first raised a worker's packages in round 5 · **Severity:** minor · **Status:** deferred · **Certainty:** mixed
● **Releases:** V0.4 (a worker's packages raised in round 5 and traced from round 6; the worker's ?inline gap left open after round 7)
● **Applies to:** Vite workers; any bundler with separate worker or sub-builds
● **Symptom:** The licence plugin guards the main build only: a file a worker's new URL() inlines with ?inline would ship without its licence.
● **Root cause:** Vite builds a worker with its worker plugins alone, so a plugin registered for the main build never sees the worker's modules.
● **Fix:** None. Left open for a follow-up; the same row notes the dashboard has no worker (inference: why it was not urgent).
● **Guard:** none recorded
● **Lesson:** When a build-time control (licences, policy checks) runs as a bundler plugin, register it for every sub-build the bundler runs, workers included, or fail the build when a sub-build appears.
● **Evidence:** docs/AUDIT-LOG.md, V0.4 row: "The plugin guards the main build only, so a file a worker's new URL() inlines with ?inline ships without its licence, since Vite builds a worker with its worker plugins alone."

### CQ-353 Third-party CI actions pinned by tag rather than commit SHA

● **Rule:** `none (supply-chain pinning of CI actions)` · **Raised by:** not recorded; inference: the V0.1 review gates, since the position first appears in c0a25dc, which fixed both gates' findings on the scaffold, and its release-page wording came in b56e04c, which closed the gates' remaining minors · **Severity:** not recorded (inference: minor, recorded with a reason and trip-wire rather than fixed) · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.1 (recorded as accepted with a trip-wire in c0a25dc, refined in b56e04c)
● **Applies to:** GitHub Actions; any CI that pulls third-party actions
● **Symptom:** The GitHub Actions workflow references its actions by tag, which the action's owner can move: actions/checkout@v4 and actions/setup-python@v5 at V0.1, and actions/setup-node@v4 as well today.
● **Root cause:** Template default: tags are mutable references.
● **Fix:** Accepted in SECURITY.md (created in c0a25dc): the workflow holds a read-only token and no secrets, and never deploys. Trip-wire: pin full commit SHAs, each confirmed against the action's GitHub release page, before the workflow gains any secret or write permission (the release-page confirmation added in b56e04c).
● **Guard:** Trip-wire in SECURITY.md; the workflow's `permissions: { contents: read }`.
● **Lesson:** Pin CI actions to full commit SHAs, confirmed against the release page, before a workflow gains secrets or write permissions; until then keep it least-privilege and record the accepted risk with its trip-wire.
● **Evidence:** SECURITY.md: "| CI actions pinned by tag, not commit SHA | The workflow holds a read-only token and no secrets, and never deploys." Also: commit messages (git log); .github/workflows/verify.yml@HEAD.

### CQ-354 Local runtime older than the engines floor of development dependencies

● **Rule:** `npm EBADENGINE warning (package `engines` field)` · **Raised by:** engineering-reviewer (a note, not a finding) · **Severity:** note (not a finding) · **Status:** open · **Certainty:** mixed
● **Releases:** V0.12 (noted in engineering round 7, left open)
● **Applies to:** Node and npm
● **Symptom:** `npm ci` printed EBADENGINE warnings for jsdom 30.1.2, @asamuzakjp/* and w3c-xmlserializer, which want node 22.22.2 or later, against the local node v22.22.0 that the loop and the simulation use.
● **Root cause:** Test-tooling dependencies set an engines floor above the local Node patch release; the warnings were not caused by the V0.12 change. Inference: the platform's node job, on node:24-alpine (Node 24.22.0 when checked in V0.5), meets the floor.
● **Fix:** None recorded.
● **Guard:** none recorded
● **Lesson:** Treat engines warnings as a sign the local runtime has drifted from what the dependencies and the platform image expect, and align the local runtime with the platform's image rather than leaving the warning.
● **Evidence:** gate report: Engineering gate V0.12 round 7: "the 'npm ci' step prints EBADENGINE warnings for jsdom 30.1.2, '@asamuzakjp/*' and w3c-xmlserializer, which want node 22.22.2 or later against the local v22.22.0." Also: scripts/simulate-pipeline.sh@HEAD; docs/AUDIT-LOG.md, V0.5 row.

### CQ-355 Imported front-end manifest used caret ranges and a test script that passes with no tests

● **Rule:** none · **Raised by:** found at the fusion (who raised it is not recorded) · **Severity:** not recorded · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (imported at 0717c05, fixed at the fusion in 55ab9f1)
● **Applies to:** Node and npm; any imported codebase
● **Symptom:** At import the dashboard's package.json pinned nothing exactly (for example axios ^1.6.8, react-router-dom ^6.23.0, vite ^5.2.11, eslint ^8.57.0, vitest ^1.6.0) and its test script was `vitest run --passWithNoTests`, so an empty suite passed. Files: frontend/package.json, frontend/package-lock.json.
● **Root cause:** The imported project followed different conventions from Holly's exact-pin, lockfile-installed dependency rule (inference on motivation).
● **Fix:** 55ab9f1 upgrades and pins every dashboard dependency exactly (axios 1.20.0, react-router-dom 7.18.4, Vite 7, Vitest 4, ESLint 10), with npm audit clean, and the test script becomes `vitest run`; CLAUDE.md requires exact pins and relocking with npm install --package-lock-only.
● **Guard:** the verification loop's npm ci from the lockfile and npm audit; the dashboard's 80% coverage floor (inference: an empty suite would fail it)
● **Lesson:** On importing code, bring its manifest to the house dependency rules at once: exact pins, a committed lockfile, a current audit, and a test command that fails when no tests run.
● **Evidence:** frontend/package.json at 0717c05: ""axios": "^1.6.8"," Also: commit messages (git log); CHANGELOG.md.

## 2.8 Documentation and records


### CQ-356 Deployment facts that lived only in the platform console failed the deploy gate

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** blocking (deploy-gate FAIL) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (deploy-gate FAIL), V0.6 (upload baseline), V0.7 (deploy-gate FAIL, then PASS on re-run)
● **Applies to:** any app deployed to a managed platform
● **Symptom:** The deploy gate failed V0.5 only on items outside the upload: no resource budget, no fsGroup 10001 request for FILE_STORAGE, the app record (slug, names, category, visibility, add-ons, resources) not in the repository, no rollback, no deployment parameters table, no upload baseline and no confirmed way to create the first admin. It failed V0.7 again on /data writability unconfirmed and the console's app details unrecorded.
● **Root cause:** Platform facts were set and seen only in the App Store console, and nothing in the repository recorded them.
● **Fix:** V0.6 adds scripts/upload-baseline.txt; V0.7 records the owner's console facts in operator manual section 03 (deployment parameters), withdrawal by removing the app, and the first admin from App Store variables. The platform team confirmed /data writability and the owner waived the app-details check; the re-run on the same bytes passed.
● **Guard:** The deploy-gate checklist before each upload.
● **Lesson:** Copy every platform setting the deployment depends on into a versioned table in the repository, with its source and date, so a gate can check it without console access.
● **Evidence:** the app owner's message: "The deploy-gate failed V0.5 only on items outside the upload: no resource budget recorded; no fsGroup 10001 request for FILE_STORAGE" Also: docs/AUDIT-LOG.md, V0.7 row.

### CQ-357 A documented rollback command that fails inside the shipped image

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised in engineering round 1), V0.10 (fixed in round 2)
● **Applies to:** any containerised app with schema migrations
● **Symptom:** The only documented rollback across migration 0018, `alembic downgrade 0017_audit_append_only`, failed in the V0.10 container with "No 'script_location' key found in configuration" (exit 255), because the lean image ships no alembic.ini. data-model.md also said downgrades were for development databases only, and no test protected the 0018 downgrade (mutant B35 survived).
● **Root cause:** The rollback text was written for the developer checkout, where alembic.ini exists, and was never rehearsed in the production image.
● **Fix:** Round 2 documents a `python -c` form calling alembic's command.downgrade with app.migrate.alembic_config(), rehearsed on PostgreSQL (exit 0, schema at 0017, V0.9 then starts), in ADR-014 and the operator manual; reconciles data-model.md (downgrades on a development database only, with the V0.10 to V0.9 rollback as the one exception); and pins the 0018 downgrade in a migration test (B35 killed).
● **Guard:** A migration test of the 0018 downgrade (tests/test_migrations.py); the deploy gate rehearses the documented rollback in the built image.
● **Lesson:** Rehearse every documented operator command inside the artefact that ships, not the development checkout; a lean image often drops the config files a CLI needs.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "**The only documented rollback across 0018 does not work in the image.**" Also: docs/AUDIT-LOG.md, V0.10 row; tests/test_migrations.py at af13871.

### CQ-358 A changelog edit that overwrote the previous release's heading

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised in engineering round 1), V0.10 (fixed in round 2)
● **Applies to:** any project keeping a CHANGELOG
● **Symptom:** The V0.10 CHANGELOG hunk replaced `## Holly V0.9 (2026-10-20)` instead of adding a heading above it, so V0.9's Fixed and Changed entries (the gateway fix, the reload fix, the address, the credentials-mode note) read as V0.10's. V0.10 also had two Changed sections and a double blank line.
● **Root cause:** The new release section was written over the top of the previous heading in a structured record that no check parses (no test or script reads the CHANGELOG at HEAD f8a00bd).
● **Fix:** Round 2 restores the V0.9 heading, gives V0.10 one Added and one Changed section and removes the double blank line; the backfilled V0.9 credentials line was checked against 83e9696.
● **Guard:** None recorded; the gates read the CHANGELOG diff each round.
● **Lesson:** Treat the changelog as structured data: add a release section above the last one, never edit into it, and read the diff for a removed heading before committing.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "**The V0.9 release has vanished from the changelog.** The hunk replaced '## Holly V0.9 (2026-10-20)' instead of adding a new heading above it." Also: gate report: Engineering gate on V0.10 round 2.

### CQ-359 Documents describing a control's intended effect rather than its measured one

● **Rule:** none · **Raised by:** security-gate, engineering-gate · **Severity:** MAJOR (engineering; a minor for security) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.7 (the worker holding ADMIN_PASSWORD raised as a security minor in round 1; the documents' false claim raised in round 2, a security minor and an engineering MAJOR), V0.7 (fixed in round 3)
● **Applies to:** any stack; security documentation
● **Symptom:** The operator manual said the gunicorn master drops ADMIN_PASSWORD "so the worker never holds it", SECURITY.md said the same more loosely, and the AUDIT-LOG row recorded the security minor as closed, while the worker's cfg.env_orig and /proc environ still held the password.
● **Root cause:** The documents and the record described the change (a pop from the master's os.environ), while gunicorn copies the environment into cfg.env_orig before on_starting runs and hands that copy to the worker. Inference: no probe of the worker preceded the claim.
● **Fix:** Round 3 drops the password from gunicorn's cfg.env_orig as well, and the comment, operator-manual.md:185 and a new SECURITY.md row say what still holds it (each process's /proc/<pid>/environ until a restart without the variable).
● **Guard:** None automated; the gates probe /proc and cfg.env_orig in the built image.
● **Lesson:** Before a document claims a control works, or a record marks a finding closed, measure the property in the running artefact and write down exactly what the measurement showed, residue included.
● **Evidence:** gate report: Security gate on V0.7: "**[minor] The worker inherits 'ADMIN_PASSWORD'**" Also: gate report: Engineering gate, V0.7 round 2; gate report: Engineering gate, V0.7 round 3.

### CQ-360 A behaviour change made for a static-analysis rule left documents and comments describing the old behaviour

● **Rule:** `SonarQube S8414 (the fix that moved CORS outermost)` · **Raised by:** engineering-gate, security-gate · **Severity:** MAJOR · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.6 (raised in engineering round 1; the comment nit in security round 2), V0.6 (fixed in round 2; the comment in round 3)
● **Applies to:** any stack with middleware ordering; SonarQube remediation
● **Symptom:** Moving CORS outermost to clear S8414 made every preflight leave without the security headers and X-Request-ID, which 5 places (the security overview, architecture overview, operator manual, a test header and request_id.py) denied, with no SECURITY.md position. The audit row and CHANGELOG also said a 413 gained CORS headers it already carried, and the strict-CSP comment in factory.py still said "on every response that is not an HTML page".
● **Root cause:** The change was filed as a code-smell fix (the V0.6 row lists S8414 under Smells). Inference: so the documents that state the affected security behaviour were not searched or re-read.
● **Fix:** Round 2 keeps CORS outermost, adds a SECURITY.md row for the preflight position with a trip-wire, corrects the 5 places, names the 429 alone and pins it with a test; the comment now ends "but a CORS preflight".
● **Guard:** A test pins the 429's CORS header; the SECURITY.md row carries a trip-wire.
● **Lesson:** A fix for a quality rule can change observable behaviour; search the docs, comments and security record for every claim about the behaviour the fix touches before calling it a smell fix.
● **Evidence:** gate report: Engineering gate on V0.6 tree: "Moving CORS to the outside layer changed security behaviour, and the security docs were not updated to match." Also: docs/AUDIT-LOG.md, V0.6 row; gate report as received.

### CQ-361 Absolute claims about a filter's coverage written into comments and the security record before they were tested

● **Rule:** none · **Raised by:** security-gate, engineering-gate · **Severity:** MAJOR (the claims were part of MAJOR findings on the CLOSED-name filter) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.12 (raised in rounds 2, 3 and 4), V0.12 (fixed by round 6)
● **Applies to:** any stack; input normalisation and security records
● **Symptom:** Round by round the _word_text comment, docstring, CHANGELOG and SECURITY.md row claimed more than the filter did: that no character could hide or split CLOSED, that every invisible character was taken out, that combining characters were removed (no test proved Mn or Me), that a combining accent folds into its letter (in a docstring that also wrapped mid-sentence), and finally that "Dropping a character can only join letters into the word, so it fails towards closed". Each was disproved by the next probe, and the last made the accepted-risk record state a property that did not hold.
● **Root cause:** Absolute wording was written to match the intended control. The last claim came with the round 3 security reviewer's suggested fix ("It is fail-safe") and was copied into the comment and SECURITY.md without testing the opposite direction (inference from the matching wording).
● **Fix:** Each round corrected the claims (c2ac5cb, c00e3d2, 8aa5ecc, fc96e56, 56d0dbc). The final rule (56d0dbc) is one marked reading, in which each hidden character is nothing inside the word and a boundary beside it; SECURITY.md describes it, says an odd name fails towards closed and names the accepted look-alike gap; round 6 reviewers confirmed the docstrings, the SECURITY.md row and the CHANGELOG describe the code.
● **Guard:** Close-cases for each dropped category (Cf, Mn, Me, Cn), the mixed hidden-character cases and the separators, each proven by removing its control; reviewers read the docstring, the SECURITY.md row and the CHANGELOG against the code each round.
● **Lesson:** Never write "every", "none" or "can only" about a security filter until a test or probe covers that claim in both directions, and treat a reviewer's suggested rationale as a hypothesis to test, not a fact to copy.
● **Evidence:** gate report: Security gate V0.12 round 2: "**Comment:** correct the claim in the '_word_text' comment." Also: gate report as received; gate report: Engineering gate V0.12 round 3; gate report: Engineering gate V0.12 round 4; SECURITY.md at f8a00bd.

### CQ-362 A process rule restated in several documents and worded from one case drifted from practice

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised on 092cf83 as a nit, then two MAJORs on 092cf83..0c67540), V0.3 (fixed in a9be004 and 6a718d0)
● **Applies to:** any project with a release or versioning policy
● **Symptom:** The version-bump rule asked for a bump on every change, while upload-neutral changes were in practice recorded in the current release's row. The first written rule (0acfafa) forbade keeping a release's gate fixes in its row, which the practice did; developer setup still stated the old rule; the definition of an upload change missed a .gitattributes and the archive command; and record-only commits went unjudged.
● **Root cause:** One rule was restated in CLAUDE.md, developer setup and the audit log header, and 0acfafa's wording covered the upload-neutral changes it named (70f0314, d1f477a, 092cf83) but not gate fixes that changed shipped files (a6ee4df in V0.3, V0.2's fixes).
● **Fix:** CLAUDE.md defines a change as a piece of work together with its gate fixes; anything that alters what scripts/package-appstore.sh writes (its paths, path list, archive command or a .gitattributes) bumps the stamp and opens a row; a change that leaves the upload alone joins the current row. Setup and the audit log header point at CLAUDE.md instead of restating it (a9be004); the owner approved the wording (6a718d0). The record commit d79cd7d says the next gate round judges it.
● **Guard:** None automated; the rule lives in one place and others point to it.
● **Lesson:** State each process rule once and point to it from everywhere else, and write it from the practice it must cover, testing the wording against past cases before adopting it.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "engineering-reviewer FAIL (MAJOR: developer setup still stated the old rule; MAJOR: the rule as worded forbade keeping a release's gate fixes in its row, which the practice did" Also: commit messages (git log).

### CQ-363 Records and commit messages claimed checks or closures that had not been verified

● **Rule:** none · **Raised by:** engineering-gate, security-gate · **Severity:** minor (one claim sat inside a V0.3 MAJOR) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.1 (raised), V0.3 (raised in the upload-record rounds), V0.8 (raised in engineering round 2); each corrected in the release
● **Applies to:** any project keeping a release or audit record
● **Symptom:** V0.1: the audit row had to be rewritten to record only checks that ran (inference that it had not). V0.3: a commit message claimed removing any guard turns the cases red when four could be deleted with the self-test green; the row called the upload "byte-identical"; SECURITY.md claimed every refusal was pinned and a case for each guard; two figures were wrong; the record rule was stated three ways. V0.8: the round 2 text said round 2 "closes each" item and that "tests pin each case named", but a temporary-directory leak remained and four blank-as-unset names were unpinned.
● **Root cause:** Closures and coverage claims were written from the intended fix rather than checked, claim by claim, against a run or a mutation.
● **Fix:** Each record was corrected: V0.1's row records only checks that ran, with each verdict's commit; V0.3's row and SECURITY.md were corrected (e40e12b, 8c70dbd, V0.4's row 29 rewrite) and name which guards turn red only through wording; V0.8's row adds "Two closures above overstate".
● **Guard:** Practice: the gates check each claimed closure by mutation, and each row names the commit each check and verdict applies to.
● **Lesson:** Write a closure or a "pinned by tests" claim only after the matching run or mutation, name the commit it ran on, and say plainly which items stay open.
● **Evidence:** commit messages (git log): "Docs: the audit row records only checks that ran and each gate verdict" Also: docs/AUDIT-LOG.md, V0.3 row; docs/AUDIT-LOG.md, V0.8 row.

### CQ-364 A release record left describing an earlier round after later rounds changed the code

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised in engineering round 2), V0.13 (raised in engineering round 2); each fixed in the record commit
● **Applies to:** any project with a per-release record
● **Symptom:** V0.10: the row still gave usernames as "1 to 50 printable characters" and the smoke rung as finding "five audit rows", and omitted the locked re-read, logout's stale_token refusal and the 422 length stripping. V0.13: the row still said the offsets were filled with `Array.fill` and the lint had "all three" rules after round 1 moved to `Array.from` and added S7723; the CHANGELOG had been updated, and its claim to enforce S7723 was only partly true.
● **Root cause:** The row was drafted in the first commit and not refreshed when a later round changed the code; the CHANGELOG and the row were updated separately.
● **Fix:** Brought up to date in the record commits (f025c2c for V0.10; 0180d55 for V0.13, which also narrowed the S7723 claim in the row and the CHANGELOG).
● **Guard:** None automated; reviewers read the record against the code each round.
● **Lesson:** Re-read the release record against the final diff as the last step before recording a round, and update the changelog and the record together.
● **Evidence:** gate report: Engineering gate on V0.10 round 2: "Still describes round 1:" Also: gate report: Engineering gate V0.13 round 2; commit messages (git log).

### CQ-365 A rollback runbook that omitted secret rotation, step order and a path without shell access

● **Rule:** none · **Raised by:** security-gate, deploy-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised by security round 2 and the deploy gate), V0.11 (raised again by the deploy gate), V0.12 (fixed)
● **Applies to:** any app with migrations and token or session state
● **Symptom:** A rollback to V0.9 revived every session V0.10 had ended, since V0.9 ignores token_version, yet the runbook did not require rotating APP_SECRET_KEY or re-issuing pending temporary passwords. V0.10 answers 500 between the downgrade and V0.9's start, and a restart in that window re-applies 0018. The only documented path needed a shell in the container, which is TBC on the App Store. At V0.11 the section still described V0.10 to V0.9 with no rotation step.
● **Root cause:** A schema downgrade undoes security state (token versions, forced password changes) and the runbook was written as a single command, not as an ordered procedure for the platform's restart behaviour.
● **Fix:** V0.12's rollback texts require rotating APP_SECRET_KEY with the V0.9 upload and again on any roll-forward, re-issue pending temporary passwords, give the order (note temporary passwords, rotate the key, downgrade, upload straight away) and describe a way with no shell: V0.9's code with migration 0018 added, released as a new version, rehearsed by the deploy gate.
● **Guard:** The deploy gate reviews and rehearses the rollback each release.
● **Lesson:** Write rollback as an ordered runbook that names the security state the downgrade undoes and how to restore it, and include a path that needs no access the platform has not confirmed.
● **Evidence:** gate report: Security gate on V0.10 round 2: "in both rollback texts, require rotating 'APP_SECRET_KEY' in the same settings change as the V0.9 upload, and again on any roll-forward." Also: gate report: Deploy gate for V0.10; docs/AUDIT-LOG.md, V0.12 row.

### CQ-366 Unconfirmed platform behaviour and inferred causes written as observed fact

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** open · **Certainty:** fact
● **Releases:** V0.5 (raised in engineering round 1; the code comments listed open after round 2 in 56c55a9), V0.7 (raised in engineering round 1); the records fixed in each release, the code comments still open at V0.13
● **Applies to:** any app deployed to a platform whose internals are not fully documented
● **Symptom:** V0.5: the row and CHANGELOG stated the node job's later commands (test and build) as fact when the job logs confirmed only `npm ci`; comments in frontend/vite.config.ts, scripts/verify.sh and scripts/package-appstore.sh still say the node job runs the tests and Code Quality reads coverage/lcov.info. V0.7: the operator manual's table of console facts and CLAUDE.md gave the cause of the detected node-react stack as fact while the audit row marked it as inference.
● **Root cause:** Template assumptions and the team's own deductions were written into places that otherwise hold observed facts.
● **Fix:** V0.5's CHANGELOG says the commands after `npm ci` follow the platform's node template until confirmed, and CLAUDE.md marks them TBC, re-verify; V0.7 round 2 marks the stack cause as inference. The three code comments were listed as an open follow-up and are unchanged at HEAD f8a00bd.
● **Guard:** Practice: unknowns carry `TBC, re-verify` and inferences are labelled.
● **Lesson:** Label every platform statement as observed (with its source), inferred or TBC, in code comments as well as in documents, and keep deductions out of tables of observed facts.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "two minors (this row's evidence; the node job's later commands stated as fact)" Also: CHANGELOG.md; commit messages (git log); gate report: Engineering gate on V0.7.

### CQ-367 An open platform question closed silently in a docstring and an open-items list

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.7 (present from round 1, raised in engineering round 3), V0.7 (fixed in round 4)
● **Applies to:** any stack
● **Symptom:** The admin_bootstrap.py docstring stated "On the App Store there is no shell in the container" as fact while four documents held it TBC, re-verify, and CLAUDE.md dropped the shell from its open items though resetting an admin and verifying the audit chain still need one. Rounds 1 and 2 missed it.
● **Root cause:** The docstring stated an unconfirmed platform assumption as fact, with no owner fact behind it (the V0.7 row records none). Inference: it was written while designing a bootstrap that needs no shell.
● **Fix:** Round 4 restores `TBC, re-verify` in the module docstring and in CLAUDE.md's open items.
● **Guard:** None recorded.
● **Lesson:** Close an open question only by recording the fact that answers it and its source; a design built around an assumption does not confirm it.
● **Evidence:** gate report: Engineering gate, V0.7 round 3: "as fact, while operator-manual.md:193, SECURITY.md:23, decision-log.md:131 and audit/overview.md:95 still hold it TBC, re-verify, and the V0.7 row records no such owner fact." Also: gate report: Engineering gate, V0.7 round 4.

### CQ-368 A confirmed platform fact left marked unknown in the documents

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (confirmed by the platform team), V0.8 and V0.9 (raised by the deploy gate), V0.10 (fixed)
● **Applies to:** any project that marks unknowns
● **Symptom:** The operator manual (line 98) and CLAUDE.md's adoption note still marked /data writability by user 10001 as TBC, re-verify after the platform team confirmed it via the owner on 19 October 2026 and V0.8 started with the store write check passing; V0.7's row had deferred recording it and V0.8 did not.
● **Root cause:** The confirmation arrived in conversation and was not folded back into the documents that carried the TBC marker.
● **Fix:** V0.10 records /data as writable by user 10001, confirmed by the platform team and shown by V0.8 and V0.9 starting.
● **Guard:** None recorded; the deploy gate reads the TBC markers each release.
● **Lesson:** When a TBC is answered, update every document carrying that marker in the next change, citing who confirmed it and when; a stale TBC hides what is actually known.
● **Evidence:** docs/AUDIT-LOG.md, V0.9 row: "'/data' writability still marked 'TBC' in the docs though settled" Also: docs/AUDIT-LOG.md, V0.10 row.

### CQ-369 Store listing fields never copied from the console into the repository

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** BLOCKER at the first V0.7 deploy gate, then waived by the owner; minor at each later gate · **Status:** open · **Certainty:** fact
● **Releases:** V0.7 (raised, waived by the owner), V0.8, V0.9, V0.10 and V0.12 (raised again by the deploy gate); still open at V0.13
● **Applies to:** any app published to a managed store or catalogue
● **Symptom:** Display name, descriptions, category and visibility live only on the App Store console; the operator manual's app record shows them as `TBC, re-verify`, so each deploy gate could not check them and asked the owner to check the console before submitting.
● **Root cause:** The owner entered the fields in the console and waived the gate's check rather than supplying the values for the record.
● **Fix:** None yet; the owner checks them on the console before each submission.
● **Guard:** The deploy gate names the gap each release.
● **Lesson:** A waiver gets one release through but leaves the gap for every later gate; capture the console values once, with their date, so the check can run.
● **Evidence:** gate report: Deploy-gate on V0.7: "[BLOCKER] App record | Category, display name and visibility are 'TBC, re-verify'." Also: gate report: Deploy-gate re-run on V0.7; gate report: Deploy-gate on Holly V0.9; docs/runbook/operator-manual.md at f8a00bd.

### CQ-370 Operator instructions that never say which variables not to set

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** minor · **Status:** open · **Certainty:** fact
● **Releases:** V0.7 (raised by the deploy gate on 452e3c7); not recorded as fixed
● **Applies to:** any app deployed with platform-injected settings
● **Symptom:** Section 03 of the operator manual never said not to type PORT into the environment tab and had no single table marking each variable as operator-set or platform-injected. The re-run gave the owner a do-not-set list, PORT first, in its report only.
● **Root cause:** The deployment parameters were recorded as console facts, not as operator instructions.
● **Fix:** None recorded in the repository. At HEAD f8a00bd the manual tells the operator to leave the database and storage variables to the add-ons, but names PORT only in the start sequence, /status and troubleshooting ("fix or remove the `PORT` variable"), with no instruction not to set it in the console.
● **Guard:** None recorded.
● **Lesson:** Give operators an explicit set and do-not-set list of environment variables, marking which the platform injects, and keep it in the runbook rather than in a gate's report.
● **Evidence:** gate report: Deploy-gate on V0.7: "Section 03 never says not to type 'PORT' into the environment tab" Also: gate report: Deploy-gate re-run on V0.7; docs/runbook/operator-manual.md at f8a00bd.

### CQ-371 A single observation generalised into a claim about every case

● **Rule:** none · **Raised by:** engineering-gate, security-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised in round 1 by both gates, again in round 2), V0.9 (fixed in round 3); the cookie wording raised in V0.9 round 3, fixed in V0.10
● **Applies to:** any app behind a third-party gateway or proxy
● **Symptom:** From one refused HS256 token, the audit row (tagged "(fact)"), operator manual, architecture overview and code comments said the App Store gateway "checks any bearer token" "before Holly saw the request". Round 2 fixed the named documents but missed CHANGELOG.md:16 and a new comment in scripts/smoke-container.sh. SECURITY.md and ADR-013 likewise said the platform sets a session cookie on Holly's host, where the record showed only `_appstore_app_session` travelling on a request to it.
● **Root cause:** One observation was written up as a general rule, and the first fix covered only the places the gate listed.
● **Fix:** Round 3 states the refusal of Holly's token as fact and marks "any bearer token" and "before Holly saw it" as inference everywhere, the CHANGELOG and the smoke comment included; V0.10 says the cookie was seen travelling on requests to Holly's host, the platform's by inference.
● **Guard:** None recorded.
● **Lesson:** Write an observation at the scope it was seen (this request, this token, this date) and label any wider rule as inference; when fixing such wording, search the whole tree, not only the places a reviewer named.
● **Evidence:** docs/AUDIT-LOG.md, V0.9 row: ""any bearer token" stated as fact" Also: gate report: Engineering gate on V0.9 round 3; gate report: Security gate on V0.9 round 3.

### CQ-372 Platform facts written into reusable skills before the project's own record held them

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor (the remainder a nit) · **Status:** open · **Certainty:** fact
● **Releases:** V0.8 (raised in engineering round 1, mostly closed in round 2); one remainder still open
● **Applies to:** any team sharing a baseline of skills or runbooks across apps
● **Symptom:** The baseline skills cited the DAST log for "one memory-limited job with a browser", "blocks on High or Critical findings" and `no_coverage`, none of which the V0.8 row recorded, and stated "retrying the same image fails the same way" as fact; the gate could not check any of it because the owner's log was not on disk. After round 2 the appstore-gate-compliance skill still quotes the log's host name `dast-target`, which the row does not record, though the log the owner pasted does name it.
● **Root cause:** Facts the owner pasted were folded into shared skills before being recorded, with their source, in the audit row.
● **Fix:** The V0.8 row now records the scan's contract from the log and the console, with how the container reaches the scan database marked TBC, re-verify. The `dast-target` remainder is listed open in the V0.8 row and unchanged at HEAD.
● **Guard:** None recorded.
● **Lesson:** Record a platform fact in the project's own record, with its source, before teaching it to other projects through shared guidance, so a reviewer can trace every shared claim.
● **Evidence:** gate report: Engineering gate on V0.8 DAST: "the skills cite the scan log for facts the V0.8 audit row does not record" Also: gate report as received; docs/AUDIT-LOG.md, V0.8 row; the app owner's message.

### CQ-373 A production address recorded from a pattern, then the correction generalised and applied unevenly

● **Rule:** none · **Raised by:** app-owner (their browser record showed the real address), engineering-gate · **Severity:** minor (the generalisation a nit) · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.9 (shown by the app owner's browser record, then raised in engineering rounds 1 and 2), V0.9 (fixed)
● **Applies to:** any app deployed to a hosted platform
● **Symptom:** The documents gave holly.apps.bluestaq.com; the owner's browser record showed the App Store serving holly.appstore.bluestaq.com. After the correction, .claude/skills/getting-started/SKILL.md:62 still gave `${APP_SLUG}.apps.bluestaq.com`, and the app-store-deployment skill and glossary turned Holly's one observed address into every app's address.
● **Root cause:** The address came from baseline notes written before the app was deployed (inference); the rename was applied to a chosen set of files rather than swept across the tree, and one observation was recorded as a rule.
● **Fix:** The operator manual, architecture overview, training manual, CLAUDE.md, the CHANGELOG and three skills moved to holly.appstore.bluestaq.com with the earlier form noted; the pattern is marked as inference from Holly's address, seen 20 October 2026.
● **Guard:** None recorded.
● **Lesson:** Record an endpoint only from an observation of the deployed app, sweep the whole tree when correcting it, and keep a one-app observation labelled as such in shared guidance.
● **Evidence:** docs/AUDIT-LOG.md, V0.9 row: "the address is 'holly.appstore.bluestaq.com', where the documents said 'holly.apps.bluestaq.com'" Also: gate report: Engineering gate on V0.9 round 1; gate report: Engineering gate on V0.9 round 2.

### CQ-374 A platform fault attributed to a local test gap that could not have caught it

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor (the comparison a nit) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised in engineering rounds 1 and 2), V0.9 (fixed)
● **Applies to:** any app behind infrastructure not reproduced locally
● **Symptom:** The audit row called the smoke rung's not sending the token "the gap that let this reach the App Store", and the app-store-deployment skill implied a smoke rung that sends it could see the fault; but V0.8's own row records the image answering /auth/me 200 locally with the bearer token. The row also called the token-expiry fault "indistinguishable" from the gateway fault, though one shows only after expiry with Holly's own 401 and the other straight after sign-in with an empty body.
● **Root cause:** A platform-only fault (an upstream gateway) was conflated with a missing local check, and a shared visible symptom was written up as identical faults.
● **Fix:** Both texts now use ADR-013's wording: the smoke rung proves the app's side, and only a gateway stand-in in front of the container reproduces the refusal; the comparison reads "with the same symptom, a return to the sign-in page".
● **Guard:** None recorded.
● **Lesson:** Before naming the gap that let a fault through, check that the proposed check would actually have failed on the faulty release; otherwise the record points the next team at the wrong fix.
● **Evidence:** gate report: Engineering gate on V0.9 round 1: "The real gap is that no local rung has a gateway." Also: .claude/skills/app-store-deployment/SKILL.md at 83e9696; gate report: Engineering gate on V0.9 round 2.

### CQ-375 A reworded claim changed in some places only, and the closure recorded before every occurrence was checked

● **Rule:** none · **Raised by:** engineering-gate, security-gate · **Severity:** minor (a security nit) · **Status:** open · **Certainty:** fact
● **Releases:** V0.7 (raised in round 3 as an engineering minor and a security nit; partly fixed in round 4, where both gates raised the remainder); still open at V0.13
● **Applies to:** any stack
● **Symptom:** The docs said the ADMIN_* variables are "not read at all" once an account exists, but admin_bootstrap.py reads all three for presence before the lock and count. Round 4 reworded 6 places to "no value is checked or used", but setup.md's ADMIN_USERNAME row, SECURITY.md's first-admin row and a test comment still say not read, and the audit row's closure overstated.
● **Root cause:** The rewording was applied in some documents only, and the closure was written before every occurrence was searched.
● **Fix:** The V0.7 audit row records the overstatement and lists the three places as a follow-up; at HEAD f8a00bd setup.md still says "none of the `ADMIN_*` variables is read", SECURITY.md still says "Only while there are none does it read" the three, and the test comment is unchanged.
● **Guard:** None recorded.
● **Lesson:** When a fix rewords a claim, grep the whole tree for the old wording and its variants before recording the finding as closed.
● **Evidence:** gate report: Engineering gate, V0.7 round 4: "claims a closure that is not complete." Also: docs/AUDIT-LOG.md, V0.7 row; tests/test_admin_bootstrap.py at f8a00bd; SECURITY.md at f8a00bd.

### CQ-376 Documented fallback behaviour that differed from the code, recurring after a partial fix

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.11 Comms review (raised), V0.12 round 1 (raised again), V0.12 round 2 (confirmed fixed)
● **Applies to:** any app with seed or fallback configuration
● **Symptom:** The code pulled the MATTERMOST_CHANNEL_IDS seed whenever the channel table was empty, even after a successful sweep that found nothing, while setup.md, the operator manual, ADR-015 and the CHANGELOG said "until a sweep has succeeded once"; a seed id the first sweep did not find vanished without a log line. After the first fix, src/app/config.py:160 and CHANGELOG.md:26 still carried the old wording.
● **Root cause:** The docs described the designed rule while the code keyed on table emptiness, and the first rewording missed two files.
● **Fix:** The wording now says the seed decides while Holly holds no channel, everywhere (0a60d93, then f6056cd for the two lines); a seed the sweep does not find is logged as a warning.
● **Guard:** test_a_seed_the_first_sweep_does_not_find_is_logged; the missing-seed log mutant went red in the V0.12 gate.
● **Lesson:** Describe configuration fallbacks from the code's actual condition, log configured values that never match, and search every document and comment for the old rule when correcting it.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "The seed list applies longer than the docs say, and a missing seed vanishes silently" Also: gate report: Engineering gate V0.12; gate report: Engineering gate V0.12 round 2.

### CQ-377 A feature's documentation sweep missed documents whose facts it changed

● **Rule:** none · **Raised by:** engineering-gate (setup.md and the security overview); not recorded for the audit overview and training manual items · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.10 (setup.md and the security overview raised in engineering round 1, fixed in round 2); V0.12 (the audit overview and training manual, recorded among V0.10's open minors, fixed)
● **Applies to:** any stack
● **Symptom:** After V0.10 added the Users page, setup.md still said no route or command creates an analyst or operator account and omitted that a create_admin rerun ends the account's sessions; the security overview still said Holly has no route that revokes another user's tokens. Inference from V0.12's fix: the audit overview did not list the new account actions or the stale_token reasons, and the training manual's navigation did not name Users and Password.
● **Root cause:** Inference: the doc sweep for the feature covered the documents it was written against, not every document stating a fact the feature changed.
● **Fix:** Round 2 points setup.md and the security overview at the Users page's reset or deactivate; V0.12 brings the audit overview and training manual up to date.
● **Guard:** None recorded.
● **Lesson:** For each fact a feature changes (who can create accounts, what revokes tokens, what is audited), search the docs for the old statement rather than editing only the documents you expected to touch.
● **Evidence:** gate report: Engineering gate on V0.10 round 1: "Point each at the Users page's reset or deactivate." Also: docs/AUDIT-LOG.md, V0.10 row; docs/AUDIT-LOG.md, V0.12 row.

### CQ-378 Docstrings, interface copy and operator warnings left describing the old ingest model

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.11 Comms review (raised), V0.12 (fixed in 0a60d93)
● **Applies to:** any app with background ingestion
● **Symptom:** After channel discovery replaced configured pulls, background_refresh.py still described pulling the configured channels with one single-flight cycle, the Comms page said Holly keeps pulling when Mattermost is not configured, the audit overview's "up to 1,440 rows a day" left out on-demand sweeps, and the operator manual did not warn that the first start follows and pulls every channel the bot is already in, and so sends them to the assistant.
● **Root cause:** Docs and copy written for the pull-only behaviour were not revisited when the ingest model changed.
● **Fix:** 0a60d93: the background loops' description names the sweep, the Comms page says when Mattermost is not configured, the audit overview counts the rows a day, and the operator manual warns that the first sweep follows every channel the bot is already in.
● **Guard:** None recorded beyond the gates' doc review.
● **Lesson:** When a data flow changes, list its side effects for operators (what is pulled on first start, where it goes, audit volume) and check every docstring and piece of UI copy that describes the flow.
● **Evidence:** gate report: Engineering gate on V0.11 round 1: "The operator manual does not warn that the first V0.11 start follows and pulls every channel the bot is already in" Also: CHANGELOG.md; commit messages (git log).

### CQ-379 New refusals that apply to every start left out of the settings reference and changelog

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** open · **Certainty:** mixed
● **Releases:** V0.8 (raised in engineering round 2); still open at V0.13
● **Applies to:** any app with validated configuration
● **Symptom:** Two refusals added with the DAST-scan work apply to every start: a blank APP_SECRET_KEY is refused, and blank database variables read as unset, so a blank POSTGRES_PASSWORD is now refused. setup.md still says only "At least 32 characters", and the CHANGELOG and operator manual section 10 are silent.
● **Root cause:** Inference: the change was documented as part of the scan's start; its side effects on normal starts were not carried into the settings reference.
● **Fix:** None yet; the V0.8 row lists it open (proposed: one CHANGELOG line, the two setup.md rows, and "a blank" in section 10's list).
● **Guard:** None recorded.
● **Lesson:** When a change tightens validation as a side effect, document the new refusal in the settings reference and changelog, even if the change's purpose was elsewhere.
● **Evidence:** gate report: Engineering gate, V0.8 round 2: "two new refusals that apply outside the scan are undocumented." Also: docs/AUDIT-LOG.md, V0.8 row.

### CQ-380 A runbook quoting the error text it expected rather than the one observed

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** minor · **Status:** open · **Certainty:** mixed
● **Releases:** V0.12 (raised by the deploy gate); still open at V0.13
● **Applies to:** any app with migrations and an operator runbook
● **Symptom:** Operator manual lines 79 and 271 quote Alembic's error as "Can't locate revision identified by", but the gate's live rollback rehearsal showed V0.11 started on a database at 0019 exits with "ResolutionError: No such revision or branch '0019_mattermost_channel'".
● **Root cause:** Inference: the manual's error text was written from expectation, not from an observed failure.
● **Fix:** None recorded; the gate's fix, to quote both strings, is not applied at HEAD f8a00bd. The gate said the edit would not change the upload, though since V0.12 (cf5a234) the operator manual ships in it.
● **Guard:** The deploy gate rehearses the rollback live.
● **Lesson:** Quote error messages in runbooks only from a reproduced failure, and include every variant an operator may see.
● **Evidence:** gate report as received: "Problem: operator manual lines 79 and 271 quote Alembic's error as 'Can't locate revision identified by'." Also: docs/AUDIT-LOG.md, V0.12 row; docs/runbook/operator-manual.md at f8a00bd.

### CQ-381 A runbook shipped inside the artefact names the previous release

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** minor · **Status:** deferred · **Certainty:** fact
● **Releases:** V0.13 (raised by the deploy gate, deferred)
● **Applies to:** any app that bundles its runbook in the deployable artefact
● **Symptom:** The operator manual's rollback section says "From V0.12 to V0.11 ... in the V0.12 container" where for this release it is the V0.13 container; the command is unchanged.
● **Root cause:** Since V0.12 (cf5a234) the operator manual ships in the upload; V0.13's fix did not touch it, and editing it after the gates would change the upload and need a version bump.
● **Fix:** Deferred to the next release that touches the upload.
● **Guard:** None recorded.
● **Lesson:** Keep release-specific text out of documents bundled into the artefact, or refresh them as part of every release, since fixing them later forces a new version.
● **Evidence:** docs/AUDIT-LOG.md, V0.13 row: "the operator manual's rollback names the V0.12 container where it is now V0.13's, the command unchanged (next release that touches the upload)" Also: gate report: Deploy gate V0.13 (fast); commit messages (git log).

### CQ-382 A release number restated in agent instructions went stale on every bump

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised in engineering round 1), V0.3 (fixed in 092cf83)
● **Applies to:** any stack
● **Symptom:** CLAUDE.md still named V0.2 as the current stamp after the bump to 0.3.0; once updated (d1f477a) the reviewer noted each future bump would raise the same finding again.
● **Root cause:** The release number was duplicated into a document no test checked.
● **Fix:** At the owner's request CLAUDE.md stopped naming the release and points at `__version__` in src/app/__init__.py and the test that holds the other copies equal.
● **Guard:** tests/test_version.py holds pyproject.toml, frontend/package.json and both root version fields of frontend/package-lock.json equal to __version__.
● **Lesson:** Keep a version in one source of truth with a test that holds every other copy equal to it, and have prose point at that source instead of repeating the number.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "CLAUDE.md still names V0.2 as the current stamp" Also: commit messages (git log).

### CQ-383 A failure's mechanism recorded from hypothesis rather than the observed sequence

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.3 (raised in engineering round 1), V0.3 (fixed in a6ee4df)
● **Applies to:** any stack
● **Symptom:** The CHANGELOG and the audit row said `docker compose --wait` had returned during the PostgreSQL image's temporary socket-only server; it returned as soon as the container started, during initdb, before that server existed.
● **Root cause:** Inference: the explanation was written from a plausible model of the image's start-up, not from the reproduced timeline.
● **Fix:** The CHANGELOG and row corrected; developer setup now says how `--wait` fails.
● **Guard:** None for the record itself; a loop step pins the TCP health check and dev.sh's wait that the record describes.
● **Lesson:** Describe a failure's mechanism from the reproduced timeline, and say which phase was observed and which inferred.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "the CHANGELOG and this row said '--wait' had returned during the temporary socket-only server, when it returned during initdb, before that server existed" Also: commit messages (git log).

### CQ-384 An append-only record line asserting outcomes the evidence did not show

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.11 (raised in engineering round 1), V0.11 (fixed in round 2)
● **Applies to:** any append-only log or ledger
● **Symptom:** The new V0.10 line in scripts/upload-baseline.txt stated "9 of 10 stages passed", "Deploy not reached" and the console date, which the owner's screenshot text passed to the gate did not show; the file can only be appended to, never edited.
● **Root cause:** Outcome details were written beyond the platform evidence relayed to the gate.
● **Fix:** Round 2 marked "Deploy not reached" as inference from the stage count (10 stages listed where V0.9's 11 included Deploy); the round 2 gate found the line consistent with the relayed screenshot facts and nothing invented.
● **Guard:** Practice: check an append-only line against the evidence before committing and mark anything not shown as inference or `TBC, re-verify`.
● **Lesson:** An append-only record cannot be corrected later, so every field in a new line must be traceable to evidence at the time it is written, with inferences labelled.
● **Evidence:** gate report: Engineering gate on V0.11 hotfix: "The line can only be appended, never edited, so check it before committing." Also: scripts/upload-baseline.txt; gate report: Engineering gate on hotfix round 2.

### CQ-385 An append-only verdict record edited in place during a format change

● **Rule:** none · **Raised by:** other (recorded in the V0.3 audit row) · **Severity:** unknown · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.3 (in e40e12b; recorded in the V0.3 row)
● **Applies to:** any append-only log or review record
● **Symptom:** Changing the review record's format rewrote the two round-4 PASS lines on 4827acb into the new format, against the record's own rule never to edit a verdict line.
● **Root cause:** A format migration was applied to existing lines instead of only to new ones.
● **Fix:** The edit was recorded in the audit row; the record's header keeps the rule to append one line per verdict and never edit or remove one.
● **Guard:** The header of scripts/upload-record.txt states the append-only rule.
● **Lesson:** When an append-only record changes format, leave old lines as written and teach the reader both formats, or record the migration explicitly; never rewrite history silently.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "It also rewrote the two round-4 PASS lines on 4827acb into the new format, against the record's own rule never to edit a verdict line." Also: scripts/upload-record.txt.

### CQ-386 Record steps skipped for a change that needed no version bump, and a verification field left as a placeholder

● **Rule:** none · **Raised by:** security-gate, engineering-gate · **Severity:** minor (V0.6 a nit) · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised by security on 97d90be, fixed in the V0.6 row); V0.11 (raised in both hotfix rounds, filled in record commit 049e162)
● **Applies to:** any project with a per-release audit record
● **Symptom:** V0.6: 97d90be left the upload alone, so CLAUDE.md required a note in the current release's row, and the commit did not touch it. V0.11: the row's Verified-by placeholder stayed open through both hotfix rounds.
● **Root cause:** The record step is easy to skip when no version bump forces a new row, and a row's verification text exists only once the gates have run.
● **Fix:** The V0.6 row records the baseline change and every round; V0.11's record commit fills Verified-by with each round's verdicts and checks.
● **Guard:** Practice: commit the exact gated tree, then a record commit touching only scripts/upload-record.txt and docs/AUDIT-LOG.md.
● **Lesson:** Make the record commit a fixed step after every gated change, bumped or not, and check for placeholders before committing it.
● **Evidence:** gate report: Security gate on 97d90be: "This change leaves the upload alone, so CLAUDE.md requires a note in the current release's row. The commit does not touch that row." Also: gate report: Engineering gate on V0.11 hotfix; session summaries.

### CQ-387 A troubleshooting list of start-up failures missing newly added refusals

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised in engineering round 2), V0.7 (fixed in round 3)
● **Applies to:** any stack with an operator runbook
● **Symptom:** The operator manual's section 10 list of causes Holly names itself left out the 5 new admin-bootstrap refusals, which were documented only in the accounts section.
● **Root cause:** New refusals were documented where the feature lives, not in the troubleshooting index operators read first.
● **Fix:** Round 3 adds a section 10 bullet naming the bootstrap's refusals and pointing to section 08.
● **Guard:** None recorded.
● **Lesson:** Every new start-up refusal belongs in the troubleshooting index as well as the feature's own section.
● **Evidence:** gate report: Engineering gate, V0.7 round 2: "leaves out the 5 bootstrap refusals. Add a bullet that points to section 08." Also: gate report: Engineering gate, V0.7 round 3.

### CQ-388 A failure table written from expected cases rather than the error codes seen live

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** nit · **Status:** open · **Certainty:** mixed
● **Releases:** V0.8 (raised in engineering round 2); still open at V0.13
● **Applies to:** any app with a database dependency
● **Symptom:** Operator manual section 10 does not say that SQLSTATE 28P01 can also mean a missing role (seen live under scram-sha-256), and its list of driver errors leaves out CannotConnectNowError (database starting) and ConnectionError (connection dropped).
● **Root cause:** Inference: the table was written from the codes' documented meanings, not from the live probe results.
● **Fix:** None yet; listed open in the V0.8 row. At HEAD section 10 still gives 28P01 as a wrong password only.
● **Guard:** None recorded.
● **Lesson:** Build troubleshooting tables from the codes actually observed in probes, including ambiguous ones, rather than from the documented meaning alone.
● **Evidence:** gate report: Engineering gate, V0.8 round 2: "28P01 also means a role that does not exist (seen live). The list of types leaves out 'CannotConnectNowError' (database starting or in recovery) and 'ConnectionError' (connection dropped)." Also: docs/runbook/operator-manual.md at f8a00bd.

### CQ-389 A runbook's start sequence out of step with the code's order

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** nit · **Status:** open · **Certainty:** mixed
● **Releases:** V0.8 (raised in engineering rounds 1 and 2); the round 2 wording still open at V0.13
● **Applies to:** any stack with an operator runbook
● **Symptom:** Round 1: section 04 said the settings were validated after describing the database wait, but they are now read first (gunicorn_conf.py:36). Round 2: section 04 says the scan start "skips steps 3 and 4", yet the settings are still read and validated; only the wait, migrations and bootstrap are skipped.
● **Root cause:** Inference: the prose was not re-derived from on_starting's new order after the scan step was added.
● **Fix:** The round 1 order is taken to be covered by the row's "Round 2 closes each" (inference). The "skips steps 3 and 4" wording is listed open in the V0.8 row and still in the manual at HEAD.
● **Guard:** None recorded.
● **Lesson:** Derive a documented start-up sequence from the code's actual call order each time a step is added, and say exactly which steps a special mode skips.
● **Evidence:** gate report: Engineering gate on V0.8 DAST: "Settings are now read at 'src/app/gunicorn_conf.py:36', before the wait. Put the validation sentence first." Also: gate report: Engineering gate, V0.8 round 2; docs/runbook/operator-manual.md at f8a00bd.

### CQ-390 Setup docs claiming a start-up hook runs locally when the development server bypasses it

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (present from round 1, raised in engineering round 3), V0.7 (fixed in round 4)
● **Applies to:** Python apps with separate production and development servers (gunicorn and uvicorn)
● **Symptom:** setup.md said the admin bootstrap works locally too, but only gunicorn's on_starting runs it, and scripts/dev.sh runs `python -m app` (uvicorn), so a developer got no admin and no log line; a setup.md heading was also stale.
● **Root cause:** The bootstrap hangs off a gunicorn hook that the local development path never calls.
● **Fix:** Round 4: setup.md says the local servers never run the bootstrap and points to `python -m app.cli.create_admin`.
● **Guard:** None recorded.
● **Lesson:** When behaviour hangs off a production server hook, check and document whether each local entry point runs it.
● **Evidence:** gate report: Engineering gate, V0.7 round 3: "is false: only gunicorn's on_starting runs the bootstrap (gunicorn_conf.py:32); scripts/dev.sh:23-25 runs python -m app, which is uvicorn (__main__.py:19)" Also: docs/developer/setup.md at f8a00bd.

### CQ-391 A security record that overstated one risk and left out the database role behind another

● **Rule:** none · **Raised by:** security-gate, engineering-gate · **Severity:** nit (the superuser's reach a security minor in round 4) · **Status:** open · **Certainty:** fact
● **Releases:** V0.7 (raised in security round 1 and engineering round 3; fixed in rounds 2 and 4; security round 4 raised the superuser's fuller reach, listed open); still open at V0.13
● **Applies to:** any app using a managed database
● **Symptom:** The new unencrypted-connection row said the database password crosses the network in clear, which is not so under SCRAM or md5 authentication; the queries and results do. Separately, the add-on's DATABASE_URL connects as `postgres`, recorded in the operator manual, but SECURITY.md's row on the application's database user did not say so, which understates its reach if that role is a superuser. Once recorded, the row still said only that a superuser's reach would extend to every database on that server, while a superuser can also delete audit rows past migration 0017's trigger and run programs on the database host.
● **Root cause:** The row inferred the password's exposure from sslmode=disable without knowing the add-on's authentication method, and a console fact, and then what a superuser can do, were not carried fully into the security positions.
● **Fix:** Round 2: queries and results cross in clear, and the password too only if the add-on uses a cleartext method (TBC). Round 4: SECURITY.md records the postgres role, with whether it is a superuser TBC, re-verify. The fuller reach is listed open in the V0.7 row and not in SECURITY.md at HEAD f8a00bd.
● **Guard:** None recorded.
● **Lesson:** State a risk exactly as far as the facts reach, mark the deciding unknown as TBC, and carry every platform fact that bears on privilege, with its consequences, into the security record.
● **Evidence:** gate report: Security gate on V0.7: "With PostgreSQL's SCRAM or md5 authentication it does not; the queries and results do." Also: gate report as received; gate report: Engineering gate, V0.7 round 4; gate report: Security gate, V0.7 round 4; docs/AUDIT-LOG.md, V0.7 row; SECURITY.md at f8a00bd.

### CQ-392 A security record understating what a relaxed-start flag does on a live start

● **Rule:** none · **Raised by:** security-gate · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.8 (raised in security round 1), V0.8 (fixed in round 2)
● **Applies to:** any app with a test or scan mode toggled by environment
● **Symptom:** SECURITY.md said that with real settings the DAST flag would only turn the background pulls off. In the image, the flag with a database and key but no store moved uploads to /tmp, lost on restart, and with no key it started on a throwaway key instead of refusing.
● **Root cause:** The record described the flag with every setting present and not a live start that carries the flag with some settings missing.
● **Fix:** The SECURITY.md row now names both effects: a missing key is filled in instead of refused, and a missing store becomes a temporary one.
● **Guard:** A documentation trip-wire: never set the flag by hand.
● **Lesson:** For any mode switch, document what it does when set by mistake in production, not only in the scenario it was built for.
● **Evidence:** gate report: Security gate on V0.8 DAST: "holds only where a store variable and key are set. Case B moved uploads to '/tmp', lost on restart; case C started with a throwaway key instead of refusing." Also: SECURITY.md.

### CQ-393 A new integrity control shipped without its accepted-position row

● **Rule:** none · **Raised by:** security-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised by security on 97d90be), V0.6 (fixed in the V0.6 tree)
● **Applies to:** any project keeping a security positions record
● **Symptom:** The upload baseline had no SECURITY.md row: anyone who can commit can append a line naming any same-version commit, dangling ones included, and so choose whether an upload reads as unchanged or bumped.
● **Root cause:** The control's limits were not written down when it was added.
● **Fix:** SECURITY.md gains "The upload baseline proves the record, not the handover", with a trip-wire; the review-record row widened to cover the baseline check's commit-graph handling.
● **Guard:** None recorded.
● **Lesson:** Ship each new control with a written statement of what it proves, what it cannot, and the trip-wire that would make it insufficient.
● **Evidence:** gate report: Security gate on 97d90be: "anyone who can commit can append a line naming any same-version commit, including an unreachable one" Also: SECURITY.md.

### CQ-394 A change that crossed a recorded security trip-wire without recording the revisit

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.9 (raised in engineering round 1), V0.9 (fixed in round 2)
● **Applies to:** any project keeping a security positions record
● **Symptom:** SECURITY.md's CORS preflight row says to revisit it if allow_headers changes; V0.9 changed allow_headers to name X-Holly-Token, but neither SECURITY.md nor the audit row recorded the revisit. The position itself still held.
● **Root cause:** Trip-wires live in prose, and nothing prompted a check when a change met one (inference).
● **Fix:** The row now records "Revisited for V0.9": still an explicit list that echoes nothing, pinned by tests/test_app.py; the audit row says it still holds.
● **Guard:** None recorded.
● **Lesson:** When a change touches a setting a security trip-wire names, record the re-review and its conclusion in the security record, even when the position still holds.
● **Evidence:** gate report: Engineering gate on V0.9 round 1: "The preflight row's trip-wire says to revisit it if 'allow_headers' changes. This change does that, but neither SECURITY.md nor the AUDIT row records the revisit." Also: SECURITY.md at 83e9696.

### CQ-395 A threat model silent on what a stolen administrator token can do

● **Rule:** none · **Raised by:** security-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.10 (raised in security round 1), V0.10 (fixed in round 2)
● **Applies to:** any app with role-based administration
● **Symptom:** SECURITY.md and the operator manual's stolen-token section said only that every admin is trusted with every account, without saying an admin token can reset another admin's password, create a new admin that outlives the theft, or demote every other admin with no in-app way back.
● **Root cause:** The account-management feature added powers whose abuse cases were not written into the accepted positions or the incident procedure.
● **Fix:** Round 2 records the hostile admin as out of scope in SECURITY.md and adds the clean-up procedure (review and revert auth.user.create, password_reset and update rows since the theft) to the operator manual.
● **Guard:** None recorded.
● **Lesson:** When a feature adds privileged powers, write down what their abuse looks like and how an operator detects and reverses it.
● **Evidence:** gate report: Security gate on V0.10 round 1: "**[MINOR] What a stolen admin token or hostile admin can do is not stated**" Also: gate report: Security gate on V0.10 round 2.

### CQ-396 Automatic discovery moved a data-handling decision outside the app without a security-record entry

● **Rule:** none · **Raised by:** security-gate · **Severity:** minor · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.11 Comms review (raised), V0.12 (recorded as an accepted gap)
● **Applies to:** any app that ingests from auto-discovered sources
● **Symptom:** SECURITY.md's trip-wire (re-review before a source with a different classification is connected) could be crossed by any Mattermost member adding the bot to a private channel: within one cycle its content was readable by every user and reached the assistant, and unfollowing recalls nothing.
● **Root cause:** Automatic channel discovery changed who decides what data enters the app, and the security record was not updated.
● **Fix:** SECURITY.md records the bot added to a private channel by mistake as an accepted gap with a remedy (switch it off for everyone, audited; the Mattermost admin removes the bot; database deletion TBC), and the operator manual asks for the bot's memberships to be checked before the first deploy.
● **Guard:** The SECURITY.md row and its trip-wire.
● **Lesson:** When automation lets an outside actor decide what data the app ingests, record the mistaken-inclusion case and its remedy before shipping.
● **Evidence:** gate report: Security gate on V0.11 round 1: "Unfollowing recalls nothing, and no documented path removes what was pulled." Also: SECURITY.md.

### CQ-397 A scanner's documented blind spots contradicted by a rule added since

● **Rule:** none · **Raised by:** security-gate · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised in security round 3, deferred), V0.10 (fixed)
● **Applies to:** any project with secret scanning
● **Symptom:** scripts/scan-package.mjs's header still listed a JWT among the shapes the content net cannot see, contradicting SECURITY.md once V0.9 added a JWT rule to the shared hook. It was deferred because the file is part of the packaging the review check compares.
● **Root cause:** The rule was added to the shared hook without updating the consumer's documented blind spots.
● **Fix:** V0.10 changes the comment to a JWT split or wrapped across lines.
● **Guard:** None recorded.
● **Lesson:** When a detection rule is added, update every place that lists what the scanner cannot see, so its stated limits stay accurate.
● **Evidence:** gate report as received: "The header comment still lists "a JWT" as a shape the content net cannot see." Also: docs/AUDIT-LOG.md, V0.10 row.

### CQ-398 An externally visible behaviour change left out of the changelog and settings reference

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised in engineering round 3, deferred), V0.10 (fixed)
● **Applies to:** any web API with CORS clients
● **Symptom:** V0.9 turned off CORS credentials mode, but neither the CHANGELOG nor setup.md's APP_ALLOWED_ORIGINS row said a listed origin no longer gets it, so a client there sending withCredentials would fail its preflight where V0.8 let it through.
● **Root cause:** The late round 3 change to allow_credentials updated the code, tests and SECURITY.md only.
● **Fix:** V0.10 adds a Changed bullet to V0.9's CHANGELOG section and the same clause to setup.md's row.
● **Guard:** None recorded.
● **Lesson:** Any change a client can observe goes in the changelog and the settings reference in the same commit, however late in review it lands.
● **Evidence:** gate report: Engineering gate on V0.9 round 3: "neither records that a listed origin no longer gets credentials mode." Also: CHANGELOG.md.

### CQ-399 A log line documented for its common status only

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** nit · **Status:** open · **Certainty:** fact
● **Releases:** V0.7 (raised in engineering round 4); still open at V0.13
● **Applies to:** any app with structured logs
● **Symptom:** The operator manual says the log names variables still set under accounts_exist, but with an account present and only ADMIN_EMAIL left the status is not_configured, which now also carries variables_still_set.
● **Root cause:** The manual was written before not_configured gained the field.
● **Fix:** None yet; listed open in the V0.7 row. The manual at HEAD still ties `variables_still_set` to accounts_exist.
● **Guard:** None recorded.
● **Lesson:** Document every status a structured log line can carry and which fields each one includes.
● **Evidence:** gate report: Engineering gate, V0.7 round 4: "With an account present and only 'ADMIN_EMAIL' left, the status is 'not_configured', not the 'accounts_exist' that :185 says." Also: docs/AUDIT-LOG.md, V0.7 row; docs/runbook/operator-manual.md at f8a00bd.

### CQ-400 A comment attributing an error to a library that does not raise it

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** nit · **Status:** open · **Certainty:** fact
● **Releases:** V0.7 (raised in engineering round 4); still open at V0.13
● **Applies to:** any stack
● **Symptom:** The unstorable_field comment in create_admin.py says bcrypt names a character that will not encode, but the error comes from Holly's own UTF-8 encode in core/security.py before bcrypt is called.
● **Root cause:** The comment credits the hashing library with an error raised earlier, by Holly's own UTF-8 encode at core/security.py:26.
● **Fix:** None yet; listed open in the V0.7 row, and the comment is unchanged at HEAD f8a00bd.
● **Guard:** None recorded.
● **Lesson:** Trace an error to the line that raises it before naming its source in a comment.
● **Evidence:** gate report: Engineering gate, V0.7 round 4: "is inaccurate. The error comes from Holly's own UTF-8 encode at 'src/app/core/security.py:26'" Also: src/app/cli/create_admin.py at f8a00bd.

### CQ-401 A comment promising a stricter format check than the parser performs

● **Rule:** none · **Raised by:** security-gate · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 (raised in security round 1), V0.7 (fixed in round 2)
● **Applies to:** Python, and any stack using a library date parser
● **Symptom:** The deadline validator's docstring said "ISO 8601 timestamp", but Python's fromisoformat also accepts a bare date and the compact or week forms, which the panel shows as written.
● **Root cause:** The comment described the intent, not the parser's actual acceptance set.
● **Fix:** Round 2 reworded the comment to match Python 3.12's fromisoformat.
● **Guard:** None recorded.
● **Lesson:** Describe a validator by what its parser accepts, checked against the parser's documentation for the runtime version in use.
● **Evidence:** gate report: Security gate on V0.7: "but 'fromisoformat' also accepts a bare date and the compact or week forms" Also: gate report: Engineering gate, V0.7 round 2.

### CQ-402 A comment and an inherited document claimed a limit and a control the code never had

● **Rule:** none · **Raised by:** security-gate (the comment, a nit); the documentation pass after the gate fixes, ad5b332 (the overview) · **Severity:** nit · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.2 (raised in the gate rounds and the documentation pass), V0.2 (fixed in e0d7f34 and ad5b332)
● **Applies to:** any project built from imported or forked code
● **Symptom:** The max_results comment, written in the fusion commit (55ab9f1), promised a cap that a request naming no limit does not get. The security overview, imported with the dashboard and reworded in the fusion, said a source carrying a higher classification must be refused at ingest, which Holly never did.
● **Root cause:** The overview's claim came with the imported documentation and survived the fusion's rewrite, which the fusion commit says checked every fact against the code; the comment described the field's upper bound as a cap on every pull (inference).
● **Fix:** The comment corrected, with UDL's own default page size marked TBC (e0d7f34); the overview claim removed and the documentation set brought in line with the code (ad5b332).
● **Guard:** Practice: each gate round is followed by a documentation pass against the code.
● **Lesson:** Treat inherited documentation as unverified and check each security claim a rewrite keeps against the code; describe a limit by what happens when the caller names none.
● **Evidence:** commit messages (git log): "comment promised a cap that a request naming no limit does not get." Also: src/app/schemas/notification.py at 55ab9f1; docs/security/overview.md at 0717c05.

### CQ-403 A security position overstating caching, and a trip-wire that read as the current setting

● **Rule:** none · **Raised by:** security-gate · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised in security rounds 2 and 3), V0.6 (caching fixed), V0.7 (trip-wire fixed)
● **Applies to:** any web app with a CORS policy
● **Symptom:** The CORS preflight row said the answer "is never cached", but browsers keep it for 600 seconds (Access-Control-Max-Age: 600), and its trip-wire named Starlette changing but not Holly's own CORS settings. Its trip-wire then said "since allow_headers=["*"] makes Starlette echo", which read as the current setting; it is an explicit list.
● **Root cause:** The row was written from HTTP-cache semantics only, and a hypothetical was written in the present tense.
● **Fix:** The row says "kept by no shared cache" and gives the 600 seconds; the trip-wire names allow_headers, allow_origin_regex and max_age; V0.7 rewords it to "would make", noting today it is an explicit list.
● **Guard:** None recorded.
● **Lesson:** In a security record, distinguish shared caches from the browser's own, and write any configuration the code does not use in the conditional so it cannot be read as current.
● **Evidence:** gate report as received: ""is never cached" is true of HTTP caches, but browsers keep the preflight answer for 600 seconds ('Access-Control-Max-Age: 600')." Also: gate report: Security gate, V0.6 round 3; SECURITY.md.

### CQ-404 A legacy protocol signal kept without recording why

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised in engineering round 1), V0.9 (fixed in round 2)
● **Applies to:** any HTTP API
● **Symptom:** After the token moved to X-Holly-Token, the app's 401 still sent `WWW-Authenticate: Bearer` and sign-in still answered token_type bearer, both pointing clients at the Authorization form the app now refuses.
● **Root cause:** Moving the credential header left adjacent protocol signals unexplained.
● **Fix:** Kept on purpose and recorded: the dependencies.py docstring and an ADR-013 consequence say the bare challenge is how an operator tells the app's 401 from the gateway's, and the token type names what the token is, not where it goes.
● **Guard:** Removing the challenge was a killed mutant in round 2.
● **Lesson:** When a deliberate inconsistency stays, record the reason beside the code and in the decision log so the next reviewer does not remove it.
● **Evidence:** gate report: Engineering gate on V0.9 round 1: "Holly's 401 still sends 'WWW-Authenticate: Bearer'" Also: src/app/dependencies.py at 83e9696.

### CQ-405 Architecture text and document stamps not moved with the change

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.9 (raised in engineering round 1), V0.9 (fixed in round 2)
● **Applies to:** any project with versioned documents
● **Symptom:** docs/architecture/overview.md:73 said the client "adds the bearer token to every call" without naming the X-Holly-Token header it now uses, and the operator manual, security overview, architecture overview and training manual were edited without moving their Last updated lines, though the CHANGELOG and decision log were moved.
● **Root cause:** Prose was updated for the behaviour but not the new name, and no check ties a document edit to its stamp.
● **Fix:** The overview names the X-Holly-Token header (ADR-013); each edited document's version and Last updated line moved to 2026-10-20.
● **Guard:** None recorded.
● **Lesson:** When a change renames an interface, update the name wherever the behaviour is described, and move each edited document's stamp in the same commit.
● **Evidence:** docs/architecture/overview.md at 83e9696: "adds the access token to every call in its own 'X-Holly-Token' header (ADR-013)" Also: gate report: Engineering gate on V0.9 round 1.

### CQ-406 Hand-maintained lists of loop steps and document fields drifting when a step is added

● **Rule:** none · **Raised by:** engineering-gate, security-gate (the commits do not say which reviewer raised each item) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised in the reviewers' follow-ups and smoke round 2), V0.3 (fixed in 0c67540 and e13a3d3)
● **Applies to:** any project documenting its CI or verification steps
● **Symptom:** Developer setup lists the verification loop's steps in order, but 65be203 added the local database step without adding it there, and the database images step later needed the same fix; ADR-002's Status line sat out of place and ADR-012 did not list ADR-002 among the records it amends.
● **Root cause:** Steps and document fields are restated by hand in several places.
● **Fix:** 0c67540 lists the local database step; e13a3d3 lists the database images step and fixes the ADR Status line and cross-reference.
● **Guard:** None recorded.
● **Lesson:** Generate a list of verification steps from the script itself, or have the script print it, rather than restating it in prose that drifts.
● **Evidence:** commit messages (git log): "Developer setup lists the verification loop's steps in order, but 65be203"

### CQ-407 Diagnostic and record wording looser than the check it describes

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** nit · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.6 (raised in engineering round 1 on 97d90be), V0.6 (fixed)
● **Applies to:** any project with custom checks and records
● **Symptom:** The baseline check's window heading said "files in the upload differ" but listed D entries no longer in the upload; "zip ff5d3658" in upload-baseline.txt did not say the hex is a SHA-256 prefix; and the operator manual's line format showed `<commit>` without saying it must be the full 40-character id, which the check requires.
● **Root cause:** Inference: headings, shorthand and placeholders were written for the common case and the author's own knowledge.
● **Fix:** The heading, the record's header and the manual reworded; the header states the note names the zip by the first 8 hex digits of its SHA-256.
● **Guard:** None recorded.
● **Lesson:** Write diagnostics and record formats to match exactly what the check accepts and prints, so a later reader needs no context the author had.
● **Evidence:** gate report: Engineering gate on 97d90be: "but the list includes 'D' entries, which are no longer in the upload." Also: docs/AUDIT-LOG.md, V0.6 row.

### CQ-408 Release record generalising a test property that holds for only some tests

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** nit · **Status:** open · **Certainty:** fact
● **Releases:** V0.5 (raised in engineering round 2 as an open follow-up); still in the V0.5 row
● **Applies to:** any project with a release record
● **Symptom:** The V0.5 row says each stale-response test holds an older request open while a newer one answers, then releases it; the gate found that holds for 11 of the 17.
● **Root cause:** A pattern seen in most tests was written as true of all of them.
● **Fix:** None recorded; listed as open below the blocking bar in 56c55a9, and the V0.5 row still carries the claim at HEAD f8a00bd.
● **Guard:** None recorded.
● **Lesson:** Quantify claims about a test suite ("11 of 17") unless every case has been checked.
● **Evidence:** commit messages (git log): "row says each stale-response test releases the older request after the" Also: docs/AUDIT-LOG.md, V0.5 row.

### CQ-409 Overlong comment lines left by rewording, then pushed onto the next line by a partial reflow

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.6 (raised in engineering rounds 1 and 2), V0.6 (fixed in round 3)
● **Applies to:** any stack
● **Symptom:** Round 1: check-baseline.sh:11 (154 characters) and upload-baseline.txt:9 (135) were left unwrapped. Round 2: the reflow moved the overflow to the next line, so the row's "the lines wrapped" overstated it.
● **Root cause:** One line of a paragraph was hand-wrapped instead of reflowing the paragraph; no line-length check covers comments in shell scripts and records (none in scripts/verify.sh at HEAD).
● **Fix:** Both paragraphs reflowed in round 3; the gate confirmed no added comment line over 100 characters.
● **Guard:** None recorded.
● **Lesson:** Reflow the whole paragraph after rewording, and extend the line-length lint to scripts and records if prose width matters.
● **Evidence:** gate report: Engineering gate on V0.6 tree: "the round-1 rewording left these comment lines unwrapped." Also: gate report: Engineering gate, V0.6 round 2; gate report: Engineering gate, V0.6 round 3.

### CQ-410 Hand edits leaving formatting and cross-reference slips that no check catches

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7, V0.8, V0.9 and V0.10 (each raised and fixed in the next round)
● **Applies to:** any project with Markdown documentation
● **Symptom:** V0.7: operator manual section 03 referred the reader to section 03. V0.8: a stray blank line split the appstore-gate-compliance scaffold checklist. V0.9: two blank lines before ADR-013 and one elsewhere. V0.10: a missing comma in the architecture overview.
● **Root cause:** Editing slips in Markdown that no lint covers (the loop at HEAD has no Markdown or link check).
● **Fix:** Each fixed in the next round (the cross-reference points to the "Deployment parameters" table).
● **Guard:** None recorded.
● **Lesson:** A Markdown lint (blank lines, list continuity) and a link check for internal section references would catch these before review.
● **Evidence:** gate report: Engineering gate, V0.7 round 3: "points to its own section" Also: gate report: Engineering gate on V0.8 DAST; gate report: Engineering gate on V0.9 round 1.

### CQ-411 Inherited document markings that did not apply, and a knowable date left unknown

● **Rule:** none · **Raised by:** app-owner (confirmed the markings were mislabelled); other (the date) · **Severity:** unknown · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (fixed in 70f0314 and 201fba0)
● **Applies to:** any project importing documentation
● **Symptom:** 10 documents carried the Daily Operations Dashboard's Commercial in Confidence marking (30 annotations), which the requester confirmed was mislabelled; the decision log marked ADR-012's date TBC, re-verify though the decision was made in the V0.2 fusion on 2026-10-14.
● **Root cause:** A template banner was copied across the imported documentation set, and TBC was used for a fact the history already held.
● **Fix:** All 30 annotations removed, data classification lines kept (70f0314); ADR-012 dated from the change that made it (201fba0).
● **Guard:** None recorded.
● **Lesson:** Re-check protective markings when importing documents into a new product, and use TBC only for facts that cannot be found, not ones the history records.
● **Evidence:** docs/AUDIT-LOG.md, V0.2 row: "70f0314, documentation only, removes the Commercial in Confidence markings, which the requester confirmed were mislabelled." Also: commit messages (git log).

### CQ-412 Real operational records in imported test fixtures

● **Rule:** none · **Raised by:** other (found at import) · **Severity:** unknown · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (fixed at import, 0717c05)
● **Applies to:** any project with data-mapping tests
● **Symptom:** An imported test fixture held what its author described as a trimmed copy of a real UDL notification, with a person's name, record ids, a dissemination marking and a link to an external host.
● **Root cause:** The imported dashboard's tests used live data.
● **Fix:** Values replaced with synthetic ones that keep the record's shape, so the tests assert the same mapping.
● **Guard:** None recorded.
● **Lesson:** Replace real records in fixtures with synthetic values of the same shape before importing or publishing tests.
● **Evidence:** commit messages (git log): "held a record its author described as a trimmed copy of a real UDL"

### CQ-413 Uploaded data products left in the git history after the import

● **Rule:** none · **Raised by:** other (recorded in the V0.2 row) · **Severity:** unknown · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.2 (removed on 2026-10-14, recorded in 77c604f)
● **Applies to:** any git repository
● **Symptom:** The uploaded dashboard zip, holding the NOTSO report and spreadsheet, sat in an early commit although nothing in Holly read it.
● **Root cause:** The source arrived as a zip committed through an upload.
● **Fix:** The upload commit was dropped from the branch history and every later commit recreated with the same tree, author and date; the audit row cites the recreated hashes.
● **Guard:** None recorded.
● **Lesson:** Remove data products from history, not just the tree, and update every record that cites the rewritten hashes.
● **Evidence:** commit messages (git log): "The uploaded Daily Operations Dashboard zip held the NOTSO report and" Also: docs/AUDIT-LOG.md, V0.2 row.

### CQ-414 A reviewer's claim about a document that misread it

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** minor · **Status:** superseded · **Certainty:** mixed
● **Releases:** V0.7 (raised by the deploy gate on 452e3c7, not repeated on the re-run)
● **Applies to:** any project using automated or human review
● **Symptom:** The deploy gate reported that CLAUDE.md line 9 says the detected template is python while the console shows node-react. CLAUDE.md line 9 at that commit says the console shows node-react and lists python only among the possible templates; the re-run recorded the stack as node-react and no change was made.
● **Root cause:** Inference: the gate read the parenthesised list of template options as the claim.
● **Fix:** No change needed.
● **Guard:** None recorded.
● **Lesson:** Check a reviewer's quoted claim against the document's actual text before changing it, and phrase option lists so they cannot be read as the value.
● **Evidence:** gate report: Deploy-gate on V0.7: "'/home/user/Holly/CLAUDE.md' line 9 says the detected template is 'python', but the console shows 'node-react' (operator manual line 88)." Also: CLAUDE.md at 452e3c7; gate report: Deploy-gate re-run on V0.7.

## 2.9 Review process


### CQ-415 A binding platform analyser with no local equivalent let fully gated uploads fail Code Quality

● **Rule:** `typescript:S1994, typescript:S6819, typescript:S2004, typescript:S6557, typescript:S4138, and V0.5's 68 findings` · **Raised by:** App Store Code Quality stage (SonarQube, 0 new issues allowed); app owner · **Severity:** platform-fail · **Status:** open · **Certainty:** mixed
● **Releases:** V0.5 (raised, 68 findings), V0.7, V0.10 and V0.12 (recurred), V0.13 (lint for V0.12's rules and a Sonar way probe; platform outcome not yet recorded)
● **Applies to:** any stack whose deployment pipeline runs SonarQube or another analyser that cannot be run locally; TypeScript and React shown
● **Symptom:** Code Quality failed 4 of the 8 recorded uploads: V0.5 on 68 findings (5 bugs, 2 vulnerabilities, 61 smells), V0.7 on 1 smell (S1994, frontend/src/utils/keys.ts:12), V0.10 on 2 (S6819, Users.tsx:255 and ChangePassword.tsx:101) and V0.12 on 8 (S2004 x6, S6557, S4138). V0.7, V0.10 and V0.12 had each passed both binding review gates and the deploy gate; V0.12 had passed 7 review rounds. At V0.6 and V0.8 the gates judged Sonar compliance by reading the named rules, with no analyser. The owner asked why work reached the deploy gate if the smells could not be anticipated.
● **Root cause:** SonarQube's TypeScript rules were not run locally, and the dashboard's ESLint set held none of the rules V0.12 failed on (fact, V0.13 row). The SonarQube engine, version and quality profile the platform uses are not available in the sandbox, so every gate could only treat the platform as the binding check. The owner's 'leave sonarjs out' at V0.6 kept eslint-plugin-sonarjs out of the project (inference from the context of that message).
● **Fix:** V0.13 fixed the 8 smells in 559a9d0 and, in the same commit, added to frontend/eslint.config.js, using ESLint core and typescript-eslint rather than the sonarjs plugin, a no-restricted-syntax selector for a fifth nested function (S2004), @typescript-eslint/prefer-for-of (S4138) and @typescript-eslint/prefer-string-starts-ends-with (S6557); 32169bf added S7723's missing-new side. On V0.12's code the lint reports exactly the platform's 8 at the same lines. The engineering gate added a Sonar way probe over the change window with V0.12's 8 as a positive control. Still open: S1994 and S6819, which failed V0.7 and V0.10, have no lint rule although the config's header says it holds the rules that failed an upload (fact, eslint.config.js); parity with the platform's profile is inference; V0.13's platform result is not in scripts/upload-baseline.txt.
● **Guard:** The SonarQube block in frontend/eslint.config.js, run by the verification loop's dashboard lint; ruff, strict mypy, complexipy and a pylint duplication proxy on the Python side; the Sonar way probe is a gate practice run from the scratchpad, not a committed script.
● **Lesson:** When a platform stage is binding and cannot be run locally, add every rule it has failed you on to the local lint as soon as it fails, and run a broader profile probe calibrated on a known failure before each upload; reading code against rule names is judgement, not evidence.
● **Evidence:** scripts/upload-baseline.txt: "Code Quality failed it on 68 findings (5 bugs, 2 vulnerabilities, 61 code smells)" Also: gate report: Engineering gate on V0.6 tree; docs/AUDIT-LOG.md, V0.13 row; the app owner's message; frontend/eslint.config.js.

### CQ-416 A local stand-in for a platform check must reproduce the platform's last failure before its clean result counts

● **Rule:** `typescript:S2004 (nesting threshold), typescript:S6557, typescript:S4138; the platform's test-job commands` · **Raised by:** App Store pipeline (test stage, Code Quality stage); SonarQube sweep; engineering-gate · **Severity:** platform-fail · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.4 (test stage), V0.5 (simulation rebuilt from job logs), V0.12 (raised), V0.13 (calibrated)
● **Applies to:** any project that simulates a CI or quality stage locally; SonarJS through ESLint shown
● **Symptom:** V0.4's pipeline simulation was green, yet its upload failed both of the platform's test jobs (pytest not installed, exit 127; npm ci with no root package, EUSAGE). At V0.12 the engineering gate's proxy (eslint-plugin-sonarjs 4.2.2 with every rule on and cognitive complexity 15, plus a few React and jsx-a11y rules) reported 0 new issues in round 2; in round 3 it set aside its only 2 new hits partly because frontend/ was outside sonar.sources=src, although the platform analyses frontend/src; the later rounds' deltas held no frontend source, so the proxy had nothing new to scan. The upload then failed on 8 smells in frontend files.
● **Root cause:** Each proxy was built from assumptions rather than from the platform's own output. V0.4's simulation ran commands other than the platform's jobs, which V0.5 took from the job logs. eslint-plugin-sonarjs 4.2.2 sets S2004's default threshold to 5 where the platform flags at 4, and S6557 and S4138 come from typescript-eslint rules the sonarjs proxy did not include (the gate's own ledger said rules needing type information were missing). The scope argument rested on the project's sonar-project.properties, which the platform's findings show it does not follow for frontend/src.
● **Fix:** V0.5 rebuilt scripts/simulate-pipeline.sh from the job logs and first reproduced V0.4's two failures on dccfbdc. V0.13's sweep and probe set no-nested-functions to 4 and trusted a clean result only after the same run reproduced the platform's 8 V0.12 findings at the same lines on f6951a6, and (in the sweep) V0.10's 2 S6819 findings on f025c2c. The project lint encodes the threshold as a fixed selector, not a plugin default.
● **Guard:** scripts/simulate-pipeline.sh runs both test jobs on a fresh checkout before every upload; the fixed S2004 selector in frontend/eslint.config.js; a positive control against the last failed upload is a gate practice, not a committed check.
● **Lesson:** Treat a local proxy for a platform stage as unproven until it reproduces the platform's last real failure on that commit; pin rule thresholds explicitly instead of trusting plugin defaults, and never infer what the platform analyses from your own configuration.
● **Evidence:** docs/AUDIT-LOG.md, V0.5 row: "Reproduced first: the new two-job simulation on dccfbdc (V0.4) failed both jobs as the platform did" Also: gate report: Engineering gate V0.12; gate report: Engineering gate V0.12 round 2; gate report: Engineering gate V0.12 round 3; gate report: find:sonarjs-scan.

### CQ-417 Fixes made in gate rounds introduced the next finding

● **Rule:** `typescript:S1994, typescript:S7723, python:S1940 (likely), python:S3358 (likely)` · **Raised by:** App Store Code Quality stage; engineering-gate; SonarQube sweep · **Severity:** platform-fail · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.6 to V0.7 (S1994 on upload), V0.12 (rounds 3 and 6), V0.13 (S7723 before upload)
● **Applies to:** any stack with a zero-new-issue quality gate; TypeScript and Python shown
● **Symptom:** V0.6's round 2 fix for a key collision both gates found made frontend/src/utils/keys.ts skip any key already issued with `for (let n = 2; issued.has(key); n++)`; V0.7's upload failed Code Quality on that line (S1994). In V0.12 the security round 2 fix (c2ac5cb) wrote `and not delete_at <= 0`, which engineering round 3 failed as a likely S1940, and the round 5 fix (56d0dbc) added a nested conditional, which round 6 failed as a likely S3358. In V0.13 the S4138 fix (559a9d0) used `Array<number>(n).fill(...)`, which the sweep caught as S7723 before upload.
● **Root cause:** Each fix was new code written under round pressure and checked against the finding it closed, not against the platform's rules; the local loop had no rule for the shapes the fixes introduced (ruff, pylint and complexipy have no S3358 equivalent, per the round 6 gate).
● **Fix:** S1994: a while loop in V0.8 (117346c), keys unchanged. S1940: an explicit NaN test, `delete_at > 0 or math.isnan(delete_at)`, in 8aa5ecc after round 3. S3358: a helper in place of the nested conditional in 6f7dcd0 after round 6. S7723: Array.from in 6085a53 and a lint rule in 32169bf. V0.13 swept its own fix diff before upload.
● **Guard:** S7723 in frontend/eslint.config.js; gates read each round's delta for Sonar-shaped constructs and fail closed on a likely new issue; no local rule for S1994, S1940 or S3358.
● **Lesson:** Treat every gate-round fix as unreviewed new code: run the platform-equivalent rules over the fix diff itself before re-gating, because the fix for one finding is the likeliest source of the next.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "keys skip any key already issued, with the colliding input as a case" Also: the app owner's message; gate report: Engineering gate V0.12 round 6; gate report: find:sonarjs-scan; commit messages (git log).

### CQ-418 Record each upload as the baseline the quality gate scores new code against

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.5 (raised by the deploy gate), V0.6 (fixed in 97d90be and 691f25b)
● **Applies to:** any platform whose quality gate scores changes since the previous submission
● **Symptom:** The deploy gate failed V0.5 on items outside the upload; one MAJOR was that nothing recorded the previous upload (V0.4's, zip ff5d3658 from dccfbdc, merge request 2, failed at the test stage), so the changed-code window SonarQube would score could not be read.
● **Root cause:** The platform scores new code against the previous upload, passed or failed, and writes that boundary nowhere in the repository; the project recorded review verdicts but not handovers.
● **Fix:** scripts/upload-baseline.txt holds one line per upload (commit, version, outcome, zip SHA-256 prefix, merge request, failing stage). scripts/check-baseline.sh, run by packaging for upload, refuses when the record is missing, unreadable or disagrees with its commit, refuses a changed upload without a higher version, and prints the files in the window; the nets' self-test gained 17 cases.
● **Guard:** scripts/check-baseline.sh in scripts/package-appstore.sh; a line appended in the first commit after each handover.
● **Lesson:** If the quality gate measures new code from the last upload rather than from a branch point, record every upload, failed ones included, in the repository and print the window before packaging, so reviewers check exactly what the platform will score.
● **Evidence:** the app owner's message: "no upload baseline record (V0.4's upload, ff5d3658 from dccfbdc, merge request 2, failed at the test stage)" Also: commit messages (git log); scripts/upload-baseline.txt.

### CQ-419 Capture the store's catalogue fields in the repository before submission, or record an explicit waiver

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** BLOCKER · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.5 (raised), V0.7 (BLOCKER, waived), V0.10 and V0.12 (still TBC)
● **Applies to:** any app published through a store or catalogue with console-only metadata
● **Symptom:** The deploy gate failed V0.5 partly because the platform's app record (slug, names, category, visibility, add-ons, resources) was not in the repository, and failed V0.7 (452e3c7) with a BLOCKER because category, display name and visibility were still TBC, re-verify; the gate must block while a required field is undefined. The owner waived the check and entered the fields in the console; the re-run recorded a waiver, not a pass. The V0.10 and V0.12 deploy gates still list the three as TBC, re-verify.
● **Root cause:** Catalogue metadata lives only in the platform console and was never written back to the repository, so a gate could not verify it.
● **Fix:** Slug, service, port, add-ons and resources recorded in operator manual section 03 at V0.7; the owner's waiver for the display fields, which remain TBC, re-verify.
● **Guard:** The deploy gate's app-record check; none for the remaining fields.
● **Lesson:** Write every field the store requires into the repository (with an explicit unknown marker where a value is not yet known) before the first submission, and record a waiver as a waiver, so a later gate can tell an accepted gap from a verified one.
● **Evidence:** gate report: Deploy-gate on V0.7: "[BLOCKER] App record | Category, display name and visibility are 'TBC, re-verify'." Also: gate report: Deploy-gate re-run on V0.7; gate report: Deploy gate for V0.10; docs/AUDIT-LOG.md, V0.12 row.

### CQ-420 Environment limits left gate rounds without run evidence

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** BLOCKER · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.9 (container restart), V0.12 (round 1 no Docker daemon; round 5 disk full), V0.13 (permission refusal)
● **Applies to:** any review run by agents or CI in a shared, resource-limited sandbox
● **Symptom:** In V0.12 round 5 (fc96e56) the sandbox disk filled, so neither reviewer's verification loop ran; engineering recorded a BLOCKER for no verification evidence and both round 5 reports are empty. Later reviewers skipped the container smoke to save disk (4.1 GB free). In V0.12 round 1 the engineering gate had no Docker daemon and relied on the author's smoke PASS. In V0.13 the permission system refused a scratch copy of frontend/, so a finding rested on reading a test instead of a mutation run. In V0.9 a container restart stopped two gates' results from being delivered.
● **Root cause:** Each reviewer cloned the repository (often twice, for mutants) and built images in a shared, size-limited sandbox whose permissions refuse recursive deletes, so clones, images and build cache accumulated across rounds (inference).
● **Fix:** Round 6 reviewers worked in one clone and restored it after mutants; the session pruned its own images and build cache; reviewers took the author's smoke PASS only where the delta did not touch the image and said so; the unrun mutation was marked inference and closed with a test.
● **Guard:** Practice: one clone per reviewer, prune images and build cache, and list every check not run, with the reason and free disk, in the coverage ledger. No committed check.
● **Lesson:** Treat a gate round that could not run its checks as failed, not passed; budget the review environment (disk, permissions, daemons) so each round produces run evidence, and require every reviewer to list what it could not run and why.
● **Evidence:** gate report: Engineering gate V0.12 round 6: "the two-reading rule missed mixed hidden characters (MAJOR), and the disk was full so you had no verification evidence (BLOCKER)" Also: gate report as received; gate report: Engineering gate V0.13 (fast); the app owner's message.

### CQ-421 Gate the exact tree before committing, and have the next round judge the record commit

● **Rule:** none · **Raised by:** app owner; engineering-gate (record commits unjudged) · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised), V0.6 (repeated with 97d90be), V0.3 to V0.13 (practice)
● **Applies to:** any project with binding pre-merge or pre-release review gates
● **Symptom:** Through V0.3 commits were made and then failed by the gates (FAIL verdicts on 7eedb7b and e40e12b). Under the owner's new rule the first V0.3 round judged an uncommitted diff, so no record line could name it. At V0.6, 97d90be (the upload baseline alone) was committed before its gates and both failed it, so its FAIL verdicts name a commit in history. The engineering gate also found that commits recording verdicts went unjudged.
● **Root cause:** Nothing tied a verdict to the bytes reviewed, and review covered code commits but not the commits that recorded their outcome.
● **Fix:** The owner's rule from V0.3: gates run before each commit, and the commit follows only a PASS from both, unchanged. From V0.5 (first at V0.4's round 7) the tree under review is committed in a scratch clone, so the packaging rungs can run on it before the gates and the gates judge a named commit; the same tree is then committed unchanged and the PASS lines name that commit (V0.6's tree was reviewed as 6b285fc, 26e170e and 4d5521f, then committed as 691f25b). Closing PASS lines land in a record commit touching only scripts/upload-record.txt and docs/AUDIT-LOG.md, which the next round judges, its delta starting at the last judged commit.
● **Guard:** scripts/check-reviews.sh refuses packaging unless each reviewer's last verdict is a PASS on a commit at or after the version bump whose upload and packaging are unchanged since.
● **Lesson:** Review a frozen, named tree and commit exactly that tree only after every binding gate passes; keep verdicts in separate record commits, and start the next round's scope at the last judged commit so no commit escapes review.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "From this change on, under the requester's rule, gates run before each commit, and a commit follows only a PASS from both." Also: docs/AUDIT-LOG.md, V0.6 row; docs/AUDIT-LOG.md, V0.5 row; scripts/upload-record.txt.

### CQ-422 A fix one gate requests to a security control needs the security gate again

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.8, V0.12
● **Applies to:** any process with parallel engineering and security review
● **Symptom:** V0.8's DAST fix relaxed start-up refusals under APPSTORE_DAST_SCAN and generated a throwaway signing key; the engineering gate flagged in both rounds that it also needed the security verdict. In V0.12 security passed round 4 at 8aa5ecc, then engineering failed the same commit on a MAJOR in the CLOSED rule (a fail-closed control) that security round 3's fix c00e3d2 had also changed, so the security PASS went stale.
● **Root cause:** Both gates run in parallel on the same commit, and a fix one gate asks for can change a control the other gate owns.
● **Fix:** Security re-ran on every later change to the rule: rounds 5 (fc96e56), 6 (56d0dbc) and 7 (d266102); V0.8's round 2 security PASS on 117346c is recorded beside the engineering PASS.
● **Guard:** scripts/check-reviews.sh needs each gate's last verdict to be a PASS on a commit whose upload is unchanged since; reviewers name security-relevant deltas in their coverage ledger.
● **Lesson:** A PASS covers only the tree it saw; when another gate's fix touches authentication, secrets or a fail-closed control, re-run the security gate on the new commit instead of carrying its earlier verdict forward.
● **Evidence:** gate report: Engineering gate, V0.8 round 2: "This change relaxes start-up under a flag and generates a secret. It needs the 'security-reviewer' round 2 verdict as well as this one before it is done." Also: gate report as received; gate report: Security gate V0.12 round 5.

### CQ-423 Decide whether the platform counts a rule from its profile metadata, not from what earlier uploads did not report

● **Rule:** `typescript:S7723, typescript:S1117, typescript:S4326, typescript:S121; unicorn/consistent-boolean-name and unicorn/no-array-reverse (no SonarQube key)` · **Raised by:** SonarQube sweep (finders and verifiers); engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.13
● **Applies to:** any project inferring a hosted SonarQube profile it cannot see; SonarJS shown
● **Symptom:** Engineering round 1 and two sweep finders judged S7723 at utils/comms.ts:115 and 116 probably inactive or unlikely, because sibling unicorn-derived S77xx rules had hit earlier new code without being reported (3 named by the gate, 6 and 8 in the two finders' counts). The verifiers showed each silence had another cause (S7718 ignores err names, S7781's decorator keeps only regexes reducible to strings, S7727 reports only multi-parameter callbacks, S7755 needs .at, absent under the ES2020 lib, S7764 and S7735 left Sonar way at 13.2), while S7723 has been in Sonar way since SonarJS 11.4. In the other direction the local scan raised S1117, S4326 and S121 on ChannelConversation.tsx and two unicorn rules that are outside Sonar way or have no key.
● **Root cause:** Calibration rested on rule silence alone, without reading each rule's defaultQualityProfiles or its SonarJS decorator; the harness also ran ESLint rules SonarJS can map but Sonar way does not activate. The platform's SonarJS version and profile are not visible.
● **Fix:** Verifiers read the rule metadata in javascript-checks jars (11.4.0 to 14.1.0) and the decorator source, with S2004, S6557 and S4138 as controls that list Sonar way. S7723 was fixed and linted; the refuted lines were left unchanged so the upload did not move again (S1117 renamed anyway, the engineering gate having offered the rename as insurance; toReversed() avoided as ES2023).
● **Guard:** Gate practice: a verify stage for every sweep candidate that confirms the line is new and reads the rule's defaultQualityProfiles and decorator. No committed check.
● **Lesson:** Silence from earlier uploads is weak evidence about a rule; decide whether the platform counts it from the rule's profile metadata and implementation, checked against rules known to have fired.
● **Evidence:** gate report: find:sonarjs-scan: "So S7723 is probably inactive on the platform (inference), but that is not proven." Also: gate report: verify:typescript:S7723@comms.ts:115#0; gate report: verify:typescript:S1117@ChannelConversation.tsx:125#2.

### CQ-424 A test that names a guard is not evidence until removing the guard turns it red

● **Rule:** none · **Raised by:** engineering-gate; security-gate · **Severity:** MAJOR · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3, V0.5, V0.6 and V0.12 (raised); V0.7 to V0.13 (practice)
● **Applies to:** any stack; security controls and verification scripts in particular
● **Symptom:** V0.3: 4 packaging guards could be deleted with the self-test green, so the claim that removing any guard turns the cases red was wrong; later, 11 of 48 single-guard mutants were killed only through the refusal's wording. V0.5: 4 tests named for a stale-response guard still passed with it removed. V0.6: 5 baseline-check guards turned red only through wording. V0.12 round 3: dropping combining and enclosing marks from the CLOSED rule left all 76 tests green.
● **Root cause:** Tests were written to the guard's name and expected message rather than its effect, and claims of coverage were made without mutating each guard.
● **Fix:** Each new guard is removed alone and its test shown red; a mutant killed only through wording is recorded with what refuses in its place; V0.5's guard battery went from 2 of 17 to 17 of 17 killed; gates re-run the previous round's named mutants; scripts/mutation-battery.mjs proves the contrast check and licence plugin self-tests.
● **Guard:** scripts/mutation-battery.mjs (run by CI); per-round mutation tables in gate reports and audit rows.
● **Lesson:** Prove each guard by deleting it and watching a test fail for the right reason; a mutant killed only by a changed error message means the test pins wording, not behaviour.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "four guards could be deleted with the self-test green" Also: docs/AUDIT-LOG.md, V0.5 row; docs/AUDIT-LOG.md, V0.6 row; gate report as received.

### CQ-425 Large ungated batches move every finding into one long gate run

● **Rule:** none · **Raised by:** app owner (decision) · **Severity:** unknown · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.12
● **Applies to:** any project that defers review to save time or cost
● **Symptom:** To save tokens the owner asked for changes without gates until they said so; the Comms work, its round 2 fixes, an assistant note and the in-app manuals were committed as 4 commits marked 'ungated, not for upload' (62ba4aa, 0a60d93, 1e29a06, cf5a234). Once gated, the release took 7 rounds and the upload still failed Code Quality; git blame at f6951a6 places the 8 flagged lines in 62ba4aa, 0a60d93, cf5a234 and round 1's fix f6056cd.
● **Root cause:** The batch reached review only when complete, so every defect class surfaced at once and was fixed under round pressure, with no local rule for the platform's TypeScript smells in between (inference).
● **Fix:** Accepted as the owner's choice; packaging refuses until both gates record a PASS, so no ungated commit could be uploaded.
● **Guard:** scripts/check-reviews.sh
● **Lesson:** If review is deferred for cost, keep the cheap deterministic checks, including a lint that mirrors the platform's rules, running on every ungated commit, and make packaging refuse ungated work, so the deferred gate starts from a clean base.
● **Evidence:** session summaries: "I do not want any gates run on these until I say so. I cannot afford the tokens for it just yet." Also: commit subjects (git log); docs/AUDIT-LOG.md, V0.12 row.

### CQ-426 Requests to package before review, or to narrow review to the diff, trade depth for speed

● **Rule:** none · **Raised by:** app owner · **Severity:** unknown · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.8, V0.13
● **Applies to:** any team under release pressure
● **Symptom:** After V0.7's failed upload the owner asked for the S1994 fix as a zip before the engineering, security and deploy gates; a rehearsal of that fix alone went first, and the first gate runs on it (agents 019 and 020) left no verdict, the DAST failure arriving minutes later and widening the change (the later rehearsal 8717fed4 was of the combined DAST and S1994 tree, 47ca13b). After V0.12's failure the owner asked for 'uber fast' gates; V0.13 round 1 judged the diff only, and the engineering gate did not re-run the verification loop, as instructed.
● **Root cause:** Pressure after a failed upload; at V0.8 only one of the upload's two failures was known when the request was made.
● **Fix:** Rehearsal zips are packaged outside the upload path without the review check; the real upload still waited for both gates' PASS and the deploy gate. V0.13's diff-only scope was compensated by a SonarQube sweep of the diff with a second reviewer per candidate, and a round 2, also fast-scoped, whose Sonar way probe covered the whole window f6951a6..32169bf with V0.12's 8 smells as a control.
● **Guard:** scripts/package-appstore.sh refuses an upload unless scripts/check-reviews.sh finds each gate's PASS; rehearsals go to separate files.
● **Lesson:** Give an urgent requester a rehearsal artefact if they need one, but keep the upload itself behind the full gates, and when a review is narrowed for speed add a targeted check for the stage that failed last.
● **Evidence:** the app owner's message: "I cannot wait for the full engineering or security gates to complete, put a fix in place which is in keeping with all our knowledge so far on this application, give me a zip of the app first, then ..." Also: docs/AUDIT-LOG.md, V0.8 row; docs/AUDIT-LOG.md, V0.13 row; gate report: Engineering gate V0.13 round 2.

### CQ-427 Confirm the platform's backup, shell and data-retention facilities before relying on them for rollback or recovery

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** minor · **Status:** open · **Certainty:** mixed
● **Releases:** V0.7 (raised), V0.10, V0.11, V0.12 and V0.13 (repeated)
● **Applies to:** any containerised app on a managed platform with database add-ons
● **Symptom:** From V0.7 the deploy gate recorded as TBC whether removing the app deletes the add-ons' data, how backups work, how to stop the app and whether the container offers a shell. Resetting an admin (python -m app.cli.create_admin) and verifying the audit chain need a shell; at V0.10 the owner chose an in-app Users page, the only other way to add users being that shell command. From V0.10, whose migration 0018 an older image cannot run on once applied, a rollback needs a downgrade run inside the container (a shell, TBC) or a database restore that depends on platform backups (TBC); V0.13's row adds an add-on snapshot, and V0.13 is the first release to apply migration 0019 in production.
● **Root cause:** Platform lifecycle facts were never supplied to the team, and recovery tools were built as CLI commands on the assumption of shell access (inference); migrations only move forward at start and an older image refuses a newer schema.
● **Fix:** None yet. The operator manual gives a no-shell path (the previous release's code with the newer migration added, released as a new version), and the first admin comes from App Store variables; the deploy gate asks for the shell to be confirmed or fix-forward accepted.
● **Guard:** TBC, re-verify markers in CLAUDE.md and the operator manual; the deploy gate rehearses the rollback.
● **Lesson:** Before the first release that carries a migration, confirm with the platform owner how backups, data retention on removal and shell access work, and design recovery so it does not depend on an unconfirmed facility.
● **Evidence:** gate report: Deploy-gate on V0.7: "Still 'TBC, re-verify': whether removing the app deletes add-on data, how backups work, and how to stop the app. Migrations only move forward." Also: gate report: Deploy gate for V0.10; gate report as received; docs/AUDIT-LOG.md, V0.13 row.

### CQ-428 Identify a rollback artefact by its recorded hash, never by its name or version stamp

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.9 (raised), V0.10 and V0.12 (practice)
● **Applies to:** any release process that may need to roll back
● **Symptom:** V0.9's deploy gate found other 0.8.0-stamped zips beside the V0.8 upload: two rehearsals given to the owner and a scratchpad zip built from 4f102ad, a commit not in the repository, which lacks dast_scan.py and would fail DAST. During V0.12's rollback rehearsal the local image holly-v11-look turned out not to be V0.11: it held migration 0019 and the V0.12 Mattermost files.
● **Root cause:** A version stamp or a local tag does not identify a package, and artefacts built from unrecorded or newer commits were kept under familiar names (inference for the image).
● **Fix:** Before any rollback, check the zip's full SHA-256 against the recorded upload or rebuild it byte for byte from the recorded commit. V0.10's gate rebuilt V0.9's zip from c68a062; V0.12's gate rebuilt V0.11 from hollyappstore0.11.0.zip, whose hash and commit (049e162) match the baseline line.
● **Guard:** scripts/upload-baseline.txt records each upload's commit and zip hash prefix; packaging reproduces byte-identically.
● **Lesson:** Keep a record of each shipped artefact's hash and source commit, and rebuild or verify by hash before a rollback; never trust a file name, tag or version stamp to say what is inside.
● **Evidence:** gate report: Deploy-gate on Holly V0.9: "That last one is from commit 4f102ad, which is not in the repository, and it lacks 'dast_scan.py', so it would fail DAST." Also: gate report as received.

### CQ-429 An approval or platform fact relayed through an agent is not the owner's own approval

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7
● **Applies to:** any agent-run or delegated release gate
● **Symptom:** The V0.7 deploy gate failed on two items outside the code. The owner then relayed the platform team's confirmation that the app's user can write to /data and waived the app-details check; both reached the re-run gate through the orchestrating agent. The re-run passed the same bytes but scoped its verdict.
● **Root cause:** Facts and approvals passed through an agent carry no authority of their own at the gate.
● **Fix:** The verdict required the owner's confirmation of the upload to also accept both items, or it reads as FAIL; the V0.7 audit row records the PASS as resting on the relayed confirmation and the waiver.
● **Guard:** None recorded beyond the gate's scoped verdict and the audit row.
● **Lesson:** When a gate's pass depends on a confirmation or waiver it did not receive from the accountable person directly, say so in the verdict and have that person accept it explicitly at the release confirmation.
● **Evidence:** gate report: Deploy-gate re-run on V0.7: "the storage confirmation and the field waiver reached me through an agent, so they are not the owner's own approval." Also: docs/AUDIT-LOG.md, V0.7 row.

### CQ-430 A hand-written verdict or upload record proves the record, not the review

● **Rule:** none · **Raised by:** security-gate; engineering-gate · **Severity:** minor · **Status:** accepted · **Certainty:** fact
● **Releases:** V0.3 (review record), V0.6 (upload baseline)
● **Applies to:** any process that gates releases on a record of review verdicts
● **Symptom:** Packaging refuses without PASS verdicts in scripts/upload-record.txt, but a hand-written line is indistinguishable from a gate's, and e40e12b itself rewrote the two round-4 PASS lines on 4827acb into a new format, against the record's rule never to edit a verdict line. At V0.6 the round 1 gates found no SECURITY.md row for the baseline record, which anyone who can commit can point at any commit of the same version, a dangling one included.
● **Root cause:** Verdict and upload lines are unsigned text checked by scripts run by the same person who packages.
● **Fix:** Accepted and recorded in SECURITY.md with trip-wires; the e40e12b edit was recorded openly in the V0.3 row; the baseline header states that a dangling commit counts.
● **Guard:** SECURITY.md trip-wires: gates write their own lines under an identity the packager checks (such as a signed commit) before anyone else packages or packaging moves to CI; the baseline line to carry the zip's full SHA-256.
● **Lesson:** A committed checklist of gate verdicts makes outcomes checkable but not trustworthy; until verdicts are signed by the gate's own identity, treat the record as a convenience and keep the human release confirmation as the control.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "It also rewrote the two round-4 PASS lines on 4827acb into the new format, against the record's own rule never to edit a verdict line." Also: SECURITY.md.

### CQ-431 Bound each gate round by what blocks, and record the rest as follow-ups

● **Rule:** none · **Raised by:** engineering-gate; security-gate; SonarQube sweep · **Severity:** unknown · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.6 to V0.13
● **Applies to:** any gated release process
● **Symptom:** Every round's fixes were new code that could draw a new finding (see the fix-chain entry). Rows from V0.6 list items 'open below the gates' blocking bar'; V0.12 left round 6's optional items untaken; in V0.13 a verifier advised leaving a refuted line unchanged so the upload would not move again, and lint gaps outside the code the platform scores were deferred.
● **Root cause:** Without a stated bar, any finding can reopen the upload and restart the cycle of gate rounds and platform scoring (inference).
● **Fix:** Gates ranked findings, and PASS verdicts carried minors and nits (V0.13 round 1 passed with 5 minors); items below the blocking bar went into the release row for a follow-up. The baseline's resource-discipline skill, present since the baseline was rehydrated (de5ba6e, 13 October 2026, just before the scaffold), asks which pipeline stage a finding would fail before a round is opened.
● **Guard:** The audit row's open items; .claude/skills/resource-discipline/SKILL.md.
● **Lesson:** Before reopening a reviewed artefact, name the stage the finding would fail; if none, record it as a follow-up rather than change the upload, since each change is new code that can carry the next finding.
● **Evidence:** docs/AUDIT-LOG.md, V0.6 row: "Open below the gates' blocking bar, for a follow-up" Also: docs/AUDIT-LOG.md, V0.12 row; gate report: verify:typescript:S4326@ChannelConversation.tsx:133#3; de5ba6e:.claude/skills/resource-discipline/SKILL.md.

### CQ-432 Re-uploading an older release is scored against the newer upload's quality window

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** minor · **Status:** accepted · **Certainty:** mixed
● **Releases:** V0.10
● **Applies to:** any platform that scores submissions against the previous one
● **Symptom:** The V0.10 deploy gate noted that a V0.9 rollback upload after V0.10 would have its Code Quality window measured against V0.10; V0.9 passed against V0.8, never against V0.10.
● **Root cause:** The platform's new-code window opens at the last upload, whatever its version.
● **Fix:** Noted only; the risk was judged low by inference.
● **Guard:** scripts/upload-baseline.txt shows the window for any candidate upload.
● **Lesson:** A rollback by re-upload is a new submission to every gate; check it against the current window rather than assuming an earlier pass carries over.
● **Evidence:** gate report: Deploy gate for V0.10: "A V0.9 upload after V0.10 would have its Code Quality window measured against V0.10. It passed against V0.8, never against V0.10; by inference the risk is low." Also: scripts/upload-baseline.txt.

### CQ-433 Mark each claim in records as fact or inference

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7 to V0.11
● **Applies to:** any project records, change logs and runbooks
● **Symptom:** Gates repeatedly failed or flagged inference written as fact: V0.7 round 1 found the detected stack's cause stated as fact; V0.7 round 3 found a module stating as fact that the App Store offers no shell, and CLAUDE.md dropping that open item; V0.11 round 1 found the baseline note's 'Deploy not reached', which the screenshot did not show.
● **Root cause:** Plausible explanations were recorded without their evidence level.
● **Fix:** Each round corrected fact claims first, marked unknowns TBC, re-verify and labelled inferences; audit rows and the upload baseline now say 'Fact from ...' or '(inference)'.
● **Guard:** Practice in every audit row and gate report; reviewers check claims against the evidence.
● **Lesson:** Label every statement in a record as fact (with its source) or inference, and mark unknowns explicitly; reviewers should fail a confident claim the evidence does not support.
● **Evidence:** docs/AUDIT-LOG.md, V0.7 row: "the stack's cause stated as fact" Also: docs/AUDIT-LOG.md, V0.11 row.

### CQ-434 Release records claimed closures that did not fully hold

● **Rule:** none · **Raised by:** engineering-gate; security-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.7, V0.8
● **Applies to:** any audit log or change record
● **Symptom:** V0.7's row said round 3's 'not read' wording was fixed, but it survived in setup.md, SECURITY.md and a test comment. V0.8's row said round 2 'closes each', but a test still left a temporary directory per run and 4 of the 5 blank-as-unset names were untested.
● **Root cause:** Closures were written from the intended change, not re-checked against every place it touches.
● **Fix:** Each row states which closures overstate and carries the remainder as open items.
● **Guard:** Practice: the next gate round re-reads the row against the tree.
● **Lesson:** Write a closure only after re-checking every place the finding touched; have the next reviewer verify each claimed closure rather than the change alone.
● **Evidence:** gate report: Engineering gate, V0.7 round 4: "Every round 3 closure the audit row names holds in code, with one exception" Also: gate report: Engineering gate, V0.8 round 2; docs/AUDIT-LOG.md, V0.8 row.

### CQ-435 Each local check must say what it cannot see, and a green loop claims only necessary conditions

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** nit · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3 (raised), later (practice)
● **Applies to:** any verification script or CI job that stands in for a stronger check
● **Symptom:** A V0.3 loop step checked the PostgreSQL health check as text but did not say what it could not see, so the CHANGELOG claimed more than it checked.
● **Root cause:** A clean result from a text-matching step reads as proof of the property.
● **Fix:** Text-matching loop steps print what they read and what they cannot see (5 of the 15 steps in scripts/verify.sh carry a 'Cannot see' line at HEAD), and the loop's header and final PASS line say green means only that the necessary conditions are met and the App Store pipeline is the binding check.
● **Guard:** scripts/verify.sh: the 'Reads:' and 'Cannot see:' lines on its text-matching steps and its final 'VERIFY: PASS (necessary conditions met; ...)' line.
● **Lesson:** State each check's blind spots next to its result, and describe a passing local loop as necessary conditions met, not as the platform's verdict.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "the step did not say what it cannot see, so the CHANGELOG claimed more than it checks" Also: scripts/verify.sh; f8a00bd:scripts/verify.sh.

### CQ-436 Reviewers must write nothing in the repository they review

● **Rule:** none · **Raised by:** other (main session); engineering-gate (self-reported) · **Severity:** minor · **Status:** open · **Certainty:** mixed
● **Releases:** V0.6 to V0.8 work (probe file; inference from the summary that covers that work), V0.10 (git object)
● **Applies to:** any agent or CI reviewer with file-system access
● **Symptom:** A gate subagent left tests/test_er_probe.py in the repository; after that, gates were told not to write under /home/user/Holly. In V0.10 the round 2 engineering gate still ran git write-tree there, writing one unreferenced loose object; no ref, index or working tree changed.
● **Root cause:** Reviewers ran probes in the working repository, and git write-tree writes a tree object even when used only to read a tree hash.
● **Fix:** The probe file was removed and every gate brief forbids writes under the repository; the loose object was left (git prune removes it).
● **Guard:** The gate brief's instruction; reviewers report git status before and after. No technical guard.
● **Lesson:** Run reviewers in their own clones or read-only checkouts, and prefer read-only commands (git rev-parse HEAD^{tree}) over ones that write objects; a reviewer that changes what it reviews undermines its own verdict.
● **Evidence:** session summaries: "A gate subagent left 'tests/test_er_probe.py'. I removed it, and gates are now told not to write under /home/user/Holly." Also: gate report: Engineering gate on V0.10 round 2.

### CQ-437 Gate runs left Docker volumes, images and scratch installs behind, and shared one scratch directory

● **Rule:** none · **Raised by:** deploy-gate; app owner; SonarQube sweep · **Severity:** minor · **Status:** open · **Certainty:** fact
● **Releases:** V0.10, V0.12, V0.13
● **Applies to:** any multi-agent or CI review that builds images or installs tools
● **Symptom:** V0.10's gate probes left 6 dangling Docker volumes because the gate's docker volume rm was denied. V0.12's deploy gate could not delete about 315 MB of scratch clones. V0.13's deploy gate found 5 old images and an exited container from earlier runs and left them, not being their creator. During the V0.13 sweep one finder overwrote another agent's package.json in a shared scratchpad/lint/ directory, and several could not remove their tool installs.
● **Root cause:** Probe containers and installs ran without clean-up, concurrent agents had no per-agent scratch directory, and the permission system refuses rm -rf and some docker removals.
● **Fix:** The owner had the 6 volumes removed; the overwritten package.json was restored from its lockfile; gates prune their own images and build cache. The V0.13 leftovers were left for the owner to remove.
● **Guard:** None recorded.
● **Lesson:** Give each review agent its own scratch directory and named resources, and have it remove what it created before reporting; a shared environment collects state no later agent will claim.
● **Evidence:** session summaries: "Six dangling Docker volumes left by the V0.10 gates' probes are still there, because the gate's docker volume rm was denied by permissions." Also: gate report: Deploy gate V0.13 (fast); gate report: find:maintainability.

### CQ-438 A hotfix that takes the next version number forces renumbering of in-flight work

● **Rule:** none · **Raised by:** other (merge conflict) · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.11 to V0.12
● **Applies to:** any project with parallel release streams
● **Symptom:** The Comms work was built and gated as V0.11 (round 1 FAIL). When the owner chose to release the S6819 fix alone as V0.11, porting Comms onto it left docs/AUDIT-LOG.md conflicted between two V0.11 rows, and the Comms docs (ADR-015, SECURITY.md, setup.md, operator manual, CHANGELOG, training manual) all said V0.11. One sentence in the V0.12 row still reads 'The version stamp moves to V0.11' and names a rollback to V0.10.
● **Root cause:** The version number was fixed when the work began, before the release order was known.
● **Fix:** Comms renumbered V0.12: both audit rows kept, the Comms row renamed and placed above the hotfix row, doc references moved to V0.12, the rollback text made V0.12 to V0.11 (0019 to 0018). The residual sentence is still in docs/AUDIT-LOG.md at HEAD (f8a00bd) and was not raised by any gate in the sources (inference that it is a renumbering leftover).
● **Guard:** None recorded; tests/test_version.py holds only the version fields equal.
● **Lesson:** Assign a release number when the release order is fixed, not when work starts, or keep in-flight records version-neutral until then; after renumbering, search every record for the old number.
● **Evidence:** docs/AUDIT-LOG.md, V0.11 row: "The owner chose a fix released on its own, ahead of the Comms change, which follows as V0.12." Also: session summaries; docs/AUDIT-LOG.md, V0.12 row.

### CQ-439 Stage a relocked lockfile before running a loop that compares it with the index

● **Rule:** none · **Raised by:** verification-loop · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3, V0.6 to V0.8, V0.9 to V0.11
● **Applies to:** Node projects using npm ci with a lockfile drift check
● **Symptom:** V0.3's first loop run, with the version bump not staged, stopped at the check that npm ci leaves the lockfile as the index holds it, since the index still held 0.2.0. The same stop recurred later, once after a git reset emptied the index.
● **Root cause:** The loop runs git diff with its exit-code option on the lockfile after npm ci, comparing it with git's index rather than the working tree.
● **Fix:** Stage the bumped or relocked lockfiles before running the loop.
● **Guard:** scripts/verify.sh: 'npm ci changed package-lock.json' check.
● **Lesson:** When a check compares against git's index to catch an unlocked change, stage intended lockfile changes first; the false stop is the check working.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "A first run, with the change not yet staged, stopped at the check that 'npm ci' leaves the lockfile as the index holds it, since the index still held 0.2.0." Also: session summaries.

### CQ-440 Fold each new platform failure class back into the shared baseline

● **Rule:** none · **Raised by:** app owner · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.8, V0.9
● **Applies to:** any team sharing a baseline across apps on one platform
● **Symptom:** V0.7's DAST no_report failure (no answer on 8080 within 300 seconds, the scan giving the container none of its settings) was a failure class the inherited baseline did not describe; the owner asked whether the baseline needed changing. V0.8's live gateway 401 ('Signed JWT rejected' with an empty body) was one the baseline's existing gateway-401 guidance routed to the platform team, never to a code change, where here the app's own bearer token in Authorization was the cause.
● **Root cause:** The baseline skills predated the DAST stage and had not met a gateway refusing the app's own token (inference).
● **Fix:** 117346c added Failure 18 (DAST scan start with no settings) and a scaffold check to appstore-gate-compliance and the DAST stage to app-store-deployment; 83e9696 added the 'Signed JWT rejected' exception to app-store-deployment's 401 guidance.
● **Guard:** The scaffold checklist line that the built image serves 200 on 8080 with only APPSTORE_DAST_SCAN=true; the smoke rung runs the image that way.
● **Lesson:** When the platform fails you in a new way, record the failure, its tell and the fix in the shared skills in the same change, so the next project starts gate-compliant.
● **Evidence:** the app owner's message: "check this out and see if there is anything we need to change in the baseline" Also: .claude baseline commits; 117346c:.claude/skills/appstore-gate-compliance/SKILL.md; commit messages (git log); 83e9696:.claude/skills/app-store-deployment/SKILL.md.

### CQ-441 Keep volatile facts out of agent instruction files, and change those files only with the owner's approval

● **Rule:** none · **Raised by:** engineering-gate · **Severity:** minor · **Status:** resolved · **Certainty:** fact
● **Releases:** V0.3
● **Applies to:** any project using agent instruction files such as CLAUDE.md
● **Symptom:** Reviewers raised CLAUDE.md's stale release stamp each round; the fix waited for the requester, since CLAUDE.md is not edited on a reviewer's word alone. Once fixed, the engineering gate noted that naming the release would raise the item again at every bump.
● **Root cause:** CLAUDE.md restated a value (the current version) whose source of truth lives elsewhere.
● **Fix:** d1f477a named V0.3 with the requester's approval; 092cf83, at the requester's request, made CLAUDE.md point at __version__ and the test that holds the other copies equal.
● **Guard:** tests/test_version.py holds pyproject.toml, frontend/package.json and frontend/package-lock.json equal to __version__.
● **Lesson:** Point agent instruction files at the source of truth instead of restating values that change, and route any change to them through the owner, not a reviewer.
● **Evidence:** docs/AUDIT-LOG.md, V0.3 row: "since CLAUDE.md is not edited on a reviewer's word alone"

### CQ-442 A formatter re-indented a whole component, breaking the surgical-edit rule

● **Rule:** none · **Raised by:** other (self-review) · **Severity:** nit · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.10
● **Applies to:** React and TypeScript with Prettier; any language with an auto-formatter
● **Symptom:** Wrapping Layout.tsx's existing JSX in the timers provider, now left out while a password change is due, made Prettier re-indent Layout.tsx, giving a non-surgical diff.
● **Root cause:** Wrapping existing JSX in a new element changes the indentation of everything inside it (inference).
● **Fix:** The change was rebuilt with a small Timers wrapper component (15 lines added, 4 removed in af13871's Layout.tsx diff), leaving the existing JSX at its indentation.
● **Guard:** CLAUDE.md surgical-edits rule; reviewed by eye.
● **Lesson:** When a formatter would re-indent untouched code, restructure the change (a wrapper component or helper) so the diff shows only what changed.
● **Evidence:** session summaries: "● **Non-surgical diff.** Prettier re-indented 'Layout.tsx'; I rebuilt the change with a 'Timers' wrapper (15 lines added, 4 removed)." Also: af13871:frontend/src/components/Layout.tsx.

### CQ-443 Editing tools wrote invisible control characters literally into test source

● **Rule:** none · **Raised by:** verification-loop (ruff); other (self-review) · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** The V0.6 to V0.8 work (V0.7 by inference), and the V0.9 to V0.11 work
● **Applies to:** any language; Python tests shown
● **Symptom:** A bidirectional override (U+202E) for a test was written as the literal character instead of an escape: once it tripped ruff, and later the Write tool decoded the escape again.
● **Root cause:** The editing tool decodes escape sequences when writing a file (fact for the second case; the first case's cause is not recorded).
● **Fix:** Replaced with the ‮ escape (via Python the second time); the tests hold the escape form at HEAD, for example tests/test_admin_bootstrap.py and tests/test_mattermost_channels.py, and no literal U+202E remains in tests, src or frontend/src.
● **Guard:** ruff, which the loop runs with the PL rules selected, flagged the literal character once (fact); no specific guard recorded for TypeScript.
● **Lesson:** Write invisible or bidirectional characters in source only as escapes, and keep a linter rule that rejects them literally.
● **Evidence:** session summaries: "A literal U+202E in a test tripped ruff; I replaced it with the escape '‮'." Also: f8a00bd:tests/test_admin_bootstrap.py.

### CQ-444 Submit each release as a new version of the existing app record, never under a new name

● **Rule:** none · **Raised by:** deploy-gate · **Severity:** minor · **Status:** resolved · **Certainty:** mixed
● **Releases:** V0.7 (raised by the deploy-gate re-run on 452e3c7; V0.7 went up as merge request 3)
● **Applies to:** any app store or platform with per-app add-ons
● **Symptom:** Holly's app record already existed, yet the owner described an 'Upload New App' form; the gate could not see whether that form adds a version to the existing app or creates a second one.
● **Root cause:** The platform console's update path was not recorded, and a new slug would move the app's address and orphan its add-ons.
● **Fix:** The gate told the owner to submit 0.7.0 to the existing holly app and to stop if the form refused the slug or offered a second app; V0.7 went up as merge request 3, and later deploy gates validate the app name against the existing Active record.
● **Guard:** the deploy-gate's submission validation of the app name against the existing record
● **Lesson:** Before each upload, confirm in the platform's console that the submission updates the existing app record, and stop if it would create a new one: a new name moves the address and strands data held by add-ons.
● **Evidence:** gate report: Deploy-gate re-run on V0.7: "The gate cannot see whether that form adds a version to the existing app or creates a new one." Also: scripts/upload-baseline.txt; gate report: Deploy gate V0.12.

# Part 3. Open, accepted and deferred items

What Holly still carries. An application that adopts these lessons should check whether it carries the same.


## Open

● CQ-001 Platform static analysis not mirrored locally, so a zero-new-issue quality gate fails uploads that passed every local check
● CQ-025 Deprecated API or value in use
● CQ-041 Unknown whether the quality gate counts test files as changed code, and hotspots in tests the owner cannot clear
● CQ-088 Upload nets do not refuse package-manager override files
● CQ-089 Two readers of the same environment flag must match names the same way
● CQ-090 A secret-strength check must count content, not raw length
● CQ-091 Validate a server-supplied error code before logging it
● CQ-092 Unhandled connect errors can echo a malformed connection-string option in a traceback
● CQ-093 Trust forwarded client addresses only from known proxies, or per-client limits key on the proxy
● CQ-094 Enforce an append-only audit table in a migration, and know what the database role can bypass
● CQ-137 Decide 'date only' with the parser, not a string-length proxy
● CQ-138 Align an LLM prompt's output instruction with the validator that checks it
● CQ-147 Re-check the current selection after every await before applying an async answer
● CQ-206 A client-side validation message outlives the input it complained about
● CQ-208 No local test rung modelled the platform's ingress gateway, so an auth failure seen only in production passed every check
● CQ-236 Defence-in-depth security guards were never reached by a test, so mutation removed them with the suite green
● CQ-263 Tests left temporary directories behind on the host
● CQ-278 No negative test proves an error message omits the database driver's text
● CQ-279 A validator covering several fields was pinned for one, and the record overstated the closure
● CQ-280 A page's interval poll still has no unmount test
● CQ-281 A fixture's incidental order matched the order under test
● CQ-282 An assertion held whether or not the code under test ran
● CQ-283 Retry deadline and error-class boundary constants were not pinned
● CQ-284 A blank-value test used only one kind of whitespace
● CQ-285 The blank optional argument was not tested separately from the padded one
● CQ-286 An integration was verified only against stand-ins for the upstream API
● CQ-288 A defensive nullish fallback branch is never taken
● CQ-289 Shell checks were not linted and their portability was proven on one awk and one git
● CQ-291 Edge cases in quick check-script parsers were left open
● CQ-293 A static contrast checker's known limits were left open
● CQ-321 Confirm what the platform's generated test jobs run and how its quality gate reads each coverage report
● CQ-322 SonarQube scope keys left from a scaffold template no longer describe the analysed code
● CQ-329 Upload nets should refuse package-manager configuration files that change how the platform installs
● CQ-354 Local runtime older than the engines floor of development dependencies
● CQ-366 Unconfirmed platform behaviour and inferred causes written as observed fact
● CQ-369 Store listing fields never copied from the console into the repository
● CQ-370 Operator instructions that never say which variables not to set
● CQ-372 Platform facts written into reusable skills before the project's own record held them
● CQ-375 A reworded claim changed in some places only, and the closure recorded before every occurrence was checked
● CQ-379 New refusals that apply to every start left out of the settings reference and changelog
● CQ-380 A runbook quoting the error text it expected rather than the one observed
● CQ-388 A failure table written from expected cases rather than the error codes seen live
● CQ-389 A runbook's start sequence out of step with the code's order
● CQ-391 A security record that overstated one risk and left out the database role behind another
● CQ-399 A log line documented for its common status only
● CQ-400 A comment attributing an error to a library that does not raise it
● CQ-408 Release record generalising a test property that holds for only some tests
● CQ-415 A binding platform analyser with no local equivalent let fully gated uploads fail Code Quality
● CQ-427 Confirm the platform's backup, shell and data-retention facilities before relying on them for rollback or recovery
● CQ-436 Reviewers must write nothing in the repository they review
● CQ-437 Gate runs left Docker volumes, images and scratch installs behind, and shared one scratch directory

## Deferred

● CQ-109 An audit hash chain must hash exactly what it stores, and needs an anchor outside the database
● CQ-110 Reads and exports of sensitive records are not audited
● CQ-148 A grouping key for external events must include the source
● CQ-149 A long synchronous manual job can outlive the ingress timeout
● CQ-163 Older pages still fetch without stale-response guards and keep stale state after a failed load
● CQ-169 Keep the display rule for timestamps in step with the server's rule, including for rows stored earlier
● CQ-199 Form fields without accessible names, and repeated button names
● CQ-200 A contrast checker's simplifications leave blind spots that must be listed and tracked
● CQ-269 A self-test that uses a stand-in binary can pass where the stand-in cannot run
● CQ-292 A test-only timeout cap is not pinned
● CQ-323 Record the scan's start conditions you have not seen, and handle each only when a scan log shows it
● CQ-331 A local lint guard that approximates a SonarQube rule covers only part of it
● CQ-352 Bundler worker builds run their own plugin pipeline, so build-time dependency checks can miss them
● CQ-381 A runbook shipped inside the artefact names the previous release

## Accepted, with a recorded reason and trip-wire

● CQ-053 Reordering middleware to satisfy a lint rule can silently change which responses carry security headers
● CQ-095 A single-page-app fallback answering 200 for every path can read as a scanner finding
● CQ-096 Moving a credential out of Authorization loses intermediaries' default protections
● CQ-097 Secret-scan regular expressions slow sharply on crafted input
● CQ-098 A bounded limiter's eviction can free a locked key
● CQ-099 Record what the app relies on the ingress for: TLS, host routing, request smuggling, slow clients
● CQ-100 A pattern-based secret scan has blind spots that must be recorded with trip-wires
● CQ-101 Zip readers disagree on a member's name through the Unicode Path extra field
● CQ-102 A baseline record accepts a dangling or unreachable commit
● CQ-103 An unencrypted database connection from a platform add-on is a recorded position
● CQ-104 State what a stolen admin session can do
● CQ-105 An integration bot's memberships decide what every user can read
● CQ-106 Write routes open to every signed-in user are a recorded risk with a trip-wire
● CQ-107 Tokens in browser storage require a strict script policy
● CQ-108 A public status endpoint may reveal a secret's length, so only high-entropy secrets may appear there
● CQ-197 Alert banners in a fixed-height shell can crowd out the page
● CQ-198 Protected pages render before the current user is known
● CQ-270 Layered refusals masked one another under mutation, so some guards turned red only through the refusal's wording
● CQ-287 Database-specific SQL was pinned only as compiled text against a fake session
● CQ-290 Some refusals in a check have no case, because an earlier check refuses first
● CQ-319 Unfixable High CVEs in the base image's OS packages: accept with evidence, rebuild when fixes ship
● CQ-320 OS package manager left in a non-root runtime image: accepted deviation with a trip-wire
● CQ-324 A single-page app fallback that answers 200 for every path can read as a DAST finding
● CQ-325 Record the residual limits of git-based packaging checks, each with a trip-wire
● CQ-326 CI actions pinned by tag rather than commit SHA
● CQ-334 Record why a container image ships without a HEALTHCHECK instruction
● CQ-335 A deliberately fail-open patch step must announce when it was skipped
● CQ-350 Unfixable base-image vulnerabilities: learn the platform scan's policy before spending an upload, and rescan when the base or feeds move
● CQ-353 Third-party CI actions pinned by tag rather than commit SHA
● CQ-385 An append-only verdict record edited in place during a format change
● CQ-396 Automatic discovery moved a data-handling decision outside the app without a security-record entry
● CQ-419 Capture the store's catalogue fields in the repository before submission, or record an explicit waiver
● CQ-425 Large ungated batches move every finding into one long gate run
● CQ-426 Requests to package before review, or to narrow review to the diff, trade depth for speed
● CQ-430 A hand-written verdict or upload record proves the record, not the review
● CQ-432 Re-uploading an older release is scored against the newer upload's quality window

# Method and limits

● **Sources.** Holly's `docs/AUDIT-LOG.md` (one row per release), `CHANGELOG.md`, `SECURITY.md`, all 131 commit messages, `scripts/upload-record.txt` and `scripts/upload-baseline.txt`, the app owner's messages reporting platform results, and the final reports of the 78 gate, deploy-gate, design-critic and SonarQube sweep agents run from V0.6 to V0.13.
● **Process.** 12 readers extracted 751 raw items, one reader per release slice plus one for platform results and one for cross-cutting records. Nine theme reviewers merged duplicates. A separate verifier checked each theme's entries against the quoted sources and corrected or dropped what the sources did not support. A completeness critic then re-read every audit row and gate report and found 22 entries missing, among them CQ-332; each was verified the same way before it was added.
● **Limits.**
  ■ Gate reports for V0.1 to V0.5 were not available. Those entries rest on audit rows and commit messages, and several attribute a finding to a gate by inference.
  ■ V0.5's 68-finding SonarQube report was never among the sources. Its per-rule entries come from the V0.6 audit row, which names the rule keys but not how many of the 68 fall under each.
  ■ Rule keys appear as the sources gave them, so V0.5's keys carry no language prefix.
  ■ The App Store's SonarQube version and quality profile were never visible. Every statement that a local proxy matches the platform is inference, supported where a proxy reproduced a platform failure.
  ■ The reports of V0.12's fifth gate round were lost when the disk filled. That round rests on its audit row.
  ■ V0.13's platform outcome is not yet recorded.
  ■ Evidence quotes are verbatim but may be shortened, and name Holly's own records, which live in the Holly repository.
  ■ Severity uses each source's own scale: BLOCKER, MAJOR and minor from the gates, platform-fail for a stage the platform failed, and unknown where no severity was recorded.

