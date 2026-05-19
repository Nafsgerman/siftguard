# syntax=docker/dockerfile:1.7
# SIFTGuard — multi-stage build, linux/amd64 only.
# Build on Apple Silicon: docker buildx build --platform=linux/amd64 --load -t siftguard:demo .

# ============================================================
# Stage 1 — dependency builder
# ============================================================
FROM python:3.11-slim-bookworm AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install pinned runtime deps first — best layer cache hit rate
COPY requirements.txt ./
RUN pip install --prefix=/install -r requirements.txt

# Clone Volatility3. Default `develop`; pin via --build-arg VOLATILITY3_REF=<tag> before T26 release.
ARG VOLATILITY3_REF=develop
RUN git clone --depth=1 --branch ${VOLATILITY3_REF} \
        https://github.com/volatilityfoundation/volatility3.git /opt/volatility3 \
    && pip install --prefix=/install /opt/volatility3

# ============================================================
# Stage 2 — runtime
# ============================================================
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    SIFTGUARD_ENV=docker

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash siftguard

# Copy installed Python packages + Volatility3 source tree
COPY --from=deps /install /usr/local
COPY --from=deps /opt/volatility3 /opt/volatility3

# Recreate the SIFT VM layout: /opt/volatility3/bin/vol — matches all hardcoded paths in src/
RUN mkdir -p /opt/volatility3/bin \
    && ln -sf "$(which vol)" /opt/volatility3/bin/vol

WORKDIR /app

COPY --chown=siftguard:siftguard pyproject.toml README.md ./
COPY --chown=siftguard:siftguard src/ ./src/
COPY --chown=siftguard:siftguard experiments/ ./experiments/

# Install siftguard itself; deps already present from stage 1
RUN pip install --no-cache-dir --no-deps -e .

# Evidence mount + writable cache/data dirs
RUN mkdir -p /cases /app/siftguard_cache /app/data \
    && chown -R siftguard:siftguard /cases /app

VOLUME ["/cases"]
EXPOSE 8080

USER siftguard

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8080/ >/dev/null || exit 1

CMD ["uvicorn", "siftguard.dashboard.app:app", "--host", "0.0.0.0", "--port", "8080"]
