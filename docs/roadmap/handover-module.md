# Holly handover module: description and implementation plan

Status: proposal, not built. Working title "Handover" (the owner has not named it yet). Decision of the owner, 6 November 2026: the module uses no external LLM. Its language model runs inside the Holly container as a batch job of up to 5 minutes near the end of each shift; it is not a chat assistant. Prepared on 6 November 2026 from the owner's dictated memo (`Holly_advancements_memo.txt`) and a survey of the Holly V0.18 code. A fact read in the code carries its file reference; an inference or an assumption says so; anything not yet verified is marked `TBC, re-verify`.

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
● **It drafts the synopsis and shows its sources.** Near the end of the shift, a language model running inside Holly reads the linked Mattermost threads and pulls out each provider's claims. Holly checks every claim against its source post. It then drafts the 3-sentence paragraph from the checked facts, and the lead edits it. Nothing is sent outside Holly. Every statement carries a source tag:
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

1. **No external LLM in the module (decided).** The owner decided on 6 November 2026 that the module never calls an external large language model (LLM). Mattermost threads and NOTSO content are read only by a model running inside the Holly container, so neither leaves the App Store. Inference: this turns a release decision into a question of whether the App Store environment is approved for this data. The owner and the data owner confirm that, and it is recorded in an architecture decision record (ADR-016) and a `SECURITY.md` row. A test fails the build if any module under `services/handover/` imports the Anthropic client (`services/claude.py`).
2. **The existing assistant still sends chat.** Fact: Holly's notice evaluations already include up to 30 recent Mattermost messages in what they send to Anthropic (`services/assistant.py:261-280`, `SECURITY.md:27`). That is separate from this module. To stop it, set `MATTERMOST_MAX_MESSAGES_IN_PROMPT=0` and restart. It is the owner's call, and the decision is recorded when made.
3. **The local-model trial (go or no-go), run before V0.20.** Protocol, pass marks and harness: `docs/roadmap/handover-trial-plan.md` and `trial/`.
   ■ **Where:** a container capped at 8Gi and 6 CPU, inside Bluestaq's environment. Real threads are never pasted into an external tool, including this conversation.
   ■ **What:** 2 or 3 permissively licensed models, quantised to 3 to 8 billion parameters, run on 5 real event threads.
   ■ **Measure:**
     ● extraction accuracy against a mission lead's own reading;
     ● time per thread;
     ● peak memory.
   ■ **Go criteria (proposed):**
     ● no unsupported figure gets through the checks;
     ● the threads for a typical shift's live events fit in the 5-minute run;
     ● peak memory leaves Holly at least 2Gi of headroom.
4. **A real record from each source**, checked before code is written against it:
   ■ a stored KBR and a stored NorthStar manoeuvre record, to confirm the key names and units in `maneuver_facts.py` (`TBC, re-verify`);
   ■ a Mattermost event thread, to confirm how threads cite NOTSOs (NOTSO number, catalogue number, channel per event?) and whether providers post under their own accounts;
   ■ RPO NOTSOs, to confirm whether `sat_ids` holds both objects or only the primary;
   ■ a photometric NOTSO, to see what it states (magnitude, sensor, time).
5. **Provider list.** Which providers to recognise in chat, and under what names and aliases, comes from the owner as configuration. It is never inferred.
6. **The list of event types**, and which types get a guided flow in the first release. The memo names manoeuvre, RPO, photometric change and separation, and says "there's a whole list".
7. **The MMB hand-off.** Copy as text (assumed for V0.20), a formatted export, or a later integration? `TBC` with the MMB's owner.
8. **The module's name.**
9. **The end-of-shift run time.** The shift change times in UTC, and how long before each the run starts, for example 40 minutes so the lead has time to review the draft (`HANDOVER_RUN_TIMES`, `TBC` from the owner), plus a "draft now" button for an off-pattern handover.

### Architecture

The module is one new tab and one backend package within the existing Holly container, plus a short-lived child process for the local model during the end-of-shift run. It follows Holly's rules on boundary validation, sign-in, audit and failing closed.

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
● `local_model.py`: the language model inside Holly. It never calls out of the container.
  ■ **Runtime.** `llama.cpp` through its Python binding, compiled in the image's build stage so the compiler toolchain stays out of the final image.
  ■ **Weights.** One quantised model with a permissive licence, pinned by SHA-256 and held on the `/data` volume or in the image; which one is for the platform team to say.
  ■ **A child process per run.** The model runs in a child process started for the end-of-shift run and ended when the run finishes. That gives 3 things:
    ● a crash in native code takes down only the child process, not Holly's background loops;
    ● the model's memory is freed between runs;
    ● a thread cap stops it starving the web app of CPU.

    It departs from Holly's one-process rule, so it is recorded in ADR-016.
  ■ **No network.** The child process gets no network access and no database connection: Holly hands it the text and reads back its answer.
● `extract.py`: reads each confirmed thread and returns structured claims through the local model, for example provider NorthStar, quantity period change, value +25, unit s, post id. Each claim is then checked in code, and any that fails a check is dropped:
  ■ the figure must appear word for word in the post it cites;
  ■ the provider must be in the configured list, and either named in the post (or by alias) or the post author's company;
  ■ the post must belong to the thread being read.

  A made-up number cannot survive, because it is not in the source post. Results are cached per thread against its newest post id, so a rerun reads only threads that have changed.
● `end_of_shift.py`: the batch run, at the configured times and on "draft now".
  ■ It works through live events in priority order: the most recent change first, then RPO, then the rest.
  ■ It stops at the 5-minute budget, and any event it did not reach is marked "template only, not read by the model".
  ■ It writes one audit row per run: events read, claims kept and dropped, time taken.
  ■ It is single-flight, like the other loops.
