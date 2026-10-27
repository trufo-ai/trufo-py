# trufo-local Dockerfile
# Build from the trufo-py root, with the package index key in TRUFO_PACKAGES_INDEX_KEY:
# docker build --secret id=TRUFO_PACKAGES_INDEX_KEY --build-arg VERSION=2.1.0 trufo-local

FROM --platform=linux/amd64 python:3.12-slim

ARG VERSION
ENV TRUFO_LOCAL_VERSION=${VERSION}

# Refresh what the base image ships, then install system dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libmagic1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the engine's dependencies as the engine itself declares them, then remove the engine;
# each container installs it at start. The index key exists only within this step
COPY requirements.txt ./
RUN --mount=type=secret,id=TRUFO_PACKAGES_INDEX_KEY,required=true \
    PIP_INDEX_URL="https://__token__:$(cat /run/secrets/TRUFO_PACKAGES_INDEX_KEY)@packages.trufo.ai/simple/" \
       pip install --no-cache-dir --no-deps --require-hashes -r requirements.txt \
    && pip install --no-cache-dir trufo==2.1.0 fastapi uvicorn 'trufo-provenance[c2pa]' \
       numpy==2.5.4 opencv-python-headless==5.0.0.93 \
    && pip uninstall -y trufo-provenance

COPY app.py entrypoint.py ./
COPY NOTICE /usr/share/doc/trufo-local/NOTICE

LABEL ai.trufo.trufo-local.source=ghcr.io/trufo-ai/trufo-local:${VERSION}-source \
      org.opencontainers.image.source=https://github.com/trufo-ai/trufo-py

# Environment defaults; HOME serves a user with no passwd entry and holds the engine
ENV HOME=/tmp
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER 10001

EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Check the settings, install the engine, then run the service
CMD ["python", "entrypoint.py"]
