---
name: ai-update-scan
description: Building an exhaustive, safe, in-app AI update or search scan. Use when an app has a one-click "refresh the data" or "find everything" feature powered by a Large Language Model (LLM) with a web-search tool. Server archetype only.
---

# AI update or search scan

## Purpose and scope

How a server app runs a deep, in-app "update scan" or "find everything" feature: one server-side call (or a fan-out of several) to a Large Language Model (LLM) with a server-hosted web-search tool, driven by a long, disciplined prompt, whose one structured result is validated at the boundary and merged into the shared store as a superset. The recall and the safety come from the METHOD, never a particular output format. Scope is the scan feature end to end. The LLM call mechanics live in `llm-integration`, the store and merge in `data-layer`, and the job wrapper in `api-and-integration`; this skill is how they compose into a scan that misses nothing and can never corrupt the data. Server archetype only; the static artifact never calls an LLM.

## When to use

- Adding or changing an in-app feature that refreshes, expands, or searches a dataset by researching the open web with an LLM.
- Any "one-click update", "scan for new items", or "deep search" that must be exhaustive and must not silently drop existing records.

## The six goals (state them to the model as non-negotiable)

- **Widest possible.** Sweep every category and every credible source, assuming there is always one more item not yet found.
- **Deepest possible.** Stand each field up against a real source; corroborate, never accept a single hit.
- **Superset, never shrink.** Carry every current record forward, re-verify and enrich it, add new finds, and only ARCHIVE (never delete) records that have genuinely ended.
- **Default the routine update to the stale cohort, not a full re-sweep.** Most records do not change between cycles, so re-scanning the whole world every time pays for work that returns the same answer. Make the DEFAULT update re-verify only the records that have gone stale (by an age or a change signal), and reserve the full worldwide sweep for an explicit deep run; in one project the stale-cohort update cost roughly a fifth to a half of a full re-scan for the same freshness. The superset and anti-shrink invariants still hold: a stale-cohort update carries every current record forward untouched and never shrinks the set, it just spends the search budget where change actually happens.
- **Retrieve, never estimate in its place.** Open the authoritative source and read the value off it; a labelled estimate is a last resort, never a substitute for retrieval.
- **Never invent.** Unverifiable fields take the exact unknown marker; the server rejects results that break this.
- **Deterministic ingestion.** The model's freedom is bounded by a defined output contract, boundary validation, and an anti-shrink merge, so a thin or bad result can never corrupt or erase the dataset.

## The prompt: how "misses nothing" is engineered

The prompt is the heart of recall. Decompose the search space along every axis and require a dedicated pass of each cell. A long system prompt with these blocks (swap the bracketed CONTENT for your domain):

1. **Role and single deliverable.** The only output is one structured result in the exact format the app expects, nothing around it.
2. **Doctrine.** The six goals above, stated as standards the model is held to.
3. **Scope.** The horizon (a rolling window), the geography or primary axis, the entities, and an explicit VOLUME FLOOR ("a thin list is a failure; return at least the carried-forward count") as an anti-laziness lever.
4. **Category decomposition.** Enumerate the [categories] and instruct the model to search EACH ONE SEPARATELY, never lumping, and to go beyond the named anchors. This is the single biggest recall lever.
5. **Anchors as a floor, not a ceiling.** List a few well-known [sources] per category as a starting point; the value is the items only that source's own listing reveals.
6. **Per-area decomposition.** Break the primary axis into [regions] and each into [sub-areas]; require a dedicated sweep of each so a broad area cannot let one part stand in for the rest.
7. **The record fields (output contract).** Every field, how to source it, and the exact unknown marker; high-value fields (dates, identifiers, source references) get explicit sourcing rules.
8. **Method: breadth-first then depth.** Enumerate candidates across all categories first, then verify each field.
9. **The chase ladder.** For any unknown field, work a fixed ladder before accepting "unknown": the source's own page, the last edition's page, archived pages, the prospectus, official listings, aggregators, then social. Most "unknown" values are simply on a page not yet opened.
10. **Retrieval discipline, no forward projection.** For every record the model MUST open the authoritative source and read the value off it, and must NEVER advance a recurring item to a later edition than the source has published. A stored future edition the source has not published was a premature estimate; the real listed edition is authoritative.
11. **Labelled estimates as a last resort.** Only when nothing is published after the full ladder, give a best estimate, labelled "(estimated, re-verify)", never presented as confirmed.
12. **Edge-case hunt.** A named checklist run every time: renamed or rebranded, merged or split, biennial and triennial (confirm the year), regional editions under near-identical names, co-located or fringe items, newly announced firsts, invite-only, postponed or moved, virtual or hybrid, cadence-irregular. Naming the edge cases surfaces them.
13. **Self-audit before returning.** A checklist the model runs on its own output: every record sourced, nothing invented, every unknown marked, no duplicate ids, editions separated, all within the horizon, counts meet the floor, all cells swept, format valid.
14. **Per-cell recall gate.** For each area and category, list the flagship items and confirm each is present or carried forward with honest markings; a zero for a cell is a search gap, not an empty world, and sends the model back to sweep it again.

The takeaway: decomposition beats exhortation. "Search thoroughly" returns the obvious few; naming every cell and requiring a dedicated pass with a self-audit gate is what makes the sweep exhaustive.

## Architecture

