# CLAUDE.md

> Adoption note (delete when the open items are resolved): this file is inherited from the Bluestaq Foundations baseline, filled at scaffold and updated when the Daily Operations Dashboard was fused in (V0.2). Still open, each `TBC, re-verify`: the platform's stage commands beyond those V0.4's job logs confirmed, which `scripts/simulate-pipeline.sh` runs (the python job's install and test, and the node job's `npm ci`), the node job's after `npm ci` among them; whether the Code Quality gate combines the python job's `coverage.xml` with the node job's `coverage/lcov.info` (each is held to 80% on its own meanwhile); the ingress addresses for `FORWARDED_ALLOW_IPS`; and whether the platform offers a shell in the container, which `python -m app.cli.create_admin` (to reset an admin) and `python -m app.cli.verify_audit` need, the first admin coming from App Store variables instead. Settings are listed in `docs/developer/setup.md` in place of a `.env.example`, which Claude's Write tool refuses under this project's `Read(./.env.*)` deny rule. Keep this file short; procedures live in `skills/`, not here.

Always-true conventions for this project. Procedures live in `.claude/skills/`. The house voice is in `.claude/output-styles/house-voice.md`. When a rule here and a skill disagree, this file wins for conventions and the skill wins for procedure.

## What this project is

Holly, the daily operations dashboard for Space Domain Awareness (SDA) watch analysts, built from the Daily Operations Dashboard: a Python 3.12 FastAPI server that also serves its React dashboard (`frontend/`, compiled into the image), with PostgreSQL and file storage from the App Store's POSTGRESQL and FILE_STORAGE add-ons. Archetype: `server` (one of: `static` single-file or built-static artifact; `server` backed container application). Deployment target: the Bluestaq App Store at `holly.appstore.bluestaq.com`, slug `holly`. The console shows the detected stack as `node-react` (one of `static-html`, `node-react`, `java-spring`, `python`, `docker-only`); inference: from the root `package.json` the platform's node test job needs, the image still building from the root `Dockerfile` as for every container template. The app record is in the operator manual, section 03.

## Hard rules (never violate)

**Both archetypes**
- **No secrets in any shippable file**, in source or in history. Read secrets from the environment; render any value in docs as `[REDACTED:type]`. The pre-write hook blocks a credential before it lands.
- **No client-side access gate.** A hardcoded Personal Identification Number (PIN), flag, or hidden field in the browser is a User Experience gate, never security. Real gates are server-side.
- **Surgical edits only.** Change the smallest region that satisfies the request. Do not reformat, re-indent, or reconstruct regions you were not asked to touch.
- **Never invent a name, title, date, organisation, or figure** in user-facing content or data. If a fact is not verifiable, mark it with the explicit unknown marker (`TBC, re-verify`); do not assert it.
- **Every untrusted value is escaped or validated at the boundary**, and a control that cannot be verified is treated as failed (fail closed).

**Static archetype**
- **No runtime network egress** from the artifact. No `fetch`, `XMLHttpRequest`, `WebSocket`, dynamic `import()`, remote fonts, or remote scripts. It runs fully offline; embed assets as `data:` Uniform Resource Identifiers (URIs).
- **No dynamic code execution.** No `eval`, `new Function`, `document.write`, or string-form `setTimeout`/`setInterval`. No cross-frame `message` listeners.
- **Locked Content-Security-Policy** (`default-src 'none'`, `connect-src 'none'`, framing denied, `referrer no-referrer`). Tighten only, never loosen.
- **One escaper** for every reflected user value; every `target="_blank"` link carries `rel="noopener noreferrer"`.

