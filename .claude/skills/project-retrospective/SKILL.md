---
name: project-retrospective
description: Build retrospective generator (the "Teach Bob" feature). Use at the end of a build, a milestone or a release, or when asked to "run a retrospective", "capture lessons learned", or "generate a Teach Bob report". Reviews code and process across six lenses and writes RETROSPECTIVE.md.
---

# Project retrospective (Teach Bob)

> Teach Bob is the friendly name of the feature and the tab that stores the report. This skill is the generator: drop it into a finished project and it writes the retrospective. The report you produce is uploaded into the Teach Bob tab in Code With Bob, which saves it locally tagged by developer name and upload time so a future reader can retrieve it and fold the lessons back into the standard.

## Purpose and scope

A retrospective is only useful if it is honest, specific, and evidence-led. This skill runs a deep review of a project once the work is done, covering the code and the process that produced it, and writes one portable Markdown report with a header the Teach Bob tab can read. It does not deploy, mutate, or grade the project against the App Store gates (that is `app-store-readiness`); it looks back so the next build goes better.

## When to use

- At the end of a build, a milestone, or a release, while the detail is fresh.
- After a difficult stretch worth learning from, whether it shipped or not.
- When asked to run a retrospective, capture lessons learned, or generate a Teach Bob report.

## Prerequisites

- Run it at the project root so the review can read the real code, the commit history, and the change log. A retrospective written from memory is a guess; read before you assert.
- Know who the report is for: capture the developer's name. If you cannot verify it, ask; never invent one.
- Nothing else. This skill is standalone: it needs no other skill, no build tooling, and no particular language or stack, so it can be sent to someone on a project you have never seen and still work.

## Procedure

1. **Establish the ground truth.** Read the repository: the source, the tests, the change log or audit trail, the README, and the recent commit history. Note the dates and figures you can verify from the tree; mark anything you cannot with `TBC, re-verify` rather than asserting it.
2. **Capture the developer's name.** Ask the person running the skill for the name the report should be filed under, plainly: "Whose retrospective is this? I will file it under that name." Do not fabricate, and do not guess from a git author string without confirming it. **If the run is non-interactive and there is nobody to ask**, derive the name from the account or git identity, use it, and say so in one line under the header: "Filed under the account running the session; correct the name and re-file if that is wrong." A derived name that is labelled as derived is honest; a derived name presented as confirmed is an invented fact.
3. **Record the context, in four lines.** Stack, archetype, duration, and whether this baseline was in use. This is the difference between a lesson a reader can apply and one they cannot: a theme that recurs across a Python service, a static artefact and a container app is a finding about engineering, while the same theme in three projects on one stack is a finding about that stack. The synthesis (`learn-from-feedback`) clusters across reports and cannot weigh a lesson it cannot place.
4. **Review across the six lenses**, for both the code and the process. For each finding, cite the evidence (a file, a commit, a decision) so a reader can check it:
   - **What went well** - the choices and habits that paid off and are worth repeating.
   - **What did not** - where the build stalled, broke, or went the wrong way, and why.
   - **Improvements** - concrete changes to how the next project is built.
   - **Optimisations** - where the same result could have come faster, cheaper, or with fewer tokens or steps.
   - **Waste** - effort, rework, or scope that produced no value, and the signal that would have caught it earlier.
   - **Missed detail** - the thing that was overlooked: an edge case, a gate, a requirement, a security or accessibility floor.
5. **If one gate rejected you more than twice, tabulate every rejection before you write a word about any of them,** with a column for **where the cause was written**. This is the cheapest instrument in the skill and the one that changes a report most. A ten-rejection report was written this way and the last column was the whole finding: every single rejection had been caused by the release immediately before it, which named both the mechanism (the gate scores changed code, so the window IS the previous release) and the trap (most of the new code was tooling written to satisfy the gate). Ten separate diagnoses had not found it, because a symptom read one at a time is a symptom. Then sort the rows into CLASSES rather than instances: a reader who can name the class can name the fix, and five classes covered all ten rows.
6. **Record which guards have been watched to fail.** Separate from the six lenses, and mandatory even when the honest answer is "none of them": list every check, test, guard or budget written in the period, and for each say whether a COMMITTED case proves it can go red. Not the coverage figure, a case that fails when the thing the guard protects is removed. A guard nobody has watched fail is not a guard. Its shape is in the format below, and it is the only section with a fixed one-line-per-guard form, because a paragraph here always turns into a claim: **name, then proved or not proved, then the case that proves it.** This is the most commonly absent section across the reports received so far, and one arrived with twelve budget call sites and no failing case anywhere in its suite.
7. **Say where the tooling or the standard cost you.** Also separate from the six lenses, and the single most useful section to whoever asked for the report: which rule, skill, gate, check or convention slowed the work down, fired wrongly, or was silent when it should have spoken. A rule that everyone quietly works around is a defect in the rule. Name it, say what it cost, and say what you did instead. Answer "nothing, it stayed out of the way" if that is the truth: a clean answer here is information too. Nobody else can see this from your repository, which is why it has to be asked rather than inferred.
8. **Calibrate before writing.** Two floors, because "honest, not flattering" is a wish until it is countable. **The summary must name one thing that went wrong**, and **"What did not" plus "Waste" together must be at least as substantial as "What went well".** A report that fails either is not finished, it is a status update. If the project genuinely went well, the honest form is a short "what went well" rather than a padded one.
9. **Rank the findings.** Lead with the few that would most change the next build. A flat list of twenty equal points is a diary, not a retrospective. Aim for roughly one to three pages: long enough to carry evidence, short enough that the person you send it to reads all of it.
10. **Scrub it before it leaves the project.** This report is written to be sent, by email or upload, to someone outside the codebase, so it is a disclosure boundary and gets treated as one. No secret, credential, token, key, internal hostname or connection string, in any form, including inside a quoted log line or a pasted error: render any such value as `[REDACTED:type]`. No customer, programme or partner name that is not already public. Then read it once as an outsider: every finding should make sense to a competent engineer who has never opened your repository, and a file path with no explanation is not a finding.
11. **Write the report** to `RETROSPECTIVE.md` at the project root, using the format below.
12. **Hand it off.** Tell the developer the file is written, and name the route: upload it into the Teach Bob tab in Code With Bob, which saves it tagged by their name and the upload time, or, if they do not have Code With Bob, send the file straight back to whoever asked for it. The report is a plain Markdown file and works either way.

