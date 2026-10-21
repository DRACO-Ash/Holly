**BLUESTAQ LIMITED** | Architectural Decision Log

# Architectural Decision Log

**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify (the Daily Operations Dashboard Team, Bluestaq Limited, owned ADR-001 to ADR-011)
**Version:** 0.7
**Last updated:** 2026-10-20

> **HOW TO READ THIS LOG**
>
> Each Architectural Decision Record (ADR) captures a single decision, its rationale, and (where helpful) alternatives considered and risks accepted. Superseded decisions remain in the log; their status line points to the ADR that replaced them. New ADRs are appended; numbering does not reset. ADR-001 to ADR-011 were made for the Daily Operations Dashboard, which Holly was built from; ADR-012 and later were made for Holly.

**ADR-001**

## Python / FastAPI Backend

**Date:** Sprint 1
**Decision:** FastAPI selected as the backend framework.
**Rationale:** Async-native, strong type support via Pydantic, automatic OpenAPI generation, high performance for API-heavy workloads.
**Alternatives considered:** Django REST Framework, rejected due to synchronous defaults and heavier footprint for this use case.

**ADR-002**

## PostgreSQL Database

**Date:** Sprint 1
**Status:** Amended by ADR-012. On the App Store, Holly's database is the POSTGRESQL add-on, which the store's upload page lists as PostgreSQL 16 (minor version `TBC, re-verify`); the container smoke rung tests 16.15, and local development stays on 15.19.
**Decision:** PostgreSQL 15 as the primary data store.
**Rationale:** Robust, mature, strong support for audit schema isolation, UUID primary keys, and async drivers (asyncpg).

**ADR-003**

## Docker Compose for Local Deployment

**Date:** Sprint 1
**Status:** Superseded by ADR-012. Docker Compose now starts only the local development database (`infra/docker-compose.yml`).
**Decision:** Docker Compose used for all local service orchestration.
**Rationale:** Consistent environment across developers; direct migration path to Kubernetes or ECS in Phase 2.

**ADR-004**

## HTTPS Enforced in Local Deployment

**Date:** Sprint 1
**Status:** Superseded by ADR-012. Holly has no nginx and no in-app TLS; TLS terminates at the App Store platform.
**Decision:** Nginx with self-signed TLS certificate used even in local development.
**Rationale:** Avoids security regressions when moving to cloud; forces correct security posture from day one.

**ADR-005**

## Audit Schema Isolation

**Date:** Sprint 1
**Status:** Amended by ADR-012. No migration ever granted INSERT-only permissions; Holly enforces append-only with a trigger instead (migration `0017_audit_append_only`).
**Decision:** Audit log stored in a separate PostgreSQL schema with INSERT-only application permissions.
**Rationale:** Prevents accidental or deliberate modification of audit records through the application layer.

**ADR-006**

## Data Classification Confirmed Unclassified

**Date:** Sprint 1
**Status:** Amended by the assistant's classification-marking control (Holly V0.2). A UDL notification reaches the assistant only when its classification marking is listed in `ASSISTANT_CLEARED_MARKINGS`, `["U"]` by default and matched exactly; a notice with any other marking, or none, never leaves Holly ([src/app/services/disclosure.py](../../src/app/services/disclosure.py)). Clearing a further marking is the data owner's decision; who that is, and whether the `JCO` source's own marking may be cleared, is `TBC, re-verify`.
**Decision:** All data processed by this system, including UDL TACREP_NOTSOs, elset records, Mattermost content, ClickUp exports, procedure documents, and analyst inputs, is confirmed Unclassified.
**Rationale:** No handling restrictions apply. Commercial AI APIs (Anthropic Claude) and all major cloud providers are permissible for Phase 2.

**ADR-007**

## UDL Ingest Pattern: Typed Columns plus Raw JSONB

**Date:** 2026-05-27
**Decision:** Every UDL-sourced table models the fields analysts query against as typed columns, and preserves the full UDL payload in a `raw` JSONB column on the same row.
**Rationale:** UDL adds fields over time. Preserving the raw payload means a schema bump on the UDL side never costs us data; typed columns keep the analyst-facing queries fast and well-indexed. The first table that follows this pattern is `elset`. NOTSO, TACREP, and Mattermost ingest will follow the same shape.
**Alternatives considered:** Pure JSONB rows, rejected because typed queries on indexed columns are dramatically faster and let us add database-level constraints where they help.

