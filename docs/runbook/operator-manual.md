**BLUESTAQ LIMITED** | Operator Manual

# Operator Manual

**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify (the Daily Operations Dashboard Team, Bluestaq Limited, owned the edition this one replaces)
**Version:** 0.7
**Last updated:** 2026-10-20
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

Holly's address is `https://holly.appstore.bluestaq.com`, the slug `holly` (the address the app owner's browser showed on 20 October 2026). Below, `<host>` stands for that address. There is no nginx and no Docker Compose deployment: the Daily Operations Dashboard's four-container stack is retired (ADR-012).

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

`sh scripts/package-appstore.sh` writes the upload, `dist/appstore.zip`, only when the last verdict from each gate in the committed `scripts/upload-record.txt` is a PASS for the upload as it stands (`scripts/check-reviews.sh`), and the committed `scripts/upload-baseline.txt` records the last upload handed over (`scripts/check-baseline.sh`); every run first removes the last upload zip. The platform scores new code against the previous upload, passed or failed, and records that nowhere in this repository, so packaging prints the files the upload changes since that baseline, and refuses an upload that has changed without a version above the baseline's. After handing a package over, append its line, `upload <full 40-hex commit> <version> <passed|failed|pending> # <zip, merge request, stage>`, in the next commit, and a later line once the outcome is known. It packages only from the tip of a local branch that is not behind its upstream, so fetch and pull first: the record counts the verdicts committed at or before the commit packaged. An upstream that is configured but does not resolve refuses; a branch with no upstream, such as one just made from an older commit, is not compared, and the run says so, so package from the branch the verdicts were recorded on. It prints the commit it packaged, which `unzip -z dist/appstore.zip` also shows: package just before uploading, and upload that file. The two rungs above package rehearsals into their own temporary files; a rehearsal is never the upload.

**Settings** are App Store environment variables; the full reference is in [developer setup](../developer/setup.md). According to the platform reference in this repository, saving them replaces the whole set at once (at most 50 variables), and a separate step applies them ([.claude/skills/app-store-deployment/SKILL.md](../../.claude/skills/app-store-deployment/SKILL.md)); always save the complete set. Holly needs at least:

● `APP_SECRET_KEY`, at least 32 characters.
● The database settings: the POSTGRESQL add-on injects `DATABASE_URL`, which Holly reads; nothing to set by hand (Deployment parameters, below).
● `ADMIN_USERNAME` and `ADMIN_PASSWORD` for the first start only (section 08).
● `UDL_USERNAME` and `UDL_PASSWORD` for UDL data, and `ANTHROPIC_API_KEY` for the assistant.
● `MATTERMOST_URL`, `MATTERMOST_BOT_TOKEN` and `MATTERMOST_CHANNEL_IDS` if the Comms page is used.

Leave `STORAGE_MOUNT_PATH` to the FILE_STORAGE add-on, which injects it; do not set it by hand. Leave `APP_ENV` at its default, `production`. Leave `ASSISTANT_CLEARED_MARKINGS` at its default, `["U"]`, unless the data owner clears a further UDL classification marking for the assistant; who that is, and whether the `JCO` source's own marking may be cleared, is `TBC, re-verify`.

**Starting, stopping and restarting** the app are platform operations: `TBC, re-verify` how. Rate-limit counters and the daily assistant token count start again from zero at every restart. **Withdrawing** the app is removing it from the App Store (the app owner, 19 October 2026); whether removal also deletes the add-ons' database and files is `TBC, re-verify`, so take what must be kept first.

**Rollback** is a resubmission of the previous package; the platform has no separate rollback (platform reference above). Migrations only move forward at start, so a package older than the database's newest migration stops at boot with Alembic's `Can't locate revision identified by '<revision>'`. Rolling back across a migration therefore needs the database restored to match the older package, or a fixed package that carries the newer migration. One migration can instead be undone in place: from V0.10 to V0.9, migration 0018. In the V0.10 container, immediately before V0.9 is deployed, run:

