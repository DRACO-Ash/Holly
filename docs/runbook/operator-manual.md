**BLUESTAQ LIMITED** | Operator Manual

# Operator Manual

**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify (the Daily Operations Dashboard Team, Bluestaq Limited, owned the edition this one replaces)
**Version:** 0.4
**Last updated:** 2026-10-17
**Audience:** Operators and on-call engineers responsible for keeping Holly healthy on the Bluestaq App Store.

> **BLUF**
>
> Holly is one container on the Bluestaq App Store, with its database and file store from platform add-ons. When something is wrong, check in this order: do the probes answer, can Holly reach its database, are its integrations configured, and what does the boot log say. This is your playbook for daily checks, releases, logs, on-demand pulls, accounts, common failures and disaster scenarios.

**SECTION 01**

## At a glance

● **One container:** a gunicorn master and one uvicorn worker, serving the dashboard, the API under `/api/v1` and the platform probes on `PORT` or 8080.
● **Database:** PostgreSQL from the App Store POSTGRESQL add-on.
● **Files:** uploaded procedures on the FILE_STORAGE add-on's volume (`/data/procedures` unless configured otherwise).
● **TLS:** terminated by the platform before requests reach Holly.
● **Outbound:** UDL, the team's Mattermost server and the Anthropic API, over HTTPS.

Holly's address is `https://<slug>.apps.bluestaq.com`; the slug is `TBC, re-verify`. Below, `<host>` stands for that address. There is no nginx and no Docker Compose deployment: the Daily Operations Dashboard's four-container stack is retired (ADR-012).

**SECTION 02**

## Daily checks

| Check | How | Healthy result |
|-------|-----|----------------|
| Dashboard reachable | Browse to `https://<host>` | The sign-in page renders |
| Liveness | `curl -i https://<host>/healthz` | HTTP 200, body `ok` |
| Status | `curl https://<host>/status` | `"storage": {"procedures": "ready"}` and the expected `version` |
| Database and UDL credentials | `curl https://<host>/api/v1/health/detailed` | `"status": "ok"`, `"database": "ok"`, `"udl_credentials": "configured"` |
| Notifications current | **Audit log** page, action type `udl.notification.ingest` | A row within the last hour, with `pulled` greater than 0 when UDL has new notices |
| Manoeuvres current | **Audit log** page, action type `udl.maneuver.ingest` | A row within the last 10 minutes |
| Assistant working | The Dashboard page's **Pending** count | Not growing from one hourly cycle to the next, apart from notices marked `Not sent to the assistant` (section 10) |
| Platform state | The App Store's view of the app | `TBC, re-verify` where and what it shows |

What the read-outs return:

```
GET /healthz                  ok
GET /status                   {"service": "holly", "version": "<version>", "config": {"PORT": {"set": <true|false>, "length": <n>}, "APP_ENV": {...}, "STORAGE_MOUNT_PATH": {...}, "PROCEDURE_STORAGE_PATH": {...}}, "storage": {"procedures": "ready"}}
GET /api/v1/health            {"status": "ok"}
GET /api/v1/health/detailed   {"status": "ok", "version": "<version>", "environment": "production", "components": {"database": "ok", "udl_credentials": "configured"}}
```

The probes (`/healthz`, `/health`, `/readyz`, `/livez`, `/ping`) answer 200 without touching anything, so they show the process is up, not that it can serve data. `/status` reports each of four inputs as set or not, and its length, never its value. `/api/v1/health` and `/api/v1/health/detailed` query the database; the second reports `"status": "degraded"` and `"database": "down"` when it cannot. None of these needs sign-in.

**SECTION 03**

## Releases, settings and rollback

Releases go through the App Store and are human-gated: they run through the `release-and-deploy` skill and the `deploy-gate` agent, never automatically. Before every upload, from a clean, committed checkout:

```sh
sh scripts/verify.sh              # the verification loop; ends "VERIFY: PASS (...)"
sh scripts/simulate-pipeline.sh   # package, check out and test the way the platform does
sh scripts/smoke-container.sh     # build the image from the upload, run it with PostgreSQL, probe the contract
```

