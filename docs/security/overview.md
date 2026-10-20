**BLUESTAQ LIMITED** | Security Overview

# Security Overview

**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify (the Daily Operations Dashboard Team, Bluestaq Limited, owned the edition this one replaces)
**Version:** 0.6
**Last updated:** 2026-10-20

> **BLUF**
>
> Holly carries Unclassified data on the Bluestaq App Store. Its controls aim at integrity, audit and operational hygiene: JSON Web Token (JWT) sign-in on every data route, an append-only and hash-chained audit log, strict response headers, a classification-marking check before a notification reaches the assistant, request and cost limits that fail closed, settings validated at boot, and scanned dependencies. TLS is the platform's. Accepted positions and their trip-wires are in [SECURITY.md](../../SECURITY.md).

**SECTION 01**

## Posture

Holly serves SDA watch analysts from one container on the Bluestaq App Store. All data it processes is recorded as Unclassified (ADR-006), so the controls below aim at integrity, audit and operational hygiene rather than at protecting classified material. The Daily Operations Dashboard assumed a sovereign UK host behind a trusted operator network; whether the App Store hosting meets that assumption is `TBC, re-verify`.

**SECTION 02**

## Data classification

● **Unclassified**, per ADR-006, which covers UDL notifications and element sets, Mattermost content, procedure documents and analyst inputs. UDL manoeuvre records are a UDL source like the others; ADR-006 does not name them.
● ADR-006 permits commercial AI APIs (Anthropic Claude) for this data; Holly narrows that by classification marking (next point). Section 09 lists exactly what Holly sends to Anthropic.
● **Classification markings.** A UDL notification reaches the assistant only when its classification marking is listed in `ASSISTANT_CLEARED_MARKINGS`, `["U"]` by default and matched exactly; a notice with any other marking, or none, never leaves Holly ([src/app/services/disclosure.py](../../src/app/services/disclosure.py)). An evaluation request for such a notice stores `Not sent to the assistant: ...` and calls nothing, the background cycle evaluates a notice only when its latest publication is cleared, and an event narrative is written from the event's cleared publications only. The manoeuvre records sent with a cleared notice must be cleared too. Clearing a further marking is the data owner's decision; who that is, and whether the `JCO` source's own marking may be cleared, is `TBC, re-verify`.

When a new data source is added, ADR-006 must be re-evaluated. Holly refuses no record at ingest by its marking: it stores and shows whatever its pulls return, and the marking decides only what reaches the assistant. Whether a source carrying a higher classification may be connected at all is the data owner's decision (`TBC, re-verify`).

**SECTION 03**

## Authentication

### Current state