● `synopsis.py`: drafts the 3 sentences from a template filled with the checked facts, each with its source tag.
  ■ Optionally, the local model smooths the wording. A check then refuses any draft that adds a number, name or time not in its input, and the template wording stands instead.
● **Migrations from `0020`:**
  ■ `handover` (object, shift date, synopsis text, flow answers, sources, status, author);
  ■ `handover_thread_link`;
  ■ `handover_claim` (the checked claims, cached per thread against its newest post id);
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

**V0.20: guided flows, the template synopsis and the end-of-shift run (size L).** It needs the local-model trial (phase 0, item 3) to have passed, and Holly raised to 8Gi and 6 CPU.
● Flow definitions for manoeuvre, RPO, photometric change and separation.
● The flow renderer, with answers filled from data, and the template synopsis.
● The local model, the extraction checks and the end-of-shift run, with provider claims from Mattermost.
● ADR-016 and the `SECURITY.md` row.
● Saved handovers per shift, "copy for MMB", and confirmed handovers listed in the Shift Log's end-of-shift view, so the two handover features agree instead of competing.
● Acceptance:
  ■ For the owner's worked example, the flow fills every node the data can answer. It names the unanswered ones, and it produces a 3-sentence synopsis with every statement sourced.
  ■ The end-of-shift run finishes within 5 minutes and sends nothing out of the container.
  ■ A planted figure that is not in its cited post never reaches a synopsis.

**V0.21: the 48-hour look-ahead and timers (size L).**
● Add the `sgp4` package. Fact: no propagator is installed today. It is pinned, relocked and licence-checked like any dependency.
● Bring back a scoped element-set pull for objects with live events only, with a freshness guard.
● Add `look_ahead.py` with tests against reference cases, the look-ahead strip, one-click timers with `origin=look-ahead`, and upcoming points in the synopsis's third sentence.
● Acceptance: for a GEO pair in an RPO NOTSO, the module lists the closest approaches, the RIC box and the lighting windows for 48 hours. Each is labelled with the element set and epoch it came from. A timer is 1 click away.

**V0.22: provider deltas, photometric context and polished wording (size M).**
● Provider pairing across manoeuvre records and the chat claims from V0.20, with the delta card.
● Photometric context: alignment with manoeuvre starts and close approaches, and time to revisit the same geometry, with a timer.
● Optional smoothing of the synopsis wording by the local model, with the no-new-facts check.
● Acceptance:
  ■ The NorthStar versus KBR example appears as a highlighted disagreement on apsis and period change, each figure linked to its source.
  ■ A smoothed draft that adds a fact is refused, and the template wording stands.

### Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Element-set accuracy at GEO | Fact: TLE and SGP4 positions carry errors of the order of kilometres. Inference: an RPO box computed from TLEs is indicative only | Label every computed figure "from element set [epoch], indicative". Prefer provider state vectors if the UDL offers them (`TBC, re-verify`). Never present a computed figure as observed |
| The local model makes up a figure | A wrong number reaches a handover | Only claims whose figure appears word for word in the cited post are kept. The lead sees the source post for every claim |
| The local model is too slow | The run does not cover every live event in 5 minutes | Priority order, cache per thread, and "template only" marked on what was not read. The trial sets the model size |
| Memory | Holly is stopped for running out of memory, taking the loops with it | 8Gi allocation; the model runs in a child process that ends after the run; peak memory measured in the trial |
| A bigger image and native code | Longer builds, a larger container scan, new CVEs to answer | Weights pinned by SHA-256; toolchain only in the build stage; the binding version pinned and audited like any dependency |
| The App Store is not approved for this data | Running the model inside Holly does not settle the question | The owner and the data owner confirm it, recorded in ADR-016 |
| Wrong thread-to-NOTSO links | A synopsis cites chat about a different event | Suggest, never assume; only a lead-confirmed link counts |
| Provider fields mis-read | Wrong deltas reach a handover | Check against a real record in phase 0. Show the raw value beside every delta |
| CPU in the single worker | The look-ahead slows the other background loops | Compute on request for named pairs only, cache by element-set id, and bound the steps |
| SonarQube smells in a large new UI | Upload fails Code Quality, as in V0.16 and V0.17 | Run the local Sonar probe on every changed file, configs included, before packaging |
| Two handover features | Shift Log and the new tab disagree | Confirmed handovers feed the Shift Log summary (V0.20) |
| Group-key trip-wire | Fact: `SECURITY.md:34` requires the source in the group key before a second notice source is ingested | Provider comparison uses manoeuvre records, not a second notice source, so the key is untouched. Revisit if a second NOTSO source is added |

### Answers needed from the owner

1. Confirm the readings in the table under "How I read the dictated memo".
2. Confirm the App Store environment is approved to hold and process the JCO data and the threads the local model reads (phase 0, item 1).
3. Whether to stop the existing assistant sending chat to Anthropic (phase 0, item 2).
4. Agreement to raise Holly to 8Gi memory and 6 CPU, and the platform team's answers: will the build accept an image several GB larger, and may it fetch the model weights from outside?
5. 1 stored KBR record, 1 NorthStar record and 1 example Mattermost event thread, for phase 0 item 4, checked inside Bluestaq's environment.
6. The provider names and aliases to recognise.
7. Which event types get a guided flow first, and the full list.
8. How the synopsis reaches the MMB.
9. The module's name.
10. The shift change times in UTC, for the end-of-shift run.
