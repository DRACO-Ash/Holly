**BLUESTAQ LIMITED** | Analyst Training Manual | **COMMERCIAL IN CONFIDENCE**

# Analyst Training Manual

**Document classification:** Commercial in Confidence
**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify (the Daily Operations Dashboard Team, Bluestaq Limited, owned the edition this one replaces)
**Version:** 0.3
**Last updated:** 2026-10-14
**Audience:** Watch analysts new to Holly, plus the trainers delivering induction. Sections labelled **Trainer note** are for delivery, not for the trainee handout.

> **BLUF**
>
> Holly pulls UDL notifications and manoeuvre records and the team's Mattermost chat in the background, has an assistant evaluate each new notice cleared for it against your uploaded procedures, and shows what needs your attention first. This manual walks the trainee through signing in, the Dashboard, Notifications, Maneuvers, Comms and Procedures pages, the shift log and event timers, common workflows, and what to do when something goes wrong.

**SECTION 01**

## What Holly is for

Holly is your watch-stand surface. It pulls Tactical Reports and Notices to Space Operators and manoeuvre records from the Unified Data Library (UDL), and recent chat from the team's Mattermost channels, and puts them in one browser tab. An assistant reads each new notice cleared for it against the procedures your team has uploaded and suggests next actions, most urgent first. You keep the shift log and your event timers in the same place. Holly was built from the Daily Operations Dashboard.

**Why care?** Time on task during a watch is the metric. Every minute you save stitching context together is a minute back on analysis.

**SECTION 02**

## Glossary

| Term | Meaning |
|------|---------|
| **SDA** | Space Domain Awareness. The mission area Holly serves. |
| **UDL** | Unified Data Library. Holly pulls notifications, manoeuvre records and element sets from it, and never writes to it. |
| **TACREP** | Tactical Report. |
| **NOTSO** | Notice to Space Operators. |
| **TACREP_NOTSO** | The message type under which UDL serves both, through one endpoint. Holly shows them together on the Notifications page. |
| **Publication** | One version of a notice as UDL published it. UDL republishes a notice as it evolves; Holly shows the latest publication of each and keeps every one. |
| **NORAD catalogue number / sat number** | The persistent integer identifier for a tracked object. The ISS is `25544`. |
| **Manoeuvre record** | A UDL record of a satellite manoeuvre, published by fusion providers. Holly's page for them is labelled **Maneuvers**. |
| **Assistant** | Anthropic's Claude, called by Holly to evaluate notices, describe how an event evolved, tidy shift-log entries and draft the end-of-shift narrative. Its output is advice. Holly shows it a notice only when the notice's classification marking is cleared for it. |
| **Procedure** | A document your team uploads to Holly. The assistant reads every procedure when it evaluates a notice. |
| **Event timer** | A countdown you set to an upcoming event, with a pre-alert before it and an alarm at it. |

> **TRAINER NOTE**
>
> Walk the trainee through the glossary before signing in. Use the ISS (`25544`) as the worked example; it is the example number the Maneuvers page itself suggests.

**SECTION 03**

## Signing in

1. Open `https://<slug>.apps.bluestaq.com` in your browser (the slug is `TBC, re-verify`; your operator will give you the address).
2. Enter your username and password and select **Sign in**.
3. You arrive on the **Dashboard** page.

There is no self sign-up. If you do not have an account, ask the on-call operator.

You stay signed in while you use Holly: your 30-minute access renews itself in the background, and each renewal lasts 7 days, unless your operator has changed those defaults. You sign in again after 7 days without using Holly, after you sign out, or if the operator signs everyone out. **Sign out**, in the header, clears your session from the browser and revokes it on the server, so it cannot be renewed. After 10 failed sign-ins for one username within 15 minutes, or 30 sign-in attempts from one address within a minute, Holly refuses further attempts for a while and says how many seconds to wait. If other sign-ins are being checked at that moment, Holly may answer `Sign-in is busy. Try again in a moment.`; sign in again shortly.

> **TRAINER NOTE**
>
> Stress that Holly records state changes against the trainee's user id: signing in and out, uploading or deleting a procedure, shift-log entries and narratives, timers, and assistant evaluations they request. Reading pages is not recorded.

**SECTION 04**

## Finding your way around

● **The header** shows Holly, your username and **Sign out**.
● **The timer banner**, under the header, appears on every page while an event timer is firing, and when sound alerts are not yet enabled.
● **The side navigation** lists **Dashboard**, **Notifications**, **Maneuvers**, **Comms**, **Procedures** and **Shift log**. Operators and administrators also see **Audit log**.

