#!/bin/sh
# smoke-container.sh :: the local rung for the platform's container build and deploy stages.
# It builds the image from the UPLOAD'S ARCHIVE (a rehearsal package of HEAD in a temporary
# file, which needs no review record: the context the platform builds from, never the working
# tree), runs it the way the platform does (a PostgreSQL database, the FILE_STORAGE add-on's
# writable mount at /data, the settings Holly requires), and fails on:
#   1. a non-200 from / or a health path, with PORT unset (8080) and with PORT injected
#   2. an error line or a traceback in the boot log
#   3. migrations that did not reach the newest revision, migrations that run while another
#      session holds their advisory lock, an audit log that accepts an UPDATE, or a dashboard
#      that is not served
#   4. a malformed PORT, a store that refuses writes, or a missing signing key that does not
#      stop the container with a clear message
# Requires Docker and curl. Behind a TLS-intercepting proxy, point DOCKERFILE at a copy whose
# pip and npm steps trust the proxy's certificate authority, and pass the build flags it needs:
#   DOCKERFILE=/path/to/copy DOCKER_BUILD_FLAGS='--network host --secret id=...' sh scripts/smoke-container.sh
# PG_IMAGE overrides the database image, for a registry mirror of the same image: it must end in
# the pinned digest, or the run refuses, and the run logs the server version it tested. The
# database password and signing key are generated per run. The script writes neither to a file,
# though Docker keeps them in its container records until the cleanup removes the containers.
# Its containers, network and build context are removed afterwards, also on Ctrl-C;
# KEEP_SMOKE=1 keeps the context. Green means necessary conditions met; the platform's build,
# scan and deploy are binding.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TAG="${TAG:-holly-smoke}"
# PostgreSQL 16.15, as the App Store's upload page lists the POSTGRESQL add-on as PostgreSQL 16.
# TBC, re-verify: the add-on's minor version.
PG_DIGEST=sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea
PG_IMAGE="${PG_IMAGE:-postgres:16-alpine@$PG_DIGEST}"
CTX="$(mktemp -d "${TMPDIR:-/tmp}/holly-smoke.XXXXXX")"
ZIP="$(mktemp "${TMPDIR:-/tmp}/holly-smoke-upload.XXXXXX")"
NET="holly-smoke-$(basename "$CTX" | tr -dc 'A-Za-z0-9')"
CIDS=""
NET_MADE=0

cleanup() {
  if [ -n "$CIDS" ]; then docker rm -f -v $CIDS >/dev/null 2>&1 || true; fi
  if [ "$NET_MADE" = 1 ]; then docker network rm "$NET" >/dev/null 2>&1 || true; fi
  if [ "${KEEP_SMOKE:-0}" != 1 ]; then rm -rf -- "$CTX"; else echo "kept $CTX"; fi
  rm -f -- "$ZIP"
}
trap cleanup EXIT
# dash runs the EXIT trap on a normal exit or a set -e failure, not on a signal: exit first.
trap 'exit 130' INT
trap 'exit 143' TERM

fail() {
  echo "SMOKE: FAIL: $1"
  exit 1
}

case "$PG_IMAGE" in
  *"@$PG_DIGEST") ;;
  *) fail "PG_IMAGE must end in the pinned digest $PG_DIGEST" ;;
esac

random_hex() {  # $1: bytes of randomness
  od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'
}

wait_until_stopped() {  # $1: container id. Prints the exit code; fails after 60 seconds.
  tries=0
  while [ "$(docker inspect -f '{{.State.Running}}' "$1")" = true ]; do
    tries=$((tries + 1))
    [ "$tries" -lt 60 ] || return 1
    sleep 1
  done
  docker inspect -f '{{.State.ExitCode}}' "$1"
}

