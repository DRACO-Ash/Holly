#!/bin/sh
# check-reviews.sh :: refuse packaging unless both binding reviews passed the upload at a commit.
# Usage: sh scripts/check-reviews.sh <commit> <upload path>...   (package-appstore.sh passes the
# commit it archives and its path list)
#
# Reads scripts/upload-record.txt at that commit, so an uncommitted line never counts. A line is
# `review <reviewer> <PASS|FAIL> <40-hex commit reviewed> [# note]`, the reviewer being
# engineering-reviewer or security-reviewer. The last line from each reviewer decides, whatever
# commit it names, so a FAIL recorded after a PASS always refuses. It must be a PASS on a commit
#   1. in this repository and in the packaged commit's history;
#   2. at or after the commit that set the version in src/app/__init__.py (the bump);
#   3. carrying the same upload: the packaged paths and the packaging tools (this script, the
#      packager, the upload nets, the binary allowlist, the secret-scan rules they use and
#      .gitattributes) are unchanged since, so a PASS recorded against a tree that has since
#      moved refuses.
# The packaging tools that run are the working tree's, so each must match its committed content
# byte for byte, whatever git's index says, and git's local overrides (replaced objects, grafts)
# are ignored. A line it cannot read, a byte outside printable ASCII and tab, a git error or a
# missing record refuses. It proves the record is present and consistent with the history, not
# that a review took place (SECURITY.md).
set -euf   # -f: the tool list splits into paths, never into patterns
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RECORD=scripts/upload-record.txt
TOOLS="scripts/check-reviews.sh scripts/package-appstore.sh scripts/check-package.sh
  scripts/scan-package.mjs scripts/upload-binaries.txt .claude/hooks/secret-scan.mjs .gitattributes"
# Git's local overrides never stand in for the committed record and history: no replaced object,
# and no graft, which could adopt a commit into the history. The graft file is a path that can
# never exist, so git reads none and prints no deprecation hint.
GIT_NO_REPLACE_OBJECTS=1
GIT_GRAFT_FILE=/dev/null/none
export GIT_NO_REPLACE_OBJECTS GIT_GRAFT_FILE

refuse() { echo "packaging refused: $1"; exit 1; }
short() { printf '%.7s' "$1"; }
first3() { printf '%s\n' "$1" | sed '/^$/d' | head -n 3 | paste -s -d ' ' -; }

[ "$#" -gt 1 ] || refuse "check-reviews.sh needs the commit to package and its upload paths"
at="$1"
shift
git -C "$ROOT" cat-file -e "$at^{commit}" 2>/dev/null || refuse "$at is not a commit in this repository"

# Each tool that runs must be the committed one: compared by content, so a skip-worktree flag, an
# assume-unchanged flag or a restored timestamp cannot hide an edit, and a tool never committed
# refuses too.
edited=""
for tool in $TOOLS; do
  committed="$(git -C "$ROOT" rev-parse -q --verify "$at:$tool" || true)"
  actual=""
  if [ -e "$ROOT/$tool" ] || [ -L "$ROOT/$tool" ]; then
    actual="$(git -C "$ROOT" hash-object --no-filters -- "$tool")" || refuse "could not read $tool"
  fi
  [ "$committed" = "$actual" ] || edited="$edited$tool
"
done
[ -z "$edited" ] || refuse "the packaging tools differ from $(short "$at") ($(first3 "$edited")): commit them for review, or restore them"

git -C "$ROOT" cat-file -e "$at:$RECORD" 2>/dev/null || refuse "$RECORD is not committed at $(short "$at")"
# Counted before the shell reads the record, since a shell drops a NUL from what it reads: a
# carriage return or a NUL could hide a verdict from a reader.
odd="$(git -C "$ROOT" show "$at:$RECORD" | LC_ALL=C tr -d '\11\12\40-\176' | wc -c | tr -d ' ')"
[ "$odd" = 0 ] || refuse "$RECORD holds $odd bytes outside printable ASCII and tab"
record="$(git -C "$ROOT" show "$at:$RECORD")"
version="$(git -C "$ROOT" show "$at:src/app/__init__.py" \
  | sed -n 's/^__version__ = "\([0-9][0-9.]*\)"$/\1/p')"
[ -n "$version" ] || refuse "no __version__ in src/app/__init__.py at $(short "$at")"
bump="$(git -C "$ROOT" log -1 --format=%H -G'^__version__ = ' "$at" -- src/app/__init__.py)"
[ -n "$bump" ] || refuse "no commit sets version $version"

# The last verdict from each reviewer, with its line. Any line that is not blank, a comment or a
# well-formed verdict refuses the whole record.
last="$(printf '%s\n' "$record" | LC_ALL=C awk '
  /^[ \t]*(#|$)/ { next }
  {
    ok = $1 == "review" && ($2 == "engineering-reviewer" || $2 == "security-reviewer") &&
      ($3 == "PASS" || $3 == "FAIL") && length($4) == 40 && $4 ~ /^[0-9a-f]+$/ &&
      (NF == 4 || $5 ~ /^#/)
    if (!ok) {
      printf "line %d is not \"review <reviewer> <PASS|FAIL> <40-hex commit> [# note]\"", NR
      bad = 1
      exit 1
    }
    verdict[$2] = $3 " " $4 " " NR
  }
  END { if (!bad) for (r in verdict) print r, verdict[r] }
')" || refuse "$RECORD $last"

for reviewer in engineering-reviewer security-reviewer; do
  entry="$(printf '%s\n' "$last" | awk -v r="$reviewer" '$1 == r { print $2, $3, $4 }')"
  [ -n "$entry" ] || refuse "$RECORD holds no $reviewer verdict"
  read -r verdict commit line <<EOF
$entry
EOF
  passed="$reviewer passed $(short "$commit") (line $line)"
  [ "$verdict" = PASS ] || refuse "the last $reviewer verdict, line $line, is $verdict, at $(short "$commit")"
  git -C "$ROOT" cat-file -e "$commit^{commit}" 2>/dev/null \
    || refuse "$passed, which is not a commit in this repository"
  git -C "$ROOT" merge-base --is-ancestor "$commit" "$at" \
    || refuse "$passed, which is not in $(short "$at")'s history"
  git -C "$ROOT" merge-base --is-ancestor "$bump" "$commit" \
    || refuse "$passed, which comes before $(short "$bump"), the commit that set version $version"
  # shellcheck disable=SC2086  # the tool list splits on purpose
  changed="$(git -C "$ROOT" diff --no-renames --name-only "$commit" "$at" -- "$@" $TOOLS)" \
    || refuse "could not compare $(short "$commit") with $(short "$at")"
  [ -z "$changed" ] || refuse "$passed, and the upload or its packaging has changed since ($(first3 "$changed")): record a verdict on a later commit"
  echo "$reviewer: PASS at $(short "$commit") (line $line) for version $version; the upload and its packaging are unchanged since"
done
