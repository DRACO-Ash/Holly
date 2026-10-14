**BLUESTAQ LIMITED** | Architecture Overview | **COMMERCIAL IN CONFIDENCE**

# Architecture Overview

**Document classification:** Commercial in Confidence
**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify (the Daily Operations Dashboard Team, Bluestaq Limited, owned the edition this one replaces)
**Version:** 0.3
**Last updated:** 2026-10-14

> **BLUF**
>
> Holly is one container on the Bluestaq App Store. One FastAPI process, run by gunicorn with a single uvicorn worker, serves the React dashboard, the JSON API under `/api/v1` and the platform probes. PostgreSQL comes from the App Store POSTGRESQL add-on and procedure files from the FILE_STORAGE add-on. Background loops pull Unified Data Library (UDL) notifications and manoeuvre records and the team's Mattermost chat; an assistant (Anthropic's Claude) evaluates each new notification against the team's uploaded procedures. Every state change is written to a hash-chained, append-only audit log. Transport Layer Security (TLS) terminates at the platform, not in Holly.

**SECTION 01**

## Intent

One browser surface for SDA watch analysts that brings together UDL Tactical Reports and Notices to Space Operators (served by UDL as `TACREP_NOTSO`), UDL manoeuvre records, the team's Mattermost channels, uploaded procedures, the assistant's evaluations, a shift log and event timers. Holly was built from the Daily Operations Dashboard and carries over its data model, its JSON Web Token (JWT) sign-in and its audit chain, with the changes listed in [CHANGELOG.md](../../CHANGELOG.md). The fusion changed how Holly is built, deployed and configured; [ADR-012](decision-log.md) records that decision.

**SECTION 02**

## System context

```
   ┌──────────────────────┐
   │  Analyst browser     │
   └──────────┬───────────┘
              │ HTTPS, TLS terminated by the App Store platform
              ▼
   ┌──────────────────────────────────────────────────────────┐
   │  Holly container: gunicorn, one uvicorn worker           │
   │  ● the dashboard (React, built into the image) at /      │
   │  ● the JSON API under /api/v1, behind JWT sign-in        │
   │  ● the probes (/healthz and others) and /status          │
   │  ● background loops: notifications, manoeuvres, chat     │
   │  ● assistant calls and the audit writer                  │
   └───────┬──────────────────┬───────────────────┬───────────┘
           │ async SQL        │ file reads and    │ outbound HTTPS
           │                  │ writes            │
           ▼                  ▼                   ▼
   ┌───────────────┐  ┌─────────────────┐  ┌────────────────────┐
   │  PostgreSQL   │  │ Procedure store │  │  UDL, Mattermost,  │
   │  (POSTGRESQL  │  │ (FILE_STORAGE   │  │  Anthropic API     │
   │   add-on)     │  │  add-on, /data) │  │                    │
   │  ● public     │  └─────────────────┘  └────────────────────┘
   │  ● audit      │
   └───────────────┘
```

Holly only reads from UDL and Mattermost. Whether the App Store permits outbound HTTPS to UDL, the team's Mattermost server and the Anthropic API is `TBC, re-verify`; without it the background loops log their failures and the assistant stores its errors, but the rest of Holly runs.

**SECTION 03**

## Components

### Application (FastAPI)

The application is the `app` package under [src/app/](../../src/app/), in four layers:

● **API layer** ([src/app/api/v1/routes/](../../src/app/api/v1/routes/)) holds the HTTP route handlers. Each handler is thin and delegates to a service. The reviewed route inventory, and the short list of routes open without sign-in, are pinned in [tests/test_app.py](../../tests/test_app.py).
● **Service layer** ([src/app/services/](../../src/app/services/)) holds domain logic: the UDL and Mattermost clients, the ingest pipelines, the assistant, the background loops, procedure storage and the audit writer.
● **Schema layer** ([src/app/schemas/](../../src/app/schemas/)) holds Pydantic models for request validation and response serialisation, including the validator every assistant reply must pass before it is stored.
● **Model layer** ([src/app/models/](../../src/app/models/)) holds the SQLAlchemy classes. The migrations define the schema; see the [data model](data-model.md).

