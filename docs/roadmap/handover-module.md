# Holly handover module: description and implementation plan

Status: proposal, not built. Working title "Handover" (the owner has not named it yet). Prepared on 6 November 2026 from the owner's dictated memo (`Holly_advancements_memo.txt`) and a survey of the Holly V0.18 code. A fact read in the code carries its file reference; an inference or an assumption says so; anything not yet verified is marked `TBC, re-verify`.

## Part 1: The module, described

### The problem

At the end of a shift the mission lead hands the watch to the oncoming crew in the Americas. Today that handover is usually one line per event: "NOTSO released, awaiting more data". The oncoming crew get no picture of the event, no idea why it matters and no sense of what to watch next. They start their shift reconstructing what the outgoing crew already knew.

A handover should tell the story of the event in the language of the mission. It should say what happened and when, what it means, and what comes next, and it should show that someone is already watching for it.

### What a good handover sounds like

Here is the owner's example as a mission lead would give it:

> During the shift a red object in GEO manoeuvred. We issued the possible-manoeuvre NOTSO and the verbal, and later verified the manoeuvre. The burn arrested the object's drift and parked it in the GEO belt close to [blue satellite], putting the two in RPO conditions within an [R x I x C] km box. Lighting for one to observe the other is good roughly every 12 hours; the next closest approach is at [time]Z and the next good-lighting window at [time]Z, and timers are set for both.

That paragraph is the standard the module exists to produce. It has 3 parts, in no more than 3 sentences:

1. **What happened**, with UTC dates and times, and the NOTSOs that marked it.
2. **The impact**: what changed for the object and for any blue asset near it.
3. **What comes next**: the next crossing points, closest approaches and best lighting in the coming 48 hours, and the timers already set for them.

### What the module does

The module is a new tab in Holly. It helps the mission lead build that handover from data Holly already pulls, and lets them add what only a human knows.

● **It assembles each object's story.**
  ■ It gathers every NOTSO on the object from the Unified Data Library (UDL).
  ■ It adds the Mattermost threads that discussed those NOTSOs and the providers' manoeuvre records.
  ■ It sets all of these on one timeline, oldest to newest, so the lead sees the event as a sequence rather than a pile of notices. A roll-up of all NOTSOs on an object may follow (the memo leaves this open).
● **It calls out the providers by name and shows where they disagree.** Where NorthStar and KBR (or any other provider) have each assessed the same event, the module sets their numbers side by side and highlights the differences. For example: NorthStar assessed a +25 s period change, a 17 km perigee raise and circularisation (parked); KBR assessed a +5 s period change and an apogee raise. The lead must know that the providers disagree before handing over, because the oncoming crew will be asked.
● **It covers each event type with its own guided flow.** Manoeuvre, RPO, photometric change and separation each get a flowchart of the questions a good handover answers for that event type; launch and others follow. The module fills in every answer it can from the data and shows where each answer came from. Questions the data cannot answer are flagged for the lead to answer or to state as unknown.
● **It reads photometric changes in context.** When an object's brightness changes, the module asks whether the change lines up with the start of a manoeuvre or with a close approach under good lighting (one satellite placed to observe another). It then gives the time until the same viewing geometry comes round again. At that revisit the crew can tell whether the change has persisted or was a one-off, with the object back to its normal pattern of life.
● **It looks 48 hours ahead.** From the latest element sets it calculates, for each object and pair of interest, these points:
  ■ the next node crossings and apsis passages (apogee and perigee);
  ■ the next closest approaches between a red object and the blue asset it is near, with the RPO box in radial, in-track and cross-track (RIC) terms;
  ■ the best lighting windows for one object to observe the other.

  These points are woven into the narrative, and the lead can turn any of them into a Holly event timer in one click.
● **It drafts the synopsis and shows its sources.** The module drafts the 3-sentence paragraph from the facts it has gathered, and the lead edits it. Every statement carries a source tag:
  ■ a NOTSO;
  ■ a provider record;
  ■ a Mattermost post;
  ■ a calculation (with the element set it used);
  ■ the lead's own note.

  The finished synopsis is ready to copy into the NOTSO compilation tool, the Mission Management Board (MMB).
● **It is a pleasure to use.** The owner was clear: the tab should be engaging, very informative and easy to use, and the flowcharts should lead the lead to the next thing they need to explain. It should be a tool the crew want to open, not a form they put up with.

### Who uses it, and when