**ADR-008**

## Hash-Chained Audit Log with Postgres Advisory Lock

**Date:** 2026-05-27
**Decision:** The audit log is tamper-evident via a SHA-256 hash chain. Each row's `entry_hash` covers the previous row's `entry_hash` plus the canonical-JSON serialisation of the new row's payload. Concurrent writes are serialised inside a single transaction via `pg_advisory_xact_lock`.
**Rationale:** The chain detects after-the-fact tampering even by someone with database-level access. The advisory lock prevents two concurrent writers from forking the chain by both reading the same `previous_hash`. Doing this inside the transaction keeps the lock duration short and bounded by the audit write itself.
**Alternatives considered:** Per-row Postgres triggers to compute the hash, rejected to keep the logic in the application layer where it can be unit-tested. External tamper-evident logging service, rejected as overkill for Phase 1.

**ADR-009**

## Frontend Auth Stubbed Pending Backend JWT

**Date:** 2026-05-27
**Status:** Superseded by ADR-010.
**Decision:** The frontend `AuthContext` accepts any non-empty username and stores a stub token in `localStorage`. The axios client and the `ProtectedRoute` gate behave as if the token were real.
**Rationale:** Lets the feature work end-to-end while the real `/api/v1/auth` endpoints are still pending. The contract on the frontend side (token in `Authorization: Bearer ...`, 401 forces logout) matches what the real backend will deliver, so the swap will be small.
**Risks accepted:** Until the real backend auth lands, anyone reaching the host can use the application. The deployed environment is on a sovereign network with network-level access controls in front of nginx, so the application-level gap is acceptable for now. This ADR is to be superseded by ADR-010 (or similar) when the JWT slice lands.

**ADR-010**

## JWT Authentication with Stateless Refresh

**Date:** 2026-05-28
**Status:** Superseded by ADR-011. Its operational note is replaced by ADR-012. Its token header is replaced by ADR-013, and the users it says administrators would create are created on the Users page (ADR-014).
**Decision:** Authentication is HS256 JWT bearer tokens issued by `/api/v1/auth/login` and refreshed at `/api/v1/auth/refresh`. Access tokens last 30 minutes; refresh tokens last 7 days. Refresh is stateless: any validly signed refresh token within its expiry window is accepted. Logout is client-side only (delete both tokens from `localStorage`). `get_current_user` enforces a valid access token on protected routes. Supersedes ADR-009.
**Rationale:** Stateless refresh keeps the Phase 1 schema simple (no refresh-token table, no blocklist). The 30-minute access window bounds the blast radius of a stolen token. Bcrypt via `passlib` hashes passwords with per-user salt. Tokens travel in `Authorization: Bearer ...` headers rather than cookies, which removes the standard CSRF vector. The frontend axios client transparently refreshes once on 401 before redirecting to the login page.
**Risks accepted:** A stolen refresh token is valid until expiry (up to 7 days). Mitigations: HTTPS-only transport, refresh tokens never sent to non-auth endpoints, single-retry interceptor that breaks token-loss loops. Real revocation (refresh-token blocklist or a JTI table) is on the Phase 1 backlog for the slice that introduces incident response.
**Operational note:** There is no public sign-up. First user is bootstrapped with `python -m scripts.create_admin --username <name> --password <secret>` from the `backend/` directory. Subsequent users are created by administrators (UI for this is on the backlog).

**ADR-011**

## Refresh-Token Rotation with JTI Block-List

