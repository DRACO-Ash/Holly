**BLUESTAQ LIMITED** | Developer Setup

# Developer Setup

**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify (the Daily Operations Dashboard Team, Bluestaq Limited, owned the edition this one replaces)
**Version:** 0.4
**Last updated:** 2026-10-15

> **BLUF**
>
> One-time path from a clean machine to a running Holly: Python 3.12 and Node 22, the hash-locked install, a local `.env` with the settings below, a local PostgreSQL, the first admin, then `sh scripts/dev.sh`. Every change then passes `sh scripts/verify.sh`. There is no `.env.example`: the settings reference in section 04 replaces it.

**SECTION 01**

## Prerequisites

● **Python 3.12.** `.python-version` pins it and the verification loop refuses any other version.
● **Node 22** with npm, for the dashboard. The container build and CI both use Node 22.
● **Docker** with Compose v2, for the local PostgreSQL in `infra/docker-compose.yml` and for the container smoke rung. Any PostgreSQL you can reach works instead.
● **A POSIX shell.** Every shell script under `scripts/` is POSIX `sh`. The Daily Operations Dashboard's PowerShell script, `scripts/dev.ps1`, is retired.
● **`node` and `unzip`** for packaging, and `python3` for the self-test of the upload nets (`CLAUDE.md`).
● **Git.**

**SECTION 02**

## Clone and install

```sh
git clone <repo-url> holly
cd holly
python3.12 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.txt
(cd frontend && npm ci --ignore-scripts --no-audit --no-fund)
```

The first install command builds the virtualenv from the hash-pinned tooling lock, which includes every runtime dependency at the versions in `requirements.txt`. The second installs the dashboard's packages from `frontend/package-lock.json`, with install scripts off. `scripts/dev.sh` runs the second for you when `frontend/node_modules` is missing.

**SECTION 03**

## Where settings come from

Holly reads its settings from the environment, or from a `.env` file in the directory it runs from, which is the repository root for every command in this document ([src/app/config.py](../../src/app/config.py)). A variable set in the environment wins over the same name in `.env`. Two kinds come from the environment only, never from `.env`: `PORT`, and the admin command's `ADMIN_*` variables. `.env` is ignored by Git; never commit it and never copy a real value into any tracked file.

Holly validates its settings when it first reads them and refuses to start with one message, `Holly cannot start: ...`, that names the settings at fault and never repeats a value: a missing signing key or one shorter than 32 characters, a value of the wrong type or one that cannot be parsed, a `*` origin, no database settings, a non-https UDL or Mattermost URL outside development, `UDL_VERIFY_SSL=false` outside development, or a procedure directory that is relative or the filesystem root. In the container, gunicorn prints it as one line beginning `Error:`. Secrets are held as secret strings, so their values never appear in a log line.

To make a signing key:

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

It prints a random 64-character string. Put it in `.env` as `APP_SECRET_KEY`.

**SECTION 04**

## Settings reference

Every setting Holly reads. Names are environment variable names. Secret values are shown here only as `[REDACTED:type]`.

### Application

| Setting | Purpose | Default | Required |
|---------|---------|---------|----------|
| `PORT` | Port Holly listens on, on `0.0.0.0`. A whole number from 1 to 65535 with no sign or leading zero; anything else stops the start. Environment only. | `8080` | No |
| `APP_ENV` | `production` or `development`. `development` allows `http://` UDL and Mattermost URLs and `UDL_VERIFY_SSL=false`. | `production` | No |
| `APP_SECRET_KEY` | Signs and verifies sign-in tokens. At least 32 characters. Changing it signs every user out. Secret. | none | Yes |
| `APP_ALLOWED_ORIGINS` | Browser origins allowed to call the API from another origin, as a JSON list such as `["https://ops.example"]`. `*` is refused. The dashboard is served from Holly's own origin and needs none. | `[]` | No |

### Database

