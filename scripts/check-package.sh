#!/bin/sh
# check-package.sh :: the upload nets, run on a built zip by package-appstore.sh.
# Usage: sh scripts/check-package.sh <zip>
#   1. Required members at the root: requirements.txt, Dockerfile and pyproject.toml (the pytest
#      configuration the platform's test stage depends on).
#   2. Name net, matched without regard to case: no virtualenv, tool cache, coverage output,
#      environment file (.env, .env.*, .env-*, .envrc, *.env), or archive or compressed file by
#      extension (zip and its family such as docx, xlsx, jar and apk; tar, gz, xz, 7z and the
#      like) at any depth. Extensions are defence in depth: the content net decides by bytes.
#      The agent configuration (CLAUDE.md, CLAUDE.local.md, .mcp.json, anything under .claude/)
#      is refused by name too: it is tracked on purpose, so its fix is the path list, not
#      .gitignore. Every name must be printable ASCII (unzip lists a control character as ^X,
#      so any ^ refuses; it lists a DEL or a byte above 0x7E as it stands, and extraction would
#      drop or change it), and every file must land under the name it is listed by, so no name
#      passes the net in one form and lands in another. A grep error refuses.
#   3. Content net: scan-package.mjs scans only readable text (strict UTF-8 without control
#      characters) with the secret-scan hook's rules, and refuses every other file whatever its
#      name, unless scripts/upload-binaries.txt, read from HEAD, pins it by SHA-256 with a
#      reason; an allowlisted binary's readable runs are still scanned, and every run names it.
#      Cannot see: secret shapes the hook has no rule for, secrets encoded inside text (base64,
#      a data: URI), or secrets encoded inside an allowlisted binary.
# Needs unzip and node; without them it refuses. scripts/test-package-nets.sh proves each net.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ZIP="$1"
SCAN="$(mktemp -d "${TMPDIR:-/tmp}/holly-package-scan.XXXXXX")"
ALLOW="$(mktemp "${TMPDIR:-/tmp}/holly-allowlist.XXXXXX")"
trap 'rm -rf -- "$SCAN"; rm -f -- "$ALLOW"' EXIT
# dash runs the EXIT trap on a normal exit or a set -e failure, not on a signal: exit first.
trap 'exit 130' INT
trap 'exit 143' TERM

# Read member NAMES only (unzip -Z1), so the patterns anchor on the real path and are not
# defeated by the size and date columns of a plain `unzip -l` listing.
names="$(unzip -Z1 "$ZIP")"
for required in requirements.txt Dockerfile pyproject.toml; do
  printf '%s\n' "$names" | grep -qx "$required" || { echo "package is missing $required"; exit 1; }
done

# Whether any member name matches, byte by byte. grep exits 1 for no match; an error (2 or more)
# refuses rather than reading as no match.
names_match() {  # grep's options and pattern
  status=0
  printf '%s\n' "$names" | LC_ALL=C grep -q "$@" || status=$?
  [ "$status" -le 1 ] || { echo "could not check the member names (grep exited $status)"; exit 1; }
  [ "$status" -eq 0 ]
}

if names_match '\^'; then
  echo "package has a member name with a control character (or a ^). Rename it."; exit 1
fi

# unzip lists a DEL or a byte above 0x7E as it stands, and extraction drops or changes it, so
# CLAUDE<DEL>.md would pass every pattern below and land as CLAUDE.md.
if names_match '[^ -~]'; then
  echo "package has a member name with a byte outside printable ASCII. Rename it."; exit 1
fi

# Anchor each banned component at the start of a name or just after a slash, so a root-level
# file is caught, not only a nested one.
if names_match -iE '(^|/)(\.venv|venv|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.complexipy_cache|coverage|htmlcov)/|(^|/)(\.env[^/]*|[^/]+\.env)$|(^|/)(coverage\.xml|\.coverage(\..+)?)$|\.(zip|jar|war|ear|apk|whl|egg|nupkg|docx|xlsx|pptx|odt|ods|odp|epub|npz|tar|tgz|gz|bz2|xz|zst|7z|rar|lz|lzma|lz4|z|br)$'; then
  echo "package contains a banned path (a virtualenv, a tool cache, coverage output, an environment file or an archive). Fix .gitignore and untrack it."; exit 1
fi

if names_match -iE '(^|/)\.claude/|(^|/)(claude(\.local)?\.md|\.mcp\.json)$'; then
  echo "package contains the agent configuration (CLAUDE.md, CLAUDE.local.md, .mcp.json or .claude/). Keep it off the path list in scripts/package-appstore.sh (exclude a nested one with a :(exclude)<path> pathspec)."; exit 1
fi

command -v node >/dev/null 2>&1 || { echo "node is required for the package secret scan"; exit 1; }
# The binary allowlist comes from HEAD, the commit being packaged, so an uncommitted entry can
# never exempt a file.
git -C "$ROOT" show HEAD:scripts/upload-binaries.txt > "$ALLOW" \
  || { echo "could not read scripts/upload-binaries.txt from HEAD"; exit 1; }
unzip -q "$ZIP" -d "$SCAN"
# Every file must land under the name the listing gave it: a name extraction changes, such as a
# doubled slash, ./ or a byte the extractor drops, could carry what the name net refused.
listed="$(printf '%s\n' "$names" | grep -v '/$' | LC_ALL=C sort)"
written="$(cd "$SCAN" && find . ! -type d | sed 's|^\./||' | LC_ALL=C sort)"
[ "$listed" = "$written" ] || { echo "package member names change on extraction. Rename them."; exit 1; }
files="$(printf '%s\n' "$names" | grep -vc '/$' || true)"
node "$ROOT/scripts/scan-package.mjs" "$SCAN" "$files" "$ROOT/.claude/hooks/secret-scan.mjs" "$ALLOW"