**Date:** 2026-05-28
**Decision:** Refresh tokens carry a `jti` (JWT ID) claim and are tracked in a `revoked_jti` block-list table. `/auth/refresh` rotates: every successful exchange issues a new access AND a new refresh token, and the old refresh token's JTI is added to the block-list. `/auth/logout` now takes the refresh token in its body, validates it, and revokes its JTI; no access-token header is required. Supersedes the stateless-refresh half of ADR-010 (the rest of ADR-010 still applies).
**Rationale:** Rotation gives every refresh token a single-use lifetime, dramatically reducing the value of a stolen refresh token. The block-list lets us forcibly invalidate a specific token without rotating `APP_SECRET_KEY` (which would invalidate every active session). Block-list is preferred over allow-list for Phase 1: smaller table, fewer writes per issue, and the natural-expiry timestamp means we can prune later. The refresh-rotation pattern is also a theft-detection primitive: if the old refresh token shows up again after rotation, that is evidence of replay.
**Risks accepted:** Access tokens still have a 30-minute lifetime gap on logout: we do not revoke the in-flight access token, only the refresh token. If immediate access-token revocation is needed, the operator hammer is still `APP_SECRET_KEY` rotation. A per-request access-token block-list lookup would close that gap at the cost of one DB read per authenticated request, and is on the backlog.
**Operational note:** The `revoked_jti` table grows by one row per logout and one row per refresh-rotation. A pruning job that removes rows past their `expires_at` is on the backlog. Until it lands, table growth is bounded by token TTL: rows older than 7 days are no longer load-bearing.

**ADR-012**

## Holly Runs as One Bluestaq App Store Container

**Date:** 2026-10-14 (Holly V0.2)
**Decision:** Holly ships as one container image on the Bluestaq App Store, `python` template, built from the `Dockerfile` at the repository root. The image compiles the React dashboard from `frontend/` in its own stage and serves it from the same FastAPI process as the API under `/api/v1` and the platform probes. gunicorn runs exactly one uvicorn worker, binds `0.0.0.0` on `PORT` (8080 when unset), and applies the Alembic migrations in its master process before the worker starts, under a PostgreSQL advisory lock. PostgreSQL comes from the App Store POSTGRESQL add-on and procedure files from the FILE_STORAGE add-on; settings arrive as App Store environment variables. TLS termination is the platform's responsibility. Supersedes ADR-003 and ADR-004; amends ADR-002, ADR-005 and the operational note of ADR-010.
**Rationale:** The reasons are recorded in the repository. The App Store builds one image from the root `Dockerfile`, so the container is the whole build (`CLAUDE.md`). Building the dashboard in its own stage keeps Node, npm and `node_modules` out of the image (`Dockerfile`). Served from the API's own origin, the dashboard needs no cross-origin access, so `APP_ALLOWED_ORIGINS` is empty by default (`src/app/config.py`). The migrations ship inside the package, so the container needs no `alembic.ini`, and the advisory lock makes a second container that starts at the same time wait and then find nothing to do (`src/app/migrate.py`). There is exactly one worker because the background loops for UDL, Mattermost and the assistant run inside it, and a second worker would pull and bill everything twice; the rate limits and the daily assistant token cap also count in that one process (`src/app/gunicorn_conf.py`).
**Consequences:**

● Retired with the fusion: the nginx configuration and certificates, the development Dockerfiles, `scripts/dev.ps1`, `.env.example`, python-jose and the `/ws` proxy. Local development runs `sh scripts/dev.sh` against a database-only `infra/docker-compose.yml`, and [developer setup](../developer/setup.md) lists every setting.
● The rate limits, the daily token cap and the background loops live in one process: they reset when the container restarts, and a second replica would run its own. The number of replicas the platform runs is `TBC, re-verify`.
● A failed migration stops the container. So does a rollback to a package older than the database's newest migration, because Alembic cannot locate a revision the older code does not have; a rollback across a migration needs the database restored to match.
● Holly's database user runs the migrations and so owns every table, `audit.audit_log` included, and ADR-005's INSERT-only permissions cannot hold for an owner. Migration `0017_audit_append_only` enforces append-only with a statement-level trigger instead. The owner could still disable the trigger deliberately; the hash chain (`python -m app.cli.verify_audit`) detects a change made that way, unless every later hash is recomputed too, because nothing anchors the chain outside the database.
● `DATABASE_URL` is the assumed name of the add-on's connection variable (`TBC, re-verify`); Holly also accepts the `POSTGRES_*` parts. The App Store's upload page lists the add-on as PostgreSQL 16, its minor version `TBC, re-verify`; the container smoke rung tests 16.15, and local development uses 15.19.
● The first admin is created with `python -m app.cli.create_admin --username <name>` inside the running container, or anywhere with the database settings. The password comes from `ADMIN_PASSWORD` or a hidden prompt; the `--password` flag in ADR-010's operational note is gone. Whether the platform offers a shell in the running container is `TBC, re-verify`.
● Behind the platform ingress, the client address Holly writes to the audit log and rate-limits by is the ingress's own, unless gunicorn is set to trust the ingress's forwarded headers (`FORWARDED_ALLOW_IPS`). Whether the platform provides those headers, and which address to trust, is `TBC, re-verify`.

