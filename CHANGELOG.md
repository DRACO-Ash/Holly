**BLUESTAQ LIMITED** | Changelog

# Changelog

**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify (the Daily Operations Dashboard Team, Bluestaq Limited, owned the history below)
**Version:** 0.3
**Last updated:** 2026-10-14

All notable changes to Holly are recorded here, newest first. Holly V0.2 is the Daily Operations Dashboard fused into the Holly App Store project and renamed; the sections after it are the Daily Operations Dashboard's own record, kept as written. Holly's releases are numbered V<major>.<minor>, and each has a row in `docs/AUDIT-LOG.md` with the checks that ran.

## Holly V0.2 (2026-10-14)

### Added

● **One App Store container.** The React dashboard is compiled in the image and served at `/`, beside the API under `/api/v1`, the platform probes and a secret-free `/status`. Migrations run at container start in the gunicorn master, under a PostgreSQL advisory lock. One worker runs the background refresh, so it runs once.
● **Limits.** A coarse rate limit per client address on the API and `/status`; sign-in attempts limited per client address, before any password is checked, and checked sign-ins per username, each counted before its check so guesses sent together cannot pass the limit; at most 4 password checks at once, on worker threads, so a burst of sign-ins cannot stall the worker; assistant calls limited per user; a daily assistant token cap (`LLM_DAILY_TOKEN_CAP`) that fails closed and holds each call's largest possible cost before it is sent; request bodies capped at 256 KiB, 11 MiB for a procedure upload, whose form is read only after sign-in.
● **`ASSISTANT_CLEARED_MARKINGS`**: the UDL classification markings whose notifications, and the manoeuvre records sent with them, may be sent to the assistant, `["U"]` by default. Any other marking, or none, never leaves Holly; the dashboard says which notices were not sent. Each background evaluation and event narrative is written to the audit chain; once a sending may have gone, any failure to store it or its row stops that phase for the cycle.
● **`python -m app.cli.verify_audit`**, which recomputes the audit chain and names the first broken link. Migration 0017 refuses every UPDATE, DELETE and TRUNCATE on the audit log, the insert-only rule ADR-005 recorded but no migration enforced.
● **Recurrence anchor for event timers** (migration 0016): a monthly timer set for the 31st now returns to the 31st after a shorter month.
● **Unit tests for the dashboard's logic** (Vitest), and a server suite of 1,050 tests at 99% line coverage.
● **`scripts/dev.sh`**, the local run: PostgreSQL from `infra/docker-compose.yml`, migrations, the API on 8080 and the dashboard on 3000.

### Changed

● **Renamed to Holly**: the page title and header, the browser storage keys (`holly.*`, so every analyst signs in once more), the service name in the logs and the package names.
● **Settings are validated at boot and fail closed**: a signing key of at least 32 characters, no `*` origin, https for UDL and Mattermost outside development, and an absolute, writable procedure store (proved with a real write at boot). A refusal is one line that names each variable at fault and repeats no value. A `DATABASE_URL` is read once, by the parser that connects: it may carry libpq's `sslmode`, and only an `@` in its password, or a `%` before two hexadecimal digits, needs encoding.
● **Failed sign-ins**: the audit chain records the username only when it names an account, since an unknown one may be a password typed into the wrong box.
● **Assistant failures** reach analysts as fixed messages; the Anthropic API's own text stays in the server log.
● **Sign-in tokens use PyJWT** in place of python-jose, whose ecdsa dependency carries an advisory with no fixed release. Decoding accepts the configured algorithm only and requires every claim.
● **The audit chain hashes each row's stored timestamp and stored detail**, so every row Holly writes can be recomputed. Rows the Daily Operations Dashboard wrote hashed a timestamp it never stored and cannot be verified.
● **The admin command takes its password** from `ADMIN_PASSWORD` or a hidden prompt; the `--password` flag is gone, so a password never lands in shell history or the process list.
● **Downloads and exports** fetch with the analyst's token; the plain links before could not carry it.
● **Dashboard dependencies**: axios 1.20.0, react-router-dom 7.18.4, Vite 7, Vitest 4 and ESLint 10, exactly pinned; `npm audit` reports no known vulnerability.
● **The interactive API documentation is off**, and every response carries a strict Content Security Policy (a dashboard policy for the page itself), `nosniff`, `no-referrer`, `no-store` and a request id.

### Fixed

