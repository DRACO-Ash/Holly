**BLUESTAQ LIMITED** | Architectural Decision Log | **COMMERCIAL IN CONFIDENCE**

# Architectural Decision Log

**Document classification:** Commercial in Confidence
**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify (the Daily Operations Dashboard Team, Bluestaq Limited, owned ADR-001 to ADR-011)
**Version:** 0.3
**Last updated:** 2026-10-14

> **HOW TO READ THIS LOG**
>
> Each Architectural Decision Record (ADR) captures a single decision, its rationale, and (where helpful) alternatives considered and risks accepted. Superseded decisions remain in the log; their status line points to the ADR that replaced them. New ADRs are appended; numbering does not reset. ADR-001 to ADR-011 were made for the Daily Operations Dashboard, which Holly was built from; ADR-012 is the first made for Holly.

**ADR-001**

## Python / FastAPI Backend

**Date:** Sprint 1
**Decision:** FastAPI selected as the backend framework.
**Rationale:** Async-native, strong type support via Pydantic, automatic OpenAPI generation, high performance for API-heavy workloads.
**Alternatives considered:** Django REST Framework, rejected due to synchronous defaults and heavier footprint for this use case.

**ADR-002**

## PostgreSQL Database

**Date:** Sprint 1
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
**Status:** Superseded by ADR-011. Its operational note is replaced by ADR-012.
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

**Date:** TBC, re-verify
**Decision:** Holly ships as one container image on the Bluestaq App Store, `python` template, built from the `Dockerfile` at the repository root. The image compiles the React dashboard from `frontend/` in its own stage and serves it from the same FastAPI process as the API under `/api/v1` and the platform probes. gunicorn runs exactly one uvicorn worker, binds `0.0.0.0` on `PORT` (8080 when unset), and applies the Alembic migrations in its master process before the worker starts, under a PostgreSQL advisory lock. PostgreSQL comes from the App Store POSTGRESQL add-on and procedure files from the FILE_STORAGE add-on; settings arrive as App Store environment variables. TLS termination is the platform's responsibility. Supersedes ADR-003 and ADR-004; amends ADR-005 and the operational note of ADR-010.
**Rationale:** The reasons are recorded in the repository. The App Store builds one image from the root `Dockerfile`, so the container is the whole build (`CLAUDE.md`). Building the dashboard in its own stage keeps Node, npm and `node_modules` out of the image (`Dockerfile`). Served from the API's own origin, the dashboard needs no cross-origin access, so `APP_ALLOWED_ORIGINS` is empty by default (`src/app/config.py`). The migrations ship inside the package, so the container needs no `alembic.ini`, and the advisory lock makes a second container that starts at the same time wait and then find nothing to do (`src/app/migrate.py`). There is exactly one worker because the background loops for UDL, Mattermost and the assistant run inside it, and a second worker would pull and bill everything twice; the rate limits and the daily assistant token cap also count in that one process (`src/app/gunicorn_conf.py`).
**Consequences:**

● Retired with the fusion: the nginx configuration and certificates, the development Dockerfiles, `scripts/dev.ps1`, `.env.example`, python-jose and the `/ws` proxy. Local development runs `sh scripts/dev.sh` against a database-only `infra/docker-compose.yml`, and [developer setup](../developer/setup.md) lists every setting.
● The rate limits, the daily token cap and the background loops live in one process: they reset when the container restarts, and a second replica would run its own. The number of replicas the platform runs is `TBC, re-verify`.
● A failed migration stops the container. So does a rollback to a package older than the database's newest migration, because Alembic cannot locate a revision the older code does not have; a rollback across a migration needs the database restored to match.
● Holly's database user runs the migrations and so owns every table, `audit.audit_log` included, and ADR-005's INSERT-only permissions cannot hold for an owner. Migration `0017_audit_append_only` enforces append-only with a statement-level trigger instead. The owner could still disable the trigger deliberately; the hash chain (`python -m app.cli.verify_audit`) detects a change made that way, unless every later hash is recomputed too, because nothing anchors the chain outside the database.
● `DATABASE_URL` is the assumed name of the add-on's connection variable (`TBC, re-verify`); Holly also accepts the `POSTGRES_*` parts. The add-on's PostgreSQL version is `TBC, re-verify`; local development and the container smoke rung use PostgreSQL 15.19.
● The first admin is created with `python -m app.cli.create_admin --username <name>` inside the running container, or anywhere with the database settings. The password comes from `ADMIN_PASSWORD` or a hidden prompt; the `--password` flag in ADR-010's operational note is gone. Whether the platform offers a shell in the running container is `TBC, re-verify`.
● Behind the platform ingress, the client address Holly writes to the audit log and rate-limits by is the ingress's own, unless gunicorn is set to trust the ingress's forwarded headers (`FORWARDED_ALLOW_IPS`). Whether the platform provides those headers, and which address to trust, is `TBC, re-verify`.

Bluestaq Limited | Holly documentation | 2026 | **COMMERCIAL IN CONFIDENCE**