Cross-cutting concerns sit in [src/app/core/](../../src/app/core/) (structured logging, tokens and passwords, rate limits, the request body cap, request ids, single-flight jobs), [src/app/db/](../../src/app/db/) (engine and sessions), [src/app/config.py](../../src/app/config.py) (every setting, validated at boot) and [src/app/cli/](../../src/app/cli/) (the admin and audit-verification commands).

`create_app` in [src/app/factory.py](../../src/app/factory.py) builds the application and never listens; [src/app/main.py](../../src/app/main.py) is the entry point gunicorn loads. A request passes the security headers, the request id, the coarse rate limit, Cross-Origin Resource Sharing (CORS) and the body-size cap, in that order. The interactive API documentation (`/docs`, `/redoc`, `/openapi.json`) is off.

### Dashboard (React)

The dashboard's source is [frontend/](../../frontend/). The Dockerfile's `dashboard` stage builds it with Node 22 from the committed lockfile and copies only the static output into `src/app/static`, so no Node tooling reaches the image. The same process serves it at `/`. API routes are matched first and only a browser's page navigation falls back to `index.html`, so a bookmarked page loads while an unknown API path still answers 404. In a source checkout with no built dashboard, `/` answers `{"service": "holly", "status": "ok"}` instead.

Sign-in state flows through the `AuthContext` provider. `ProtectedRoute` sends a visitor without an access token to `/login`; that redirect is a convenience, and the server's token check on every API route is the control. The axios client at [frontend/src/api/client.ts](../../frontend/src/api/client.ts) adds the bearer token to every call, refreshes once on a 401 (concurrent calls share one refresh), stores the rotated refresh token, and returns the analyst to `/login` when the refresh fails. Tokens live in the browser's `localStorage` under `holly.auth.access` and `holly.auth.refresh`. Downloads and exports are fetched with the token and handed to the browser to save ([frontend/src/utils/download.ts](../../frontend/src/utils/download.ts)), because a plain link cannot carry it.

The pages are Dashboard, Notifications (with a detail page per notice), Maneuvers, Comms, Procedures, Shift log (with the event timers) and Audit log, which only operators and admins see. The [analyst training manual](../user-handbook/training-manual.md) walks through each one.

### Database (PostgreSQL)

