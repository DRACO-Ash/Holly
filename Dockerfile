# syntax=docker/dockerfile:1
# Hardened, multi-stage Python container for the Bluestaq App Store container template.
# Shipped as a scaffold template by the deploy-recipes skill. Copy to your repository root
# as `Dockerfile` and adjust only the marked lines. Replace every <pinned-digest> with the
# real image digest at build time (the quality gate expects a pinned base). The venv is built
# in the first stage so the package manager never reaches the final image.
#
# Holly's changes to the template, each required by the appstore-gate-compliance
# build-compliant-from-start checklist (section 3) or by Holly's layout:
#   - The base is pinned to the python:3.12-slim multi-platform index digest (Python 3.12.15 on
#     Debian trixie, image created 2026-10-06). Refresh it deliberately; never float the tag.
#   - Hygiene moves into a `prep` stage: OS packages patched; pip removed from the base and the
#     venv; the app copied root-owned, since nothing writes to /app at runtime; then the
#     setuid/setgid sweep over files AND directories as the LAST mutation, failing closed.
#   - The shipped stage is flattened to one layer (FROM scratch, one COPY --from=prep / /), so
#     the image policy scan finds no layer history.
#   - The start command loads app.main:app from src/ and uses uvicorn-worker, the maintained
#     replacement for the deprecated uvicorn.workers module.

# ---- build: install from the hash-locked requirements into an isolated venv ----
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --require-hashes -r requirements.txt

# ---- prep: every hygiene step, so the shipped stage can be one clean layer ----
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS prep
# Patch OS packages. Fail-open by design and in its own RUN: an offline runner may not reach the
# Debian mirror, and a tolerated miss here must never swallow a mandatory step below.
RUN (apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y upgrade) \
      || echo "WARNING: OS package upgrade skipped"; \
    rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/venv /opt/venv
COPY . /app
# Mandatory and fail-closed: remove pip from the venv and the base (and the bundled pip wheels),
# add the numeric non-root user, then strip every setuid/setgid bit on files and directories.
# The sweep is the LAST mutation in this stage; nothing may follow it.
RUN /opt/venv/bin/python -m pip uninstall --yes --quiet --root-user-action=ignore pip && \
    python -m pip uninstall --yes --quiet --root-user-action=ignore pip && \
    rm -rf /usr/local/lib/python3.12/ensurepip && \
    useradd -u 10001 -r -s /usr/sbin/nologin appuser && \
    find / -xdev -perm /6000 \( -type f -o -type d \) -exec chmod a-s {} +

# ---- ship: one flattened layer, with the metadata re-declared ----
# No WORKDIR here: in this stage it writes a second layer. gunicorn's --chdir sets the
# working directory instead, so the image stays one layer.
FROM scratch
COPY --from=prep / /
ENV PATH="/opt/venv/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LANG=C.UTF-8 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
EXPOSE 8080
# Bind 0.0.0.0 and read PORT (default 8080). `exec` so SIGTERM reaches gunicorn and shutdown
# does not hang. For Flask (WSGI) drop the uvicorn worker class.
CMD ["sh","-c","exec gunicorn --chdir /app --pythonpath /app/src app.main:app -k uvicorn_worker.UvicornWorker -b 0.0.0.0:${PORT:-8080}"]