Times are shown in UTC unless a field says otherwise.

**SECTION 05**

## The Dashboard page

The Dashboard answers one question: what needs your attention. It covers the TACREP_NOTSO notices from the last 5 days (your operator can change the window), the latest publication of each and at most the 100 most recent, each evaluated by the assistant against your uploaded procedures when its classification marking is cleared for it.

● **The counts** across the top show how many notices sit at **High**, **Medium** and **Low** urgency, how many are **Pending**, and how many are **Info only**.
● **The feed** groups notices by urgency, most urgent first and newest first within each group. A notice's urgency is the most urgent of the actions the assistant recommends. **Informational** means the assistant recommended no action. **Awaiting analysis** means there is no evaluation yet, or the last one failed. A notice marked `Not sent to the assistant: its classification marking is not cleared.` stays there: Holly does not send it to the assistant.
● **Each notice** shows its identifier, its UDL creation time, its event class, the **Event evolution** narrative (with the number of publications when there is more than one), the assistant's summary and its top action, marked **Next:**. The narrative is written only from publications whose marking is cleared for the assistant, so it can lag a notice whose newest publication is not cleared.
● **Select a notice** to open its detail page.

The page refreshes itself every 60 seconds; **Refresh** reloads it at once. New notices arrive with the hourly pull, or sooner when someone selects **Pull from UDL** on the Notifications page.

**SECTION 06**

## The Notifications page

The list of every stored notice, one row per notice, showing its latest publication.

### Filtering, sorting and paging

● **Event type** narrows the list to one type, for example `other`, `maneuver` or `launch`; type it and select **Apply**.
● **Status** narrows it to `OPEN` or `CLOSED`.
● **Clear** removes the filters; **Refresh** reloads the list.
● Select the **Notice**, **Status**, **Type** or **UDL created** column heading to sort by it; select it again to reverse the order. The default is UDL created, newest first.
● **Sat IDs** shows up to three satellite numbers and how many more there are.
● **Previous** and **Next** walk pages of 50 rows; the footer shows the total and the page.

### Pulling fresh data

Holly pulls notices from UDL every hour on its own. **Pull from UDL** runs the whole cycle at once: the pull, the assistant's evaluation of new notices, and the event narratives. It can take a while; the button reads **Pulling...** until the cycle finishes and the list reloads. If a pull is already running, yours joins it. Each pull counts towards your assistant allowance of 30 requests in any 10 minutes.

### A notice's detail page

● **Assistant:** the latest evaluation, with the model and the time it ran. It holds a summary; **Next actions**, each with an urgency, an optional deadline and the rationale; **Applicable procedures**, with why each applies; and **Open questions** the assistant could not answer. **Run assistant** evaluates a notice that has none; **Re-evaluate** runs it again, for example after a new procedure is uploaded. If the assistant could not produce a usable evaluation, the panel says why. For a notice whose classification marking is not cleared, running the assistant sends nothing: the panel says the notice was not sent to the assistant.
● **Status:** status, event type, message type, classification and data mode.
● **Identification:** the notice identifier, event id, UDL id, source, origin network, creator, author and, when the notice has one, a link to the source page, which opens in a new tab.
● **Timing:** UDL creation, publication, and the effective-from and effective-until times.
● **Associated objects:** the satellite numbers and the region.
● **Event description**, **Source artefacts** (links to the files the notice lists) and the **Raw UDL payload**, verbatim.

> **TRAINER NOTE**
>
> The assistant's output is advice, not authority. Holly checks that each reply has the right shape before it shows it, not that it is right. Have the trainee compare one recommended action with the procedure it cites and with the raw payload.

**SECTION 07**

## The Maneuvers page

UDL manoeuvre records from fusion providers, pulled in the background every 10 minutes. The assistant reads the records for a notice's satellites, from the last 30 days, when it evaluates the notice.

● **Satellite number** and **Maneuver type** (for example `ESPMV`) filter the list; **Apply**, **Clear** and **Refresh** work as on the Notifications page.
● **Sat No**, **Start**, **Stop** and **Type** sort; **Delta-V (m/s)** and **Source** are shown. The default is start time, newest first.
● Pages hold 50 rows. There is no detail page for a manoeuvre record.

**SECTION 08**

## The Comms page