● **The mission lead, in the last hour of the shift**, builds handovers for the live events.
● **The mission lead, during the shift**, can open the same view to brief upwards or to check what the providers are saying.
● **The oncoming crew** reads the handover and inherits the timers.

### How I read the dictated memo

The memo was dictated, and speech-to-text garbled a few terms. These are the readings I took; correct any that are wrong.

| Memo says | Read as |
|---|---|
| missionary leads, mission area leads | mission leads |
| nots, notsos, notcells, nuts | NOTSOs (UDL notices) |
| the Americas | the oncoming crew on the Americas shift |
| upsids points | apsides (apogee and perigee) |
| a deficient handover | an efficient (effective) handover |
| apag race, perrogy rays | apogee raise, perigee raise |
| mattmost, mathemat | Mattermost |
| Perth red, rolled app of the notcells | per thread; a roll-up of the NOTSOs |
| gerbelt | the GEO belt |
| mission management board | the NOTSO compilation tool (MMB) the synopsis is pasted into |

## Part 2: Implementation plan

### What Holly already has, and what is missing

Holly V0.18 already holds more than half of what the module needs. The plan is to join those pieces up rather than build a parallel system.

| Need | Already in Holly (fact) | Gap |
|---|---|---|
| NOTSOs | Hourly UDL pull of `TACREP_NOTSO`, source `JCO`, with `event_class`, `sat_no`, `sat_ids`, `raw` (`services/background_refresh.py:74-77`, `models/notification.py`) | No query by object; `sat_ids` (JSONB) has no index |
| Event grouping | `event_key` = `COALESCE(event_id, notso_identifier, udl_id)` (`services/notification_query.py:28-34`) used by summaries and timers | None |
| Event type | `parseEventClass` reads kind, objects and regime from `event_class` in the browser (`frontend/src/utils/ops.ts:75-95`); kinds include maneuver, photometric, rpo, launch | No "separation"; not on the server; the RPO secondary object is only in free text |
| Provider records | Manoeuvres from fusion providers every 10 minutes, `origin` per row, pre/post period, apogee, perigee, longitude and drift in `maneuver_facts.py` | Nothing pairs two providers' records of one event; field names `TBC, re-verify` against a real KBR or NorthStar record |
| Mattermost | 60 s ingest of followed channels, `raw` stored, text search (`services/mattermost_ingest.py`, `routes/mattermost.py`) | No thread grouping (`root_id` only in `raw`); no link from a post to a NOTSO; no provider tag |
| 3-sentence narrative | `event_summary`: per event, from cleared notices, sentence cap, provenance ids, background refresh (`services/event_summary.py`) | Per event, not per object; does not check what the sentences say |
| Timers | `event_timer` with `event_key`, pre-alert, recurrence; banner on every page (`models/event_timer.py`, `TimerBanner.tsx`) | Only the manual form creates them; no origin marker |
| Shift handover | Shift Log notes and an end-of-shift summary (`pages/ShiftLog.tsx`, `services/shift_log.py`) | Built from typed notes only |
| Orbital maths | Element sets stored with TLE lines (`models/elset.py`) | No propagator, no sun model; element sets have no background pull since it was removed (`background_refresh.py:15-16`) |
| Charts | Hand-drawn SVG: `ActivityTimeline` with brush and pick, `ObjectBoard`, `GeoBelt` | No flowchart component |

### Decisions and checks before any build (phase 0)

These come first, because each one changes what gets built.

1. **Disclosure of NOTSO content to the assistant.** Fact: only markings listed in `ASSISTANT_CLEARED_MARKINGS` reach the assistant, and the JCO feed's marking is not cleared by default (`SECURITY.md:27`). Until a data owner clears it, any drafting by a large language model (LLM) gets no NOTSO content. The owner is setting this now; the decision is recorded in `SECURITY.md` before the module relies on it. **The plan does not depend on the LLM:** phases 1 to 3 draft the synopsis from a deterministic template, and the LLM is an optional upgrade in phase 4.
2. **Disclosure of Mattermost threads.** Fact: chat carries no marking and is already sent to the assistant from followed channels (`SECURITY.md:27`). Feeding threads into a synopsis widens that. This needs an architecture decision record (ADR-016) and a `SECURITY.md` row: either a per-channel "cleared for assistant" flag that fails closed, or chat kept out of every prompt and used only on screen.
3. **A real record from each source**, checked before code is written against it:
   ■ a stored KBR and a stored NorthStar manoeuvre record, to confirm the key names and units in `maneuver_facts.py` (`TBC, re-verify`);
   ■ a Mattermost event thread, to confirm how threads cite NOTSOs (NOTSO number, catalogue number, channel per event?) and whether providers post under their own accounts;
   ■ RPO NOTSOs, to confirm whether `sat_ids` holds both objects or only the primary;
   ■ a photometric NOTSO, to see what it states (magnitude, sensor, time).