# Start Holly as the platform would and print its id. Extra docker run arguments follow the
# first two.
run_holly() {  # $1: PORT value to inject, or empty for unset. $2: storage mount options.
  port_env="$1"
  storage="$2"
  shift 2
  set -- --network "$NET" --tmpfs "/data:$storage" \
    -e "DATABASE_URL=postgresql://holly:$DB_SECRET@db:5432/holly" \
    -e "APP_SECRET_KEY=$SIGNING_KEY" -e STORAGE_MOUNT_PATH=/data \
    -e BACKGROUND_REFRESH_ENABLED=false "$@"
  if [ -n "$port_env" ]; then set -- -e "PORT=$port_env" "$@"; fi
  docker run -d "$@" "$TAG"
}

WRITABLE="rw,uid=10001,gid=10001,mode=0700"

probe() {  # $1: PORT value to inject, or empty for unset. $2: the port the container listens on.
  cid="$(run_holly "$1" "$WRITABLE" -p "127.0.0.1::$2")"
  CIDS="$CIDS $cid"
  host_port="$(docker port "$cid" "$2/tcp" | head -n 1 | sed 's/.*://')"
  base="http://127.0.0.1:$host_port"
  tries=0
  until curl -fsS -o /dev/null "$base/healthz" 2>/dev/null; do
    tries=$((tries + 1))
    [ "$tries" -lt 60 ] || { docker logs "$cid"; fail "no answer on port $2 after 60 seconds"; }
    sleep 1
  done
  for path in / /healthz /health /readyz /livez /ping; do
    code="$(curl -s -o /dev/null -w '%{http_code}' "$base$path")"
    [ "$code" = 200 ] || fail "GET $path answered $code on port $2"
  done
  curl -fsS "$base/api/v1/health/detailed" | grep -q '"database":"ok"' \
    || fail "the database is not reachable from the container on port $2"
  curl -fsS "$base/" | grep -q '<title>Holly</title>' || fail "/ does not serve the dashboard"
  curl -fsS -H 'Accept: text/html' "$base/notifications" | grep -q '<title>Holly</title>' \
    || fail "a dashboard page does not load on its own address"
  curl -fsSI "$base/" | grep -qi "^content-security-policy: default-src 'none'; script-src 'self'" \
    || fail "the dashboard is served without its content security policy"
  if docker logs "$cid" 2>&1 | grep -E '\[ERROR\]|"level": "ERROR"|Traceback'; then
    fail "an error in the boot log on port $2"
  fi
  docker logs "$cid" 2>&1 | grep -q '"event": "migrations", .*"status": "applied"' \
    || fail "the boot log does not show the migrations applied on port $2"
  echo "port $2: / and every health path answer 200, migrations applied, the dashboard is served, the boot log is clean"
}

refused() {  # $1: container id. $2: text the log must hold. $3: what was refused.
  code="$(wait_until_stopped "$1")" || fail "$3 left the container running"
  [ "$code" != 0 ] || fail "$3 exited 0 instead of refusing to start"
  docker logs "$1" 2>&1 | grep -q "$2" || fail "$3 stopped without the expected message"
  echo "$3: refused at boot (exit $code) with the expected message"
}

# 1. Build from the archive the platform receives, packaged as a rehearsal.
sh "$HERE/package-appstore.sh" --rehearsal "$ZIP"
unzip -q "$ZIP" -d "$CTX"
# DOCKER_BUILD_FLAGS is split into separate flags on purpose.
docker build ${DOCKER_BUILD_FLAGS:-} -f "${DOCKERFILE:-$CTX/Dockerfile}" -t "$TAG" "$CTX"

# 2. A database on a private network, as the POSTGRESQL add-on provides one. Both values are
#    random for this run only.
DB_SECRET=$(random_hex 16)
SIGNING_KEY=$(random_hex 32)
docker network create "$NET" >/dev/null
NET_MADE=1
db="$(docker run -d --network "$NET" --network-alias db \
  -e POSTGRES_DB=holly -e POSTGRES_USER=holly -e "POSTGRES_PASSWORD=$DB_SECRET" "$PG_IMAGE")"
