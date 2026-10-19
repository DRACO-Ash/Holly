#!/bin/sh
# check-baseline.sh :: refuse packaging unless the last upload is recorded, then print the window.
# Usage: sh scripts/check-baseline.sh <commit> <upload path>...   (package-appstore.sh passes the
# commit it archives and its path list)
#
# Reads scripts/upload-baseline.txt at that commit, so an uncommitted line never counts. A line is
# `upload <40-hex commit packaged> <version> <passed|failed|pending> [# note]`, and the last line
# is the baseline: the platform scores new code against the previous upload, whatever its outcome.
# It must name a commit in this repository, reachable or not, whose src/app/__init__.py sets that
# version in exactly one line. When the upload differs from the baseline's, the version must be
# higher, compared number by number, since a change to the upload bumps it. It then prints the
# upload's files that differ from the baseline's, compared as committed trees over the same
# paths: the files whose changed lines the gate scores. That is a necessary condition read from
# git, not the gate's verdict or any of its numbers. A missing or
# unreadable record, a byte outside printable ASCII and tab, or a git error refuses.
set -euf   # -f: the path list splits into paths, never into patterns
# An exported CDPATH would send a relative cd to another directory of the same name.
unset CDPATH
# The repository's root, kept exact, as in check-reviews.sh.
ROOT="$(cd "$(dirname "$0")/.." && pwd && echo .)"
ROOT="${ROOT%??}"
RECORD=scripts/upload-baseline.txt
# Git's local overrides never stand in for the committed record and history, as in
# check-reviews.sh: no replaced object, no graft, and no commit-graph file, from which git diff
# would take each commit's tree unchecked. Set here, since check-reviews.sh's settings stay in
# its own process.
GIT_NO_REPLACE_OBJECTS=1
GIT_GRAFT_FILE=/dev/null/none
GIT_CONFIG_COUNT=1
GIT_CONFIG_KEY_0=core.commitGraph
GIT_CONFIG_VALUE_0=false
export GIT_NO_REPLACE_OBJECTS GIT_GRAFT_FILE GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0
# Settings passed in GIT_CONFIG_PARAMETERS (git -c) would win over the ones above.
unset GIT_CONFIG_PARAMETERS

refuse() { echo "packaging refused: $1"; exit 1; }
short() { printf '%.7s' "$1"; }
# $1: commit. Nothing unless exactly one line starts with __version__, and in the strict form:
# Python honours an annotated or a later assignment that a pattern for the strict one would skip.
version_at() {
  git -C "$ROOT" show "$1:src/app/__init__.py" 2>/dev/null | awk '/^__version__/ { n++; v = $0 } END {
      if (n == 1 && v ~ /^__version__ = "[0-9][0-9.]*"$/) { sub(/^__version__ = "/, "", v); sub(/"$/, "", v); print v }
    }'
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
[ -n "$now_version" ] || refuse "no single __version__ in src/app/__init__.py at $(short "$at")"
changed="$(git -C "$ROOT" diff --no-renames --no-textconv --name-status "$base" "$at" -- "$@")" \
  || refuse "could not compare $(short "$base") with $(short "$at")"
echo "upload baseline: $(short "$base"), version $recorded, $outcome (line $line)"
if [ -z "$changed" ]; then
  echo "the upload is unchanged since the baseline: the gate has no new code to score"
  exit 0
fi
# Number by number, so 0.6 and 0.6.0 are the same version and 0.10 is above 0.9.
order="$(awk -v a="$now_version" -v b="$recorded" 'BEGIN {
  n = split(a, x, "."); m = split(b, y, "."); if (m > n) n = m
  for (i = 1; i <= n; i++) if (x[i] + 0 != y[i] + 0) { print (x[i] + 0 > y[i] + 0 ? "higher" : "lower"); exit }
  print "equal"
}')"
[ "$order" != equal ] \
  || refuse "the upload has changed since the baseline, and version $now_version is the baseline's: bump the version"
[ "$order" = higher ] \
  || refuse "the upload has changed since the baseline, and version $now_version is below the baseline's $recorded: bump the version above it"
count="$(printf '%s\n' "$changed" | wc -l | tr -d ' ')"
echo "the gate's window: $count files differ between the baseline's upload and this one (A added, M modified, D deleted, T type changed):"
printf '%s\n' "$changed" | sed 's/^/  /'
echo "every changed line in these files is new code to the gate; no whole-tree figure is the gate's number"