● Every uploaded procedure was stored in one file per extension, named after an id the row did not have yet, so a later upload replaced an earlier one's content and refusing a duplicate deleted the original's file. An upload that fails for any reason now removes its own file, a blank name is refused, and a download whose file is missing answers 404 instead of failing.
● A failed event narrative no longer replaces the earlier one and hides it: nothing is written, and the event is retried in the next cycle.
● Event summaries: a summary is refreshed only when the window holds a publication it has not seen, and from the event's full history, so it never shrinks as older publications age out; a timestamp tie no longer triggers a fresh narrative every hour; the newest events are summarised first when the per-cycle cap applies. The assistant is shown at most 20 publications of one event, the first and the newest, so a long-lived event costs no more to summarise than a busy one.
● The hourly loop survives a cycle cancelled by another caller, and stopping the loops no longer swallows the caller's own cancellation.
● A spent assistant limit no longer refuses a shift note: the note is kept as written and can be re-polished later.
● The dashboard did not compile as uploaded: `SortDirection` was imported in three files and defined in none.
● A failed re-polish no longer discards a note's polished text, including an analyst's own edit; a failed summary no longer hides an earlier good one.
● Mattermost: a malformed post is skipped and counted instead of aborting the run, or stalling every later run on the same post; an answer that is not a JSON object is a client error; ids are checked before they reach a request path.
● Satellite ids that UDL sends as numbers no longer crash evaluations and event summaries.
● Event timers: a whitespace-only label is refused, targets are bounded to the years 2000 to 2099, and an unknown recurrence value is dismissed once instead of looping. The pre-alert badge and browser notification give the timer's own lead time, not a fixed 5 minutes.
● A manual UDL ingest may ask for at most 10,000 records in one pull. The element-set ingest's audit entry now records the data mode it asked for.
● One UDL record that its table cannot store, such as text longer than its column, a NUL or lone surrogate in any text, NaN in its raw JSON, a number or time beyond its column's type, or an element that is not a record, no longer fails the whole pull: it is skipped, counted and logged by column.
● A model reply holding a character PostgreSQL cannot store is refused like any unusable reply, instead of failing the write after the call.
● Text holding a NUL is refused with 422 in every request body, upload and free-text query parameter. A shift note holding one was sent to the assistant before its write failed with a 500, and a NUL in a query or a sign-in answered 500. A 422 now names each field and its problem but never echoes the submitted value, which could be a password, and a lone surrogate in a JSON body gets its 422 instead of a 500.
● Each refused request built a new traceback onto one shared exception, so memory grew with every 401; each refusal is now a new exception.
● An upload whose file write fails part-way, or whose request is cancelled, no longer leaves a file behind.
● An assistant reply nested too deeply to read is an assistant error, not a crash that re-billed the notice every cycle; the parser tries at most 20 opening braces, so a crafted reply cannot hold the worker.
● Audit rows are timed after the newest row, so two containers whose clocks differ cannot make the verifier report a break.
● A failed download shows the server's message, such as a missing procedure file, not the bare status code.
● A 500 response carries the request id.
● Each evaluation read every previewable procedure file whole, up to 10 MB, for a 64 KiB preview; it now reads the preview only.
● The empty Comms page no longer tells analysts to edit a local `.env` file.
● Links from UDL records become clickable only for http and https, and every new-tab link carries `noopener noreferrer`.

### Removed

● The nginx configuration and certificates, the development Dockerfiles, `scripts/dev.ps1`, `.env.example` (`docs/developer/setup.md` lists every setting), the `/ws` development proxy, and the unused `EventSummaryRead` schema.

## Daily Operations Dashboard: [Unreleased]

### Added

● **`scripts\dev.ps1` one-file local deploy and run.** Idempotent: creates `.env` from `.env.example` with a fresh `APP_SECRET_KEY` if missing, generates a self-signed TLS certificate via docker if `infra/certs/` is empty, brings up the full stack, waits for the database, applies pending alembic migrations inside the backend container, bootstraps the first admin user if `app_user` is empty, and tails backend logs. Supports `-Down`, `-Restart`, `-Reset` (destructive), `-NoLogs`, `-RegenerateCerts`. Admin credentials can be supplied via `-AdminUsername`/`-AdminPassword` flags or `$env:ADMIN_USERNAME`/`$env:ADMIN_PASSWORD` for non-interactive runs.
● **Real TACREP_NOTSO shape support.** UDL nests the interesting fields inside `msgBody`; mapper now extracts `NOTSO` (notice identifier), `Event_Class`, `Event_Type`, `Event_Id`, `Status` (OPEN/CLOSED), `Event_Description`, `Company_Name`, `NOTSO_Link`, `Publish_Date`, and the `SatIds` array. Top-level envelope fields (`createdBy`, `origNetwork`, `classificationMarking`, etc.) are now captured too. Migration `0006_notif_msgbody` adds eleven new typed columns plus four query indexes (`notso_identifier`, `status`, `event_type`, `publish_date`).
● **Notifications page redesign.** List view now shows Notice / Status / Type / Event class / Sat IDs / UDL created. Status filter (OPEN/CLOSED), event-type filter, and status indicator pills. Ingest form defaults `Source` to `JCO` to match the production query.
● **Notification detail view.** New sections for Status, Identification (including the `NOTSO_Link` URL to the JCO source page), Timing, Associated objects (rendering the full `SatIds` array), Event description (preformatted), and Source artefacts (parses `NOTSO_Image_Metadata` and renders clickable links to the underlying assets).
● Single-sat convenience: when `SatIds` has exactly one numeric value, `sat_no` is populated so existing filter and sort paths still work; multi-sat notices populate `sat_ids` only.

