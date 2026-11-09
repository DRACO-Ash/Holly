# The Handover local-model trial container. Trial only: never part of Holly's image or upload.
#
# Build:  docker build -t holly-handover-trial trial/
# Run:    docker run --rm --network none --memory 8g --memory-swap 8g --cpus 6 \
#           -v "$PWD/trial-data:/data:ro" -v "$PWD/trial-out:/out" holly-handover-trial \
#           run --threads /data/threads --keys /data/keys --providers /data/providers.json \
#               --model /data/models/<file>.gguf --holly-peak-gib <measured> \
#               --shift-threads <typical> --out /out
#
# --network none and the 8Gi / 6 CPU caps mirror where the model would run in Holly: the App
# Store's ceiling per app, with no network. The data volume is read-only.

# python:3.12 (Debian trixie), the full image: it carries the C++ compiler llama.cpp needs, so the
# build installs no OS packages and needs only PyPI (cmake arrives as a build dependency).
FROM python@sha256:cad37dd20c7cac861af9003af8796d03ea7a998ec1e3a664429740fc9d7d2691

ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1

COPY requirements-trial.txt /tmp/requirements-trial.txt
# Built for a generic x86-64 CPU so the result does not depend on the build machine's CPU.
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF"
RUN pip install --require-hashes -r /tmp/requirements-trial.txt

RUN useradd --uid 10001 --create-home trial
WORKDIR /trial
COPY handover_trial ./handover_trial
COPY samples ./samples
COPY tests ./tests
USER 10001
ENTRYPOINT ["python", "-m", "handover_trial"]
CMD ["--help"]
