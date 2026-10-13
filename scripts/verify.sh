#!/bin/sh
# verify.sh :: Holly's verification loop, the toolchain-adapters canonical steps for Python,
# cheapest first. Run it from anywhere: `sh scripts/verify.sh`. It stops at the first failure.
# Green means the necessary conditions are met. The App Store pipeline is the binding check.
set -eu
cd "$(dirname "$0")/.."
BIN="${VENV:-.venv}/bin"

step() { printf '\n== %s\n' "$1"; }

step "Runtime pin (.python-version)"
want="$(cat .python-version)"
have="$("$BIN/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "pinned $want, the venv runs $have"
[ "$have" = "$want" ] || { echo "FAIL: rebuild the venv on Python $want"; exit 1; }

step "Format (ruff format --check)"
"$BIN/ruff" format --check src tests

step "Lint (ruff check)"
"$BIN/ruff" check src tests

step "Types (mypy, strict)"
"$BIN/mypy"

step "Cognitive complexity, at most 15 per function (complexipy; SonarQube rule S3776)"
"$BIN/complexipy" src --max-complexity-allowed 15 --color no --plain

step "Duplication proxy (pylint duplicate-code over sonar.sources; tests excluded, as the gate excludes them)"
sources="$(sed -n 's/^sonar\.sources=//p' sonar-project.properties)"
echo "Reads: $sources. Cannot see: repeats inside a single file. Stricter than the 3% gate elsewhere: any repeated block of 4 lines fails."
"$BIN/pylint" --disable=all --enable=duplicate-code "$sources"

step "Tests with coverage (pytest --cov; writes coverage.xml and fails under 80%)"
"$BIN/pytest" --cov --cov-report=xml --cov-report=term-missing
test -s coverage.xml || { echo "FAIL: coverage.xml is missing or empty; the gate would read 0%"; exit 1; }

step "Dependency audit (pip-audit: the runtime lock, then the tooling lock)"
"$BIN/pip-audit" --strict --require-hashes --disable-pip --progress-spinner off -r requirements.txt
"$BIN/pip-audit" --strict --require-hashes --disable-pip --progress-spinner off -r requirements-dev.txt

printf '\nVERIFY: PASS (necessary conditions met; the App Store pipeline is the binding check)\n'
