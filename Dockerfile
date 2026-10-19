# Hardened, multi-stage Python container for the Bluestaq App Store container template.
# Shipped as a scaffold template by the deploy-recipes skill. Copy to your repository root
# as `Dockerfile` and adjust only the marked lines. Replace every <pinned-digest> with the
# real image digest at build time (the quality gate expects a pinned base). The venv is built
# in the first stage so the package manager never reaches the final image.
#
# Holly's changes to the template, each required by the appstore-gate-compliance
# build-compliant-from-start checklist (section 3), by security-hardening, or by Holly's layout:
#   - No `# syntax=` directive: it would pull a floating frontend image on every build, and
#     nothing here needs one. The base is pinned to the python:3.12-slim multi-platform index
#     digest (Python 3.12.15 on Debian trixie). Refresh it deliberately; never float the tag.
#   - Hygiene moves into a `prep` stage: OS packages patched; pip removed from the base and the
#     venv; only src/ copied, root-owned and not group- or world-writable; then the
#     setuid/setgid sweep over files AND directories as the LAST mutation, failing closed,
#     followed only by read-only checks that fail the build if an invariant does not hold.
#   - The shipped stage is flattened to one layer (FROM scratch, one COPY --from=prep / /), so
#     the image policy scan finds no layer history. It has no WORKDIR, which would add a layer.
#   - gunicorn starts in exec form with app/gunicorn_conf.py, which binds through the same
#     validated PORT parser as the dev server (a malformed PORT stops the container), turns
#     off gunicorn's admin control socket, runs one worker, and applies the database
#     migrations in the master before the worker starts. The worker is uvicorn-worker, the
#     maintained replacement for the deprecated uvicorn.workers module.
#   - The dashboard is built from frontend/ in its own stage, from the committed lockfile, and
#     only its static output is copied into app/static, so neither Node nor npm nor any
#     node_modules reach the image. The node base is pinned to the node:22-alpine index digest
#     (Node 22.23.3); refresh it deliberately, as with the Python base.
#   - No HEALTHCHECK: the platform runs on Kubernetes, which ignores it and probes the health
#     paths itself.

# ---- dashboard: compile the React app to static files ----
FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS dashboard
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
# Install scripts stay off: nothing in the tree needs one, and none may run at build time.
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- build: install from the hash-locked runtime requirements into an isolated venv ----
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements-runtime.txt .
RUN pip install --require-hashes -r requirements-runtime.txt

# ---- prep: every hygiene step, so the shipped stage can be one clean layer ----
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS prep
# Patch OS packages. Fail-open by design and in its own RUN: an offline runner may not reach the
# Debian mirror, and a tolerated miss here must never swallow a mandatory step below.
# --error-on=any makes a failed index fetch reach the warning instead of passing as "0 upgraded".
RUN (apt-get update --error-on=any && DEBIAN_FRONTEND=noninteractive apt-get -y upgrade) \
      || echo "WARNING: OS package upgrade skipped"; \
    rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/venv /opt/venv
COPY src /app/src
COPY --from=dashboard /frontend/dist /app/src/app/static
# Mandatory and fail-closed: remove pip from the venv and the base (and the bundled pip wheels),
# add the numeric non-root user with a matching group and no home directory, make the code
# writable by root alone, then strip every setuid/setgid bit on files and directories. The
# sweep is the LAST mutation; the checks after it only read.
RUN /opt/venv/bin/python -m pip uninstall --yes --quiet --root-user-action=ignore pip && \
    python -m pip uninstall --yes --quiet --root-user-action=ignore pip && \
    rm -rf /usr/local/lib/python3.12/ensurepip && \
    groupadd -g 10001 appuser && \
    useradd -u 10001 -g 10001 -M -s /usr/sbin/nologin appuser && \
    chmod -R go-w /app && \
    find / -xdev -perm /6000 \( -type f -o -type d \) -exec chmod a-s {} + && \
    test -z "$(find / -xdev -perm /6000 -print -quit)" && \
    ! /opt/venv/bin/python -c "import pip" 2>/dev/null && \
    ! python -c "import pip" 2>/dev/null

# ---- ship: one flattened layer, with the metadata re-declared ----
FROM scratch
COPY --from=prep / /
ENV PATH="/opt/venv/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LANG=C.UTF-8 PYTHONPATH=/app/src PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
EXPOSE 8080
# Exec form, so gunicorn is PID 1 and receives SIGTERM directly. The config module reads PORT
# (default 8080) through resolve_port and binds 0.0.0.0. For Flask (WSGI), change worker_class.
CMD ["gunicorn", "--chdir", "/app", "--config", "python:app.gunicorn_conf", "app.main:app"]
