# CLAUDE.md

> Adoption note (delete after filling): this file is inherited from the Bluestaq Foundations baseline. Replace every `${PLACEHOLDER}` with a real value (the list and how to obtain each is in `AUDIT.md`), then delete this note. Keep this file short; procedures live in `skills/`, not here.

Always-true conventions for this project. Procedures live in `.claude/skills/`. The house voice is in `.claude/output-styles/house-voice.md`. When a rule here and a skill disagree, this file wins for conventions and the skill wins for procedure.

## What this project is

`${PROJECT_ONE_LINE}` Archetype: `${ARCHETYPE}` (one of: `static` single-file or built-static artifact; `server` backed container application). Deployment target: the Bluestaq App Store at `${APP_SLUG}.apps.bluestaq.com`, detected template `${APP_STORE_TEMPLATE}` (one of `static-html`, `node-react`, `java-spring`, `python`, `docker-only`).

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

## Commands (fill the ones this project uses)

```
${INSTALL_CMD}          # e.g. npm ci
${TEST_CMD}             # e.g. npm test                          local verification loop
${DEV_CMD}              # e.g. npm run dev                       static archetype: open the file
${BUILD_CMD}            # e.g. ./scripts/build-package.sh <v> <date>   OR   docker build -t ${APP_SLUG} .
```

Every change runs the verification loop, then passes the `engineering-reviewer` and `security-reviewer` gates before it is done. Anything that deploys, publishes, or mutates external state requires the `deploy-gate` verdict and an explicit human confirmation.

## Directory layout

```
${SOURCE_PATH}          the application source (static: the single artifact; server: src/, public/)
scripts/ or Dockerfile  build and verification (static: scripts/; server: Dockerfile)
tests/ or test/         the spec table / test suite
docs/                   deployment runbooks, changelog
.claude/                this baseline (skills, agents, output style, hooks, settings)
```

## Naming and versioning

- Releases are `V${MAJOR}.${MINOR}`. Bump the in-app version stamp and add one audit row on every change.
- Static delivery copies follow `Bluestaq_Limited_-_${PRODUCT}_-_V${MAJOR}_${MINOR}_-_<date>.html`.
- The App Store app name (slug) is lowercase, hyphenated, starts and ends alphanumeric, unique in the store: `${APP_SLUG}`.

## House voice (applies to all prose, UI copy, comments, commits)

A guide, not a leash. Held everywhere: never fabricate data; avoid the long em-dash (a single dash is fine); no `+` meaning "and" in prose. The Bluestaq default, which is your call on your own project: UK English, the `£`/`$`/`%` symbols, expand an uncommon acronym on first use, lead with the decision then the reasoning. Anything publish-facing or Bluestaq-brand-facing follows the brand in full. Full voice: `.claude/output-styles/house-voice.md`.
