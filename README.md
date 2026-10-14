# Holly

The daily operations dashboard for Space Domain Awareness (SDA) watch analysts: Unified Data Library (UDL) notifications, element sets and maneuvers, the team's Mattermost channels, procedures, the shift log and event timers in one place, with an assistant that evaluates notifications against the team's procedures. Holly is built from the Daily Operations Dashboard.

One Python 3.12 FastAPI server for the Bluestaq App Store (`python` template) serves the API under `/api/v1` and the React dashboard at `/`. It is built on the Bluestaq Foundations baseline in `.claude/`; conventions and commands live in `CLAUDE.md`, accepted security positions in `SECURITY.md`.

## Develop

```
python3.12 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.txt
(cd frontend && npm ci --ignore-scripts)
sh scripts/verify.sh                     # the verification loop, server and dashboard
sh scripts/dev.sh                        # PostgreSQL, migrations, the API on 8080, the dashboard on 3000
```

Holly validates its settings at boot and refuses to start without them; `docs/developer/setup.md` lists every setting. The operator manual is `docs/runbook/operator-manual.md`; the analysts' guide is `docs/user-handbook/training-manual.md`.

Deployment is human-gated: it runs through the `release-and-deploy` skill and the `deploy-gate` agent, never automatically.
