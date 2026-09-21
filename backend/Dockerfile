# PolicyGuard AI backend - multi-stage, Python 3.12, non-root (Plan D1)
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY backend/requirements.txt ./requirements.txt
RUN pip install --prefix=/install -r requirements.txt

FROM python:3.12-slim

# Tesseract for OCR of scanned tender/bidder documents
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STORAGE_PATH=/data/storage

WORKDIR /app

COPY --from=builder /install /usr/local
COPY backend/app ./app

# Non-root runtime user; /data is the only writable volume
RUN useradd --system --create-home --uid 10001 policyguard \
    && mkdir -p /data/storage \
    && chown -R policyguard:policyguard /data /app

USER policyguard

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