| Setting | Purpose | Default | Required |
|---------|---------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection URL with a host; `postgres://`, `postgresql://` and `postgresql+asyncpg://` are accepted. SQLAlchemy's parser reads it once, as the connection does: punctuation in the password may stay unencoded except `@`, as a URL holding more than one `@` stops the start, and `%` before two hexadecimal digits, which reads as an escape; write them as `%40` and `%25`. An `sslmode` query parameter, as PostgreSQL's own clients write it, is passed to asyncpg as `ssl`, which takes the same values. Wins over the `POSTGRES_*` parts. On the App Store this is the assumed name of the POSTGRESQL add-on's variable: `TBC, re-verify`. Secret, because it carries the password. | none | Yes, unless the `POSTGRES_*` parts are set |
| `POSTGRES_HOST` | Database host name or IP address, used when `DATABASE_URL` is not set. | none | Yes, without `DATABASE_URL` |
| `POSTGRES_PORT` | Database port, 1 to 65535. | `5432` | No |
| `POSTGRES_DB` | Database name. | none | Yes, without `DATABASE_URL` |
| `POSTGRES_USER` | Database user. | none | Yes, without `DATABASE_URL` |
| `POSTGRES_PASSWORD` | Database password. Secret. | none | Yes, without `DATABASE_URL` |

### Sign-in tokens

| Setting | Purpose | Default | Required |
|---------|---------|---------|----------|
| `JWT_ALGORITHM` | Signing algorithm: `HS256`, `HS384` or `HS512`. Decoding accepts this one only. | `HS256` | No |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime in minutes, 1 to 1440. | `30` | No |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh-token lifetime in days, 1 to 90. | `7` | No |

### Unified Data Library (UDL)

| Setting | Purpose | Default | Required |
|---------|---------|---------|----------|
| `UDL_BASE_URL` | UDL API base URL. Must be https outside development. | `https://unifieddatalibrary.com/udl` | No |
| `UDL_USERNAME` | UDL account, sent with HTTP Basic auth. Without it every UDL pull fails and is logged; the rest of Holly runs. | empty | For UDL data |
| `UDL_PASSWORD` | UDL password. Secret. | empty | For UDL data |
| `UDL_REQUEST_TIMEOUT_SECONDS` | Timeout per UDL request, 1 to 300 seconds. | `30` | No |
| `UDL_VERIFY_SSL` | Verify UDL's TLS certificate. `false` is accepted only in development. | `true` | No |

### Mattermost

| Setting | Purpose | Default | Required |
|---------|---------|---------|----------|
| `MATTERMOST_URL` | Mattermost server URL; Holly calls `/api/v4` under it. Must be https outside development. | empty | For chat |
| `MATTERMOST_BOT_TOKEN` | The bot account's personal access token. Secret. | empty | For chat |
| `MATTERMOST_CHANNEL_IDS` | Comma-separated channel ids to poll. The bot must be a member of each; a channel it cannot read is skipped and logged. | empty | For chat |
| `MATTERMOST_INTERVAL_SECONDS` | Chat poll interval, at least 10 seconds. | `60` | No |
| `MATTERMOST_PROMPT_WINDOW_HOURS` | How many hours of chat the assistant reads per evaluation; `0` sends none. | `6` | No |
| `MATTERMOST_MAX_MESSAGES_IN_PROMPT` | Most chat messages per evaluation; `0` sends none. | `30` | No |

### Assistant

