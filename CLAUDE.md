# CLAUDE.md

> Adoption note (delete when the open items are resolved): this file is inherited from the Bluestaq Foundations baseline and was filled at scaffold. Still open: the App Store slug (`TBC, re-verify`); the platform's exact stage commands for the python template, install, test, check and build (`TBC, re-verify`; rehearse the confirmed ones with `INSTALL_CMD='...' TEST_CMD='...' sh scripts/simulate-pipeline.sh`); the upload baseline record and the rung that refuses without it, due before the first upload (appstore-gate-compliance section 3); and `.env.example` (`PORT=`), needed before the first secret-bearing variable, which Claude's Write tool refuses under this project's `Read(./.env.*)` deny rule. Keep this file short; procedures live in `skills/`, not here.

Always-true conventions for this project. Procedures live in `.claude/skills/`. The house voice is in `.claude/output-styles/house-voice.md`. When a rule here and a skill disagree, this file wins for conventions and the skill wins for procedure.

## What this project is

Holly, the Daily Ops Dashboard: a Python 3.12 FastAPI server. Archetype: `server` (one of: `static` single-file or built-static artifact; `server` backed container application). Deployment target: the Bluestaq App Store at `<slug>.apps.bluestaq.com`, slug `TBC, re-verify` (assumed `holly` in `sonar-project.properties`), detected template `python` (one of `static-html`, `node-react`, `java-spring`, `python`, `docker-only`), detected from `requirements.txt` with the `Dockerfile` at the root.

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
- **Secrets are server-side only.** Compare the team token in constant time. Validate every request body and every LLM output before storing or returning it; the dataset merge never silently shrinks.

## Commands

```
python3.12 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.txt   # install from the lockfile
sh scripts/verify.sh                     # the verification loop: pin, format, lint, types, complexity, duplication, tests with coverage, audit
PYTHONPATH=src .venv/bin/python -m app   # dev server on 0.0.0.0, at PORT or 8080
sh scripts/simulate-pipeline.sh          # before every upload: package, check out and test the way the platform does
sh scripts/smoke-container.sh            # before every upload: build the image from the upload, run it, probe the contract
```

Relock after any dependency change with the `uv pip compile` command in the header of `requirements.in`, then `requirements-dev.in`; never edit a lockfile by hand. Packaging scans every packaged file's content with the secret-scan hook's rules, so it needs `node`.

Every change runs the verification loop, then passes the `engineering-reviewer` and `security-reviewer` gates before it is done. Anything that deploys, publishes, or mutates external state requires the `deploy-gate` verdict and an explicit human confirmation.

## Directory layout

```
src/app/                the application: factory.py (create_app), main.py (ASGI entry), config.py, gunicorn_conf.py
Dockerfile              the container build, hardened and flattened to one layer
scripts/                verify.sh (the loop), package-appstore.sh, simulate-pipeline.sh, smoke-container.sh
tests/                  the pytest suite (coverage.xml, 80% floor)
docs/AUDIT-LOG.md       one row per change
SECURITY.md             the accepted security positions and their trip-wires
.claude/                this baseline (skills, agents, output style, hooks, settings)
```

## Naming and versioning

- Releases are `V<major>.<minor>`; the current stamp is V0.1 (`__version__` in `src/app/__init__.py`, held equal to `pyproject.toml` by a test). Bump the in-app version stamp and add one audit row to `docs/AUDIT-LOG.md` on every change.
- Static delivery copies (static archetype only, so not used here) follow `Bluestaq_Limited_-_<product>_-_V<major>_<minor>_-_<date>.html`.
- The App Store app name (slug) is lowercase, hyphenated, starts and ends alphanumeric, unique in the store: `TBC, re-verify`.

## House voice (applies to all prose, UI copy, comments, commits)

A guide, not a leash. Held everywhere: never fabricate data; avoid the long em-dash (a single dash is fine); no `+` meaning "and" in prose. The Bluestaq default, which is your call on your own project: UK English, the `£`/`$`/`%` symbols, expand an uncommon acronym on first use, lead with the decision then the reasoning. Anything publish-facing or Bluestaq-brand-facing follows the brand in full. Full voice: `.claude/output-styles/house-voice.md`.
