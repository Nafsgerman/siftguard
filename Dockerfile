# ── Stage 1: deps ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS deps
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[dev]"

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# System deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Volatility3 at the path SIFTGuard expects
RUN pip install --no-cache-dir volatility3 \
    && mkdir -p /opt/volatility3/bin \
    && printf '#!/bin/sh\nexec python3 -m volatility3 "$@"\n' \
       > /opt/volatility3/bin/vol \
    && chmod +x /opt/volatility3/bin/vol

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=deps /usr/local/bin/siftguard* /usr/local/bin/
COPY --from=deps /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy source
COPY --from=deps /build/src /app/src

# Non-root user
RUN useradd -m -u 1000 siftguard \
    && chown -R siftguard:siftguard /app

WORKDIR /app

# Mount point for evidence (never baked in)
VOLUME ["/cases"]

EXPOSE 8080

HEALTHCHECK --interval=5s --timeout=3s --start-period=15s --retries=6 \
    CMD curl -f http://localhost:8080/ || exit 1

USER siftguard

ENV PYTHONPATH=/app/src

CMD ["uvicorn", "siftguard.dashboard.app:app", \
     "--host", "0.0.0.0", "--port", "8080"]