| Setting | Purpose | Default | Required |
|---------|---------|---------|----------|
| `ANTHROPIC_API_KEY` | Key for every assistant call. Without it each call fails closed and the error is stored, except that an event narrative keeps its earlier text. Secret. | empty | For the assistant |
| `ANTHROPIC_MODEL` | Model id for every assistant call. | `claude-sonnet-4-6` | No |
| `ANTHROPIC_MAX_TOKENS` | Most output tokens per evaluation, shift-note polish and shift summary, 256 to 16000. Event narratives use a fixed 400. | `4096` | No |
| `LLM_DAILY_TOKEN_CAP` | Most assistant tokens, input and output, per UTC day across every caller. Counted in the process, so a restart starts the count again. Each call holds its whole output allowance and one token for every 3 characters of its prompt before it is sent, then settles to its real use; a call the rest of the day's cap cannot cover fails. | `2000000` | No |
| `ASSISTANT_CLEARED_MARKINGS` | The UDL classification markings whose notifications may be sent to the assistant, as a JSON list such as `["U"]`, matched exactly as UDL writes them. A notice with any other marking, or none, is never sent: evaluating it stores `Not sent to the assistant: ...` and calls nothing. Clearing a further marking is the data owner's decision; who that is, and whether the `JCO` source's own marking may be cleared, is `TBC, re-verify`. | `["U"]` | No |

### Procedure storage

| Setting | Purpose | Default | Required |
|---------|---------|---------|----------|
| `PROCEDURE_STORAGE_PATH` | Directory for uploaded procedures. Absolute and not the filesystem root. `scripts/dev.sh` sets it to `data/procedures` in the checkout when unset. | unset | No |
| `STORAGE_MOUNT_PATH` | Set by the App Store FILE_STORAGE add-on (`/data`). When `PROCEDURE_STORAGE_PATH` is unset, procedures go to this path followed by `/procedures`; with neither set, to `/data/procedures`. Do not set it yourself on the App Store. | unset | No |

### Background loops

| Setting | Purpose | Default | Required |
|---------|---------|---------|----------|
| `BACKGROUND_REFRESH_ENABLED` | Starts the notification, manoeuvre and Mattermost loops with the application. | `true` | No |
| `BACKGROUND_AUTO_EVALUATE` | Lets the notification cycle have the assistant evaluate new notices. | `true` | No |
| `BACKGROUND_MAX_EVALUATIONS_PER_CYCLE` | Most automatic evaluations per notification cycle. | `20` | No |
| `BACKGROUND_MAX_EVENT_SUMMARIES_PER_CYCLE` | Most event narratives refreshed per notification cycle. | `20` | No |
| `BACKGROUND_NOTIFICATION_INTERVAL_SECONDS` | Notification cycle interval, at least 60 seconds. | `3600` | No |
| `BACKGROUND_NOTIFICATION_WINDOW_HOURS` | How far back the notification cycle pulls and evaluates, and the window the Dashboard page shows. | `120` | No |
| `BACKGROUND_MANEUVER_INTERVAL_SECONDS` | Manoeuvre pull interval, at least 60 seconds. | `600` | No |
| `BACKGROUND_MANEUVER_WINDOW_HOURS` | How far back the manoeuvre pull reaches, by event start time. | `48` | No |

### Read by the admin command only, from the environment

| Setting | Purpose | Default | Required |
|---------|---------|---------|----------|
| `ADMIN_USERNAME` | Username for `python -m app.cli.create_admin` when `--username` is not given. | prompted | No |
| `ADMIN_EMAIL` | Email for the admin account when `--email` is not given. | none | No |
| `ADMIN_PASSWORD` | The admin's password, at least 12 characters. When unset, the command prompts without echo. Never a command-line flag. Secret. | prompted | No |

gunicorn's own `FORWARDED_ALLOW_IPS` is not a Holly setting, but it decides whether the client address Holly records and rate-limits by is the caller's or the ingress's ([src/app/core/net.py](../../src/app/core/net.py)). gunicorn trusts only `127.0.0.1` and `::1` by default.

A setting that is added to `Settings` belongs in this reference, and in `tests/conftest.py` when the test environment needs it.

**SECTION 05**

## Local database

`infra/docker-compose.yml` runs PostgreSQL 15.19, database `holly`, user `holly`, published on `127.0.0.1:5432` only. It needs `POSTGRES_PASSWORD` in your shell and refuses to start without it:

```sh
export POSTGRES_PASSWORD=[REDACTED:password]
docker compose -f infra/docker-compose.yml up -d --wait db
```