### Changed

● `infra/docker-compose.yml` now mounts the repo root at `/workspace` on the backend container so alembic can find `alembic.ini` and `migrations/` (which live at the repo root, not under `backend/`). No effect on the production-time backend (uvicorn still runs from `/app`).
● `frontend/vite.config.ts` pins the dev server to port `3000` to match the `proxy_pass http://frontend:3000;` line in `infra/nginx/nginx.conf`. Previously vite defaulted to `5173` and the nginx proxy would have failed; fix went unnoticed because nobody had brought the full stack up locally yet.

● **`notso` → `notification` rename.** UDL serves Tactical Reports (TACREP) and Notices to Space Operators (NOTSO) through a single `/notification` endpoint under `msgType=TACREP_NOTSO`; the earlier naming treated them as separate surfaces, which was wrong. Alembic migration `0005_rename_notso` renames the table, its indexes, and the unique constraint. Backend model, schemas, ingest service, routes, UDL client method, and audit action type (`udl.notso.ingest` → `udl.notification.ingest`) all renamed accordingly. Frontend page, types, API wrapper, navigation label, and route URL move from `/notsos` to `/notifications`. UDL endpoint corrected from `/notso` to `/notification`. New ingest parameters (`msg_type`, `created_at_gte`, `data_mode`, `source`, `max_results`) match the example URL used in production. `msg_type` defaults to `TACREP_NOTSO`.

### Added