PostgreSQL comes from the App Store POSTGRESQL add-on. Holly reads `DATABASE_URL` (the assumed name of the add-on's variable, `TBC, re-verify`) or the `POSTGRES_*` parts, and connects with the asyncpg driver through one connection pool per process. Two schemas:

● `public` holds operational data in 12 tables, among them `notification`, `maneuver`, `shift_note` and `event_timer`.
● `audit` holds the tamper-evident audit log, `audit.audit_log`. A trigger refuses every UPDATE, DELETE and TRUNCATE on it (migration 0017).

The PostgreSQL version the add-on provides is `TBC, re-verify`; the local database in [infra/docker-compose.yml](../../infra/docker-compose.yml) and the container smoke rung both use 15.19. Table and column detail is in the [data model](data-model.md).

### Procedure store

Uploaded procedures are files in one directory: `PROCEDURE_STORAGE_PATH` when set, otherwise the FILE_STORAGE add-on's `STORAGE_MOUNT_PATH` followed by `/procedures`, otherwise `/data/procedures`. At boot Holly creates the directory and proves it accepts a real write; if it does not, the container stops with the error number in its boot log line ([src/app/services/procedure_storage.py](../../src/app/services/procedure_storage.py)). Each file is stored as `<procedure id><extension>`, so an uploaded file name never reaches the filesystem beyond a short plain extension. The database indexes the files in the `procedure` table.

### Background loops

Three loops start with the application unless `BACKGROUND_REFRESH_ENABLED` is `false` ([src/app/services/background_refresh.py](../../src/app/services/background_refresh.py)). Each logs and survives any failure.

| Loop | Default cadence | What it does |
|------|-----------------|--------------|
| Notifications | Every 3600 seconds (`BACKGROUND_NOTIFICATION_INTERVAL_SECONDS`) | Pulls `TACREP_NOTSO` notifications created in the last 120 hours (`BACKGROUND_NOTIFICATION_WINDOW_HOURS`) with data mode `REAL` and source `JCO`, then has the assistant evaluate up to 20 notices that have no evaluation yet, then refreshes up to 20 event narratives. |
| Manoeuvres | Every 600 seconds (`BACKGROUND_MANEUVER_INTERVAL_SECONDS`) | Pulls UDL manoeuvre records whose event started in the last 48 hours (`BACKGROUND_MANEUVER_WINDOW_HOURS`), data mode `REAL`. |
| Mattermost | Every 60 seconds (`MATTERMOST_INTERVAL_SECONDS`) | Pulls new posts from each channel in `MATTERMOST_CHANNEL_IDS`, from the newest stored post onwards, or the last 24 hours on the first run. |

The notification cycle is single-flight: an analyst's **Pull from UDL** during a running cycle joins it rather than starting a second. No loop pulls element sets; the element-set routes and table remain for recovery. gunicorn runs exactly one worker ([src/app/gunicorn_conf.py](../../src/app/gunicorn_conf.py)), so each loop runs once per container.

### Assistant

Every assistant call goes through `call_claude` ([src/app/services/claude.py](../../src/app/services/claude.py)): notification evaluations, event narratives, shift-note polish and the end-of-shift summary. The API key is read server-side at call time and a missing key fails closed. A daily token cap (`LLM_DAILY_TOKEN_CAP`, 2,000,000 by default) applies across every caller, and each signed-in user may make 30 requests that call the assistant in any 10 minutes. Replies are untrusted: an evaluation must parse as JSON of the expected shape, is retried once, and is otherwise stored as an error with no advice. Each call writes one `llm.call` log line with its token usage.

### TLS and the platform ingress

Holly serves plain HTTP on `0.0.0.0`, on `PORT` or 8080. TLS termination, the public hostname `<slug>.apps.bluestaq.com` (slug `TBC, re-verify`) and request routing are the platform's responsibility; the details of the ingress are `TBC, re-verify`. What Holly relies on the ingress for is listed in [SECURITY.md](../../SECURITY.md). There is no nginx and no in-app TLS.

**SECTION 04**

## Data flow: the notification cycle

1. The notifications loop starts a cycle every hour. An analyst can start one at once with **Pull from UDL** on the Notifications page, which calls `POST /api/v1/notifications/refresh`, counts against that analyst's assistant allowance, and answers once the cycle completes.
2. The cycle opens a `UDLClient` (HTTPS with Basic auth from `UDL_USERNAME` and `UDL_PASSWORD`) and requests UDL's `/notification` endpoint for `msgType=TACREP_NOTSO` created in the window.
3. The ingest service maps each record's typed fields, keeps the full payload in `raw`, and upserts on `udl_id` with `INSERT ... ON CONFLICT DO UPDATE`. It writes one `udl.notification.ingest` audit row with the counts. A cycle's row carries no user id, even when an analyst started the cycle.
4. Up to 20 notices in the window that have no evaluation are evaluated, latest UDL publication of each notice only. Each prompt carries the notification, manoeuvre records for the same satellites from the last 30 days (up to 10), the last 6 hours of team chat (up to 30 messages) and every uploaded procedure, with the text of those uploaded as plain text, Markdown, JSON or CSV. The validated reply is stored in `assistant_evaluation`. A persistent failure, such as a missing key or the spent daily cap, stops the phase early.
5. Every logical event with a publication in the window that its narrative has not yet seen gets a fresh narrative of at most three sentences in `event_summary`, written from the event's stored publications: all of them, or the first and the newest 19 when it has more than 20. Newest events go first, up to 20 per cycle.
6. The Dashboard page reads `GET /api/v1/assistant/feed` every 60 seconds and groups the notices by the urgency of their most urgent recommended action.

**SECTION 05**

## Deployment topology

Holly is one container on the Bluestaq App Store, `python` template, with the [Dockerfile](../../Dockerfile) at the repository root:

● **dashboard** stage: `node:22-alpine`, pinned by digest, builds the React app.
● **build** stage: `python:3.12-slim`, pinned by digest, installs the hash-locked `requirements.txt` into a virtualenv.
● **prep** stage: patches OS packages, removes pip, adds the numeric user and group 10001 with no home directory, and strips every setuid and setgid bit.
● **ship** stage: `FROM scratch` with one copy of the prepared filesystem, so the image is a single layer. It runs as `10001:10001` and starts `gunicorn --chdir /app --config python:app.gunicorn_conf app.main:app` in exec form.

At start, the gunicorn master binds `0.0.0.0` on `PORT` (8080 when unset; a malformed value stops the container), applies the database migrations under a PostgreSQL advisory lock, and then starts the single uvicorn worker. The image has no `HEALTHCHECK`: the platform runs on Kubernetes and probes the health paths itself. `/healthz`, `/health`, `/readyz`, `/livez` and `/ping` answer 200 without touching anything.

The POSTGRESQL add-on provides the database and the FILE_STORAGE add-on provides the volume that `STORAGE_MOUNT_PATH` names. Settings arrive as App Store environment variables. Logs are JSON lines on standard output; where the platform shows them is `TBC, re-verify`.

The rate limits, the daily assistant token cap and the background loops live in the one worker process, and reset when the container restarts. A second replica would run its own loops and its own limits; how many replicas the platform runs is `TBC, re-verify`.

The Daily Operations Dashboard's Docker Compose stack (`backend`, `frontend`, `db` and `nginx`) is retired. [infra/docker-compose.yml](../../infra/docker-compose.yml) now starts only a local PostgreSQL for development; see [developer setup](../developer/setup.md).

**SECTION 06**

## Security boundaries

● **Internet boundary:** the platform ingress terminates TLS (details `TBC, re-verify`). Holly sets its own security headers and Content Security Policy (CSP) on every response.
● **Public paths:** the probes, `/status`, `/api/v1/health`, `/api/v1/health/detailed`, the sign-in, refresh and sign-out routes, and the dashboard's static files. Every other route under `/api/v1` requires a valid access token ([tests/test_app.py](../../tests/test_app.py)).
● **Authorisation:** `GET /api/v1/audit` requires the `operator` or `admin` role; every other signed-in route is open to any role.
● **Holly to database:** through the add-on's connection settings. Network isolation of the database is the platform's: `TBC, re-verify`.
● **Holly to UDL, Mattermost and Anthropic:** outbound HTTPS with credentials from environment variables. Outside development, Holly refuses to start with a non-https UDL or Mattermost URL or with TLS verification for UDL turned off.
● **Audit schema:** append-only by trigger, and tamper-evident by hash chain.
● **Tokens:** access tokens last 30 minutes and refresh tokens 7 days by default; refresh tokens rotate (ADR-011).

A fuller treatment is in [docs/security/overview.md](../security/overview.md).

**SECTION 07**

## See also

● [Architectural decision log](decision-log.md) for the why behind the choices on this page, ADR-012 in particular.
● [Data model](data-model.md) for table and column detail.
● [Audit logging overview](../audit/overview.md) for the hash-chain mechanics.
● [Operator manual](../runbook/operator-manual.md) for running Holly on the App Store.

Bluestaq Limited | Holly documentation | 2026 | **COMMERCIAL IN CONFIDENCE**