`--wait` returns once the database takes connections on `127.0.0.1:5432`: its health check connects over TCP, so it holds through the first start's initialisation. Without `--wait`, `up -d` returns at once, and a migration run straight after can have its connection reset. If the database is not ready within about a minute, `--wait` exits 1 and names the container unhealthy: `docker compose -f infra/docker-compose.yml logs db` shows why, and after a slow first start, re-running `up -d --wait db` succeeds once the database is up.

Point Holly at it in `.env`, using the same password:

```
DATABASE_URL=postgresql://holly:[REDACTED:password]@localhost:5432/holly
```

Or leave the password out of `.env` altogether with the parts, since Holly reads the exported `POSTGRES_PASSWORD` too:

```
POSTGRES_HOST=localhost
POSTGRES_DB=holly
POSTGRES_USER=holly
```

A minimal `.env` for local work then adds:

```
APP_ENV=development
APP_SECRET_KEY=[REDACTED:key]
BACKGROUND_REFRESH_ENABLED=false
```

Turning the background loops off avoids a failed UDL pull being logged every cycle when you hold no UDL credentials. Turn them on, with `UDL_USERNAME`, `UDL_PASSWORD` and `ANTHROPIC_API_KEY`, when you work on the loops or the assistant.

**SECTION 06**

## Migrations

`scripts/dev.sh` applies pending migrations before it starts Holly, as the container does at start. To apply them yourself from the repository root:

```sh
PYTHONPATH=src .venv/bin/python -c "from app.migrate import run_migrations; run_migrations()"
```

It prints two JSON lines, `"status": "starting"` and `"status": "applied"`. `.venv/bin/alembic upgrade head` does the same through `alembic.ini`. To see the result:

```sh
docker compose -f infra/docker-compose.yml exec db psql -U holly -d holly -c '\dt public.*' -c '\dt audit.*'
```

Expected: 12 tables and `alembic_version` in `public`, and `audit_log` in `audit`. Migration commands, and the rules for adding one, are in the [data model](../architecture/data-model.md).

**SECTION 07**

## Bootstrap the first admin

There is no public sign-up. Create the first admin from the repository root:

```sh
PYTHONPATH=src .venv/bin/python -m app.cli.create_admin --username <name>
```

It prompts `Admin password (hidden):` unless `ADMIN_PASSWORD` is set, refuses a password shorter than 12 characters with exit status 2, and prints `Admin user '<name>' created.` Running it again for the same username resets the password, the `admin` role and the active flag, and prints `updated`. Each run writes an `auth.user.admin_upsert` audit row. The command takes no password flag, so a password never lands in shell history or the process list.

No route or command creates an `analyst` or `operator` account; see the [operator manual](../runbook/operator-manual.md).

**SECTION 08**

## Running Holly

```sh
sh scripts/dev.sh
```

It starts the local database when Docker is available and `POSTGRES_PASSWORD` is set, applies the migrations, runs the API on `PORT` or 8080, and runs the dashboard's development server on `http://localhost:3000`, which sends `/api` to `http://localhost:8080`. Ctrl-C stops both. Uploaded procedures go to `data/procedures` in the checkout unless `PROCEDURE_STORAGE_PATH` is set. The dashboard's proxy target is fixed at port 8080 in [frontend/vite.config.ts](../../frontend/vite.config.ts), so leave `PORT` unset when you use `dev.sh`.

To run the API alone:

```sh
PYTHONPATH=src .venv/bin/python -m app
```

It listens on `0.0.0.0`, on `PORT` or 8080. Without a built dashboard, `/` answers `{"service": "holly", "status": "ok"}`; `curl http://localhost:8080/healthz` prints `ok`.

To run the dashboard's development server alone, `cd frontend && npm run dev`.

**SECTION 09**

## The verification loop

```sh
sh scripts/verify.sh
```

Every change runs it. It stops at the first failure and, in order, checks the Python version against `.python-version`; `ruff format --check`; `ruff check`; strict `mypy`; cognitive complexity of at most 15 per function (`complexipy`); duplicated code (`pylint`); the test suite with coverage, which writes `coverage.xml` and fails under 80%; the dashboard's lockfile install, lint, format check, build and unit tests; `npm audit`; the upload nets' self-test; and `pip-audit` over both Python locks. A green run ends with:

