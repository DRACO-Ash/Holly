#!/bin/sh
# simulate-pipeline.sh :: run what the App Store pipeline does, against the ACTUAL artefact.
# Shipped as a scaffold template by appstore-gate-compliance. Run it before EVERY upload.
# A green repository loop is not a green upload: the platform checks out your zip, adds its
# own generated .gitlab-ci.yml, and runs your tests with coverage in its own environment.
# This reproduces that checkout state and command, not just the command.
#
# Adapted for Holly (Python): POSIX sh rather than bash, a fresh temporary checkout on every
# run, the transport reproduced through a Git round-trip, a PATH holding only the venv and sh,
# the locked pip install, and pytest writing coverage.xml. It packages the COMMITTED tree
# (git archive HEAD), so commit before you simulate. The checkout is removed afterwards, also
# on Ctrl-C; KEEP_SIM=1 keeps it.
# TBC, re-verify: the baseline does not record the platform's exact stage commands for the
# python template. By default this runs the canonical pair from toolchain-adapters under
# GITLAB_CI=true. Once the platform team confirms its commands, rehearse exactly those:
#   INSTALL_CMD='pip install -r requirements.txt' TEST_CMD='coverage run -m pytest && coverage xml' \
#     sh scripts/simulate-pipeline.sh
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PYTHON="${PYTHON:-python3.12}"
INSTALL_CMD="${INSTALL_CMD:-pip install --require-hashes -r requirements-dev.txt}"
TEST_CMD="${TEST_CMD:-pytest --cov --cov-report=xml}"
SIM="$(mktemp -d "${TMPDIR:-/tmp}/appstore-sim.XXXXXX")"

cleanup() {
  if [ "${KEEP_SIM:-0}" != 1 ]; then rm -rf -- "$SIM"; else echo "kept $SIM"; fi
}
trap cleanup EXIT
# dash runs the EXIT trap on a normal exit or a set -e failure, not on a signal: exit first.
trap 'exit 130' INT
trap 'exit 143' TERM

# 1. Produce the real upload artefact.
sh "$HERE/package-appstore.sh"

# 2. Check it out the way the platform does: the zip is committed into a fresh Git project and
#    the pipeline runs on a checkout of that commit, so the transport is reproduced (file modes,
#    empty directories), not just the tree. Then the platform adds its own CI file.
mkdir "$SIM/upload" "$SIM/checkout" "$SIM/bin"
unzip -q "$ROOT/dist/appstore.zip" -d "$SIM/upload"
git -C "$SIM/upload" init -q
git -C "$SIM/upload" add -A
git -C "$SIM/upload" -c user.name=simulation -c user.email=simulation@localhost \
  -c commit.gpgsign=false commit -q -m upload
git -C "$SIM/upload" archive HEAD | tar -x -C "$SIM/checkout"
printf 'stages: [test]\n' > "$SIM/checkout/.gitlab-ci.yml"   # the platform commits its own CI file

# 3. Run the platform's install, command, and environment. PATH holds the venv and sh only, so
#    no tool on this machine (git, curl, a compiler) can stand in for one the platform lacks.
cd "$SIM/checkout"
"$PYTHON" -m venv .venv
ln -s "$(command -v sh)" "$SIM/bin/sh"
SIM_PATH="$SIM/checkout/.venv/bin:$SIM/bin"
for tool in git curl tar bash; do
  if (PATH="$SIM_PATH"; command -v "$tool" >/dev/null 2>&1); then
    echo "premise failed: $tool is reachable on the simulation PATH"; exit 1
  fi
done
echo "install command: $INSTALL_CMD"
PATH="$SIM_PATH" sh -c "$INSTALL_CMD"
echo "test command: $TEST_CMD"
PATH="$SIM_PATH" GITLAB_CI=true sh -c "$TEST_CMD"

# 4. Confirm the artefact the SonarQube gate reads actually exists.
test -s coverage.xml || {
  echo "coverage.xml is missing or empty; the Code Quality gate would score 0%"; exit 1
}

echo "pipeline simulation green: necessary conditions met for the test and coverage stages, not proof the upload passes"
