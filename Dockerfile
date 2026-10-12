# =============================================================================
#  IDRM — application image
# =============================================================================
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# psycopg2 needs libpq; build-essential only in the builder stage
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------- dependencies ----------
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

# ---------- source ----------
COPY . .

# ---------- non-root user ----------
RUN useradd --create-home --uid 10001 idrm \
    && chown -R idrm:idrm /app
USER idrm

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["gunicorn", "-w", "4", "-k", "gthread", "--threads", "4", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "-b", "0.0.0.0:8000", "run:app"]
