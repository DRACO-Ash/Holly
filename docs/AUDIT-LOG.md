# Audit log

One row per change, newest first. CLAUDE.md requires the version stamp bump and the row in the same change. Record only checks that have actually run, and each gate verdict with the commit it judged.

| Version | Date | Change | Verified by |
|---|---|---|---|
| V0.1 | 2026-10-14 | Scaffold: Python 3.12 FastAPI server on the App Store python template, with hash-pinned lockfiles, a hardened single-layer image, the verification loop, the pipeline simulation and the container smoke rung. | Loop: `sh scripts/verify.sh`. Pipeline simulation with all three documented coverage commands. Container smoke rung. GitHub CI `verify` green on 9616c41 and c0a25dc. Gates: engineering-reviewer and security-reviewer FAIL on 9616c41, then PASS on c0a25dc; both FAIL on b56e04c, because its new package content net reported files clean that it could not read (bracketed and control-character names). The following commit replaces that net and goes back through both gates. |
