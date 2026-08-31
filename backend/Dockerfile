# AutoScore backend — FastAPI + music21 + librosa audio stack.
#
# Note: this runs on Linux, so the Apple-Silicon accelerated paths are NOT
# available in-container:
#   * Stemdeck (CoreML) does not run — use demucs instead (build arg below)
#   * torch runs on CPU (TORCH_DEVICE=cpu)
# The librosa fallback for melody / rhythm / harmony works normally.
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg -> yt-dlp / audio decode ; libsndfile1 -> soundfile ; default-jre -> Audiveris (optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Optional CPU stem separation:  docker build --build-arg WITH_DEMUCS=1
ARG WITH_DEMUCS=0

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt \
    && if [ "$WITH_DEMUCS" = "1" ]; then pip install "demucs>=4.0"; fi

COPY backend/ ./

ENV APP_ENV=production \
    STORAGE_DIR=/data \
    TORCH_DEVICE=cpu \
    CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