● HS256 JWT bearer tokens, issued by `POST /api/v1/auth/login` and refreshed at `POST /api/v1/auth/refresh` (ADR-010 and ADR-011), signed with `APP_SECRET_KEY` through PyJWT. `JWT_ALGORITHM` may select HS384 or HS512. Decoding accepts the configured algorithm only and requires the `exp`, `sub`, `type` and `jti` claims, so an unsigned or differently signed token never verifies ([src/app/core/security.py](../../src/app/core/security.py)). The Daily Operations Dashboard's python-jose is gone.
● Access tokens last 30 minutes and refresh tokens 7 days by default. Every token carries its own JWT ID (JTI).
● **Refresh-token rotation (ADR-011).** Every successful refresh issues a new access token and a new refresh token, and the old refresh token's JTI joins the `revoked_jti` block-list. A reused refresh token is refused and audited with reason `revoked_token`.
● **Server-side sign-out.** `POST /api/v1/auth/logout` takes the refresh token in its body, revokes its JTI and audits the action.
● **Access tokens are not block-listed.** After sign-out, an access token stays valid until it expires, up to 30 minutes by default. Every request does check that the user still exists and is active.
● **A token version ends a user's sessions (ADR-014).** Every token carries the user's `token_version`, checked on every request and every refresh. A password change, an admin's reset or deactivation, and `create_admin` on an existing account raise it, so every token issued before stops at once; a change keeps only the session it was made in, with a new pair. Each reads the account again under a row lock before it writes, and a password change refuses if its session ended while it ran, so a reset always beats a change running at the same moment (`services/accounts.py`). A token from before V0.10 carries no version and reads as 0.
● **A temporary password must be changed.** A password an admin sets on the **Users** page is temporary: until the user chooses their own at `POST /api/v1/auth/password`, every route but `/auth/me` and `/auth/password` answers 403, server-side. The change checks the current password against the same per-username limit as sign-in and needs a new one of 12 to 1,024 characters, not spaces alone; the dashboard checks the same rule first, counting as the server does (`tests/test_password_rule.py`).
● **Passwords** are bcrypt hashes from the `bcrypt` library; only the first 72 bytes of a password count.
● **Guessing is limited.** Every sign-in attempt counts against its client address before any password is checked: after 30 in a minute, further attempts from that address answer 429 `Too many sign-in attempts from this address. Try again in <n> seconds.` with `Retry-After`, unaudited. Each sign-in whose password is checked counts against its username before the check starts, so guesses sent together cannot pass the limit: after 10 within 15 minutes, further attempts for that username answer 429 with `Retry-After` and are audited with reason `rate_limited`. A success clears the count, and an attempt refused because sign-in is busy does not count. An unknown username still costs a real bcrypt check against a dummy hash, so response time does not reveal which usernames exist ([src/app/api/v1/routes/auth.py](../../src/app/api/v1/routes/auth.py)).
● **Sign-in cannot stall the worker.** bcrypt runs on worker threads, at most 4 checks at once. A sign-in beyond them answers 503 `Sign-in is busy. Try again in a moment.` with `Retry-After: 1` at once, rather than queueing; a password change, `Password checks are busy. Try again in a moment.`
● **An unknown username is not recorded.** A failed sign-in's audit row carries the username only when it names an account: an unknown one may be a password typed into the wrong box, and the audit chain is append-only.
● **Bounded input.** Usernames are at most 50 characters, passwords 1,024 and tokens 4,096; anything longer is refused before any work.
● **In the browser**, both tokens are kept in `localStorage` under `holly.auth.access` and `holly.auth.refresh`. Any script running in Holly's origin could read them; the dashboard's Content Security Policy (CSP), which allows scripts from Holly's own origin only and no inline script, is the mitigation.

### Bootstrap

There is no public sign-up. The first admin is created with:

```sh
python -m app.cli.create_admin --username <name>
```

The password comes from `ADMIN_PASSWORD` or a hidden prompt, never a command-line flag, and must be at least 12 characters. Each run writes an `auth.user.admin_upsert` audit row. On the App Store the first admin comes from the `ADMIN_*` variables instead (operator manual, section 08). Every later account is created by an admin on the **Users** page.

**SECTION 04**

## Authorisation

The `User` model holds one of three roles (`analyst`, `operator`, `admin`), and `require_role(*roles)` in [src/app/dependencies.py](../../src/app/dependencies.py) gates a route by role.

Currently gated:

● `GET /api/v1/audit` requires `operator` or `admin`. Analysts receive HTTP 403.
● `/api/v1/users` and its routes require `admin`: listing accounts, creating one, resetting a password, and changing a role or status. An admin cannot reset, demote or deactivate their own account there, and the last active admin cannot be demoted or deactivated (ADR-014).

Every other signed-in route is open to any role. In particular, any signed-in user can delete any procedure, edit or delete any shift-log entry, and dismiss or delete any event timer; nothing checks ownership.