`sh scripts/package-appstore.sh` writes the upload, `dist/appstore.zip`, only when the last verdict from each gate in the committed `scripts/upload-record.txt` is a PASS for the upload as it stands (`scripts/check-reviews.sh`); every run first removes the last upload zip. It packages only from the tip of a local branch that is not behind its upstream, so fetch and pull first: the record counts the verdicts committed at or before the commit packaged. An upstream that is configured but does not resolve refuses; a branch with no upstream, such as one just made from an older commit, is not compared, and the run says so, so package from the branch the verdicts were recorded on. It prints the commit it packaged, which `unzip -z dist/appstore.zip` also shows: package just before uploading, and upload that file. The two rungs above package rehearsals into their own temporary files; a rehearsal is never the upload.

**Settings** are App Store environment variables; the full reference is in [developer setup](../developer/setup.md). According to the platform reference in this repository, saving them replaces the whole set at once (at most 50 variables), and a separate step applies them ([.claude/skills/app-store-deployment/SKILL.md](../../.claude/skills/app-store-deployment/SKILL.md)); always save the complete set. Holly needs at least:

● `APP_SECRET_KEY`, at least 32 characters.
● The database settings. Whether the POSTGRESQL add-on provides `DATABASE_URL` or the `POSTGRES_*` parts is `TBC, re-verify`.
● `UDL_USERNAME` and `UDL_PASSWORD` for UDL data, and `ANTHROPIC_API_KEY` for the assistant.
● `MATTERMOST_URL`, `MATTERMOST_BOT_TOKEN` and `MATTERMOST_CHANNEL_IDS` if the Comms page is used.

Leave `STORAGE_MOUNT_PATH` to the FILE_STORAGE add-on, which injects it; do not set it by hand. Leave `APP_ENV` at its default, `production`. Leave `ASSISTANT_CLEARED_MARKINGS` at its default, `["U"]`, unless the data owner clears a further UDL classification marking for the assistant; who that is, and whether the `JCO` source's own marking may be cleared, is `TBC, re-verify`.

**Starting, stopping and restarting** the app are platform operations: `TBC, re-verify` how. Rate-limit counters and the daily assistant token count start again from zero at every restart.

**Rollback** is a resubmission of the previous package; the platform has no separate rollback (platform reference above). Migrations only move forward at start, so a package older than the database's newest migration stops at boot with Alembic's `Can't locate revision identified by '<revision>'`. Rolling back across a migration therefore needs the database restored to match the older package, or a fixed package that carries the newer migration.

**SECTION 04**

## What happens at start

1. gunicorn reads its configuration. A malformed `PORT` stops it with `PORT must be a whole number from 1 to 65535, got '<value>'`.
2. The master applies pending migrations under a PostgreSQL advisory lock, logging `{"event": "migrations", "status": "starting"}` and then `"applied"`. Reading the database URL here validates every setting, so a misconfiguration stops the container at this step with one line that names each problem and repeats no value, for example `Error: Holly cannot start: APP_SECRET_KEY: Field required` or `Error: Holly cannot start: UDL_BASE_URL must use https outside development`. A failed migration stops it here too, with Alembic's error.
3. The worker starts and proves the procedure store accepts a write. On success it logs `{"event": "boot", "version": "<version>", "storage": "/data/procedures", "storage_writable": true, "background_refresh": true, ...}`. On failure it logs `"storage_writable": false` with the `errno` and `error`, and the container stops.
4. The background loops start, each logging a line such as `Background notifications loop enabled: every 3600s`.

At shutdown Holly stops the loops, closes its database connections and logs `{"event": "shutdown", ...}`.

**SECTION 05**

## Logs

Holly writes one JSON object per line to standard output. Named events (`boot`, `migrations`, `shutdown`, `llm.call`) carry an `event` field; everything else carries `time`, `level`, `logger` and `message`. Every line carries `"service": "holly"` and a `request_id`, which is `-` outside a request. Holly does not log each request: the access log is set to warnings only. No line carries a secret value. Where the App Store shows container logs is `TBC, re-verify`.