```
VERIFY: PASS (necessary conditions met; the App Store pipeline is the binding check)
```

The test suite needs no database: [tests/conftest.py](../../tests/conftest.py) sets every setting to a test-only value and the tests replace the database session; the migration tests run Alembic offline. To run part of it:

```sh
.venv/bin/pytest tests/test_auth.py
(cd frontend && npm test)
```

CI ([.github/workflows/verify.yml](../../.github/workflows/verify.yml)) runs the same loop on every push and on pull requests to `main`.

Optional commit hooks are in [.pre-commit-config.yaml](../../.pre-commit-config.yaml): `ruff format --check`, `ruff check`, `mypy` and the dashboard's `eslint`, each from the project's own tools. `pre-commit` itself is not in the locked tooling. The loop stays the gate.

**SECTION 10**

## Dependencies

Runtime dependencies are listed with exact pins in `requirements.in`, tooling in `requirements-dev.in`. After any change, relock with the `uv pip compile` command in the header of `requirements.in`, then the one in `requirements-dev.in`. Never edit `requirements.txt` or `requirements-dev.txt` by hand. The dashboard's dependencies are exact pins in `frontend/package.json`, locked in `frontend/package-lock.json`.

**SECTION 11**

## Before an upload

Deployment is human-gated: it runs through the `release-and-deploy` skill and the `deploy-gate` agent, never automatically. Before every upload:

```sh
sh scripts/simulate-pipeline.sh   # package the committed tree, check it out and test it the way the platform does
sh scripts/smoke-container.sh     # build the image from the upload, run it with PostgreSQL, probe the contract
```

The smoke rung needs Docker and `curl`. It fails on a non-200 probe, an error in the boot log, migrations that miss the newest revision, migrations that run while another session holds their advisory lock, an audit log that accepts an UPDATE, a dashboard that is not served, or a misconfiguration that does not stop the container. `sh scripts/package-appstore.sh` alone writes the upload, `dist/appstore.zip`, after the upload nets pass.

**SECTION 12**

## Changes and commits

● Every change runs the verification loop, then passes the `engineering-reviewer` and `security-reviewer` gates (`CLAUDE.md`).
● Every change bumps the version stamp (`__version__` in `src/app/__init__.py`, which a test holds equal to `pyproject.toml`) and adds one row to `docs/AUDIT-LOG.md`.
● Commit messages: an imperative summary line, then what changed and why.
● Whether `main` requires a pull request to land is `TBC, re-verify`.

When a commit hook rejects a change, fix the cause and commit again. Do not bypass the hooks with `--no-verify`.

**SECTION 13**

## Common commands

| Task | Command |
|------|---------|
| Run Holly with the dashboard | `sh scripts/dev.sh` |
| Run the verification loop | `sh scripts/verify.sh` |
| Start the local database | `docker compose -f infra/docker-compose.yml up -d --wait db` |
| Open a database shell | `docker compose -f infra/docker-compose.yml exec db psql -U holly -d holly` |
| Stop the local database | `docker compose -f infra/docker-compose.yml down` |
| Reset the local database (destructive) | `docker compose -f infra/docker-compose.yml down -v`, then start it and apply the migrations |
| Apply migrations | `.venv/bin/alembic upgrade head` |
| Create or reset an admin | `PYTHONPATH=src .venv/bin/python -m app.cli.create_admin --username <name>` |
| Verify the audit chain | `PYTHONPATH=src .venv/bin/python -m app.cli.verify_audit` |

**SECTION 14**

## Where to read next

● [Architecture overview](../architecture/overview.md)
● [Architectural decision log](../architecture/decision-log.md)
● [Data model](../architecture/data-model.md)
● [Operator manual](../runbook/operator-manual.md)

Bluestaq Limited | Holly documentation | 2026