CIDS="$CIDS $db"
# Over TCP, as Holly connects: on a fresh volume the image first answers on its Unix socket alone
# while it initialises, then restarts and listens on TCP.
tries=0
until docker exec "$db" pg_isready -q -h 127.0.0.1 -U holly -d holly 2>/dev/null; do
  tries=$((tries + 1))
  [ "$tries" -lt 60 ] || { docker logs "$db"; fail "the database did not start"; }
  sleep 1
done
pg_version="$(docker exec "$db" psql -U holly -d holly -qtAc 'SHOW server_version')" \
  || fail "could not read the database's server version"
[ -n "$pg_version" ] || fail "the database reported no server version"
echo "database: $PG_IMAGE, PostgreSQL $pg_version"

# 3. Run and probe with PORT unset, then with PORT injected as the platform does. The second
#    container finds the schema already at head.
probe "" 8080
probe 9090 9090
head="$(docker exec "$db" psql -U holly -d holly -qtAc 'SELECT version_num FROM alembic_version')"
[ "$head" = "$(ls "$CTX/src/app/migrations/versions" | sed -n 's/\.py$//p' | sort | tail -n 1)" ] \
  || fail "the database is at $head, not the newest migration"
if docker exec "$db" psql -U holly -d holly -qtAc 'UPDATE audit.audit_log SET action_type = action_type' >/dev/null 2>&1; then
  fail "the audit log accepted an UPDATE"
fi
echo "the schema is at $head and the audit log refuses an UPDATE"

# 3b. Two containers starting together must not migrate at once. While a psql session holds the
#     migration lock, a starting container must not report its migrations applied, and once the
#     session ends and frees it, it must.
lock_key="$(sed -n 's/^MIGRATION_ADVISORY_LOCK_KEY = //p' "$CTX/src/app/migrations/env.py")"
[ -n "$lock_key" ] || fail "the packaged migrations name no MIGRATION_ADVISORY_LOCK_KEY"
lock_key=$(( $lock_key ))
docker exec -d "$db" psql -U holly -d holly -qtAc "SELECT pg_advisory_lock($lock_key), pg_sleep(20)"
tries=0
until [ "$(docker exec "$db" psql -U holly -d holly -qtAc \
  "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND granted")" = 1 ]; do
  tries=$((tries + 1))
  [ "$tries" -lt 20 ] || fail "could not hold the migration lock for the check"
  sleep 1
done
cid="$(run_holly "" "$WRITABLE")"
CIDS="$CIDS $cid"
tries=0
until docker logs "$cid" 2>&1 | grep -q '"event": "migrations", .*"status": "starting"'; do
  tries=$((tries + 1))
  [ "$tries" -lt 15 ] || fail "the container did not start its migrations"
  sleep 1
done
sleep 3
if docker logs "$cid" 2>&1 | grep -q '"event": "migrations", .*"status": "applied"'; then
  fail "migrations ran while another session held the migration lock"
fi
tries=0
until docker logs "$cid" 2>&1 | grep -q '"event": "migrations", .*"status": "applied"'; do
  tries=$((tries + 1))
  [ "$tries" -lt 60 ] || fail "migrations did not run once the migration lock was freed"
  sleep 1
done
echo "migrations wait while another session holds the migration lock, then run"

# 4. Each of these must stop the container at boot, never run in a degraded state.
for bad in 0 "8080 --check-config"; do
  cid="$(docker run -d -e "PORT=$bad" "$TAG")"
  CIDS="$CIDS $cid"
  refused "$cid" "PORT must be a whole number" "PORT='$bad'"
done
cid="$(run_holly "" "ro")"
CIDS="$CIDS $cid"
refused "$cid" '"storage_writable": false' "a read-only store"
cid="$(docker run -d --network "$NET" -e "DATABASE_URL=postgresql://holly:$DB_SECRET@db:5432/holly" "$TAG")"
CIDS="$CIDS $cid"
refused "$cid" "APP_SECRET_KEY" "a missing APP_SECRET_KEY"

echo "SMOKE: PASS (necessary conditions met for the container build and deploy stages)"