**Correlating a request.** Every response carries an `X-Request-ID` header. Capture it (browser developer tools, `curl -i`, or your client's logs) and search the logs for `"request_id": "<id>"`. A caller's own `X-Request-ID` is kept and echoed when it is a plain token of at most 128 letters, digits, `.`, `_`, `:` or `-`; anything else is replaced with a fresh id.

**Lines worth knowing:**

● `llm.call`: one per assistant call, with `purpose` (`assistant.evaluate`, `assistant.event_summary`, `shift_log.polish` or `shift_log.summary`), `model`, `tokens` and `stop_reason`.
● `Anthropic API error (<type>): ...`: the Anthropic API's own error text. Analysts see only a fixed message for its class (section 10).
● `Notification ingest complete (window: last 120h)` and `Maneuver ingest complete (window: last 48h)`: a background pull succeeded.
● `Notification ingest skipped: UDL auth failed (...)` or `Notification ingest failed: ...`: see section 10.
● `Skipping UDL record <id>: <column> <problem>`, for example `status is longer than 20 characters`, `description holds a character PostgreSQL cannot store` (a NUL or a lone surrogate) or `raw holds a number PostgreSQL JSON cannot store` (NaN or an infinity): a record its table cannot store, skipped and counted in `skipped`; the rest of the pull is stored. The line names the column, never the value.
● `Skipping a UDL record that is not a JSON object`: an element of UDL's answer that is not a record, skipped and counted in `skipped`.
● `Stopping auto-evaluate cycle early: ...`: a persistent assistant failure; see section 10.
● `Auto-evaluate of notification <id> failed; stopping`, followed by a traceback: evaluating that notice, storing its evaluation or writing its audit row failed once the notice may have been sent, so no further notice was sent for evaluation in that cycle.
● `Event summary for <event key> failed; stopping`, followed by a traceback: the narrative, its audit row or the commit that stores both failed once the event's publications may have been sent, so no further event was sent in that cycle.
● `Event summary failed for <event key>`: the event's stored publications could not be read, so nothing was sent for it; the next event still runs.
● `Sign-in refused: too many attempts from <address>` or `Sign-in refused: 4 password checks already running`: see section 10.
● `Mattermost channel <id> skipped: ...`: the bot cannot read that channel.

**SECTION 06**

## Pulling data on demand

**Notifications.** On the Notifications page, **Pull from UDL** runs the whole notification cycle at once: the UDL pull, the assistant's evaluations of new notices, and the event narratives. It answers when the cycle completes, joins a cycle already running, and counts against the caller's assistant allowance (30 requests in any 10 minutes). The ingest audit row it produces carries no user id.

**Through the API.** Sign in to get a token. Put the credentials in a file rather than on the command line, and delete it afterwards:

```sh
# login.json holds {"username": "<name>", "password": "[REDACTED:password]"}
curl -s https://<host>/api/v1/auth/login -H 'Content-Type: application/json' -d @login.json
```

The answer is `{"access_token": "<token>", "refresh_token": "<token>", "token_type": "bearer"}`. The access token lasts 30 minutes by default.

```sh
export TOKEN=<the access_token value>
curl -s -X POST https://<host>/api/v1/notifications/ingest \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"msg_type": "TACREP_NOTSO", "created_at_gte": "<ISO 8601 time>", "data_mode": "REAL", "source": "JCO", "max_results": 100}'
```

The answer is `{"pulled": <n>, "inserted": <n>, "updated": <n>, "skipped": <n>}`, and the audit row records your user id and address. `max_results` may be at most 10,000; a pull that names none, as the background pulls do, gets UDL's own default page size (`TBC, re-verify` its value). `POST /api/v1/elsets/ingest` takes `{"epoch_gte": "<ISO 8601 time>", "sat_no": <number>, "max_results": <number>}` and answers the same way; it is the only way element sets arrive. Manoeuvres and Mattermost chat are pulled only by the background loops.

**SECTION 07**

## Inspecting ingest history

The **Audit log** page (operators and admins) filters by action type: `udl.notification.ingest`, `udl.maneuver.ingest`, `udl.elset.ingest` or `mattermost.ingest`. Each row's detail holds the request and the counts. Through the API, with an operator's or admin's token:

```sh
curl -s 'https://<host>/api/v1/audit?action_type=udl.notification.ingest&limit=20' -H "Authorization: Bearer $TOKEN"
```

Rows come newest first. With a database shell (on the App Store, `TBC, re-verify`):

```sql
SELECT timestamp, user_id, ip_address, detail
  FROM audit.audit_log
 WHERE action_type = 'udl.notification.ingest'
 ORDER BY timestamp DESC
 LIMIT 20;
```

**SECTION 08**

## Accounts

### Create or reset an admin

```sh
python -m app.cli.create_admin --username <name>
```

Run it in the running container, or on any machine with Holly's database settings. It takes the password from `ADMIN_PASSWORD` in that shell's environment, or prompts for it without echo; it never accepts one as a flag, and refuses one shorter than 12 characters. It prints `Admin user '<name>' created.` or `updated.` and writes an `auth.user.admin_upsert` audit row. For an existing username it resets the password and makes the account an active admin, whatever its role was. Whether the App Store offers a shell in the running container, and whether the add-on database is reachable from outside the platform, are both `TBC, re-verify`.

### Analyst and operator accounts

No route or command creates an `analyst` or `operator` account, changes a role, or deactivates a user: `create_admin` creates admins only. Until one exists, these need a direct change to the `app_user` table, and the procedure for that is `TBC, re-verify`. Setting `is_active` to false stops a user at once: every request checks it, so the user's tokens stop working too.

### Sign everyone out

Rotate `APP_SECRET_KEY` (at least 32 characters) and apply the settings. Every access and refresh token stops verifying, and every user signs in again. A user's own **Sign out** revokes only their refresh token; their access token stays valid until it expires, up to 30 minutes by default.

**SECTION 09**

## Database and storage

● **Migrations** apply themselves at every start. Do not run Alembic by hand against the App Store database, and never edit `alembic_version`.
● **Database shell:** whether the App Store offers one for the POSTGRESQL add-on is `TBC, re-verify`.
● **Backups** of the add-on database and of the FILE_STORAGE volume, their frequency and their retention are the platform's: `TBC, re-verify`.
● **Audit chain:** run `python -m app.cli.verify_audit` wherever the database settings are available. It prints `Audit chain intact: <n> entries verified.` and exits 0, or names the first broken row on standard error and exits 1. Rows written by the Daily Operations Dashboard before Holly V0.2 cannot be verified. Full mechanics are in [docs/audit/overview.md](../audit/overview.md).

**SECTION 10**

## Common failures and fixes

### Symptom: the container restarts or never becomes ready

Read the start of its log (section 04). The causes Holly names itself:

● `PORT must be a whole number ...`: fix or remove the `PORT` variable.
● `Error: Holly cannot start: ...`: a setting failed validation. Fix each setting the line names; it never repeats a value. A missing or short `APP_SECRET_KEY`, missing database settings, a `DATABASE_URL` that does not read as a postgres URL with a host (an unencoded `@` in the password does this: write it as `%40`), a `*` origin, an http UDL or Mattermost URL, `UDL_VERIFY_SSL=false` or a relative procedure path each stops the start.
● An Alembic error: a migration failed. If it reads `Can't locate revision identified by ...`, the package is older than the database (section 03). Escalate any other migration failure to engineering.
● `"storage_writable": false`: the procedure store refused a write. The `errno` and `error` say why; check the FILE_STORAGE add-on and `PROCEDURE_STORAGE_PATH`.

### Symptom: `/api/v1/health` answers 500, or `/api/v1/health/detailed` shows `"database": "down"`

Holly cannot reach its database. Check the POSTGRESQL add-on's state and the database settings Holly receives.

### Symptom: every signed-in request answers 401

`APP_SECRET_KEY` changed, which invalidates every token: expected after a rotation, and users sign in again. Otherwise the user's access token expired and the refresh failed; the same answer applies.

### Symptom: HTTP 429 `Too many requests`, `Too many sign-in attempts from this address` or `Too many failed sign-ins`

Holly's limits, all counted in the one worker and reset when the container restarts ([src/app/core/rate_limit.py](../../src/app/core/rate_limit.py)):

| Limit | Applies to | Allowance |
|-------|------------|-----------|
| Coarse | Every request under `/api/` and `/status`, per client address | 600 in any 60 seconds |
| Sign-in attempts | Every sign-in attempt, per client address, counted before any password check | 30 in any 60 seconds |
| Sign-in | Checked sign-ins, per username, each counted before its check; a success clears the count | 10 in any 15 minutes |
| Assistant | Evaluations, **Pull from UDL**, new shift-log entries, re-polish and the end-of-shift narrative, per user | 30 in any 10 minutes |
| Daily tokens | Every assistant call, across all users, per UTC day | `LLM_DAILY_TOKEN_CAP`, 2,000,000 by default |

The first four answer 429 with `Retry-After`, with one exception: a new shift-log entry made after the assistant allowance is spent is still saved, unpolished, with `Not polished: the assistant limit is reached. Re-polish in <n> seconds.` The daily token cap refuses nothing at the door: each assistant call holds its output allowance and an estimate of its input against the cap before it is sent, and a call the rest of the day's cap cannot cover fails. An evaluation, polish or end-of-shift narrative then stores the error; an event narrative keeps its earlier text. The probes and the dashboard's static files are never limited. Behind the platform ingress, the client address may be the ingress's own for every caller (see the [security overview](../security/overview.md)); if so, all users share one coarse allowance and one allowance of sign-in attempts, which anyone who can reach Holly can spend, with no credentials, by one attempt every 2 seconds. Setting `FORWARDED_ALLOW_IPS` to the ingress's addresses ends the sharing.

### Symptom: sign-in answers HTTP 503 `Sign-in is busy. Try again in a moment.`

At most 4 password checks run at once, each on a worker thread, so a burst of sign-ins cannot stall the one worker. A sign-in beyond them is refused at once, with `Retry-After: 1`, logged as `Sign-in refused: 4 password checks already running`, not audited and not counted against the username. It clears as the running checks finish.

### Symptom: HTTP 413 `Request body too large`

A request body over 256 KiB is refused before it is read, except a procedure upload (`POST /api/v1/procedures`), whose limit is 11 MiB. A procedure file over 10 MiB is refused with `File exceeds 10MB limit`.

### Symptom: UDL pulls fail

A pull through the API (`/api/v1/notifications/ingest` or `/api/v1/elsets/ingest`) answers HTTP 502 with Holly's own message. The background loops, and **Pull from UDL**, which runs the background cycle, log the same message as a warning and complete without new data:

| Message | Meaning and fix |
|---------|-----------------|
| `UDL credentials are not configured (UDL_USERNAME / UDL_PASSWORD).` | Set both settings and apply. |
| `UDL rejected credentials (401).` | The credentials are wrong or were rotated. Confirm them with the UDL account owner, update the settings and apply. |
| `UDL request failed: <error type>` | UDL is unreachable: outbound access from the platform (`TBC, re-verify`), DNS or a UDL outage. |
| `UDL returned HTTP <code>.` | UDL refused the request; the response body is in Holly's log, cut to 200 characters. |
| `UDL response was not valid JSON.` | UDL answered with something unexpected; check UDL's status. |

`UDL_VERIFY_SSL=false` is refused outside development, so it is not a workaround on the App Store.

### Symptom: the Dashboard's **Pending** count does not clear

A notice stays **Awaiting analysis** until it has a successful evaluation. The background cycle evaluates only notices that have no evaluation at all, so a notice whose evaluation failed is not retried automatically: open it and select **Re-evaluate**. The panel shows the stored error. Common causes:

● `ANTHROPIC_API_KEY is not configured`: set the key and apply.
● `The daily assistant token cap is spent; assistant calls resume tomorrow (UTC).`: what is left of the day's cap cannot cover the call. Wait, or raise `LLM_DAILY_TOKEN_CAP` and apply.
● `The assistant rejected Holly's API key.`, `The assistant refused this request for Holly's API key.`, `The assistant does not offer the model Holly is set to use.`, `The assistant is limiting Holly's requests; try again later.` or `The assistant account has no credit left.`: a persistent fault in the key, its permissions, `ANTHROPIC_MODEL`, Anthropic's rate limit or the account's credit. It stops the background phase early, logged as `Stopping auto-evaluate cycle early`.
● `The assistant rejected the request.` or `The assistant could not be reached or failed; try again.`: not persistent, so the background phase moves on to the next notice. Re-evaluate later.
● `Model response was truncated at <n> tokens ... Raise ANTHROPIC_MAX_TOKENS.`: raise it and re-evaluate.

The Anthropic API's own error text never reaches the panel; it is in the server log as `Anthropic API error (<type>): ...`.

A notice the Dashboard marks `Not sent to the assistant: its classification marking is not cleared.` stays there: its UDL classification marking is not in `ASSISTANT_CLEARED_MARKINGS`, so the background cycle never selects it, and **Run assistant** or **Re-evaluate** stores `Not sent to the assistant: this notice's classification marking is not cleared for it (ASSISTANT_CLEARED_MARKINGS).` without calling the assistant. Clearing a further marking is the data owner's decision (section 03); once the setting lists the notice's marking, select **Run assistant** or **Re-evaluate**.

### Symptom: the Comms page stays empty

Check `MATTERMOST_URL` (https), `MATTERMOST_BOT_TOKEN` and `MATTERMOST_CHANNEL_IDS`, and that the bot account is a member of every listed channel. A channel the bot cannot read is logged as `Mattermost channel <id> skipped: Mattermost denied access (403): is the bot in the channel?`. A wrong token logs `Mattermost rejected the bot token (401).`

### Symptom: a procedure upload is refused

● `A procedure with identical content already exists` (409): the same file is already uploaded.
● `Uploaded file is empty` (400), or `File exceeds 10MB limit` (413).

### Symptom: event timers are silent

Browsers play sound only after the analyst interacts with the page: each time Holly loads, sound starts after the first click or key press, and until then the banner offers **Enable alerts**. Browser notifications also need the browser's permission; without it the banner says `Browser notifications denied; audio only.` A pre-alert sounds once, in the first open Holly page that notices it, because Holly then records it as acknowledged.

**SECTION 11**

## Disaster scenarios

> **KEY DECISION**
>
> If audit log integrity is ever in doubt, stop Holly before doing anything else and preserve the database. The hash chain is forensic evidence; do not delete or modify any row.

### Audit log integrity in doubt

1. Stop Holly, so nothing more is written (`TBC, re-verify` how on the App Store).
2. Preserve the database: a snapshot or backup through the add-on (`TBC, re-verify`).
3. Run `python -m app.cli.verify_audit` against it and record its output.
4. Escalate to engineering and to the security point of contact for Holly (`TBC, re-verify` who that is).
5. Do not delete or modify any row, and do not disable the append-only trigger.

### Database lost or corrupted

Restore it from the add-on's backups (`TBC, re-verify` how). Then start Holly, which applies any missing migrations, and run `python -m app.cli.verify_audit`. Procedure rows whose files are missing from the store still list; see the next scenario.

### Procedure store lost

The rows stay and still list, but a download answers 404 `The file for this procedure is missing; upload it again.`, previews are empty and the assistant reads nothing from those files. For each one, delete the procedure in the dashboard (a missing file is not an error) and upload it again. Uploading the same content without deleting first is refused as a duplicate. A procedure uploaded to the Daily Operations Dashboard before Holly V0.2 can show the same symptom, because the dashboard wrote every upload with the same extension to one file.

### Suspected secret leak

1. Rotate the credential at its source: `APP_SECRET_KEY`, the UDL password, the Mattermost bot token, the Anthropic key, or the database password through the add-on (`TBC, re-verify` how).
2. Update the App Store settings and apply them.
3. Treat the old value as compromised; rewriting Git history does not un-leak it.
4. Record an incident.

### Suspected stolen token

Holly has no route that revokes another user's tokens. Deactivating the user (section 08) stops that user at once. Rotating `APP_SECRET_KEY` stops every token for every user.

**SECTION 12**

## See also

● [Architecture overview](../architecture/overview.md)
● [Security overview](../security/overview.md)
● [Audit logging overview](../audit/overview.md)
● [Developer setup](../developer/setup.md), for the settings reference
● [Analyst training manual](../user-handbook/training-manual.md)

Bluestaq Limited | Holly documentation | 2026