**ADR-013**

## Holly's Access Token Travels in X-Holly-Token

**Date:** 2026-10-20 (Holly V0.9)
**Decision:** The dashboard sends Holly's access token in a header of Holly's own, `X-Holly-Token`, holding the token alone, and `get_current_user` reads that header and never `Authorization`. The tokens, their signing and lifetimes, and the refresh and sign-out bodies are unchanged. Amends ADR-010, whose tokens travelled in `Authorization: Bearer ...`.
**Rationale:** On the App Store, V0.8 signed the admin in and then returned to the sign-in page at once. The browser's record of the failing `GET /api/v1/auth/me` (20 October 2026) shows a 401 with an empty body and `WWW-Authenticate: Bearer error="invalid_token", error_description="An error occurred while attempting to decode the Jwt: Signed JWT rejected: Another algorithm expected, or no matching key(s) found"`, naming the platform's own `/.well-known/oauth-protected-resource`, and none of the headers Holly sets: the gateway in front of the app answered for Holly and refused Holly's token as one it could not verify with the platform's keys (fact). That it did so before Holly saw the request, and would do the same to any bearer token in `Authorization` the platform did not sign, are inference from the missing headers and from the wording, which is Spring Security's resource server. Sign-in carries no bearer token and passed. The same sequence against the V0.8 image locally, with no gateway, stayed signed in. A header of Holly's own leaves `Authorization` to the platform. The alternative, asking the platform team to stop checking bearer tokens on Holly's host, would relax a platform-wide control on their timeline, and exempting the path alone would not do, since such a gateway refuses a bad bearer token even on an open path (inference).
**Consequences:**

● Holly never reads `Authorization`: a token the gateway puts there changes nothing, and a Holly token there signs nobody in.
● CORS no longer allows credentials mode for a listed origin: Holly reads no cookie, and the `_appstore_app_session` cookie seen on requests to Holly's host (the platform's, by inference from its name) would only ride along.
● The CSRF position of ADR-010 holds: the token is a header only the page's own script sets, never a cookie, and a page on another origin cannot send it without a CORS preflight, which Holly refuses while `APP_ALLOWED_ORIGINS` is empty.
● Scripts send `X-Holly-Token: <token>` (operator manual, section 06). Whether the gateway lets a request through without the caller's App Store sign-in is `TBC, re-verify`.
● That the gateway passes `X-Holly-Token` through unchanged is inference until V0.9 runs on the App Store. The container smoke rung proves Holly's side, signing in and then calling `/api/v1/auth/me` with the token in each header; only a gateway in front of the container can reproduce the refusal, and none is in the repository.
● Leaving `Authorization` gives up the care intermediaries give it. A shared cache does not store the answer to a request carrying it unless told it may (RFC 9111, section 3.5), and log tools commonly redact it; neither holds for `X-Holly-Token`. Holly's `Cache-Control: no-store` on every response is now the only shared-cache protection for a signed-in answer, and whether the gateway logs the header is `TBC, re-verify` (SECURITY.md).
● Holly's 401 still challenges `Bearer`, and sign-in still answers `token_type: "bearer"`, though the token no longer travels in `Authorization`. The bare challenge is how an operator tells Holly's 401 from the gateway's (operator manual, section 10), and the token type names what the token is, not where it goes.
● The secret-scan hook gains rules for a JSON Web Token and for a token in `X-Holly-Token`, which its `Bearer` rule caught only in `Authorization`.

**ADR-014**

## Admins Manage Accounts; a Token Version Ends Sessions

