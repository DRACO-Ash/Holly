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

step "Locks: the image's runtime set pinned alike in the test job's lock and the tooling lock"
echo "Reads: requirements-runtime.txt, requirements.txt and requirements-dev.txt, as text: each package a lock pins must be pinned in the lock that extends it at the same version, under the same environment marker and with the same hashes, so the platform's test job runs against what the image ships. Cannot see: whether a lock matches its manifest, which uv pip compile decides."
"$BIN/python" - <<'PY'
import re
import sys

ENTRY = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^]]*\])?==([^\s;\\]+)\s*(?:;([^\\]*))?")


def entries(path):
    found, hashes = {}, None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = ENTRY.match(line)
            if match:
                hashes = set()
                name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
                found[name] = (match.group(2), " ".join((match.group(3) or "").split()), hashes)
            elif hashes is not None and line.strip().startswith("--hash="):
                hashes.add(line.split("--hash=", 1)[1].split()[0])
            elif not line[:1].isspace():
                hashes = None
    return {name: (version, marker, frozenset(h)) for name, (version, marker, h) in found.items()}


paths = ("requirements-runtime.txt", "requirements.txt", "requirements-dev.txt")
locks = [entries(path) for path in paths]
for path, lock in zip(paths, locks):
    if not lock or any(not entry[2] for entry in lock.values()):
        print(f"FAIL: {path} pins nothing, or pins a package without its hashes")
        sys.exit(1)
for inner, outer, name in ((locks[0], locks[1], paths[1]), (locks[1], locks[2], paths[2])):
    drift = sorted(f"{k}=={v[0]}" for k, v in inner.items() if outer.get(k) != v)
    if drift:
        print(f"FAIL: {name} must pin each package of the lock it extends alike, version, marker and hashes: {drift[:5]}")
        sys.exit(1)
print(f"the runtime lock's {len(locks[0])} entries are in the test lock's {len(locks[1])}, and those in the tooling lock's {len(locks[2])}, each with the same version, marker and hashes")
PY

step "Local database: the health check asks over TCP, and dev.sh waits for it before migrating"
echo "Reads: infra/docker-compose.yml and scripts/dev.sh, as text. A check through the Unix socket passes before PostgreSQL listens on TCP. Cannot see: a check turned off with disable: true, or a fallback (||) inside a shell-form check."
grep -Eq '^ +test: [^#]*pg_isready[^#]*-h[", ]+127\.0\.0\.1' infra/docker-compose.yml \
  || { echo "FAIL: the db health check must run pg_isready over TCP (-h 127.0.0.1)"; exit 1; }
waits="$(grep -n '^[^#]*up -d --wait db[[:space:]]*$' scripts/dev.sh | head -n 1 | cut -d: -f1)"
migrates="$(grep -n '^[^#]*run_migrations()' scripts/dev.sh | head -n 1 | cut -d: -f1)"
[ -n "$waits" ] && [ -n "$migrates" ] && [ "$waits" -lt "$migrates" ] \
  || { echo "FAIL: scripts/dev.sh must run 'up -d --wait db', with nothing after it on the line, before the migrations"; exit 1; }
echo "pg_isready asks over TCP; dev.sh waits at line $waits and migrates at line $migrates"

step "Database images: both pin PostgreSQL by digest, and the smoke rung refuses any other image and waits over TCP"
echo "Reads: scripts/smoke-container.sh and infra/docker-compose.yml, as text, then runs the smoke rung's refusal on an image with no digest and one with another digest, with a stand-in docker first on PATH and DOCKER_HOST pointing nowhere, so no real Docker is reached. Cannot see: whether a digest holds the version its comment names, a later reassignment of PG_IMAGE or PG_DIGEST, a database run that names another image, or another database service in the compose file."
grep -Eq '^PG_DIGEST=sha256:[0-9a-f]{64}$' scripts/smoke-container.sh \
  && grep -Eq '^PG_IMAGE="\$\{PG_IMAGE:-postgres:[0-9]+-alpine@\$PG_DIGEST\}"$' scripts/smoke-container.sh \
  || { echo "FAIL: the smoke rung's database image must be postgres:<major>-alpine, pinned by the digest in PG_DIGEST"; exit 1; }
grep -Eq '^ +image: postgres:[0-9]+-alpine@sha256:[0-9a-f]{64}$' infra/docker-compose.yml \
  || { echo "FAIL: the local database image must be postgres:<major>-alpine, pinned by digest"; exit 1; }
grep -Eq '^until docker exec "\$db" pg_isready -q -h 127\.0\.0\.1 -U holly -d holly 2>/dev/null; do$' scripts/smoke-container.sh \
  || { echo "FAIL: the smoke rung must wait for the database over TCP, on a line of its own: pg_isready -q -h 127.0.0.1 -U holly -d holly"; exit 1; }
