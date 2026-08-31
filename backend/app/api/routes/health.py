"""Health and engine-status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.jobs import EngineStatus, HealthResponse
from app.services import omr_engine, stem_splitter

router = APIRouter(tags=["health"])


def _engine_statuses(settings: Settings) -> list[EngineStatus]:
    available, engine, path = stem_splitter.engine_available(settings)
    stem_status = EngineStatus(
        name="stemdeck",
        configured=available,
        executable=path,
        version=stem_splitter.probe_version(settings),
        detail=None if available else "Set STEMDECK_BIN or STEM_FALLBACK=demucs",
    )

    omr_ok, omr_path = omr_engine.engine_available(settings)
    omr_status = EngineStatus(
        name="audiveris",
        configured=omr_ok,
        executable=omr_path,
        version=omr_engine.probe_version(settings),
        detail=None if omr_ok else "Set AUDIVERIS_BIN to the launcher path",
    )
    return [stem_status, omr_status]


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_env=settings.app_env,
        engines=_engine_statuses(settings),
    )