**Date:** 2026-10-20 (Holly V0.10)
**Decision:** An admin manages accounts on a Users page backed by admin-only routes under `/api/v1/users`: list, create with a role and a temporary password, reset a password to a temporary one, and change a role or an account's status. Accounts are never deleted. Every user changes their own password at `POST /api/v1/auth/password`, giving the current one. A password an admin sets is temporary: the account's `must_change_password` is set, and `get_current_user` refuses it with a 403 on every route but `/auth/me` and `/auth/password` until the user chooses their own. Every token carries its user's `token_version`, checked on every request and refresh; a password change, a reset, a deactivation and `create_admin` on an existing account raise it. Migration 0018 adds both columns. Amends ADR-010's operational note and ADR-012's consequence on creating accounts.
**Rationale:** Holly had no way to add an account but the first admin: the app owner asked for one on 20 October 2026, choosing a temporary password the user must change at first sign-in, and a password change for every user, over a generated one-time password or an admin-set password with no forced change. Without a token version, a reset would not end a stolen session: the stolen refresh token, valid for 7 days, would work again as soon as the user had chosen a new password, since the forced change would be cleared. The version ends every earlier session at once instead, with one integer compared on each request, where a per-token block-list would grow with every session. The 403 keeps the dashboard's session, which a 401 would end through the refresh-and-sign-out path, and the gate is the server's: the dashboard's redirect to the password page is a convenience. An admin cannot change their own account on the page, and the last active admin cannot be demoted or deactivated, counted with the account under one row lock so two admins changing each other at once cannot leave none.
**Consequences:**

● Any admin can create another admin, so every admin is trusted with every account, and the admin knows a temporary password until the user changes it (SECURITY.md).
● A token issued before V0.10 carries no version and reads as 0, so V0.10 signs nobody out; the first change to an account ends that account's older tokens.
● Every change to a password, a role or a status reads the account again under a row lock before it decides, and writes what it decided on that read (`services/accounts.py`). Without it, a password change running at the same moment as a reset undid the reset: both gates reproduced it on PostgreSQL, 8 times in 8 (fact), the change's password, version and cleared flag landing after the reset's, so a stolen session survived it. The lock is `FOR NO KEY UPDATE`, so a row that names the user, such as a shift note, never waits on it, and the rows are locked in one statement in id order, so two changes cannot deadlock. The container smoke rung races the two three times on PostgreSQL.
● A new username is lowercase `a` to `z`, `0` to `9` and `. _ @ -`, so no new name can pass for another on the Users page or in the audit view (a Cyrillic letter for a Latin one, a combining accent). The first admin's, from `ADMIN_USERNAME` or `create_admin`, is not held to it; nor is any account made before V0.10. An email already in use in any case is refused.
● A rollback to V0.9 needs the database at migration 0017 first: V0.9 cannot start on a database at 0018 it does not know (ADR-012). The image ships no `alembic.ini`, so `alembic downgrade` fails there. In the V0.10 container, immediately before V0.9 is deployed, run `python -c "from alembic import command; from app.migrate import alembic_config; command.downgrade(alembic_config(), '0017_audit_append_only')"`. V0.10's engineering review rehearsed it on PostgreSQL 16 (fact): the schema went to 0017 and both columns went; V0.9 then started, and an account created in V0.10 with a temporary password signed in and read notifications. Meanwhile V0.10 answers 500 to requests that read an account, and a restart of V0.10 applies 0018 again. Under V0.9 a temporary password grants full access with no change asked. V0.9 checks no version, so every session V0.10 ended by raising it works again under V0.9 until it expires (V0.10's security gate showed a refresh token refused by V0.10 answering 200 under V0.9); `APP_SECRET_KEY` is rotated before the downgrade for that reason, and again with any later V0.10 upload, since rolling forward starts every version at 0 and clears every pending change, which an admin then sets again. The operator manual (section 03) gives the order, and a way with no shell: V0.9's code with migration 0018 added, released as a new version. Whether the App Store offers a shell in the container is `TBC, re-verify`; without one, restore the database instead.
● `tests/test_app.py` pins the routes reachable while a password change is due, beside the routes open without sign-in.

**ADR-015**

## Holly Finds the Bot's Channels; a Shared Follow List Decides What It Pulls