The dashboard hides the **Audit log** link from analysts and the **Users** link from everyone but admins, and sends a visitor without a token to the sign-in page. Both are conveniences: the server's checks are the control. [tests/test_app.py](../../tests/test_app.py) pins the routes open without sign-in: the probes, `/`, `/status`, `/api/v1/health`, `/api/v1/health/detailed`, and the login, refresh and logout routes. Any other route that does not demand a valid access token fails that test.

**SECTION 05**

## Audit logging

Every state-changing action writes an audit row. The log is tamper-evident through a SHA-256 hash chain over each row's stored fields (ADR-008), with concurrent writes serialised by a PostgreSQL advisory lock inside the transaction. A trigger refuses every UPDATE, DELETE and TRUNCATE on `audit.audit_log` (migration `0017_audit_append_only`). It is a trigger, not a permission: Holly's database user owns the table and could disable it deliberately (ADR-012). `python -m app.cli.verify_audit` recomputes the chain and names the first broken row. The hash uses no secret and nothing outside the database records the chain's head, so an edit made with the trigger disabled is detected unless every later hash is recomputed too.

The action types, what each records, and what is not recorded are in [docs/audit/overview.md](../audit/overview.md). The viewer at `GET /api/v1/audit` (operators and admins only) backs the dashboard's **Audit log** page.

**SECTION 06**

## Transport security

● **TLS** terminates at the App Store platform; its configuration is the platform's responsibility and `TBC, re-verify`. Holly serves plain HTTP inside the platform, on `0.0.0.0` and `PORT` or 8080. There is no nginx and no in-app TLS (ADR-012).
● Holly sets no Strict-Transport-Security (HSTS) header; whether the platform adds one is `TBC, re-verify`.
● **Outbound:** outside development, Holly refuses to start with a UDL or Mattermost URL that is not https, or with `UDL_VERIFY_SSL=false`. The Mattermost client verifies certificates; the Anthropic client uses its library's default endpoint.
● **Database:** reached through the POSTGRESQL add-on's connection settings. Network isolation of the database is the platform's: `TBC, re-verify`. The Daily Operations Dashboard's internal Docker network is retired.
● What Holly relies on the platform ingress for (host routing, malformed framing, slow clients) is listed in [SECURITY.md](../../SECURITY.md).

**SECTION 07**

## HTTP hardening

From [src/app/factory.py](../../src/app/factory.py) and [src/app/core/](../../src/app/core/):