## The report format

Write one self-contained Markdown file. Begin with the header block exactly as below: the Teach Bob tab reads the `Developer` and `Date` lines to tag and sort the saved report, and falls back to the file name and the upload time if they are absent. Keep the labels; fill the values.

```
# Teach Bob retrospective

- Developer: <full name, as it should be filed>
- Project: <project or repository name>
- Date: <YYYY-MM-DD, the day the retrospective was run>
- Scope: <the release, milestone, or window this covers>
- Stack: <language and framework, e.g. Node 22, or Python 3.12 and FastAPI>
- Archetype: <what it is: static artefact, container service, library, CLI, data pipeline, other>
- Duration: <how long this scope took, in the honest unit: days, weeks, or commits>
- Baseline: <which standard or skill bundle was in use, and its version, or "none">

## Summary
<three or four sentences: the shape of the project, the single most important lesson, and at
least one thing that went wrong>

## What went well
- <finding> (evidence: <file, commit, or decision>)

## What did not
- <finding> (evidence: ...)

## Improvements
- <concrete change for next time>

## Optimisations
- <where the same result could have come faster, cheaper, or leaner>

## Waste
- <effort or scope that produced no value, and the earlier signal>

## Missed detail
- <the overlooked edge case, gate, requirement, or floor>

## Rejection ledger (only if one gate rejected you more than twice)
| # | Failing condition | Detail | Where the cause was written |
|---|---|---|---|
| 1 | <condition> | <the number or finding> | <which release introduced it> |

## Guards seen to fail
- <guard name>: **proved** / **not proved** - <the committed case that makes it go red, or why
  there is none. One line each. Say "not proved" where that is the truth; an unproved guard named
  here is worth more than a silent one>

## Where the tooling or the standard cost us
- <the rule, skill, gate, check or convention, what it cost, and what was done instead. Or
  "nothing, it stayed out of the way", which is also an answer>

## Top three to carry forward
1. <the highest-value lesson>
2. <the second>
3. <the third>
```

## Rules

- **Honest and specific, never flattering.** A retrospective that only praises is worthless. Name the real problems, and attribute them to decisions and process, not people.
- **Evidence-led.** Every material claim cites something a reader can verify in the tree or the history. No invented names, dates, figures, or organisations; mark the unverifiable with `TBC, re-verify`.
- **Self-contained and portable.** One Markdown file, readable offline, no links to anything that must be fetched. It has to survive being uploaded, stored, and reread months later.
- **A guard is unproved until watched.** Do not describe a check as protecting anything unless a committed case makes it fail. Where a guard was written this period and has no such case, list it in the guards section as unproved rather than omitting it.
- **It is a disclosure, so scrub it.** No secret, credential, key, internal hostname or connection string in any form, including inside a quoted log or error; render any such value as `[REDACTED:type]`. No customer, programme or partner name that is not already public. The report is written to be sent to someone outside the codebase.
- **Written for a reader who has never opened the repository.** Cite the file, then say what it shows. A bare path is provenance, not a finding.
- **Blame decisions, never people.** Attribute a problem to a choice, a rule, a gap or a process. This is what makes it safe to be specific, and a report nobody can be blamed for is a report people write honestly.
- **House voice.** UK English, plain language, decision before reasoning, a single dash rather than a long dash, and "and" rather than "+".

## Pairs with

- `working-with-ai` for the review and debugging habits a retrospective tends to reward.
- `resource-discipline` for the token and time waste the optimisation lens looks for.
- `app-store-readiness` when the question is "will it pass", not "how did it go".
- `learn-from-feedback` on the receiving end: it reads a corpus of these reports and turns the recurring themes into changes to the standard. It reads the guards section and the tooling section separately from the six lenses, which is why both have a fixed shape.

None of those is required. If you were sent this skill on its own, ignore this section: the procedure above is complete, and the report it writes is a plain Markdown file that stands by itself.