**Server archetype**
- **The container is the whole build.** A single `Dockerfile` installs from the lockfile and runs the server; no separate bundler output. Runs as a non-root numeric user, no setuid/setgid binaries.
- **Listen on `process.env.PORT`, default 8080, bound to `0.0.0.0`.** Never add `ENV PORT=` to the Dockerfile. Answer `/`, `/healthz`, `/readyz`, `/livez`, `/ping` with HTTP 200, unauthenticated, touching nothing.
- **Secrets are server-side only.** Compare secrets in constant time (bcrypt and PyJWT's signature check do). Sign-in guards every route outside the reviewed public set in `tests/test_app.py`. Validate every request body and every LLM output before storing or returning it; the dataset merge never silently shrinks.
- **One process.** gunicorn runs one worker: the background loops, the rate limits and the assistant's daily token cap live in it. Migrations run in the gunicorn master at start, under an advisory lock.

## Commands

```
python3.12 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.txt   # install from the lockfile
sh scripts/verify.sh                     # the verification loop: pin, format, lint, types, complexity, duplication, tests with coverage, audit
PYTHONPATH=src .venv/bin/python -m app   # dev server on 127.0.0.1, at PORT or 8080
sh scripts/simulate-pipeline.sh          # before every upload: package, check out and run both of the platform's test jobs
sh scripts/smoke-container.sh            # before every upload: build the image from the upload, run it with PostgreSQL, probe the contract
node scripts/mutation-battery.mjs        # after changing the contrast check, the licence plugin or their self-tests (CI runs it)
sh scripts/dev.sh                        # local run: PostgreSQL, migrations, the API on 8080, the dashboard on 3000
```

The dashboard installs from its lockfile with `cd frontend && npm ci --ignore-scripts`; the loop runs its lint, format, build (which copies each bundled package's licence to `licences/` and stops on a package without one), unit tests with coverage (80% floor, `coverage/lcov.info`), the theme's contrast check (`scripts/contrast-check.mjs`, WCAG AA for every token pair) and `npm audit`. Pin dashboard packages exactly and relock with `npm install --package-lock-only`, never by hand. The root `package.json` holds no packages; it exists for the platform's node job, whose `npm ci` (and test and build, TBC, re-verify) it hands to the dashboard, installed with install scripts off. Lock a new dashboard package with a 15-day cooldown (`--before`).

Relock after any dependency change with the `uv pip compile` command in the header of `requirements-runtime.in` (the image's set), then `requirements.in` (the platform test job's), then `requirements-dev.in`; never edit a lockfile by hand. Packaging runs the upload nets in `scripts/check-package.sh` (required members, banned names, and a content scan with the secret-scan hook's rules), so it needs `node` and `unzip`; the loop's self-test of those nets also needs `python3`. The upload may carry only strict UTF-8 text, plus any binary pinned by SHA-256 with a reason in `scripts/upload-binaries.txt` (read from HEAD); treat any change there as a security change. Packaging for upload also refuses unless the last verdict from each gate in the committed `scripts/upload-record.txt` is a PASS on a commit with the same upload and packaging (`scripts/check-reviews.sh`), and unless the committed `scripts/upload-baseline.txt` records the last upload handed over, whose window it prints (`scripts/check-baseline.sh`); append its line in the commit after each handover. The rungs package with `--rehearsal <file>` into their own temporary files, never the upload.

Every change runs the verification loop, then passes the `engineering-reviewer` and `security-reviewer` gates before it is done; append each verdict to `scripts/upload-record.txt` in the commit that records the round. Anything that deploys, publishes, or mutates external state requires the `deploy-gate` verdict and an explicit human confirmation.

## Directory layout

```
src/app/                the application: factory.py (create_app), main.py (ASGI entry), config.py, gunicorn_conf.py,
                        migrate.py; api/ (routes), core/, db/, models/, schemas/, services/, cli/
src/app/migrations/     the Alembic migrations, applied at container start (alembic.ini serves the CLI)
frontend/               the React dashboard (Vite, TypeScript), built into src/app/static by the Dockerfile;
                        its Vitest suite writes coverage/lcov.info (80% floor)
package.json            the root Node project for the platform's node job, handing npm ci, test and build to frontend/
infra/docker-compose.yml  a local PostgreSQL for development only
Dockerfile              the container build: the dashboard stage, then hardened and flattened to one layer
scripts/                verify.sh (the loop), package-appstore.sh with check-package.sh, scan-package.mjs,
                        upload-binaries.txt and test-package-nets.sh (the upload nets), check-reviews.sh
                        and upload-record.txt (the review record), check-baseline.sh and upload-baseline.txt
                        (the last upload, where the gate's window opens), simulate-pipeline.sh with check-lcov.sh,
                        smoke-container.sh, contrast-check.mjs, the self-tests test-contrast-check.mjs and
                        test-bundled-licences.mjs, and mutation-battery.mjs, which proves them
tests/                  the pytest suite (coverage.xml, 80% floor); tests/fakes.py holds the session fake
docs/                   architecture, runbook, user handbook, security and developer setup (settings reference)
docs/AUDIT-LOG.md       one row per release
SECURITY.md             the accepted security positions and their trip-wires
.claude/                this baseline (skills, agents, output style, hooks, settings)
```

## Naming and versioning

- Releases are `V<major>.<minor>`; the current stamp is `__version__` in `src/app/__init__.py`, never restated here, so a bump leaves this file alone. `tests/test_version.py` holds `pyproject.toml`, `frontend/package.json` and both root version fields of `frontend/package-lock.json` equal to it. A change is a piece of work together with the fixes its gate rounds ask for. One that alters the upload, meaning anything that changes what `scripts/package-appstore.sh` writes (a file under its paths, its path list or archive command, or a `.gitattributes`), bumps the in-app version stamp and opens a new row in `docs/AUDIT-LOG.md`; one that leaves the upload alone keeps the stamp and is recorded in the current release's row.
- Static delivery copies (static archetype only, so not used here) follow `Bluestaq_Limited_-_<product>_-_V<major>_<minor>_-_<date>.html`.
- The App Store app name (slug) is lowercase, hyphenated, starts and ends alphanumeric, unique in the store: `holly`.

## House voice (applies to all prose, UI copy, comments, commits)

A guide, not a leash. Held everywhere: never fabricate data; avoid the long em-dash (a single dash is fine); no `+` meaning "and" in prose. The Bluestaq default, which is your call on your own project: UK English, the `£`/`$`/`%` symbols, expand an uncommon acronym on first use, lead with the decision then the reasoning. Anything publish-facing or Bluestaq-brand-facing follows the brand in full. Full voice: `.claude/output-styles/house-voice.md`.