Recent messages from the team's Mattermost channels that Holly is configured to read, pulled every minute, newest first, 100 to a page. Each shows the channel, the author, the time and the text. **Channel ID** filters to one channel.

The assistant reads up to 30 messages from the last 6 hours as soft context when it evaluates a notice. Holly only reads Mattermost; it never posts. An empty page means no channel is configured or the bot account is not a member of the channels; tell the operator.

**SECTION 09**

## The Procedures page

Your team's procedures, which the assistant reads every time it evaluates a notice.

### Uploading

1. Enter a **Name**, and optionally a **Description** of when the procedure applies.
2. Choose the **File** and select **Upload**.

A file can be at most 10 MB. Holly refuses an empty file, and a file whose content is identical to one already uploaded. The assistant reads the text of procedures uploaded as plain text, Markdown, JSON or CSV, up to the first 64 KiB of each; for any other file type it sees only the name and description. Write procedures as text if you want the assistant to apply them. Holly goes by the file type your browser reports, so check with **View**: if the content shows, the assistant can read it.

### Viewing, downloading and deleting

● **View** shows the procedure's details and, for the same text types, its content.
● **Download** saves the file under its original name.
● **Delete** removes the procedure and its file, after you confirm. This cannot be undone, and any signed-in user can delete any procedure.

**SECTION 10**

## The Shift log

Capture observations as you go; the assistant tidies your words into a professional record, and drafts the end-of-shift narrative when you are ready to hand over.

● **Shift date** picks the day (UTC); it starts on today. **Recent shifts** lists the days in the last 30 with entries, how many each has, and whether it has a narrative.
● **New entry:** type whatever you want, however you want, up to 10,000 characters, and select **Add to log**. The assistant rewrites it as a short, factual paragraph without opinion or blame, and Holly keeps your original words too. If the rewrite fails, the entry is saved with your original text and the error is shown.
● **Timeline:** each entry shows its time (UTC) and the tidied text. **Show raw** shows what you typed; **Edit** changes the tidied text; **Re-polish** asks the assistant again, and keeps the current text if that fails; **Delete** removes the entry after you confirm.
● **End-of-shift narrative:** **Generate** (or **Regenerate**) has the assistant write a handover from the day's entries: a headline line, a few paragraphs in time order, and a **Handover items** list of anything unresolved. It needs at least one entry. If a later attempt fails, the export keeps the last good narrative.
● **Export .md** and **Export .html** download the day's log, titled "Daily Operations Shift Log", with the narrative and every entry.

New entries, re-polishes and narratives each count towards your assistant allowance of 30 requests in any 10 minutes. Once it is spent, a new entry is still saved, without the tidy-up, and says how many seconds to wait before you **Re-polish** it.

**SECTION 11**

## Event timers

The **Event timers** panel sits on the Shift log page. Timers are shared: everyone signed in sees every timer, and anyone can dismiss or delete one.

### Setting a timer

● **Label**, for example `ISS station-keeping burn`.
● **Event ID** (optional): the event id or NOTSO number it relates to.
● **Target time**, in your browser's local time; Holly stores and shows it in UTC.
● **Pre-alert** in minutes, 0 to 720; 5 by default.
● **Recurrence:** **One-off**, **Daily**, **Weekly** or **Monthly**.

Select **Add timer**.

### What happens

1. **Pre-alert:** when the timer enters its pre-alert window, its badge reads, for example, **15-min alert**, and the first open Holly page to notice plays a sound and, if allowed, shows a browser notification. Holly then records the pre-alert as acknowledged, so other open Holly pages normally stay quiet for it.
2. **Firing:** at the target time, a **FIRING** banner appears at the top of every page and the alarm sounds at once and again every 30 seconds until someone selects **Dismiss**.
3. **Dismiss:** a one-off timer is marked dismissed and leaves the list after 12 hours. A recurring timer moves to its next occurrence instead, counted from the first one you set, so a monthly timer set for the 31st returns to the 31st after a shorter month.

Browsers play sound only after you interact with the page: each time Holly loads, sound starts after your first click or key press, and until then the banner offers **Enable alerts**. The same first interaction asks permission for browser notifications. If notifications are refused, the banner says the alerts are audio only.

**SECTION 12**

## Common analyst workflows

### Workflow 1: start of watch

1. Sign in and select **Enable alerts** if the banner offers it.
2. On the **Dashboard**, work down from **High**: open each notice, read the assistant's next actions, and check them against the cited procedure and the raw payload.
3. Set an event timer for each deadline you need to meet.
4. Add a shift-log entry for anything you act on.

