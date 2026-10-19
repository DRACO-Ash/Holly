#!/bin/sh
# simulate-pipeline.sh :: run what the App Store pipeline does, against the ACTUAL artefact.
# Shipped as a scaffold template by appstore-gate-compliance. Run it before EVERY upload.
# A green repository loop is not a green upload: the platform checks out your zip, adds its
# own generated .gitlab-ci.yml, and runs your tests with coverage in its own environment.
# This reproduces that checkout state and those commands, not just the commands.
#
# Adapted for Holly: POSIX sh rather than bash, fresh temporary checkouts on every run, the
# transport reproduced through a Git round-trip, and a PATH holding only what each job needs. It
# packages the COMMITTED tree (git archive HEAD), so commit before you simulate, as a rehearsal:
# the upload's bytes and nets without the review check, written into its own temporary
# directory, so it can run before the reviews. The checkouts are removed afterwards, also on
# Ctrl-C; KEEP_SIM=1 keeps them.
#
# The platform ran two test jobs on V0.4's upload, each on its own checkout, and their logs give
# the commands verbatim. This runs both, each on a fresh copy of the checkout, and fails if
# either fails, so one job's failure never hides the other's:
#   python, on python:3.12-slim: pip install -r requirements.txt, then
#     pytest --cov --cov-report=xml:coverage.xml (INSTALL_CMD and TEST_CMD replace the two);
#   node, on node:24-alpine: npm ci, at the checkout's root.
# TBC, re-verify: what the node job runs after npm ci. This runs the node template's commands,
# npm test -- --coverage and npm run build (appstore-gate-compliance 2.0.1), then checks with
# check-lcov.sh that coverage/lcov.info names every file under frontend/src that is not a test,
# each by its path in the checkout, since the gate scores a file it cannot find at 0%. This machine's python3.12 and node stand in for the
# jobs' images, so a difference between the images and this machine is not reproduced.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3.12}"
INSTALL_CMD="${INSTALL_CMD:-pip install -r requirements.txt}"
TEST_CMD="${TEST_CMD:-pytest --cov --cov-report=xml:coverage.xml}"
SIM="$(mktemp -d "${TMPDIR:-/tmp}/appstore-sim.XXXXXX")"

cleanup() {
  if [ "${KEEP_SIM:-0}" != 1 ]; then rm -rf -- "$SIM"; else echo "kept $SIM"; fi
}
trap cleanup EXIT
# dash runs the EXIT trap on a normal exit or a set -e failure, not on a signal: exit first.
trap 'exit 130' INT
trap 'exit 143' TERM

# 1. Produce the upload's archive, as a rehearsal.
sh "$HERE/package-appstore.sh" --rehearsal "$SIM/upload.zip"

# 2. Check it out the way the platform does: the zip is committed into a fresh Git project and
#    the pipeline runs on a checkout of that commit, so the transport is reproduced (file modes,
#    empty directories), not just the tree.
mkdir "$SIM/upload"
unzip -q "$SIM/upload.zip" -d "$SIM/upload"
git -C "$SIM/upload" init -q
git -C "$SIM/upload" add -A
git -C "$SIM/upload" -c user.name=simulation -c user.email=simulation@localhost \
  -c commit.gpgsign=false commit -q -m upload
git -C "$SIM/upload" archive -o "$SIM/checkout.tar" HEAD

# A job's own checkout, with the CI file the platform commits, and a directory for its PATH
# holding sh and the tools named, so no tool on this machine (git, curl, a compiler) can stand
# in for one the job's image lacks.
checkout() {  # $1: the job, then the tools its PATH holds besides sh
  job="$1"
  shift
  mkdir "$SIM/$job" "$SIM/$job-bin"
  tar -x -C "$SIM/$job" -f "$SIM/checkout.tar"
  printf 'stages: [test]\n' > "$SIM/$job/.gitlab-ci.yml"
  for tool in sh "$@"; do
    found="$(command -v "$tool")" || { echo "premise failed: $tool is not installed here"; exit 1; }
    ln -s "$found" "$SIM/$job-bin/$tool"
  done
}

unreachable() {  # $1: the job's PATH, then the tools that must not be on it
  path="$1"
  shift
  for tool in "$@"; do
    if (PATH="$path"; command -v "$tool" >/dev/null 2>&1); then
      echo "premise failed: $tool is reachable on the simulation PATH"; exit 1
    fi
  done
}

python_job() {
  checkout python
  cd "$SIM/python"
  "$PYTHON" -m venv .venv
  path="$SIM/python/.venv/bin:$SIM/python-bin"
  unreachable "$path" git curl tar bash node npm
  echo "python job: $INSTALL_CMD"
  PATH="$path" sh -c "$INSTALL_CMD"
  echo "python job: $TEST_CMD"
  PATH="$path" CI=true GITLAB_CI=true sh -c "$TEST_CMD"
  # The artefact the SonarQube gate reads.
  test -s coverage.xml || {
    echo "python job: coverage.xml is missing or empty; the Code Quality gate would score 0%"; exit 1
  }
}

node_job() {
  checkout node node npm
  cd "$SIM/node"
  path="$SIM/node-bin"
  unreachable "$path" git curl tar bash python3 pip
  for command in 'npm ci' 'npm test -- --coverage' 'npm run build'; do
    echo "node job: $command"
    PATH="$path" CI=true GITLAB_CI=true sh -c "$command"
  done
  # The report the Code Quality gate reads, checked as the loop checks it (check-lcov.sh).
  sh "$HERE/check-lcov.sh" "$SIM/node"
}

# 3. Both jobs, each in a subshell of its own that stops at its first failure, so this shell
#    reports both.
set +e
(set -e; python_job)
python_status=$?
(set -e; node_job)
node_status=$?
set -e
verdict() { if [ "$1" = 0 ]; then echo pass; else echo "FAIL (exit $1)"; fi; }
echo "python job: $(verdict "$python_status"); node job: $(verdict "$node_status")"
[ "$python_status" = 0 ] && [ "$node_status" = 0 ] || exit 1

echo "pipeline simulation green: necessary conditions met for both test jobs and their coverage reports, not proof the upload passes"