● **Observability and code-quality bar.** Every HTTP response now carries an `X-Request-ID` header (honoured from inbound or generated as a UUID), and every backend log line includes the active `request_id` so traces can be correlated end-to-end. New `GET /api/v1/health/detailed` returns a component breakdown (database connectivity, UDL credential configuration) plus version and environment. Coverage is enforced in CI via `pytest-cov` with a 40% floor (initial bar, will ratchet up). Frontend code is now governed by Prettier; a `format:check` step runs in CI alongside the existing eslint step.
● **Audit log viewer.** New `GET /api/v1/audit` endpoint role-gated to `operator` and `admin` via the existing `require_role` factory. Filters by `action_type`, `user_id`, `since`, and `until`; paginated. Frontend Audit log page shows timestamp, action, entity, user, IP, and the parsed detail payload. AuthContext now fetches `/auth/me` on mount and exposes the current `user`; Layout filters the side nav by role so the audit link only appears for operators and admins.
● **UI polish.** Sortable column headers on the Element sets and NOTSOs list pages (click to toggle direction, with an arrow indicator). Detail pages at `/elsets/:id` and `/notsos/:id` showing parsed fields, the TLE for elsets, the description for NOTSOs, and the full raw UDL payload. Rows in the list pages are clickable and route through to the detail. Dashboard refreshed with live count cards for each surface (Element sets, NOTSOs) including the most recent record's label and timestamp.
● Backend list routes now accept `sort_by` and `sort_dir` query parameters (whitelisted via `Literal` types, validated by FastAPI). Defaults preserve previous behaviour (elsets by epoch desc, NOTSOs by effective_from desc).
● Reusable `SortableHeader` component, design tokens for sortable headers, clickable rows, detail-grid, raw-json, TLE block, NOTSO description block, and the dashboard surface cards.
● **NOTSO ingest, end-to-end.** New `Notso` model and migration `0004_create_notso`, `UDLClient.get_notsos()`, `ingest_notsos` service mirroring the elset pattern, REST API at `/api/v1/notsos` (list with `msg_type` and `sat_no` filters, detail, and a manual ingest trigger). Frontend Notsos page with the same shape as Element sets. Action type `udl.notso.ingest` is now Active in the audit taxonomy.
● `UDLClient` factored to share a single `_get_list` helper between `get_elsets` and `get_notsos`. No behaviour change for the existing elset path.
● Backend tests for the NOTSO UDL-to-model mapping (full record, datetime parsing across `effectiveFrom`/`effectiveUntil`/`expirationTime`/`createdAt`, raw payload preservation, missing-id skip, fallback aliases for `text` and `expirationTime`).
● Refresh-token rotation and JTI block-list (ADR-011). Every JWT now carries a `jti` claim. `POST /auth/refresh` rotates: it issues a new access AND a new refresh token and revokes the old refresh-token JTI in the `revoked_jti` table. A reused old refresh token is rejected with audit reason `revoked_token`. New alembic migration `0003_create_revoked_jti` adds the block-list table. New `app/services/token_revocation.py` exposes `is_revoked` and `revoke`.
● `POST /auth/logout` now takes the refresh token in its body (no access-token header required) and revokes its JTI. The audit row carries success or one of `invalid_token`, `missing_claim`, `malformed_subject`, `already_revoked`.
● Audit-log emission for auth events. `POST /auth/login` writes `auth.user.login` rows for both success and the three failure modes (unknown user, inactive user, wrong password); `POST /auth/refresh` writes `auth.token.refresh` rows for success and the new revoked-token failure reason. Action types are Active in the audit taxonomy.
● Real JWT authentication. `POST /api/v1/auth/login` and `POST /api/v1/auth/refresh` issue HS256 tokens (30-minute access, 7-day refresh). `GET /api/v1/auth/me` returns the current user. Supersedes the frontend auth stub.
● `User` model with role enum (analyst / operator / admin), bcrypt password hashing, alembic migration `0002_create_user`.
● `get_current_user` dependency wired onto every `/elsets` route. `POST /elsets/ingest` now records the authenticated user's `id` and IP address in the audit log.
● Admin bootstrap script at `backend/scripts/create_admin.py`. Run via `python -m scripts.create_admin --username <name> --password <secret>` from the `backend/` directory.
● Frontend axios refresh-on-401 interceptor; `AuthContext` now talks to the real backend.
● Backend tests for password hashing, JWT round-trip, login flow (happy path, wrong password, unknown user, inactive user), `/auth/me` token validation, refresh, and the auth gate on `/elsets/ingest`.
● Decision log ADR-010 (JWT authentication with stateless refresh, supersedes ADR-009).
● End-to-end UDL element-set ingest. `Elset` model, alembic baseline migration, async UDLClient, ingest service with `(udl_id)` upsert, hash-chained audit writes, REST API at `/api/v1/elsets`.
● Analyst-facing Element sets page with filter, pagination, and a manual ingest trigger. Styled against the Bluestaq palette.
● Frontend scaffold: `index.html`, `main.tsx`, `ProtectedRoute`, `Layout`, `Login`, `Dashboard`, axios client, design tokens.
● Audit writer with SHA-256 hash chain and Postgres advisory-lock concurrency control.
● Alembic configuration (`alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`).
● Backend tests covering the UDL client (happy path, 401, 500, non-list responses, missing credentials, epoch formatting) and the UDL-to-model field mapping.
● Documentation set: README, architecture overview, data model, security overview, audit overview, developer setup, operator manual, analyst training manual, Phase 1 roadmap, this changelog.
● Decision log entries ADR-007 (UDL ingest pattern), ADR-008 (hash-chained audit), ADR-009 (frontend auth stubbed, now superseded).

### Changed

● `POST /auth/refresh` response is now `TokenResponse` (both `access_token` and `refresh_token`) instead of `RefreshResponse`. Frontend stores the new refresh token returned by the server.
● `POST /auth/logout` now takes a body `{refresh_token: "..."}` instead of relying on the access-token header. Supersedes the bearer-only logout from the prior auth-events slice.
● **Documentation aligned to the Bluestaq Ltd Document Design and Narrative Style Guide v3 (March 2026).** Every doc now carries the brand-banner top line, the metadata block, `**SECTION NN**` eyebrows before every H2 (or `**ADR-NNN**` in the decision log), copper and blue callout patterns where they earn their place, and the standard footer line. Version bumped to 0.2 across the set.
● `Settings` now exposes `UDL_USERNAME`, `UDL_PASSWORD`, `UDL_REQUEST_TIMEOUT_SECONDS`, and `UDL_VERIFY_SSL`.
● `.env.example` mirrors the new UDL configuration.

### Removed

● Frontend stub authentication (any-non-empty-username accepted). Superseded by real backend JWT.

### Fixed

● Frontend `context/AuthContent.tsx` typo replaced with the correctly-named `AuthContext.tsx`.

### Security

● Bcrypt password hashing via `passlib`. JWT signed with `APP_SECRET_KEY` using HS256. Tokens travel in the `Authorization` header, never in cookies.
● No real credentials are stored in source. `.env*` is gitignored; `.env.example` is the only committed environment file.
● gitleaks runs in CI and as a pre-commit hook.
● bandit at severity `-ll` runs across `backend/app/` in CI and pre-commit.

## Prior history

Captured in git log up to `18fff46` (Merge pull request #1, CI pipeline check).

Bluestaq Limited | Daily Operations Dashboard documentation | 2026