**Date:** 2026-10-21 (Holly V0.12)
**Decision:** Every Mattermost cycle (60 seconds by default, `MATTERMOST_INTERVAL_SECONDS`) begins with a sweep: Holly asks Mattermost for the bot's teams (`GET /api/v4/users/me/teams`), then for the bot's channels in each team, archived ones included (`GET /api/v4/users/me/teams/{team_id}/channels?include_deleted=true`), and records each public (`O`) and private (`P`) channel in the `mattermost_channel` table (migration 0019). A direct (`D`) or group (`G`) message is never recorded or pulled. A channel found for the first time is followed at once and flagged new until someone marks it reviewed, unless it is already closed, when it arrives reviewed. A channel whose name or display name holds the word CLOSED, in any case and with no letter either side, or that is archived, is closed: Holly keeps what it pulled from it and pulls nothing more; should the word go, it reopens. A channel a complete sweep no longer finds is marked as one the bot can no longer read and is not pulled; a sweep that skipped a malformed record marks none so. A bot in more than 100 teams or 1,000 channels fails the sweep. The sweep is committed before the pull, so no channel row stays locked while Mattermost answers. Holly pulls the channels that are followed, open and readable. Any signed-in user may follow or unfollow a channel, or mark new ones reviewed, on the Comms page, and each change is audited. `MATTERMOST_CHANNEL_IDS` becomes a seed: while the table is empty it decides what Holly pulls, and the channels it names arrive reviewed on the first sweep that finds any. The feed of the followed channels asks the server by the follow list (`followed=true`), not by a list of ids, so it holds however many channels are followed. The Comms page shows the followed channels in one feed, or one channel as a conversation, with a toggle between the two.
**Rationale:** The app owner asked for it on 20 October 2026 (fact): the list of channel ids in an environment variable is not dynamic, the team opens new channels often, and a channel missing from the list was missed. They asked for Holly to find the channels itself, for a channel with CLOSED in its title to yield nothing more than what was already pulled, and for a list of open channels to choose from; and they chose, from the options put to them, that any signed-in user may change the shared follow list, that a new channel is followed at once and flagged new, that CLOSED counts in any case, and both layouts with a toggle. Following at once means a new channel is never missed; flagging it means someone sees that it arrived. Asking for the bot's own memberships, rather than every channel on the server, reads only what the bot can read, in two calls and one more a team each cycle. A sweep that fails part-way changes nothing, so a Mattermost outage never marks a channel lost; while the table is empty, the old list keeps working.
**Consequences:**

● Whoever adds the bot to a Mattermost channel, public or private, decides that Holly reads it and that every signed-in user of Holly sees it (SECURITY.md). Taking the bot out of a channel, archiving it or putting CLOSED in its name stops Holly pulling it; what was pulled stays.
● The follow list is shared, so one user's unfollow stops the pull for everyone; the audit log names who made each change, from and to. Messages already pulled stay, on the Comms page; from V0.12 a channel switched off or closed no longer reaches the assistant's soft context at once, and the rest reach it until they are older than its window (`MATTERMOST_PROMPT_WINDOW_HOURS`, 6 by default). A channel is closed by the word CLOSED in either name as Mattermost sent it, before Holly cleans the names to show, so a name too odd to show still closes it.
● A sweep on demand (**Find channels now**, `POST /api/v1/mattermost/sweep`) runs the same cycle at once, joining one already running, at most 6 times a minute for each user.
● What the latest sweep found, when it ran and as which bot are held in the process, not the database, and start again empty at every restart; a sweep's problem is Holly's own message, never Mattermost's.
● A rollback to V0.11 needs the database at migration 0018 first, since V0.11 cannot start on a database at 0019: in the V0.12 container, immediately before V0.11 is deployed, run `python -c "from alembic import command; from app.migrate import alembic_config; command.downgrade(alembic_config(), '0018_user_password_state')"`, which drops `mattermost_channel` and keeps every message. V0.10 then pulls the channels `MATTERMOST_CHANNEL_IDS` names again, so set it to the channels to keep. Both releases check the token version, so no key rotation is needed for this step.

Bluestaq Limited | Holly documentation | 2026
