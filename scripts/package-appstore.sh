#!/bin/sh
# package-appstore.sh :: build the App Store upload zip for a quality-gated container.
# Shipped as a scaffold template by deploy-recipes and packaging. Run it from anywhere as
# `sh scripts/package-appstore.sh`.
#
# The upload must be a self-sufficient, TESTABLE source tree (Dockerfile and lockfiles at
# root, source, build tooling, tests, docs), NOT a built artefact: the platform runs your
# tests with coverage inside the checkout. `git archive` ships exactly the tracked files and
# nothing gitignored, which is why a virtualenv, coverage, and .env never leak in. Keep
# tests and docs TRACKED, or the platform test stage cannot find them.
#
# Adapted for Holly (Python): POSIX sh rather than bash (the platform's shell may be BusyBox),
# the archive is an ALLOWLIST of tracked paths rather than the whole tree (packaging: the
# archive is the analysed surface, so .claude/, CLAUDE.md, scripts/ and the bundle zip stay
# out), and every package must pass the upload nets in scripts/check-package.sh (required
# members, banned names, and a content scan for secrets) before it reaches the upload path.
set -eu
cd "$(dirname "$0")/.."

OUT="dist/appstore.zip"
mkdir -p dist
# Build under a temporary name and move it into place only when every net passes, so a refused
# or unscanned package never sits at the upload path. Any failure removes the temporary zip and
# a stale upload zip from an earlier run.
TMP="$(mktemp dist/.appstore.XXXXXX)"
packaged=0
finish() {
  if [ "$packaged" != 1 ]; then rm -f -- "$TMP" "$OUT"; fi
}
trap finish EXIT
# dash runs the EXIT trap on a normal exit or a set -e failure, not on a signal: exit first.
trap 'exit 130' INT
trap 'exit 143' TERM

# frontend/ is the dashboard's source, which the Dockerfile compiles; alembic.ini is the
# developer's migration entry point, which the test suite checks against the packaged
# migrations in src/app/migrations.
git archive --format=zip -o "$TMP" HEAD -- \
  Dockerfile .dockerignore .python-version pyproject.toml README.md alembic.ini \
  requirements.in requirements.txt requirements-dev.in requirements-dev.txt \
  sonar-project.properties src tests frontend

sh scripts/check-package.sh "$TMP"

chmod 644 "$TMP"   # mktemp creates it private; the upload zip is an ordinary readable file
mv -f -- "$TMP" "$OUT"
packaged=1
echo "wrote $OUT"