4. **Provider list.** Which providers to recognise in chat, and under what names and aliases, comes from the owner as configuration. It is never inferred.
5. **The list of event types**, and which types get a guided flow in the first release. The memo names manoeuvre, RPO, photometric change and separation, and says "there's a whole list".
6. **The MMB hand-off.** Copy as text (assumed for phase 2), a formatted export, or a later integration? `TBC` with the MMB's owner.
7. **The module's name.**

### Architecture

The module is one new tab and one backend package within the existing Holly container. It adds no new process, and it follows Holly's rules on boundary validation, sign-in, audit and failing closed.

**Backend.** These go in `src/app/services/handover/` with routes under `/api/v1/handover`, all signed-in:

● `object_story.py`: everything on one object, in time order.
  ■ It draws on NOTSOs (by `sat_no` or `sat_ids`), manoeuvre records with their facts, linked Mattermost threads, event summaries, timers and analyst notes.
  ■ It builds the story from what Holly already stores and adds no new copy of the data.
● `taxonomy.py`: the server-side port of `parseEventClass`.
  ■ It adds "separation" and extracts the RPO secondary's catalogue number.
  ■ It is tested against the same cases as the browser version so the two never disagree.
● `thread_links.py`: groups Mattermost posts into threads and suggests the NOTSO each thread belongs to.
  ■ Threads are grouped by `root_id`, a new indexed column backfilled from `raw`.
  ■ Suggestions come from NOTSO numbers and catalogue numbers found in the text.
  ■ A suggestion is shown as such until a lead confirms it. Only a confirmed link enters a synopsis (fail closed).
● `provider_deltas.py`: pairs providers' records of the same event and computes the differences.
  ■ It matches records on catalogue number and an overlapping time window, or on a shared `event_id`.
  ■ It compares the period change, apogee change, perigee change, eccentricity change and longitude and drift before and after.
  ■ It flags an apsis disagreement and any delta above a configurable threshold.
  ■ It never averages two providers into one figure.
● `look_ahead.py`: a pure function with no database access and full unit tests.
  ■ It takes element sets and returns points of interest for 48 hours: node crossings and apsis passages, closest approach for named pairs with the RIC box, and lighting windows.
  ■ For lighting, the observer is the other satellite, so the test is the target sunlit and the sun-target-observer phase angle under a threshold. No ground site is needed for the RPO case.
  ■ The sun position comes from a low-precision analytic model, so no ephemeris file is downloaded and the container stays offline.
  ■ Each point carries the `udl_id` and epoch of the element set it used.
  ■ It refuses an element set older than a set age, and says so.
● `synopsis.py`: drafts the 3 sentences from a template filled with the verified facts, each with its source tag.
  ■ In phase 4, an optional `call_claude(purpose="handover.synopsis")` rewrites the template into fluent prose.
  ■ The model returns JSON citing only source ids it was given; anything else is rejected. It gets one retry, then fails closed back to the template.
● **Migrations from `0020`:**
  ■ `handover` (object, shift date, synopsis text, flow answers, sources, status, author);
  ■ `handover_thread_link`;
  ■ `mattermost_message.root_id` with its index;
  ■ a GIN index on `notification.sat_ids`;
  ■ `event_timer.origin` (manual or look-ahead).

**Frontend.** The new route is `/handover`, with one entry in `NAV_ITEMS`.

● **Object rail.** It reuses `ObjectBoard`, ranks objects with live events, and filters by event type.
● **Story timeline.** It reuses `ActivityTimeline` with lanes for NOTSOs, provider records, Mattermost and analyst notes. A second strip, after a "now" line, shows the 48-hour look-ahead with one-click timers.
● **Guided flow.**
  ■ A flowchart per event type, drawn as hand-made SVG. Fact: the page's style policy blocks the styles that libraries such as Mermaid inject (`factory.py:62-66`), and hand-drawn SVG adds no dependency.
  ■ Each node is a question. Answered nodes show the answer and a source chip; open nodes pulse for the lead's attention.
  ■ The flow definitions are data, so a new event type is a new definition, not new code.