```sh
python -c "from alembic import command; from app.migrate import alembic_config; command.downgrade(alembic_config(), '0017_audit_append_only')"
```

The image ships no `alembic.ini`, so `alembic downgrade` fails there. The command drops `must_change_password` and `token_version` and keeps every account; V0.10's engineering review rehearsed it on PostgreSQL 16 (ADR-014). Until V0.9 replaces it, V0.10 answers 500 to requests that read an account, and a restart of V0.10 applies 0018 again. Under V0.9 a temporary password grants full access with no change asked, so reset no password between the downgrade and the upload. Whether the platform offers a shell in the container is `TBC, re-verify`; without one, restore the database instead.

### Deployment parameters

The app record as the App Store console showed it on 19 October 2026 (fact, from the app owner's screenshots). A change here is a change to the platform's record, made in the console, not in this repository.

| Parameter | Value |
|---|---|
| App name (slug) | `holly`, at `https://holly.appstore.bluestaq.com` |
| Detected stack | `node-react` (inference: from the root `package.json`, which exists for the platform's node test job; the image still builds from the root `Dockerfile`, as the platform reference says of every container template) |
| Service | `app`, the entrypoint |
| Port | 8080 |
| Health check | `/` |
| Memory | 4Gi |
| CPU | 2000m |
| POSTGRESQL add-on | PostgreSQL 16, 256Mi memory, 973 MiB storage; injects `DATABASE_URL` (`postgresql://postgres:[REDACTED:password]@appstore-holly-postgresql:5432/app?sslmode=disable`), `PGHOST`, `PGPORT`, `PGDATABASE` and `PGUSER` |
| FILE_STORAGE add-on | An S3-backed persistent volume at `/data`; injects `STORAGE_MOUNT_PATH=/data` |
| Category, display name, visibility | `TBC, re-verify` |

Holly reads `DATABASE_URL` and ignores the `PG*` variables; its own `POSTGRES_*` fallback is for local runs. `sslmode=disable` means the connection to the database is not encrypted inside the platform (SECURITY.md). The platform team confirmed that the `/data` volume is writable by Holly's numeric user, 10001 (relayed by the app owner, 19 October 2026), and V0.8 and V0.9 have started on the App Store, which Holly does only with a writable store. Should that change, Holly stops at start with the errno in the log (section 10), and the fix is a platform request for that user's group on the volume.

**SECTION 04**

## What happens at start

1. gunicorn reads its configuration. A malformed `PORT` stops it with `PORT must be a whole number from 1 to 65535, got '<value>'`.
2. Only when the App Store's DAST scan starts the container (`APPSTORE_DAST_SCAN=true`, with none of Holly's settings), the master fills in what the scan leaves out: a throwaway `APP_SECRET_KEY` if none is set, a temporary procedure store if none is configured, and the background pulls off. It logs `{"event": "dast_scan", "status": "active", ...}`, naming what it set and never a value. With no database at all it then skips steps 3 and 4 (`{"event": "migrations", "status": "skipped"}`), and each request that needs the database answers 503. A live start never carries the flag: if this line appears outside a scan, remove `APPSTORE_DAST_SCAN` from the variables.
3. The master reads and validates every setting, so a misconfiguration stops the container here with one line that names each problem and repeats no value, for example `Error: Holly cannot start: APP_SECRET_KEY: Field required` or `Error: Holly cannot start: UDL_BASE_URL must use https outside development`. It then waits for the database for about a minute while it cannot be reached, is starting, or drops the connection, logging `{"event": "database_wait", "status": "retrying", "attempt": <n>, "error": "<type>"}`, then `"ready"`; after about a minute it stops with `Error: the database could not be reached within about 60 seconds (last error: <type>)`. A database that answers and refuses stops it at once with `Error: the database refused the connection (SQLSTATE <code>, <driver error>)`. It then applies pending migrations under a PostgreSQL advisory lock, logging `{"event": "migrations", "status": "starting"}` and then `"applied"`. A failed migration stops it here too, with Alembic's error.
4. The master counts the accounts. With none, and `ADMIN_USERNAME` and `ADMIN_PASSWORD` set, it creates the first admin, logging `{"event": "admin_bootstrap", "status": "created", "username": "<name>"}`; otherwise it logs `"not_configured"`, or `"accounts_exist"` with any `ADMIN_*` variable still set. With no account yet, half a pair, a password shorter than 12 characters, or a value Holly cannot store stops the container here with a line naming the variable (section 08).
5. The worker starts and proves the procedure store accepts a write. On success it logs `{"event": "boot", "version": "<version>", "storage": "/data/procedures", "storage_writable": true, "background_refresh": true, ...}`. On failure it logs `"storage_writable": false` with the `errno` and `error`, and the container stops.
6. The background loops start, each logging a line such as `Background notifications loop enabled: every 3600s`.

At shutdown Holly stops the loops, closes its database connections and logs `{"event": "shutdown", ...}`.

**SECTION 05**

## Logs

Holly writes one JSON object per line to standard output. Named events (`boot`, `migrations`, `shutdown`, `llm.call`) carry an `event` field; everything else carries `time`, `level`, `logger` and `message`. Every line carries `"service": "holly"` and a `request_id`, which is `-` outside a request. Holly does not log each request: the access log is set to warnings only. No line carries a secret value. Where the App Store shows container logs is `TBC, re-verify`.

**Correlating a request.** Every response but a CORS preflight carries an `X-Request-ID` header. Capture it (browser developer tools, `curl -i`, or your client's logs) and search the logs for `"request_id": "<id>"`. A caller's own `X-Request-ID` is kept and echoed when it is a plain token of at most 128 letters, digits, `.`, `_`, `:` or `-`; anything else is replaced with a fresh id.

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
  -H "X-Holly-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"msg_type": "TACREP_NOTSO", "created_at_gte": "<ISO 8601 time>", "data_mode": "REAL", "source": "JCO", "max_results": 100}'
```

The token goes in `X-Holly-Token`, the token alone. Holly never reads `Authorization`, and the App Store's gateway refuses a Holly token there (section 10). Whether the gateway lets a request through without your App Store sign-in is `TBC, re-verify`.

The answer is `{"pulled": <n>, "inserted": <n>, "updated": <n>, "skipped": <n>}`, and the audit row records your user id and address. `max_results` may be at most 10,000; a pull that names none, as the background pulls do, gets UDL's own default page size (`TBC, re-verify` its value). `POST /api/v1/elsets/ingest` takes `{"epoch_gte": "<ISO 8601 time>", "sat_no": <number>, "max_results": <number>}` and answers the same way; it is the only way element sets arrive. Manoeuvres and Mattermost chat are pulled only by the background loops.

**SECTION 07**

## Inspecting ingest history

The **Audit log** page (operators and admins) filters by action type: `udl.notification.ingest`, `udl.maneuver.ingest`, `udl.elset.ingest` or `mattermost.ingest`. Each row's detail holds the request and the counts. Through the API, with an operator's or admin's token:

```sh
curl -s 'https://<host>/api/v1/audit?action_type=udl.notification.ingest&limit=20' -H "X-Holly-Token: $TOKEN"
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

### The first admin

Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` (at least 12 characters, a secret) as App Store variables before the first start, with `ADMIN_EMAIL` if wanted. At start, after the migrations, Holly counts the accounts. While there are none, it creates that admin, writes an `auth.user.admin_bootstrap` audit row and logs `{"event": "admin_bootstrap", "status": "created", ...}` without the password; one variable without the other, a shorter password, or a username, password or email Holly cannot store stops the start before the value reaches a query, naming the variable and never its value, and nothing is written. Once any account exists, no value is checked or used: the log shows `"status": "accounts_exist"` and names any still set in `variables_still_set`, and no value, however set, can reset a password or stop a start. After the first start, remove all three from the App Store and apply the settings: until the app restarts without it, the password stays in the environment block each process started with (`/proc/<pid>/environ`), though the master drops it from the worker's `os.environ` and from gunicorn's own copy before the worker starts.

### Create or reset an admin

```sh
python -m app.cli.create_admin --username <name>
```

Run it in the running container, or on any machine with Holly's database settings. It takes the password from `ADMIN_PASSWORD` in that shell's environment, or prompts for it without echo; it never accepts one as a flag, and refuses one shorter than 12 characters. It prints `Admin user '<name>' created.` or `updated.` and writes an `auth.user.admin_upsert` audit row. For an existing username it resets the password, makes the account an active admin, whatever its role was, and ends every session the account holds. Once one admin can sign in, the **Users** page does the rest without a shell. Whether the App Store offers a shell in the running container, and whether the add-on database is reachable from outside the platform, are both `TBC, re-verify`.

### Add, reset and deactivate accounts

Sign in as an admin and open **Users** in the navigation (ADR-014). Every change is written to the audit log, with the admin who made it and their address.

● **Create a user:** enter a username (1 to 50 of `a` to `z`, `0` to `9` and `. _ @ -`, stored in lower case, so no two names can look alike), an email if wanted (one already in use, in any case, is refused), a role (`analyst`, `operator` or `admin`) and a temporary password of at least 12 characters, then select **Create**. Give the user the temporary password by a channel other than the one carrying their username. At their first sign-in Holly shows only **Change password**, and every other request answers 403 `Change your password before continuing`, until they choose their own.
● **Reset a password:** select **Reset password** on the account's row and enter a new temporary password. Every session the account holds ends at once, any sign-in lockout on the username is lifted, and the user chooses their own password at their next sign-in.
● **Change a role:** choose it in the account's **Role** column. The new role applies to the user's next request.
● **Deactivate or activate:** select **Deactivate** on the account's row. Every request checks the account, so its sessions stop at once, and none of them comes back if it is activated again.

An admin cannot reset, demote or deactivate their own account on this page, and Holly refuses to demote or deactivate the last active admin, answering `Holly needs at least one active admin.` Each change reads the account again under a row lock before it is made, so a reset made while the user is changing their password wins. Accounts are never deleted, since the audit chain names them.

What an admin can do, anyone holding an admin's session can do too. They can reset another admin's password and sign in as them, their later actions then audited under that admin's name; create an admin whose password they know, which outlives their own session and the victim's next password change; and demote every other admin, after which only `create_admin` (which needs a shell, `TBC, re-verify`) restores one, since the `ADMIN_*` variables apply only while Holly holds no account. The audit actions are `auth.user.create`, `auth.user.password_reset` and `auth.user.update`, whose detail holds what changed, from and to; a temporary password is never recorded.

### Change your own password

Every user can open **Password** in the navigation, enter their current password and a new one of 12 to 1,024 characters, not spaces alone, twice. A wrong current password answers `The current password is not correct.` and counts against the same per-username limit as a failed sign-in (10 in any 15 minutes). A change ends every other session the user holds, on any device, and keeps the one it was made in. A change still running when an admin resets the password or deactivates the account is refused with a 401, and the dashboard signs out. The audit action is `auth.user.password_change`, with `success` and, when it fails, the `reason`: `wrong_password`, `rate_limited`, `same_password`, `stale_token` (the session ended while the change ran) or `inactive_user`.

### Sign everyone out

To end one user's sessions, reset their password or deactivate them (above). To end everyone's, rotate `APP_SECRET_KEY` (at least 32 characters) and apply the settings. Every access and refresh token stops verifying, and every user signs in again. A user's own **Sign out** revokes only their refresh token; their access token stays valid until it expires, up to 30 minutes by default.

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
● `Error: the database could not be reached within about 60 seconds (last error: <type>)`: check the POSTGRESQL add-on and the `database_wait` lines before it; `gaierror` means the host name did not resolve, `ConnectionRefusedError` that nothing listened on the port, `TimeoutError` that the host never answered.
● `Error: the database refused the connection (SQLSTATE <code>, <driver error>)`: the database answered and refused, which waiting will not change. `28P01` (`InvalidPasswordError`) is a wrong password and `28000` a role that may not connect: check the add-on's `DATABASE_URL`. `3D000` (`InvalidCatalogNameError`) is a database that does not exist.
● `Error: Holly cannot start: ...`: a setting failed validation. Fix each setting the line names; it never repeats a value. A missing or short `APP_SECRET_KEY`, missing database settings, a `DATABASE_URL` that does not read as a postgres URL with a host (an unencoded `@` in the password does this: write it as `%40`), a `*` origin, an http UDL or Mattermost URL, `UDL_VERIFY_SSL=false` or a relative procedure path each stops the start.
● An Alembic error: a migration failed. If it reads `Can't locate revision identified by ...`, the package is older than the database (section 03). Escalate any other migration failure to engineering.
● `Error: ADMIN_... `: the first-admin bootstrap refused a variable while no account exists (section 08). Fix the variable the line names, or remove `ADMIN_USERNAME`, `ADMIN_PASSWORD` and `ADMIN_EMAIL` to start without an admin.
● `"storage_writable": false`: the procedure store refused a write. The `errno` and `error` say why; check the FILE_STORAGE add-on and `PROCEDURE_STORAGE_PATH`.

### Symptom: `/api/v1/health` answers 500, or `/api/v1/health/detailed` shows `"database": "down"`

Holly cannot reach its database. Check the POSTGRESQL add-on's state and the database settings Holly receives.

### Symptom: every request but the password page answers 403 `Change your password before continuing`

An admin created the account or reset its password, and the user has not yet chosen their own. Holly shows the user only **Change password** until they do (section 08). The answer is a 403, not a 401, so the dashboard keeps the session rather than signing out.

### Symptom: every signed-in request answers 401

First tell whose 401 it is. Holly's own has the body `{"detail":"Could not validate credentials"}`, a bare `WWW-Authenticate: Bearer` and an `X-Request-ID`. A 401 with an empty body and a `WWW-Authenticate` naming `invalid_token` and `Signed JWT rejected` came from the App Store's gateway, which refused Holly's token in `Authorization` as one it could not verify with the platform's keys (by inference, before Holly saw the request, and for any bearer token there that the platform did not sign). The dashboard sends its token in `X-Holly-Token` from V0.9; a script, or a dashboard older than V0.9, sending it in `Authorization` meets that refusal. In the browser it shows as the dashboard appearing after sign-in, then returning to the sign-in page.

For Holly's own 401: `APP_SECRET_KEY` changed, which invalidates every token: expected after a rotation, and users sign in again. Otherwise the user's access token expired and the refresh failed; the same answer applies.

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

On the **Password** page the same refusal reads `Password checks are busy. Try again in a moment.` At most 4 password checks run at once, each on a worker thread, so a burst of sign-ins cannot stall the one worker. A sign-in beyond them is refused at once, with `Retry-After: 1`, logged as `Sign-in refused: 4 password checks already running`, not audited and not counted against the username. It clears as the running checks finish.

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

On the **Users** page, an admin's **Reset password** or **Deactivate** ends every session the user holds at once (section 08); the user's own password change ends every session but the one it was made in. Rotating `APP_SECRET_KEY` stops every token for every user.

If the token was an admin's, also read the audit log from the time of the theft for `auth.user.create`, `auth.user.password_reset` and `auth.user.update` rows, and undo each one the admin did not make: deactivate an account they did not create, and reset any password and restore any role or status changed on their behalf. An account the thief created, or whose password they reset, gives them a way back in that outlives the stolen token.

**SECTION 12**

## See also

● [Architecture overview](../architecture/overview.md)
● [Security overview](../security/overview.md)
● [Audit logging overview](../audit/overview.md)
● [Developer setup](../developer/setup.md), for the settings reference
● [Analyst training manual](../user-handbook/training-manual.md)

Bluestaq Limited | Holly documentation | 2026
