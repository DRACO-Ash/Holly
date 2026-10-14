# Audit log

One row per change, newest first. CLAUDE.md requires the version stamp bump and the row in the same change.

| Version | Date | Change | Verified by |
|---|---|---|---|
| V0.1 | 2026-10-14 | Scaffold: Python 3.12 FastAPI server on the App Store python template, with hash-pinned lockfiles, a hardened single-layer image, the verification loop, the pipeline simulation and the container smoke rung. | `sh scripts/verify.sh`, `sh scripts/simulate-pipeline.sh` (all three documented coverage commands), `sh scripts/smoke-container.sh`, and the engineering-reviewer and security-reviewer gates. |