● **Headers on every response**, errors included, but a Cross-Origin Resource Sharing (CORS) preflight, which CORS answers before them (SECURITY.md): `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, an `X-Request-ID`, and a CSP. HTML pages (the dashboard) get `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`; every other response gets `default-src 'none'; frame-ancestors 'none'`.
● **Body cap:** a request body over 256 KiB is refused with 413; only a procedure upload (`POST /api/v1/procedures`) may reach 11 MiB. The refusal comes at once when the declared length is too large, or the moment a streamed body passes the cap, so an oversized upload never fills memory or disk.
● **Procedures:** the upload's form is read only after sign-in, with at most one file and two fields, so an anonymous caller cannot make Holly parse or spool a large body. Uploads are capped at 10 MiB and stored as `<id><plain extension>`, so an uploaded file name never reaches the filesystem. Every download is an `application/octet-stream` attachment with a safely encoded file name, whatever type the uploader claimed, so a stored file cannot render as a page in Holly's origin.
● **Text Holly cannot store is refused at the door:** a NUL, which PostgreSQL can neither store nor compare, or text that will not encode as UTF-8, answers 422 in every request body, upload form field, upload file name and type, and free-text query parameter, before any query, assistant call or write ([src/app/schemas/common.py](../../src/app/schemas/common.py)). Every 422 names each field and its problem, never the submitted value, so a refused sign-in never sends a password back.
● **No interactive API documentation** (`/docs`, `/redoc` and `/openapi.json` answer 404), and no trailing-slash redirect, which would echo the request's `Host` header.
● **No Cross-Origin Resource Sharing (CORS)** by default: `APP_ALLOWED_ORIGINS` is empty, and Holly refuses to start with `*`.
● **Request ids** from a caller are kept only when they are a plain token of at most 128 characters, so a caller cannot write arbitrary text into logs or headers.
● **Errors:** a 500 has a generic body, with the detail in the server log. A failed upstream call answers 502 with Holly's own short message; the upstream body goes to the server log, cut to 200 characters, never to the browser.
● **Untrusted values in the dashboard:** a link that arrives in UDL data becomes clickable only when it is an absolute http or https URL, and every link that opens a new tab carries `rel="noopener noreferrer"`. The shift-log HTML export escapes every stored value.

**SECTION 08**

## Rate limits and cost caps

All limits live in the one worker process and reset when the container restarts ([src/app/core/rate_limit.py](../../src/app/core/rate_limit.py), [src/app/services/claude.py](../../src/app/services/claude.py)):

| Limit | Applies to | Allowance |
|-------|------------|-----------|
| Coarse | Every request under `/api/` and `/status`, per client address | 600 in any 60 seconds |
| Sign-in attempts | Every sign-in attempt, per client address, counted before any password check | 30 in any 60 seconds |
| Sign-in | Checked sign-ins, per username, each counted before its check; a success clears the count | 10 in any 15 minutes |
| Assistant | Each request that calls the assistant, per user: evaluations, **Pull from UDL**, new shift-log entries, re-polish and the end-of-shift narrative | 30 in any 10 minutes |
| Daily tokens | Every assistant call, across all users and the background cycle, per UTC day | `LLM_DAILY_TOKEN_CAP`, 2,000,000 by default |

The first four answer 429 with `Retry-After`, except that a new shift-log entry made after the assistant allowance is spent is saved unpolished rather than refused. Sign-in also runs at most 4 password checks at once and answers 503 beyond them (section 03). The probes and the dashboard's static files are never limited. Each limiter remembers at most 10,000 keys, dropping the stalest first, so a flood of distinct keys cannot grow memory without bound. A locked username is dropped like any other key, and only a checked attempt takes a place: checking 10,000 other usernames, about 13 minutes with all four checks busy, frees it for 10 more guesses (SECURITY.md). Each assistant call holds its whole output allowance and one token for every 3 characters of its prompt against the daily token cap before it is sent, with nothing awaited between the check and the hold, so calls made together cannot overrun the cap; the hold is settled to the call's real use afterwards, or given back when no reply arrives. A call the rest of the day's cap cannot cover fails closed; the count starts again each UTC day.

**The client address** is the one the server sees. Behind the platform ingress that is the ingress's own address unless gunicorn is set to trust the ingress's forwarded headers through `FORWARDED_ALLOW_IPS`; by default gunicorn trusts only `127.0.0.1` and `::1` ([src/app/core/net.py](../../src/app/core/net.py)). Until that is confirmed (`TBC, re-verify`), assume every caller shares one coarse allowance and one allowance of sign-in attempts, and the audit log records the ingress's address. Anyone who can reach Holly could then spend the shared sign-in allowance, with no credentials, by one attempt every 2 seconds, and keep every analyst from signing in while they kept it up.

**SECTION 09**

## The assistant

Every call goes through one function, `call_claude` ([src/app/services/claude.py](../../src/app/services/claude.py)):

● The API key is read server-side at call time; without it every call fails closed and the error is stored, except that an event narrative keeps its earlier text.
● Model output is untrusted. An evaluation must parse as one JSON object of the expected shape, with bounded lengths and counts and an urgency of `high`, `medium` or `low` ([src/app/schemas/assistant.py](../../src/app/schemas/assistant.py)). A procedure id the model was not given is dropped. A reply that fails, including one nested too deeply to decode, one with no JSON object among its first 20 opening braces, or one holding a character PostgreSQL cannot store (a NUL, which the model can write as a JSON escape), is retried once and then stored as an error, with no advice.
● Each call writes one `llm.call` log line with its purpose, model and token count, never its content.
● An Anthropic API failure reaches analysts as a fixed message for its class, such as `The assistant rejected Holly's API key.`; the API's own error text goes to the server log only.
● A persistent failure (a rejected key, no permission, a model the API does not offer, rate limiting, exhausted credit, or a daily cap that cannot cover the call) stops the background phase early instead of retrying every notice.
● Each background evaluation writes an `assistant.evaluate` audit row and each background narrative an `assistant.event_summary` row, as an on-demand evaluation does. Once a notice or event may have been sent, any failure to store its result or write its row stops that phase for the cycle, so at most one sending a phase can go unrecorded; a narrative is stored only in the same transaction as its row.

