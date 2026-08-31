"""Step 2 endpoint: run melody + rhythm + harmony analysis over a job's stems."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core.exceptions import AudioAnalysisError
from app.schemas.jobs import AnalysisResponse
from app.services.audio_analyzer import analyze as run_analysis
from app.services.audio_analyzer import backend_status, discover_stems

router = APIRouter(prefix="/api", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    window: tuple[float, float] | None = None


@router.get("/analyze/backends")
def analyze_backends() -> dict:
    return backend_status()


@router.post("/analyze/{job_id}", response_model=AnalysisResponse)
def analyze_job(
    job_id: str,
    body: AnalyzeRequest | None = None,
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    stems = discover_stems(job_id, settings)
    if not stems:
        raise AudioAnalysisError(
            f"No stems found for job {job_id}. Run /api/separate first, "
            "or upload pre-split stems.",
            detail={
                "looked_in": [
                    str(settings.stems_path / job_id),
                    str(settings.uploads_path / job_id),
                ]
            },
        )

    window = body.window if body else None
    result = run_analysis(stems, settings=settings, window=window)

    out_dir = settings.outputs_path / Path(job_id).name
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "analysis.json"
    result_path.write_text(json.dumps(dataclasses.asdict(result), indent=2), encoding="utf-8")

    return AnalysisResponse(
        job_id=job_id,
        duration_sec=result.duration_sec,
        bpm=result.bpm,
        key=result.key,
        time_signature=result.time_signature,
        beat_times=result.beat_times,
        downbeat_times=result.downbeat_times,
        notes=[dataclasses.asdict(n) for n in result.notes],
        chords=[dataclasses.asdict(c) for c in result.chords],
        backends=result.backends,
        window_offset_sec=result.window_offset_sec,
        result_path=str(result_path),
    )