● **Provider comparison card.** Providers sit side by side, with disagreements highlighted in a new token that passes the contrast check.
● **Synopsis composer.** It holds the draft, a sentence counter, source chips, the lead's notes, and "copy for MMB".

### Delivery in 4 releases

Each release is a version bump and goes through the verification loop, both gates and the App Store pipeline. Each one is useful on its own. Sizes are relative estimates, not commitments.

**V0.19: the object story (size M).** No LLM, and no new dependency.
● Server-side taxonomy, the object-story route, Mattermost thread grouping and the thread-to-NOTSO suggestion with lead confirmation.
● The Handover tab with the object rail, the story timeline, provenance chips and free-text notes.
● Acceptance: a lead can open any object named in a NOTSO in the last 120 hours. They see its NOTSOs, provider records and confirmed threads in time order, each with its source.

**V0.20: guided flows and the template synopsis (size M).**
● Flow definitions for manoeuvre, RPO, photometric change and separation.
● The flow renderer, with answers filled from data, and the template synopsis.
● Saved handovers per shift, "copy for MMB", and confirmed handovers listed in the Shift Log's end-of-shift view, so the two handover features agree instead of competing.
● Acceptance: for the owner's worked example, the flow fills every node the data can answer. It names the unanswered ones, and it produces a 3-sentence synopsis with every statement sourced.

**V0.21: the 48-hour look-ahead and timers (size L).**
● Add the `sgp4` package. Fact: no propagator is installed today. It is pinned, relocked and licence-checked like any dependency.
● Bring back a scoped element-set pull for objects with live events only, with a freshness guard.
● Add `look_ahead.py` with tests against reference cases, the look-ahead strip, one-click timers with `origin=look-ahead`, and upcoming points in the synopsis's third sentence.
● Acceptance: for a GEO pair in an RPO NOTSO, the module lists the closest approaches, the RIC box and the lighting windows for 48 hours. Each is labelled with the element set and epoch it came from. A timer is 1 click away.

**V0.22: provider deltas, photometric context and optional AI drafting (size M).**
● Provider pairing and the delta card.
● Provider names in Mattermost from the configured list.
● Photometric context: alignment with manoeuvre starts and close approaches, and time to revisit the same geometry, with a timer.
● The optional LLM rewrite of the synopsis, only if decisions 1 and 2 are recorded, with its own audit row and a cap within the daily token budget.
● Acceptance: the NorthStar versus KBR example appears as a highlighted disagreement on apsis and period change. An LLM draft never cites a source it was not given, and it falls back to the template on any failure.

### Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Element-set accuracy at GEO | Fact: TLE and SGP4 positions carry errors of the order of kilometres. Inference: an RPO box computed from TLEs is indicative only | Label every computed figure "from element set [epoch], indicative". Prefer provider state vectors if the UDL offers them (`TBC, re-verify`). Never present a computed figure as observed |
| JCO marking not cleared | The LLM drafting has no NOTSO content | The template synopsis works without the LLM; the LLM is phase 4 and optional |
| Wrong thread-to-NOTSO links | A synopsis cites chat about a different event | Suggest, never assume; only a lead-confirmed link counts |
| Provider fields mis-read | Wrong deltas reach a handover | Check against a real record in phase 0. Show the raw value beside every delta |
| CPU in the single worker | The look-ahead slows the other background loops | Compute on request for named pairs only, cache by element-set id, and bound the steps |
| SonarQube smells in a large new UI | Upload fails Code Quality, as in V0.16 and V0.17 | Run the local Sonar probe on every changed file, configs included, before packaging |
| Two handover features | Shift Log and the new tab disagree | Confirmed handovers feed the Shift Log summary (V0.20) |
| Group-key trip-wire | Fact: `SECURITY.md:34` requires the source in the group key before a second notice source is ingested | Provider comparison uses manoeuvre records, not a second notice source, so the key is untouched. Revisit if a second NOTSO source is added |

### Answers needed from the owner

1. Confirm the readings in the table under "How I read the dictated memo".
2. Disclosure: will NOTSO content and Mattermost threads go to the assistant, and who records that decision (phase 0, items 1 and 2)?
3. 1 stored KBR record, 1 NorthStar record and 1 example Mattermost event thread, for phase 0 item 3.
4. The provider names and aliases to recognise.
5. Which event types get a guided flow first, and the full list.
6. How the synopsis reaches the MMB.
7. The module's name.