**What Holly sends to Anthropic:** for an evaluation of a notice whose marking is cleared (section 02), the notification's fields, up to 10 manoeuvre records for its satellites from the last 30 days whose own marking is cleared, up to 30 team chat messages from the last 6 hours (each cut to 500 characters), and every uploaded procedure, with the text of those uploaded as plain text, Markdown, JSON or CSV (up to 64 KiB each). For an event narrative, the fields of each of the event's publications whose marking is cleared. For the shift log, the analyst's raw entry (polish) or the day's entries (summary).

**SECTION 10**

## Secrets management

● Every setting is read from the environment: App Store environment variables in deployment, and the shell or a local `.env` in development ([developer setup](../developer/setup.md) lists them). There is no `.env.example`.
● Secrets are held as secret strings, so their values never appear in a log line. Holly's own configuration errors never repeat the database URL.
● `/status` reports only whether four non-secret inputs are set, and their lengths: `PORT`, `APP_ENV`, `STORAGE_MOUNT_PATH` and `PROCEDURE_STORAGE_PATH`.
● `APP_SECRET_KEY` signs the tokens and must be at least 32 characters. Treat it as a credential; rotating it signs every user out.
● Environment files are ignored by Git (`.gitignore`) and kept out of the image's build context (`.dockerignore`).
● The upload sent to the App Store is an allowlist of tracked paths, and every file in it passes a content scan with the secret-scan hook's rules before the package is written ([scripts/check-package.sh](../../scripts/check-package.sh)). The same check refuses the agent configuration (`CLAUDE.md`, `CLAUDE.local.md`, `.mcp.json` and anything under `.claude/`) by name, so a change to the path list cannot ship it, and refuses any member name that is not printable ASCII, holds a backslash, or would change on extraction, any member that is not a regular file, and a zip that does not hold exactly the committed files of the commit packaged, byte for byte. [SECURITY.md](../../SECURITY.md) lists what that scan cannot see.
● Claude Code's pre-write hook ([.claude/hooks/secret-scan.mjs](../../.claude/hooks/secret-scan.mjs)) blocks a credential-shaped string in any file Claude writes.
● No repository-wide secret scanner, such as the Daily Operations Dashboard's gitleaks, runs in CI or as a commit hook.

**SECTION 11**

## Dependency, code and container scanning

The verification loop, [scripts/verify.sh](../../scripts/verify.sh), runs on every change and in CI ([.github/workflows/verify.yml](../../.github/workflows/verify.yml)):

● **ruff** for formatting and lint, including its `S` (security) rules.
● **mypy** in strict mode over `src` and `tests`.
● **complexipy** (cognitive complexity at most 15 per function) and **pylint**'s duplicate-code check, the local stand-ins for the platform's SonarQube quality gate.
● **pytest** with coverage, failing under 80%.
● **pip-audit** over both hash-pinned Python locks, and **npm audit** over the dashboard, which fails on any known vulnerability of any severity.

Supply chain: Python installs only from the hash-pinned locks (`--require-hashes`), the dashboard installs from its lockfile with install scripts off, and both base images are pinned by digest. The image runs as the numeric user 10001, carries no pip and no setuid or setgid bit, and ships as one flattened layer. The App Store's own pipeline, quality gate and image scan are the binding checks.

