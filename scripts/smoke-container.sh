#!/bin/sh
# smoke-container.sh :: the local rung for the platform's container build and deploy stages.
# It builds the image from the UPLOAD ARTEFACT (dist/appstore.zip, the context the platform
# builds from, never the working tree), runs it the way the platform does, and fails on:
#   1. a non-200 from / or a health path, with PORT unset (8080) and with PORT injected
#   2. an ERROR line or a traceback in the boot log
#   3. a malformed PORT that does not stop the container with the validation message
# Requires Docker and curl. Behind a TLS-intercepting proxy, point DOCKERFILE at a copy whose
# pip step trusts the proxy's certificate authority, and pass the build flags it needs:
#   DOCKERFILE=/path/to/copy DOCKER_BUILD_FLAGS='--network host --secret id=...' sh scripts/smoke-container.sh
# Its containers and build context are removed afterwards, also on Ctrl-C; KEEP_SMOKE=1 keeps
# the context. Green means necessary conditions met; the platform's build, scan and deploy are
# binding.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TAG="${TAG:-holly-smoke}"
CTX="$(mktemp -d "${TMPDIR:-/tmp}/holly-smoke.XXXXXX")"
CIDS=""

cleanup() {
  if [ -n "$CIDS" ]; then docker rm -f $CIDS >/dev/null 2>&1 || true; fi
  if [ "${KEEP_SMOKE:-0}" != 1 ]; then rm -rf -- "$CTX"; else echo "kept $CTX"; fi
}
trap cleanup EXIT
# dash runs the EXIT trap on a normal exit or a set -e failure, not on a signal: exit first.
trap 'exit 130' INT
trap 'exit 143' TERM

fail() {
  echo "SMOKE: FAIL: $1"
  exit 1
}

wait_until_stopped() {  # $1: container id. Prints the exit code; fails after 30 seconds.
  tries=0
  while [ "$(docker inspect -f '{{.State.Running}}' "$1")" = true ]; do
    tries=$((tries + 1))
    [ "$tries" -lt 30 ] || return 1
    sleep 1
  done
  docker inspect -f '{{.State.ExitCode}}' "$1"
}

probe() {  # $1: PORT value to inject, or empty for unset. $2: the port the container listens on.
  if [ -n "$1" ]; then
    cid="$(docker run -d -e "PORT=$1" -p "127.0.0.1::$2" "$TAG")"
  else
    cid="$(docker run -d -p "127.0.0.1::$2" "$TAG")"
  fi
  CIDS="$CIDS $cid"
  host_port="$(docker port "$cid" "$2/tcp" | head -n 1 | sed 's/.*://')"
  tries=0
  until curl -fsS -o /dev/null "http://127.0.0.1:$host_port/healthz" 2>/dev/null; do
    tries=$((tries + 1))
    [ "$tries" -lt 30 ] || { docker logs "$cid"; fail "no answer on port $2 after 30 seconds"; }
    sleep 1
  done
  for path in / /healthz /health /readyz /livez /ping; do
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$host_port$path")"
    [ "$code" = 200 ] || fail "GET $path answered $code on port $2"
  done
  if docker logs "$cid" 2>&1 | grep -E '\[ERROR\]|Traceback'; then
    fail "an error in the boot log on port $2"
  fi
  echo "port $2: / and every health path answer 200, and the boot log is clean"
}

# 1. Build from the artefact the platform receives.
sh "$HERE/package-appstore.sh"
unzip -q "$ROOT/dist/appstore.zip" -d "$CTX"
# DOCKER_BUILD_FLAGS is split into separate flags on purpose.
docker build ${DOCKER_BUILD_FLAGS:-} -f "${DOCKERFILE:-$CTX/Dockerfile}" -t "$TAG" "$CTX"

# 2. Run and probe with PORT unset, then with PORT injected as the platform does.
probe "" 8080
probe 9090 9090

# 3. A malformed PORT must stop the container at boot, never bind somewhere else.
for bad in 0 "8080 --check-config"; do
  cid="$(docker run -d -e "PORT=$bad" "$TAG")"
  CIDS="$CIDS $cid"
  code="$(wait_until_stopped "$cid")" || fail "PORT='$bad' left the container running"
  [ "$code" != 0 ] || fail "PORT='$bad' exited 0 instead of refusing to start"
  docker logs "$cid" 2>&1 | grep -q "PORT must be a whole number" \
    || fail "PORT='$bad' stopped without the validation message"
  echo "PORT='$bad' refused at boot (exit $code) with the validation message"
done

echo "SMOKE: PASS (necessary conditions met for the container build and deploy stages)"
