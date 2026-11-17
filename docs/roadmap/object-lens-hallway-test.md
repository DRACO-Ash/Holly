# Object Lens hallway test: facilitator guide

Status: ready to run. The prototype is `docs/roadmap/object-lens-prototype.html`, one file that opens in Edge or Chrome on Windows with a double-click. It needs no install, no server and no network, and it makes no network call (checked on 17 November 2026: every request it made was to the file itself). Every object, notice, record, message, timer and note in it is synthetic: names start `SAMPLE-`, catalogue numbers are `90xxx`, people are `sample.*`. Decision this test feeds: Phase 1 of the Object Lens (`docs/roadmap/object-lens-proposal.html`).

## What it is

● The real Holly V0.19 dashboard, built from the repository, answering every page from synthetic data inside the browser.
● The lens drawn on top: catalogue and NOTSO numbers as links, the lens drawer, Find (Ctrl K or `/`) and the watch strip. A switch turns it off, so the same file shows today's Holly.
● A facilitator console that runs the test, times each task and exports the results as CSV.

## Before the day

● 3 analysts, 20 to 25 minutes each, one at a time, at your laptop. Bring nothing else: the file holds the whole test.
● Open the file once beforehand and click **Explore freely, lens on** to see it, then **back to set-up**.
● Do not show participants the lens before their lens half.

## Running a participant

1. Open the file. The set-up screen shows the next participant code (P1, P2, P3) and suggests the order. Keep the suggestion: P1 and P3 start in today's Holly, P2 starts with the lens. Click **Start session**; the page reloads with a fresh synthetic world.
2. Read the question in the console aloud. Press **Start task** as you finish reading. The page returns to the dashboard and the clock starts.
3. When they answer, press **Correct**, **Wrong** or **Gave up**. **Key** shows the expected answer to you; minimise the console with **–** if it is in their way.
4. Ask "How easy was that, from 1, very hard, to 7, very easy?" and press their number.
5. After 5 tasks the console shows half 2. Read the short script it gives, then **Start half 2**. The questions are the same 5 about a different object, in the other condition.
6. At the end, ask "What, if anything, would you change about the lens?" and note the answer. Click **Next participant**.

Do not help with where to look. If they ask, say "wherever you would look on shift". Stop a task at 3 minutes and mark it **Gave up**.

## The 5 questions

Asked about set A's object (SAMPLE-LEO 2612, 90762) in one half and set B's (SAMPLE-SJ 21, 90330) in the other. The two objects have stories of the same shape, so the halves are equal in difficulty.

1. What is the next timer due on the object, and roughly when?
2. Which provider reported its most recent manoeuvre, and roughly when?
3. Someone on the floor raised a concern about it. Who, and in which channel?
4. What is the NOTSO number of its open notice, and what urgency did the assistant give it?
5. What does the latest analyst note on it say needs doing?

Each is answerable in today's Holly (checked on 17 November 2026): the timer on the Shift log, the record on Maneuvers, the message on Comms, the notice on Notifications and the note on Handover. The set-up screen holds the full answer key.

## What is recorded

One row per task: participant, half, condition, set, task, question, outcome, seconds, page changes, lens opens, Find opens, link clicks, ease (1 to 7) and start time in UTC. Results stay in the browser until **Export CSV** on the set-up or end screen. Export after the last participant, then **Clear results**.

## Reading the result

The proposal's success measure: median time at least halved with the lens, no task needing more than 2 page changes, and no more wrong answers. The stop rule: no clear gain means Phase 1 is shelved. With 3 participants this is a direction, not a statistic (inference); read the times alongside the comments.

## Known limits of the prototype

● "Since you last looked" starts 4 hours back the first time an object is opened, standing in for the start of a shift, and is kept in this browser only. Phase 2 would keep it per user on the server.
● Numbers inside whole-row links (dashboard and notification list rows) stay plain, as nesting a link inside a link is not valid; Find covers them.
● Notes, timers and thread decisions made during the test change only the in-browser world and are reset for the next participant.
● Built from V0.19 on 17 November 2026. Rebuild with `prototypes/object-lens/build.sh` after Holly changes.
