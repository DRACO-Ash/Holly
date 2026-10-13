#!/bin/sh
# simulate-pipeline.sh :: run what the App Store pipeline does, against the ACTUAL artefact.
# Shipped as a scaffold template by appstore-gate-compliance. Run it before EVERY upload.
# A green repository loop is not a green upload: the platform checks out your zip, adds its
# own generated .gitlab-ci.yml, and runs your tests with coverage in its own environment.
# This reproduces that checkout state and command, not just the command.
#
# Adapted for Holly (Python): POSIX sh rather than bash, a fresh temporary checkout on every
# run, the locked pip install, and pytest writing coverage.xml. It packages the COMMITTED tree
# (git archive HEAD), so commit before you simulate.
# TBC, re-verify: the baseline does not record the platform's exact install and test commands
# for the python template. By default this runs the canonical pair from toolchain-adapters under
# GITLAB_CI=true. Once the platform team confirms its test command, rehearse that exact command:
#   TEST_CMD='coverage run -m pytest && coverage xml' sh scripts/simulate-pipeline.sh
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PYTHON="${PYTHON:-python3.12}"
TEST_CMD="${TEST_CMD:-pytest --cov --cov-report=xml}"
SIM="$(mktemp -d "${TMPDIR:-/tmp}/appstore-sim.XXXXXX")"

# 1. Produce the real upload artefact.
(cd "$ROOT" && sh "$HERE/package-appstore.sh")

# 2. Check it out the way the platform does.
unzip -q "$ROOT/dist/appstore.zip" -d "$SIM"
printf 'stages: [test]\n' > "$SIM/.gitlab-ci.yml"   # the platform commits its own CI file

# 3. Run the platform's install, command, and environment.
cd "$SIM"
"$PYTHON" -m venv .venv
.venv/bin/pip install --quiet --disable-pip-version-check --require-hashes -r requirements-dev.txt
echo "test command: $TEST_CMD"
PATH="$SIM/.venv/bin:$PATH" GITLAB_CI=true sh -c "$TEST_CMD"

# 4. Confirm the artefact the SonarQube gate reads actually exists.
test -s coverage.xml || {
  echo "coverage.xml is missing or empty; the Code Quality gate would score 0%"; exit 1
}

echo "pipeline simulation green in $SIM: necessary conditions met for the test and coverage stages, not proof the upload passes"
