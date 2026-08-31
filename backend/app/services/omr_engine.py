"""Audiveris OMR integration wrapper (input mode 3).

Invokes the Audiveris batch CLI (Java) as a subprocess to convert a sheet-music
image/PDF into MusicXML (``.mxl``), then loads and validates the result with
``music21``.
"""
from __future__ import annotations

import shutil
import subprocess
import time
import zipfile
from pathlib import Path

from app.config import Settings, get_settings
from app.core.exceptions import EngineNotConfiguredError, OMRProcessingError, ScoreValidationError
from app.core.logging import get_logger
from app.schemas.jobs import OMRResult

logger = get_logger(__name__)

_MXL_EXTS = (".mxl", ".musicxml", ".xml")


def _resolve_bin(name: str) -> str | None:
    if not name:
        return None
    p = Path(name)
    if p.is_file():
        return str(p)
    return shutil.which(name)


def engine_available(settings: Settings | None = None) -> tuple[bool, str | None]:
    settings = settings or get_settings()
    return (_resolve_bin(settings.audiveris_bin) is not None, _resolve_bin(settings.audiveris_bin))


def probe_version(settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()
    exe = _resolve_bin(settings.audiveris_bin)
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-help"], capture_output=True, text=True, timeout=30
        )
        blob = (out.stdout or "") + (out.stderr or "")
        for line in blob.splitlines():
            if "audiveris" in line.lower() and any(c.isdigit() for c in line):
                return line.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def _run_audiveris(exe: str, src: Path, out_dir: Path, timeout: int) -> None:
    cmd = [
        exe, "-batch", "-export",
        "-output", str(out_dir),
        str(src),
    ]
    logger.info("audiveris: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise OMRProcessingError("Audiveris timed out", detail={"timeout_sec": timeout}) from exc
    except OSError as exc:
        raise OMRProcessingError(f"Failed to launch Audiveris: {exc}") from exc
    if proc.returncode != 0:
        raise OMRProcessingError(
            "Audiveris exited with an error",
            detail={"returncode": proc.returncode, "stderr": proc.stderr[-2000:]},
        )


def _find_export(out_dir: Path) -> Path:
    candidates = [
        p for p in sorted(out_dir.rglob("*"))
        if p.is_file() and p.suffix.lower() in _MXL_EXTS
    ]
    if not candidates:
        raise OMRProcessingError(
            "Audiveris produced no MusicXML export", detail={"output_dir": str(out_dir)}
        )
    # Prefer compressed .mxl, then largest file.
    mxl = [p for p in candidates if p.suffix.lower() == ".mxl"]
    pool = mxl or candidates
    return max(pool, key=lambda p: p.stat().st_size)


def _unpack_if_mxl(path: Path) -> Path:
    if path.suffix.lower() != ".mxl":
        return path
    try:
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if n.endswith((".xml", ".musicxml"))]
            inner = next((n for n in names if not n.startswith("META-INF")), None)
            if inner is None:
                return path
            target = path.with_suffix(".musicxml")
            with zf.open(inner) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            return target
    except (zipfile.BadZipFile, OSError) as exc:
        raise OMRProcessingError(f"Could not read .mxl archive: {exc}") from exc


def validate_musicxml(path: Path) -> tuple[int, int, list[str]]:
    """Load with music21 and return (measure_count, part_count, warnings)."""
    try:
        from music21 import converter, stream  # imported lazily; heavy dependency
    except ImportError as exc:  # pragma: no cover
        raise ScoreValidationError("music21 is not installed") from exc

    try:
        score = converter.parse(str(path))
    except Exception as exc:  # music21 raises many subclasses
        raise ScoreValidationError(
            f"music21 failed to parse the score: {exc}", detail={"path": str(path)}
        ) from exc

    parts = list(score.parts) if hasattr(score, "parts") else []
    part_count = len(parts) or (1 if isinstance(score, stream.Stream) else 0)
    measures = parts[0].getElementsByClass("Measure") if parts else []
    measure_count = len(list(measures))

    warnings: list[str] = []
    if measure_count == 0:
        warnings.append("No measures detected in the first part.")
    if part_count == 0:
        warnings.append("No parts detected.")
    ts = score.recurse().getElementsByClass("TimeSignature")
    if not list(ts):
        warnings.append("No time signature found; downstream quantization may guess 4/4.")
    return measure_count, part_count, warnings


def run_omr(
    source: Path,
    job_id: str,
    *,
    settings: Settings | None = None,
    timeout: int | None = None,
) -> OMRResult:
    settings = settings or get_settings()
    source = Path(source)
    if not source.is_file():
        raise OMRProcessingError(f"Source image not found: {source}")

    exe = _resolve_bin(settings.audiveris_bin)
    if not exe:
        raise EngineNotConfiguredError(
            "Audiveris is not configured. Set AUDIVERIS_BIN to the launcher path.",
            detail={"audiveris_bin": settings.audiveris_bin},
        )

    out_dir = settings.outputs_path / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    _run_audiveris(exe, source, out_dir, timeout or settings.omr_timeout)
    export = _unpack_if_mxl(_find_export(out_dir))
    measure_count, part_count, warnings = validate_musicxml(export)
    elapsed = time.perf_counter() - started

    logger.info(
        "omr ok job=%s measures=%d parts=%d elapsed=%.1fs",
        job_id, measure_count, part_count, elapsed,
    )
    return OMRResult(
        job_id=job_id,
        source=str(source),
        musicxml_path=str(export),
        measure_count=measure_count,
        part_count=part_count,
        warnings=warnings,
        elapsed_sec=round(elapsed, 2),
    )
