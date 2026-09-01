# AutoScore — one image: FastAPI backend + the built React UI, one port (8000).
#
# Linux container, so the Apple-Silicon accelerated paths are unavailable:
#   * Stemdeck (CoreML) does not run — build with --build-arg WITH_DEMUCS=1 for
#     CPU demucs, or point STEMDECK_BIN at a reachable separator
#   * torch runs on CPU (TORCH_DEVICE=cpu)
# The librosa fallback for melody / rhythm / harmony works normally.

# ---- stage 1: build the web UI ------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # -> /web/dist  (calls the API at a relative /api path)

# ---- stage 2: backend + bundled UI -----------------------------------------
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg -> yt-dlp / audio decode ; libsndfile1 -> soundfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Optional CPU stem separation:  docker build --build-arg WITH_DEMUCS=1 .
ARG WITH_DEMUCS=0

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt \
    && if [ "$WITH_DEMUCS" = "1" ]; then pip install "demucs>=4.0"; fi

COPY backend/ ./
COPY --from=web /web/dist ./static

ENV APP_ENV=production \
    STORAGE_DIR=/data \
    STATIC_DIR=/app/static \
    TORCH_DEVICE=cpu

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
