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
#
# The upload, dist/appstore.zip, is written only when scripts/check-reviews.sh finds that both
# binding reviews passed the upload at the commit packaged (scripts/upload-record.txt). HEAD is
# resolved once and that commit is checked, archived and verified, so a commit landing meanwhile
# can never slip in: it refuses instead. Every run first removes the last upload zip, so dist/
# never holds one a later run did not write. `--rehearsal <file>` skips the review check and
# writes <file> instead, outside dist/: the same bytes through the same nets, for the rungs that
# test a package before its reviews exist. A rehearsal, like `git archive` by hand, is never the
# upload: the check covers only the file this script writes, when it writes it (SECURITY.md).
set -euf   # -f: no path in the list is ever matched against the working tree as a pattern
CALLER="$PWD"
cd "$(dirname "$0")/.."
rm -f -- dist/appstore.zip

OUT="dist/appstore.zip"
rehearsal=0
case "$#:${1-}" in
  0:) ;;
  2:--rehearsal) rehearsal=1; OUT="$2" ;;
  *) echo "usage: sh scripts/package-appstore.sh [--rehearsal <file>]"; exit 2 ;;
esac
mkdir -p dist
if [ "$rehearsal" = 1 ]; then
  case "$OUT" in /*) ;; *) OUT="$CALLER/$OUT" ;; esac
  case "$(cd "$(dirname "$OUT")" && pwd -P)/" in
    "$(pwd -P)/dist/"*) echo "a rehearsal never writes into dist/, which holds only checked uploads"; exit 2 ;;
  esac
fi

# Replaced objects never stand in for the committed ones, here or in the checks below.
GIT_NO_REPLACE_OBJECTS=1
export GIT_NO_REPLACE_OBJECTS
COMMIT="$(git rev-parse --verify 'HEAD^{commit}')"

# Build under a temporary name and move it into place only when every net passes, so a refused
# or unscanned package never sits at the output path.
TMP="$(mktemp dist/.appstore.XXXXXX)"
trap 'rm -f -- "$TMP"' EXIT
# dash runs the EXIT trap on a normal exit or a set -e failure, not on a signal: exit first.
trap 'exit 130' INT
trap 'exit 143' TERM

# frontend/ is the dashboard's source, which the Dockerfile compiles; alembic.ini is the
# developer's migration entry point, which the test suite checks against the packaged
# migrations in src/app/migrations. The review check and the nets compare the same list.
PATHS="Dockerfile .dockerignore .python-version pyproject.toml README.md alembic.ini
  requirements.in requirements.txt requirements-dev.in requirements-dev.txt
  sonar-project.properties src tests frontend"

# shellcheck disable=SC2086  # the path list splits on purpose
if [ "$rehearsal" = 0 ]; then sh scripts/check-reviews.sh "$COMMIT" $PATHS; fi

# shellcheck disable=SC2086  # as above
git archive --format=zip -o "$TMP" "$COMMIT" -- $PATHS

# shellcheck disable=SC2086  # as above
sh scripts/check-package.sh "$TMP" "$COMMIT" $PATHS

now="$(git rev-parse --verify 'HEAD^{commit}')"
[ "$now" = "$COMMIT" ] || {
  echo "HEAD moved from $(printf '%.7s' "$COMMIT") to $(printf '%.7s' "$now") while packaging: package again"
  exit 1
}

chmod 644 "$TMP"   # mktemp creates it private; the upload zip is an ordinary readable file
mv -f -- "$TMP" "$OUT"
if [ "$rehearsal" = 1 ]; then
  echo "wrote $OUT from $COMMIT: a REHEARSAL, never the upload (the reviews were not checked)"
else
  echo "wrote $OUT from $COMMIT"
fi
