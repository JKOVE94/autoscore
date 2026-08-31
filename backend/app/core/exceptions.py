"""Domain-specific exceptions and FastAPI handlers."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AutoScoreError(Exception):
    """Base class for all recoverable pipeline errors."""

    status_code: int = 400
    code: str = "autoscore_error"

    def __init__(self, message: str, *, detail: object | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class UnsupportedMediaError(AutoScoreError):
    status_code = 415
    code = "unsupported_media"


class UploadTooLargeError(AutoScoreError):
    status_code = 413
    code = "upload_too_large"


class EngineNotConfiguredError(AutoScoreError):
    status_code = 503
    code = "engine_not_configured"


class StemSeparationError(AutoScoreError):
    status_code = 502
    code = "stem_separation_failed"


class OMRProcessingError(AutoScoreError):
    status_code = 502
    code = "omr_failed"


class ScoreValidationError(AutoScoreError):
    status_code = 422
    code = "score_validation_failed"


class AudioDecodeError(AutoScoreError):
    status_code = 415
    code = "audio_decode_failed"


class AudioAnalysisError(AutoScoreError):
    status_code = 502
    code = "audio_analysis_failed"


class YouTubeError(AutoScoreError):
    status_code = 502
    code = "youtube_fetch_failed"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AutoScoreError)
    async def _handle(_: Request, exc: AutoScoreError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "detail": exc.detail}},
        )