stub="$(mktemp -d "${TMPDIR:-/tmp}/holly-docker-stub.XXXXXX")"
printf '#!/bin/sh\nexit 97\n' > "$stub/docker"
chmod +x "$stub/docker"
for image in postgres:16-alpine "postgres:16-alpine@sha256:$(printf '%064d' 0)"; do
  rc=0
  out="$(PG_IMAGE="$image" KEEP_SMOKE=0 DOCKER_HOST=unix:///nonexistent PATH="$stub:$PATH" \
    sh scripts/smoke-container.sh 2>&1)" || rc=$?
  if [ "$rc" != 1 ] || ! printf '%s\n' "$out" | grep -q '^SMOKE: FAIL: PG_IMAGE must end in the pinned digest sha256:'; then
    rm -rf -- "$stub"
    printf 'FAIL: the smoke rung must refuse PG_IMAGE=%s; it exited %s after:\n%s\n' "$image" "$rc" \
      "$(printf '%s\n' "$out" | tail -n 5)"
    exit 1
  fi
done
rm -rf -- "$stub"
echo "both database images are pinned by digest; the smoke rung refuses any other image and waits over TCP"

step "Format (ruff format --check)"
"$BIN/ruff" format --check src tests

step "Lint (ruff check)"
echo "Reads: src and tests with the committed ruff profile. Cannot see: SonarQube rules outside it; the platform's analysis is binding."
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

step "Dashboard: install from the lockfile, then lint, format, types and build, unit tests with coverage"
echo "Reads: frontend/ with its committed configuration. The lockfile must not change."
(
  cd frontend
  npm ci --ignore-scripts --no-audit --no-fund
  git diff --exit-code -- package-lock.json \
    || { echo "FAIL: npm ci changed package-lock.json; relock from package.json"; exit 1; }
  npm run lint
  npm run format:check
  npm run build
  # The build ships the licence of every package it bundles (bundled-licences.mjs), so each
  # runtime dependency's licence must be in its output.
  node --input-type=module -e '
    import { existsSync, readFileSync } from "node:fs";
    import { licenceFileName } from "./bundled-licences.mjs";
    const deps = Object.keys(JSON.parse(readFileSync("package.json", "utf8")).dependencies);
    const missing = deps.filter((name) => !existsSync(`dist/${licenceFileName(name)}`));
    if (missing.length > 0) {
      console.log(`FAIL: the build ships no licence for ${missing.join(", ")}`);
      process.exit(1);
    }
    console.log(`licences: the build ships the licence of each of the ${deps.length} runtime dependencies; dist/licences/index.txt lists every bundled package`);
  '
  # The plugin's own self-test: what it ships, and each way it stops a build, on small projects.
  node ../scripts/test-bundled-licences.mjs
  # With coverage, as the platform's node job runs them: Vitest fails under its 80% floor and
  # writes coverage/lcov.info at the repository's root, the artefact the Code Quality gate reads.
  npm test -- --coverage
)
sh scripts/check-lcov.sh

step "Dashboard contrast (WCAG AA for every text, edge and focus pair the theme's tokens make)"
node scripts/contrast-check.mjs
# The check's own self-test: each form it must refuse, and each it must accept, on copies.
node scripts/test-contrast-check.mjs

step "Dashboard dependency audit (npm audit: runtime and tooling, every severity)"
# npm audit exits 0 with an error-shaped report when it cannot reach the advisory service, so
# the report's shape is checked: no metadata means the audit did not run, which fails.
(cd frontend && npm audit --json || true) | node -e '
let text = "";
process.stdin.on("data", (chunk) => (text += chunk)).on("end", () => {
  let report;
  try {
    report = JSON.parse(text);
  } catch {
    console.log("FAIL: npm audit gave no report");
    process.exit(1);
  }
  if (!report.metadata) {
    console.log("FAIL: npm audit could not check: " + (report.message || "no metadata"));
    process.exit(1);
  }
  const found = report.metadata.vulnerabilities;
  const total = ["info", "low", "moderate", "high", "critical"].reduce((n, k) => n + (found[k] || 0), 0);
  console.log(`npm audit: ${total} known vulnerabilities in ${report.metadata.dependencies.total} packages`);
  process.exit(total === 0 ? 0 : 1);
});'

step "Upload nets self-test (every planted problem refused, a clean upload accepted)"
sh scripts/test-package-nets.sh

step "Dependency audit (pip-audit: the runtime lock, the test job's lock, then the tooling lock)"
for lock in requirements-runtime.txt requirements.txt requirements-dev.txt; do
  "$BIN/pip-audit" --strict --require-hashes --disable-pip --progress-spinner off -r "$lock"
done

printf '\nVERIFY: PASS (necessary conditions met; the App Store pipeline is the binding check)\n'
