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
# binding reviews passed the upload at the commit packaged (scripts/upload-record.txt), and only
# from the tip of a branch that is not behind its upstream as last fetched; a branch with no
# upstream is not compared, and the run says so. HEAD is resolved once and that commit is
# checked, archived and verified, so a commit landing meanwhile can never slip in: it refuses
# instead. Every run first removes the last upload zip and any temporary zip a killed run left,
# so dist/ never holds one a later run did not write. `--rehearsal <file>` skips the review check
# and writes <file> instead, outside dist/ and never named appstore.zip: the same bytes through
# the same nets, for the rungs that test a package before its reviews exist. A rehearsal, like `git archive` by
# hand, is never the upload: the check covers only the file this script writes, when it writes
# it (SECURITY.md).
set -euf   # -f: no path in the list is ever matched against the working tree as a pattern
# An exported CDPATH would send a relative cd to another directory of the same name.
unset CDPATH
CALLER="$PWD"
cd "$(dirname "$0")/.."
rm -f -- dist/appstore.zip
# A run that was killed can leave its temporary zip behind: an archive nobody checked. The slash
# makes find enter dist/ when it is a symlink to a directory.
if [ -d dist ]; then find dist/ -maxdepth 1 -type f -name '.appstore.*' -exec rm -f -- {} +; fi

OUT="dist/appstore.zip"
rehearsal=0
case "$#:${1-}" in
  0:) ;;
  2:--rehearsal) rehearsal=1; OUT="$2" ;;
  *) echo "usage: sh scripts/package-appstore.sh [--rehearsal <file>]"; exit 2 ;;
esac
mkdir -p dist
TMPDIR_OUT=dist
if [ "$rehearsal" = 1 ]; then
  [ -n "$OUT" ] || { echo "usage: sh scripts/package-appstore.sh [--rehearsal <file>]"; exit 2; }
  case "$OUT" in /*) ;; *) OUT="$CALLER/$OUT" ;; esac
  # Split by parameter expansion, and resolved with a sentinel after pwd, since command
  # substitution drops a trailing newline from a name. The directory is resolved as the kernel
  # resolves it (cd -P, so a symlink and .. cannot steer it), failing closed, and the file is
  # written there.
  name="${OUT##*/}"
  parent="${OUT%/*}"
  dir="$(cd -P "${parent:-/}" 2>/dev/null && pwd -P && echo .)" \
    || { echo "a rehearsal needs an existing directory: ${parent:-/}"; exit 2; }
  dir="${dir%??}"
  # Never under the upload's name, in any case, so no checkout's dist/appstore.zip is ever a
  # rehearsal; and never in dist/ or below it, compared by device and inode, so no symlink,
  # bind mount or other spelling of the path reaches it.
  case "$name" in
    [Aa][Pp][Pp][Ss][Tt][Oo][Rr][Ee].[Zz][Ii][Pp])
      echo "a rehearsal is never named appstore.zip, the upload's name"; exit 2 ;;
  esac
  up="$dir"
  while [ -n "$up" ]; do
    if [ "$up" -ef dist ]; then echo "a rehearsal never writes into dist/, which holds only checked uploads"; exit 2; fi
    up="${up%/*}"
  done
  OUT="$dir/$name"
  if [ -L "$OUT" ] || { [ -e "$OUT" ] && [ ! -f "$OUT" ]; }; then
    echo "a rehearsal writes a regular file, and $OUT is something else"; exit 2
  fi
  # It replaces only an empty file or an earlier rehearsal: a .zip file that holds a zip.
  if [ -s "$OUT" ]; then
    case "$name:$(head -c 2 "$OUT")" in
      *.zip:PK) ;;
      *) echo "a rehearsal replaces only an empty file or an earlier .zip rehearsal, and $OUT is neither"; exit 2 ;;
    esac
  fi
  TMPDIR_OUT="$dir"
fi

# Git's local overrides never stand in for the committed history: no replaced object in the
# archive, and no graft, which could hide that the branch is behind its upstream. The graft file
# is a path that can never exist, so git reads none and prints no deprecation hint.
GIT_NO_REPLACE_OBJECTS=1
GIT_GRAFT_FILE=/dev/null/none
export GIT_NO_REPLACE_OBJECTS GIT_GRAFT_FILE
COMMIT="$(git rev-parse --verify 'HEAD^{commit}')"

# Build under a temporary name beside the output and move it into place only when every net
# passes, so a refused or unscanned package never sits at the output path.
TMP="$(mktemp "$TMPDIR_OUT/.appstore.XXXXXX")"
trap 'rm -f -- "$TMP"' EXIT
# dash runs the EXIT trap on a normal exit or a set -e failure, not on a signal: exit first.
trap 'exit 130' INT
trap 'exit 143' TERM

# frontend/ is the dashboard's source, which the Dockerfile compiles and the platform's node job
# installs, tests and builds through package.json and package-lock.json at the root; alembic.ini
# is the developer's migration entry point, which the test suite checks against the packaged
# migrations in src/app/migrations. The review check and the nets compare the same list.
PATHS="Dockerfile .dockerignore .python-version pyproject.toml README.md alembic.ini
  package.json package-lock.json requirements-runtime.in requirements-runtime.txt
  requirements.in requirements.txt requirements-dev.in requirements-dev.txt
  sonar-project.properties src tests frontend"

# The record counts the verdicts committed at or before the commit packaged, so an upload comes
# from the tip of a local branch, never a detached HEAD or one on another ref, such as a tag, and
# never from a branch behind its upstream as last fetched, whose record could predate a FAIL
# recorded there. An upstream that is configured but does not resolve refuses, since the lag
# cannot be measured. A branch with no upstream is not compared, and the run says so: only a
# fetched upstream shows a later FAIL.
if [ "$rehearsal" = 0 ]; then
  ref="$(git symbolic-ref -q HEAD)" \
    || { echo "packaging refused: HEAD is detached; package from the tip of a branch"; exit 1; }
  case "$ref" in
    refs/heads/?*) branch="${ref#refs/heads/}" ;;
    *) echo "packaging refused: HEAD is on $ref, not a local branch; package from the tip of one"; exit 1 ;;
  esac
  status=0
  git config --get "branch.$branch.merge" > /dev/null || status=$?
  case "$status" in
    0)
      upstream="$(git rev-parse -q --verify "$branch@{upstream}^{commit}")" || {
        echo "packaging refused: the upstream of $branch does not resolve; fetch it, or remove it with git branch --unset-upstream"
        exit 1
      }
      behind="$(git rev-list --count "$COMMIT..$upstream" --)" \
        || { echo "packaging refused: could not compare $branch with its upstream"; exit 1; }
      [ "$behind" = 0 ] || {
        echo "packaging refused: $branch lacks $behind of its upstream's commits; pull first, so every recorded verdict counts"
        exit 1
      }
      ;;
    1) echo "note: $branch has no upstream, so packaging cannot tell whether it is behind one" ;;
    *) echo "packaging refused: could not read the upstream of $branch"; exit 1 ;;
  esac
  # shellcheck disable=SC2086  # the path list splits on purpose
  sh scripts/check-reviews.sh "$COMMIT" $PATHS
fi

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