### Workflow 2: "Has anything changed on this notice?"

1. Open the notice from the **Dashboard** or **Notifications**.
2. The **Event evolution** narrative on the Dashboard, and its publication count, summarise how the event has moved across publications.
3. The detail page shows the latest publication; **Raw UDL payload** shows it verbatim.
4. If the notice changed since the last evaluation, select **Re-evaluate**.

### Workflow 3: "I need the latest now"

1. On **Notifications**, select **Pull from UDL** and wait for the list to reload.
2. Return to the **Dashboard**; new notices show as **Awaiting analysis** until the assistant has evaluated them.

### Workflow 4: shift handover

1. Check that the day's entries are complete and read well.
2. Select **Generate** under **End-of-shift narrative** and review the draft.
3. Export it as `.md` or `.html` for the incoming crew.

**SECTION 13**

## What Holly does not do (yet)

● **Element sets** have no page; they are reachable only through the API.
● **Manoeuvre records** have no detail page.
● **Saved filters:** you cannot bookmark a filter.
● **Accounts:** there is no screen to create or change accounts.
● **Retry failed evaluations:** a notice whose evaluation failed stays **Awaiting analysis** until someone selects **Re-evaluate**.
● **Audit export:** there is no export of the audit log.

If you find yourself wishing Holly did something it does not, tell the team.

**SECTION 14**

## When something goes wrong

| Symptom | Action |
|---------|--------|
| The page will not load | Refresh. Then tell the operator. |
| Sign-in fails | Check your username and password. If Holly says to wait a number of seconds, wait. If it says sign-in is busy, try again in a moment. If it still fails, ask the operator whether your account is active. |
| You are sent back to the sign-in page | Your session ended; sign in again. |
| **Pull from UDL** shows a red error | If it says to try again in a number of seconds, your assistant allowance is spent: wait. Otherwise tell the operator. |
| **Pull from UDL** finishes but nothing new appears | Either UDL has nothing new, or the pull failed: UDL failures show only in Holly's log. If it persists, tell the operator. |
| A notice stays **Awaiting analysis** | Open it. If the assistant panel shows an error, select **Re-evaluate**; if the error mentions the daily token cap, evaluations resume the next UTC day. If the Dashboard says the notice was not sent to the assistant, its classification marking is not cleared and no evaluation will come; tell the operator if you expected one. |
| The Comms page is empty | No channel is configured or the bot cannot read the channels; tell the operator. |
| A timer makes no sound | Click anywhere in Holly or select **Enable alerts** in the banner, and check your browser allows sound for Holly. |
| A table is empty when you expect rows | Check your filter, then **Clear** and look again. |

The operator-facing playbook for these is in [docs/runbook/operator-manual.md](../runbook/operator-manual.md).

**SECTION 15**

## Trainer notes: delivering this material

● **Hands-on first.** Have the trainee add a shift-log entry and set a timer as soon as the glossary is covered. Holly makes far more sense once they have done it.
● **Stable example.** Use the ISS (`25544`) on the Maneuvers page; whether recent records exist for it depends on what UDL holds.
● **The audit log is the punchline.** With an operator or administrator account, open **Audit log** after the trainee's first shift-log entry and show them their own `shift_log.note.create` row.
● **Common questions and answers.**

  | Question | Answer |
  |---|---|
  | "How long is my session?" | Access lasts 30 minutes and renews itself while you use Holly; each renewal lasts 7 days by default. Signing out ends it. |
  | "Where are NOTSOs and TACREPs?" | The **Notifications** page. UDL serves both as `TACREP_NOTSO`, so they share a table and a page here. |
  | "Can I delete a pull?" | No. A fresher pull updates a notice, but Holly never removes pulled records, and the audit log is append-only. |
  | "What if UDL changes its schema?" | Holly keeps every record verbatim as well as its typed fields, so nothing is lost; new typed columns can follow in a migration. |
  | "Should I trust the assistant?" | Treat it as a quick first read. Check its actions against the procedure and the source before you act. |
  | "Is anyone watching what I do?" | The audit log records your state changes, not your page views. Use Holly accordingly. |

**SECTION 16**

## Feedback

Holly exists to make the watch easier. If anything here is unclear, or a workflow is missing, tell the team; the channel for feedback is `TBC, re-verify`.

Bluestaq Limited | Holly documentation | 2026 | **COMMERCIAL IN CONFIDENCE**