- **Async single-flight job.** A deep scan runs for minutes, so the request that starts it returns a job id immediately and the client polls a status endpoint. Only one scan runs at a time (a double-click or leaked trigger cannot start a second). See `api-and-integration`.
- **Streaming with bounded pause-turn continuation.** The request is streamed (a long sweep would time out otherwise); server-side search can pause the turn, and the client resumes by echoing the assistant turn back verbatim, bounded so it can never run away. Derive the continuation limit from the search budget, not an arbitrary count. See `llm-integration`.
- **Prompt caching.** Cache the large stable prefix (the system prompt, which carries the whole current dataset, plus the tool definition) with an ephemeral breakpoint, so continuations and the retry re-read it cheaply.
- **High output ceiling.** A deep superset is a large payload; set max output tokens high so the result is not truncated. Streaming means a high ceiling does not risk a timeout.
- **Boundary validation then superset merge, then persist.** Validate (fail closed) and merge (anti-shrink) before anything touches the store. On the deepest tier, persist after each pass so a long run's progress survives a restart and grows live.

## The multi-pass "deepest" engine

A single request has token, time and attention ceilings; a truly exhaustive sweep exceeds them, so the deepest tier fans out into independent passes: one pass per in-scope area (each covering that area exclusively across all categories, so none is diluted), one dedicated pass for the historically under-covered category, and one edge-case pass across everything already swept. Each pass receives only the slice of the dataset it re-verifies (so its input stays bounded while the merge preserves the rest), runs to a parsed result with a single format-only retry, drops invalid or duplicate records (not the whole pass), is merged and persisted immediately, and is wrapped so a pass that errors or times out is skipped and logged, never taking the run down. Total depth is per-pass budget times passes.

## The output contract and fail-closed validation (format-agnostic)

Define your own contract; the FORM matters, not the serialisation (JSON, another format, typed records). Every contract needs: a defined set of fields per record with a stable identifier (plus an edition or version discriminator so recurring items stay separate), a required type or category from a closed set, the descriptive and temporal fields your domain needs, any scores, and a source reference; a single agreed unknown marker; and FAIL-CLOSED validation at the boundary that rejects a malformed record with a clear message and writes nothing. Normalise known aliases before the closed-set check. Assert with a test that the closed category set matches exactly across the prompt, the validator, and the interface (a drift guard).

## The anti-shrink superset merge

This is what lets the model have an open research brief without risking the data (see `data-layer` for the general rule). Match an incoming record to a current one by stable id, or failing that by a FINGERPRINT (normalised name plus edition discriminator), so a re-scan that changes the id still updates in place. Update only fields that carry a real, confirmed value (an incoming empty or unknown value never overwrites a known one). Merge multi-dimensional scores dimension by dimension, keeping the existing value when the incoming one is missing. Add records not already present. ARCHIVE, never delete: a record whose lifecycle has ended is flagged (moved to a Past view), and a correction un-archives it. Supersede a premature estimate only when a later scan confirms the real edition of the same series. The red line: a thin or partial scan can correct and grow the dataset but can NEVER silently drop a valid record. Snapshot the pre-scan dataset so a bad scan can be rolled back.

## Budget, scope, and cost transparency

Scale effort by depth and scope, bounded by a hard cap so cost cannot run away: per-tier base search budgets, a hard cap, and per-tier targets for new finds. The budget scales with how many areas are in scope, with a high floor so a narrow single-area scan still searches hard (a starved narrow scope is a real failure mode). Show the estimated searches, time, and cost BEFORE the run, so the spend is the user's informed choice; the tier the user picks is the real limit. Sum token and web-search counts across the streamed message, every continuation, the retry, and every pass, and write them to an audit log with a cost estimate (`observability-and-audit`).

## Robustness

- One format-only retry per malformed reply, then fail closed.
- A pass that errors, times out, or is unparseable is skipped and logged; the run continues.
- Invalid or duplicate records within a pass are dropped, not fatal.
- Every persistence step is best-effort and surfaced, never silently swallowed.
- The whole result is validated before any write; a bad scan cannot corrupt the store, and the pre-scan snapshot allows rollback.

## What to swap for your domain

Reuse every mechanism above. Swap: the closed category set (shared between prompt, validator, and interface, with a drift-guard test); the category decomposition and its anchor sources; the primary axis (geography, product lines, research fields) and its cells; the output contract (fields, identifier, unknown marker, format); the scoring dimensions and weights, if any; the horizon and the archive lifecycle signal; the anchors and the per-cell recall-gate flagship list; the volume floor; and the fingerprint definition if records are not identified by name-plus-edition.

## Definition of done

- The closed category set and output contract are defined once and shared, with a drift-guard test.
- The prompt carries all fourteen blocks with your CONTENT and states the exact output format.
- The call streams, uses the web-search tool with a per-run cap, bounds pause-turn continuation by the budget, caches the stable prefix, and sets a high output ceiling.
- Boundary validation is fail-closed and the merge is anti-shrink (update-confirmed-only, score-merge, archive-not-delete, estimate-supersede), with tests for each.
- The deepest tier fans out per area plus the under-covered category plus an edge-case pass, each merged and persisted incrementally and wrapped so a failed pass is skipped.
- The scan runs as an async single-flight job with a poll endpoint, an up-front cost estimate, and usage accounting in the audit log.
