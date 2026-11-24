# trufo-local Dockerfile
# Build from the trufo-py root, with an sdk-download key in TRUFO_SDK_DOWNLOAD_API_KEY:
# docker build --secret id=TRUFO_SDK_DOWNLOAD_API_KEY --build-arg VERSION=2.4.0 trufo-local

FROM python:3.12-slim

ARG VERSION
ENV TRUFO_LOCAL_VERSION=${VERSION}

# Refresh what the base image ships, then install system dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libmagic1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Upgrade the base image's pip, which each container also uses to install the engine at start
RUN pip install --no-cache-dir pip==26.2.2

WORKDIR /app

# Resolve dependencies with the pinned private packages installed. Remove the private packages
# in this layer so each container downloads them at start. Keep extra-sources.txt and licenses/
# in sync with the libraries bundled by the pinned wheels.
COPY requirements.txt ./
RUN --mount=type=secret,id=TRUFO_SDK_DOWNLOAD_API_KEY,required=true \
    PIP_INDEX_URL="https://__token__:$(cat /run/secrets/TRUFO_SDK_DOWNLOAD_API_KEY)@packages.trufo.ai/simple/" \
       pip install --no-cache-dir --no-deps --require-hashes -r requirements.txt \
    && PIP_EXTRA_INDEX_URL="https://__token__:$(cat /run/secrets/TRUFO_SDK_DOWNLOAD_API_KEY)@packages.trufo.ai/simple/" \
       pip install --no-cache-dir trufo==2.4.0 fastapi uvicorn 'trufo-provenance[c2pa]' \
       numpy==2.5.4 opencv-python-headless==5.0.0.93 pillow-heif==1.8.1+trufo.1 jxlpy==0.9.5 \
       imagecodecs==2026.10.10 soundfile==0.14.0 \
    && pip uninstall -y trufo-provenance trufo-avio

COPY app.py entrypoint.py ./
COPY NOTICE /usr/share/doc/trufo-local/NOTICE
COPY licenses /usr/share/doc/trufo-local/licenses

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
