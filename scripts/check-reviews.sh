#!/bin/sh
# check-reviews.sh :: refuse packaging unless both binding reviews passed the upload at HEAD.
# Usage: sh scripts/check-reviews.sh <upload path>...   (package-appstore.sh passes its list)
#
# Reads scripts/upload-record.txt from HEAD, so an uncommitted edit never counts. For the
# version in src/app/__init__.py at HEAD, the last verdict from engineering-reviewer and the
# last from security-reviewer must each be a PASS against a commit that is
#   1. in this repository and in HEAD's history;
#   2. at or after the commit that set the version (the bump);
#   3. carrying the same upload as HEAD: the packaged paths, .gitattributes and the packaging
#      tools (this script, the packager, the upload nets, the binary allowlist and the
#      secret-scan rules they use) are unchanged since, so a PASS recorded against a tree that
#      has since moved refuses.
# The packaging tools that run are the working tree's, so one edited or never committed refuses
# too. A line it cannot read, a git error or a missing record refuses. It proves the record is
# present and consistent with the history, not that a review took place (SECURITY.md).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RECORD=scripts/upload-record.txt
TOOLS="scripts/check-reviews.sh scripts/package-appstore.sh scripts/check-package.sh
  scripts/scan-package.mjs scripts/upload-binaries.txt .claude/hooks/secret-scan.mjs .gitattributes"

refuse() { echo "packaging refused: $1"; exit 1; }
short() { printf '%.7s' "$1"; }

[ "$#" -gt 0 ] || refuse "check-reviews.sh was given no upload paths"
# shellcheck disable=SC2086  # the tool list splits on purpose
edited="$(git -C "$ROOT" status --porcelain --untracked-files=all -- $TOOLS)" \
  || refuse "could not compare the packaging tools with HEAD"
[ -z "$edited" ] || refuse "the packaging tools differ from HEAD ($(printf '%s\n' "$edited" | cut -c4- | head -n 3 | paste -s -d ' ' -)): commit them for review, or restore them"
record="$(git -C "$ROOT" show "HEAD:$RECORD" 2>/dev/null)" || refuse "$RECORD is not committed at HEAD"
version="$(git -C "$ROOT" show HEAD:src/app/__init__.py \
  | sed -n 's/^__version__ = "\([0-9][0-9.]*\)"$/\1/p')"
[ -n "$version" ] || refuse "no __version__ in src/app/__init__.py at HEAD"
bump="$(git -C "$ROOT" log -1 --format=%H -G'^__version__ = ' HEAD -- src/app/__init__.py)"
[ -n "$bump" ] || refuse "no commit sets version $version"

# The last verdict from each reviewer for this version. Any line that is not blank, a comment
# or a well-formed review line refuses the whole record.
last="$(printf '%s\n' "$record" | awk -v version="$version" '
  /^[ \t]*(#|$)/ { next }
  {
    ok = $1 == "review" && $2 ~ /^[0-9]+(\.[0-9]+)*$/ &&
      ($3 == "engineering-reviewer" || $3 == "security-reviewer") &&
      ($4 == "PASS" || $4 == "FAIL") && length($5) == 40 && $5 ~ /^[0-9a-f]+$/ &&
      (NF == 5 || $6 ~ /^#/)
    if (!ok) {
      printf "line %d is not \"review <version> <reviewer> <PASS|FAIL> <40-hex commit> [# note]\"", NR
      bad = 1
      exit 1
    }
  }
  # Compared as text: awk would read 9.1 and 9.10 as the same number.
  ($2 "") == (version "") { verdict[$3] = $4 " " $5 }
  END { if (!bad) for (r in verdict) print r, verdict[r] }
')" || refuse "$RECORD $last"

for reviewer in engineering-reviewer security-reviewer; do
  entry="$(printf '%s\n' "$last" | awk -v r="$reviewer" '$1 == r { print $2, $3 }')"
  [ -n "$entry" ] || refuse "$RECORD holds no $reviewer verdict for $version"
  verdict="${entry% *}"
  commit="${entry#* }"
  [ "$verdict" = PASS ] || refuse "the last $reviewer verdict for $version is $verdict, at $(short "$commit")"
  git -C "$ROOT" cat-file -e "$commit^{commit}" 2>/dev/null \
    || refuse "$reviewer passed $(short "$commit"), which is not a commit in this repository"
  git -C "$ROOT" merge-base --is-ancestor "$commit" HEAD \
    || refuse "$reviewer passed $(short "$commit"), which is not in HEAD's history"
  git -C "$ROOT" merge-base --is-ancestor "$bump" "$commit" \
    || refuse "$reviewer passed $(short "$commit"), which comes before $(short "$bump") set version $version"
  # shellcheck disable=SC2086  # as above
  changed="$(git -C "$ROOT" diff --name-only "$commit" HEAD -- "$@" $TOOLS)" \
    || refuse "could not compare $(short "$commit") with HEAD"
  [ -z "$changed" ] || refuse "$reviewer passed $(short "$commit"), and the upload or its packaging has changed since ($(printf '%s\n' "$changed" | head -n 3 | paste -s -d ' ' -)): record a verdict on a later commit"
  echo "$reviewer: PASS at $(short "$commit") for $version; the upload and its packaging are unchanged since"
done
