#!/bin/sh
# check-package.sh :: the upload nets, run on a built zip by package-appstore.sh.
# Usage: sh scripts/check-package.sh <zip>
#   1. Required members at the root: requirements.txt, Dockerfile and pyproject.toml (the pytest
#      configuration the platform's test stage depends on).
#   2. Name net, matched without regard to case: no virtualenv, tool cache, coverage output,
#      environment file (.env, .env.*, .env-*, .envrc, *.env), or archive or compressed file by
#      extension (zip and its family such as docx, xlsx, jar and apk; tar, gz, xz, 7z and the
#      like) at any depth, and no member name holding a control character (unzip lists one as
#      ^X, so any ^ refuses). Extensions are defence in depth: the content net decides by bytes.
#   3. Content net: every extracted file is read by scan-package.mjs. A file whose leading bytes
#      mark an archive or compressed stream is refused whatever its name; every other file is
#      scanned with the secret-scan hook's rules, as UTF-8 and as UTF-16 in either byte order.
#      Cannot see: secret shapes the hook has no rule for, other encodings, or compressed
#      streams embedded inside other formats (a PDF, a Parquet file, an image).
# Needs unzip and node; without them it refuses. scripts/test-package-nets.sh proves each net.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ZIP="$1"
SCAN="$(mktemp -d "${TMPDIR:-/tmp}/holly-package-scan.XXXXXX")"
trap 'rm -rf -- "$SCAN"' EXIT
# dash runs the EXIT trap on a normal exit or a set -e failure, not on a signal: exit first.
trap 'exit 130' INT
trap 'exit 143' TERM

# Read member NAMES only (unzip -Z1), so the patterns anchor on the real path and are not
# defeated by the size and date columns of a plain `unzip -l` listing.
names="$(unzip -Z1 "$ZIP")"
for required in requirements.txt Dockerfile pyproject.toml; do
  printf '%s\n' "$names" | grep -qx "$required" || { echo "package is missing $required"; exit 1; }
done

if printf '%s\n' "$names" | grep -q '\^'; then
  echo "package has a member name with a control character (or a ^). Rename it."; exit 1
fi

# Anchor each banned component at the start of a name or just after a slash, so a root-level
# file is caught, not only a nested one.
if printf '%s\n' "$names" | grep -iqE '(^|/)(\.venv|venv|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.complexipy_cache|coverage|htmlcov)/|(^|/)(\.env[^/]*|[^/]+\.env)$|(^|/)(coverage\.xml|\.coverage(\..+)?)$|\.(zip|jar|war|ear|apk|whl|egg|nupkg|docx|xlsx|pptx|odt|ods|odp|epub|npz|tar|tgz|gz|bz2|xz|zst|7z|rar|lz|lzma|lz4|z|br)$'; then
  echo "package contains a banned path (a virtualenv, a tool cache, coverage output, an environment file or an archive). Fix .gitignore and untrack it."; exit 1
fi

command -v node >/dev/null 2>&1 || { echo "node is required for the package secret scan"; exit 1; }
unzip -q "$ZIP" -d "$SCAN"
files="$(printf '%s\n' "$names" | grep -vc '/$' || true)"
node "$ROOT/scripts/scan-package.mjs" "$SCAN" "$files" "$ROOT/.claude/hooks/secret-scan.mjs"
