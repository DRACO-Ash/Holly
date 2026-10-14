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
# out), and every packaged file's CONTENT is scanned for secrets, which needs node.
set -eu
cd "$(dirname "$0")/.."

OUT="dist/appstore.zip"
HOOK=".claude/hooks/secret-scan.mjs"
mkdir -p dist

# git archive -o replaces any previous zip, so nothing needs deleting first.
git archive --format=zip -o "$OUT" HEAD -- \
  Dockerfile .dockerignore .python-version pyproject.toml README.md \
  requirements.in requirements.txt requirements-dev.in requirements-dev.txt \
  sonar-project.properties src tests

# Verify the contracts that most often fail on upload, before a human ever uploads.
# Read member NAMES only (unzip -Z1), so the pattern anchors on the real path and is not
# defeated by the size and date columns of a plain `unzip -l` listing.
names="$(unzip -Z1 "$OUT")"
for required in requirements.txt Dockerfile pyproject.toml; do
  # pyproject.toml carries the pytest configuration the platform's test stage depends on.
  printf '%s\n' "$names" | grep -qx "$required" || { echo "package is missing $required"; exit 1; }
done
# Name net: anchor each banned component at the start of a name or just after a slash, so a
# root-level file is caught, not only a nested one. Banned: a virtualenv, a tool cache, coverage
# output, and any environment file (.env, .env.*, .env-*, .envrc, *.env). git archive already
# omits gitignored files; this catches one tracked by mistake.
if printf '%s\n' "$names" | grep -qE '(^|/)(\.venv|venv|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.complexipy_cache|coverage|htmlcov)/|(^|/)(\.env[^/]*|[^/]+\.env)$|(^|/)(coverage\.xml|\.coverage(\..+)?)$'; then
  echo "package contains a banned path (a virtualenv, a tool cache, coverage output, or an environment file). Fix .gitignore and untrack it."; exit 1
fi

# Content net: a secret in an unexpected file escapes every name pattern, so each packaged file
# is scanned with the secret-scan hook's rules, the one list that also guards every write.
command -v node >/dev/null 2>&1 || { echo "node is required for the package secret scan"; exit 1; }
hits="$(printf '%s\n' "$names" | while IFS= read -r member; do
  case "$member" in */) continue ;; esac
  unzip -p "$OUT" "$member" \
    | node -e 'let s = ""; process.stdin.setEncoding("utf8");
        process.stdin.on("data", (d) => { s += d; }).on("end", () => process.stdout.write(
          JSON.stringify({ tool_name: "Write", tool_input: { file_path: process.argv[1], content: s } })));' "$member" \
    | node "$HOOK" >/dev/null 2>&1 || printf '%s\n' "$member"
done)"
if [ -n "$hits" ]; then
  echo "secret-scan rules matched in: $hits"; exit 1
fi

echo "wrote $OUT"
