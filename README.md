# Holly
Daily Ops Dashboard

A Python 3.12 FastAPI server for the Bluestaq App Store (`python` template), built on the Bluestaq Foundations baseline in `.claude/`. Conventions and commands live in `CLAUDE.md`.

## Develop

```
python3.12 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.txt
sh scripts/verify.sh                     # the verification loop
PYTHONPATH=src .venv/bin/python -m app   # serves on 0.0.0.0:8080, or $PORT
```

Deployment is human-gated: it runs through the `release-and-deploy` skill and the `deploy-gate` agent, never automatically.
