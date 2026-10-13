#!/bin/sh
# package-appstore.sh :: build the App Store upload zip for a quality-gated container.
# Shipped as a scaffold template by deploy-recipes and packaging. Run it from the repo root as
# `sh scripts/package-appstore.sh`.
#
# The upload must be a self-sufficient, TESTABLE source tree (Dockerfile and lockfiles at
# root, source, build tooling, tests, docs), NOT a built artefact: the platform runs your
# tests with coverage inside the checkout. `git archive` ships exactly the tracked files and
# nothing gitignored, which is why a virtualenv, coverage, and .env never leak in. Keep
# tests and docs TRACKED, or the platform test stage cannot find them.
#
# Adapted for Holly (Python): POSIX sh rather than bash (the platform's shell may be BusyBox),
# and the archive is an ALLOWLIST of tracked paths rather than the whole tree (packaging: the
# archive is the analysed surface, so .claude/, CLAUDE.md, scripts/ and the bundle zip stay out).
set -eu

OUT="dist/appstore.zip"
mkdir -p dist
rm -f "$OUT"

git archive --format=zip -o "$OUT" HEAD -- \
  Dockerfile .dockerignore .python-version pyproject.toml README.md \
  requirements.in requirements.txt requirements-dev.in requirements-dev.txt \
  sonar-project.properties src tests

# Verify the two contracts that most often fail on upload, before a human ever uploads.
# Read member NAMES only (unzip -Z1), so the pattern anchors on the real path and is not
# defeated by the size and date columns of a plain `unzip -l` listing.
names="$(unzip -Z1 "$OUT")"
printf '%s\n' "$names" | grep -qx "requirements.txt" || { echo "package is missing requirements.txt"; exit 1; }
printf '%s\n' "$names" | grep -qx "Dockerfile"       || { echo "package is missing the Dockerfile"; exit 1; }
# Anchor each banned component at the start of a name or just after a slash, so a root-level
# .env (and .env.local, .env.production), a virtualenv, a cache, or coverage output is caught,
# not only a nested one. git archive already omits gitignored files; this net catches one
# tracked by mistake.
if printf '%s\n' "$names" | grep -qE '(^|/)(\.venv|venv|__pycache__|\.pytest_cache|coverage)/|(^|/)\.env($|\.)|(^|/)(coverage\.xml|\.coverage)$'; then
  echo "package contains a banned path (a virtualenv, a cache, coverage output, or a .env file). Fix .gitignore and untrack it."; exit 1
fi

echo "wrote $OUT"
