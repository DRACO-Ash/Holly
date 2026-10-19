#!/bin/sh
# check-baseline.sh :: refuse packaging unless the last upload is recorded, then print the window.
# Usage: sh scripts/check-baseline.sh <commit> <upload path>...   (package-appstore.sh passes the
# commit it archives and its path list)
#
# Reads scripts/upload-baseline.txt at that commit, so an uncommitted line never counts. A line is
# `upload <40-hex commit packaged> <version> <passed|failed|pending> [# note]`, and the last line
# is the baseline: the platform scores new code against the previous upload, whatever its outcome.
# It must name a commit in this repository whose src/app/__init__.py sets that version. When the
# upload differs from the baseline's, the version must differ too, since a change to the upload
# bumps it. It then prints the upload's files that differ from the baseline's, compared as
# committed trees over the same paths: the files whose changed lines the gate scores. That is a
# necessary condition read from git, not the gate's verdict or any of its numbers. A missing or
# unreadable record, a byte outside printable ASCII and tab, or a git error refuses.
set -euf   # -f: the path list splits into paths, never into patterns
# An exported CDPATH would send a relative cd to another directory of the same name.
unset CDPATH
# The repository's root, kept exact, as in check-reviews.sh.
ROOT="$(cd "$(dirname "$0")/.." && pwd && echo .)"
ROOT="${ROOT%??}"
RECORD=scripts/upload-baseline.txt
# Git's local overrides never stand in for the committed record and history, as in check-reviews.sh.
GIT_NO_REPLACE_OBJECTS=1
GIT_GRAFT_FILE=/dev/null/none
export GIT_NO_REPLACE_OBJECTS GIT_GRAFT_FILE

refuse() { echo "packaging refused: $1"; exit 1; }
short() { printf '%.7s' "$1"; }
version_at() {  # $1: commit
  git -C "$ROOT" show "$1:src/app/__init__.py" 2>/dev/null \
    | sed -n 's/^__version__ = "\([0-9][0-9.]*\)"$/\1/p'
}

[ "$#" -gt 1 ] || refuse "check-baseline.sh needs the commit to package and its upload paths"
at="$1"
shift
git -C "$ROOT" cat-file -e "$at^{commit}" 2>/dev/null || refuse "$at is not a commit in this repository"
git -C "$ROOT" cat-file -e "$at:$RECORD" 2>/dev/null \
  || refuse "$RECORD is not committed at $(short "$at"): record the last upload handed over, so its window can be read"
odd="$(git -C "$ROOT" show "$at:$RECORD" | LC_ALL=C tr -d '\11\12\40-\176' | wc -c | tr -d ' ')"
[ "$odd" = 0 ] || refuse "$RECORD holds $odd bytes outside printable ASCII and tab"

# The last upload, with its line. Any line that is not blank, a comment or a well-formed upload
# refuses the whole record.
last="$(git -C "$ROOT" show "$at:$RECORD" | LC_ALL=C awk '
  /^[ \t]*(#|$)/ { next }
  {
    ok = $1 == "upload" && length($2) == 40 && $2 ~ /^[0-9a-f]+$/ && $3 ~ /^[0-9]+(\.[0-9]+)*$/ &&
      ($4 == "passed" || $4 == "failed" || $4 == "pending") && (NF == 4 || $5 ~ /^#/)
    if (!ok) {
      printf "line %d is not \"upload <40-hex commit> <version> <passed|failed|pending> [# note]\"", NR
      bad = 1
      exit 1
    }
    entry = $2 " " $3 " " $4 " " NR
  }
  END { if (!bad) print entry }
')" || refuse "$RECORD $last"
[ -n "$last" ] || refuse "$RECORD records no upload"
read -r base recorded outcome line <<EOF
$last
EOF

git -C "$ROOT" cat-file -e "$base^{commit}" 2>/dev/null \
  || refuse "the baseline, line $line, $(short "$base"), is not a commit in this repository"
then_version="$(version_at "$base")"
[ "$then_version" = "$recorded" ] \
  || refuse "the baseline, line $line, records version $recorded, and $(short "$base") sets ${then_version:-no version}"
now_version="$(version_at "$at")"
[ -n "$now_version" ] || refuse "no __version__ in src/app/__init__.py at $(short "$at")"
changed="$(git -C "$ROOT" diff --no-renames --no-textconv --name-status "$base" "$at" -- "$@")" \
  || refuse "could not compare $(short "$base") with $(short "$at")"
echo "upload baseline: $(short "$base"), version $recorded, $outcome (line $line)"
if [ -z "$changed" ]; then
  echo "the upload is unchanged since the baseline: the gate has no new code to score"
  exit 0
fi
[ "$now_version" != "$recorded" ] \
  || refuse "the upload has changed since the baseline, and version $now_version is the baseline's: bump the version"
count="$(printf '%s\n' "$changed" | wc -l | tr -d ' ')"
echo "the gate's window: $count files in the upload differ from the baseline's (A added, M modified, D deleted, T type changed):"
printf '%s\n' "$changed" | sed 's/^/  /'
echo "every changed line in these files is new code to the gate; no whole-tree figure is the gate's number"