**SECTION 12**

## Threat surface

| Vector | Mitigation |
|--------|-----------|
| External attacker reaches the application | TLS and routing at the platform ingress. Every data route needs a valid access token; the open routes are pinned by a test. Strict headers and CSP on every response but a CORS preflight. |
| Password guessing | 30 sign-in attempts per client address a minute, counted before any password check; 10 checked sign-ins per username per 15 minutes, each counted before its check; a constant bcrypt cost for unknown usernames, on worker threads at most 4 at once, so a burst cannot stall the worker; and each attempt that is checked, or refused for its username, audited with its reason. |
| Compromised analyst credentials | Every state change is audited. Access tokens expire after 30 minutes. Refresh tokens rotate on every use, so a stolen one is single-use and its reuse is refused and audited. Deactivating the user stops their tokens at once. |
| Compromised UDL, Mattermost or Anthropic credentials | Held in environment variables, never in source. Holly only reads from UDL and Mattermost. Holly's daily token cap does not limit use of a stolen key outside Holly; rotate it at the source. |
| SQL injection | SQLAlchemy parameterises every query; no SQL is built by string concatenation. |
| Cross-site scripting (XSS) | React escapes by default and the dashboard uses no `dangerouslySetInnerHTML`. The CSP allows no inline or third-party script. Links from UDL data are limited to http and https. |
| Cross-site request forgery (CSRF) | Tokens travel in Holly's own `X-Holly-Token` header, not a cookie, which removes the standard CSRF vector: a page on another origin cannot send that header without a CORS preflight, which Holly refuses while `APP_ALLOWED_ORIGINS` is empty. `Authorization` is left to the App Store's gateway (ADR-013). |
| Prompt injection through UDL data, chat or procedures | Model output is validated, bounded and shown as advice; the assistant has no tools and cannot act. |
| Marked UDL content sent to Anthropic | Only notifications and manoeuvre records whose classification marking is listed in `ASSISTANT_CLEARED_MARKINGS` are sent, and each evaluation and narrative writes an audit row; once a sending may have gone, any failure to store it or its row stops that background phase for the cycle. |
| Cost exhaustion | Per-user assistant limit and a daily token cap that fails closed. |
| Supply-chain compromise | Hash-pinned Python locks, a committed npm lockfile with install scripts off, digest-pinned base images, `pip-audit` and `npm audit` in every loop. |
| Insider modifies the audit log | The append-only trigger refuses changes through the application's database user. The hash chain detects a change made by disabling the trigger or from outside the database, unless every later hash is recomputed too; nothing anchors the chain outside the database. |
| Accidental commit of secrets | `.env` files ignored by Git and kept out of the image; the upload content scan; Claude Code's pre-write hook. No repository-wide scanner runs (section 10). |

**SECTION 13**

## Incident response

There is no formal incident response runbook. Operational response is owned by the on-call engineer, following the [operator manual](../runbook/operator-manual.md) when the probes or `/api/v1/health` fail or the dashboard is unreachable.

> **KEY DECISION**
>
> A compromised refresh token is revoked when its holder signs out or when it is next used, through the `revoked_jti` block-list (ADR-011). To stop one user at once, an admin resets their password or deactivates them on the **Users** page, which raises their token version (ADR-014); to stop everyone, rotate `APP_SECRET_KEY`. If the token was an admin's, undo the account changes made with it (operator manual, section 11).

**SECTION 14**

## Review

This document is reviewed when a security-relevant change lands. Triggers include:

● New ingest sources.
● Authentication or authorisation changes.
● Network, platform or infrastructure changes, including any change in what the App Store ingress provides.
● New external integrations (AI APIs, cloud providers).
● Findings from a penetration test or audit.

Bluestaq Limited | Holly documentation | 2026
