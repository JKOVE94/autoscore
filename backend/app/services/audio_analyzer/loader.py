"""Audio loading / mixing helpers (numpy + soundfile/librosa, imported lazily)."""
from __future__ import annotations

from pathlib import Path

from app.core.exceptions import AudioAnalysisError, AudioDecodeError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _import_np():
    try:
        import numpy as np  # noqa: PLC0415

        return np
    except ImportError as exc:  # pragma: no cover
        raise AudioAnalysisError(
            "numpy is required for audio analysis (pip install -r requirements.txt)"
        ) from exc


def load_audio(path: Path, target_sr: int, *, mono: bool = True):
    """Load ``path`` as a float32 mono signal resampled to ``target_sr``.

    Returns (samples: np.ndarray, sr: int).
    """
    np = _import_np()
    path = Path(path)
    if not path.is_file():
        raise AudioDecodeError(f"Audio file not found: {path}")

    # Prefer soundfile (fast, no ffmpeg) then fall back to librosa/audioread.
    y = None
    sr = None
    try:
        import soundfile as sf  # noqa: PLC0415

        y, sr = sf.read(str(path), dtype="float32", always_2d=False)
    except Exception as sf_exc:  # noqa: BLE001 - broad on purpose, we fall back
        logger.debug("soundfile failed for %s (%s); trying librosa", path.name, sf_exc)
        try:
            import librosa  # noqa: PLC0415

            y, sr = librosa.load(str(path), sr=None, mono=False)
        except Exception as lb_exc:  # noqa: BLE001
            raise AudioDecodeError(
                f"Could not decode audio: {path.name}",
                detail={"soundfile_error": str(sf_exc), "librosa_error": str(lb_exc)},
            ) from lb_exc

    y = np.asarray(y, dtype=np.float32)
    if y.ndim == 2:
        # soundfile gives (frames, channels); librosa gives (channels, frames)
        axis = 1 if y.shape[0] <= 8 else 0
        y = y.mean(axis=axis) if mono else y
    if y.size == 0:
        raise AudioDecodeError(f"Audio file is empty: {path.name}")

    if sr != target_sr:
        try:
            import librosa  # noqa: PLC0415

            y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
        except ImportError as exc:  # pragma: no cover
            raise AudioAnalysisError("librosa is required to resample audio") from exc
        sr = target_sr

    return np.ascontiguousarray(y, dtype=np.float32), int(sr)


def mix(*signals):
    """Sum-and-normalise a set of equal-length mono signals."""
    np = _import_np()
    sigs = [s for s in signals if s is not None and getattr(s, "size", 0) > 0]
    if not sigs:
        raise AudioAnalysisError("mix() received no usable signals")
    n = min(len(s) for s in sigs)
    stacked = np.stack([np.asarray(s[:n], dtype=np.float32) for s in sigs], axis=0)
    out = stacked.sum(axis=0)
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak).astype(np.float32)


def slice_signal(y, sr: int, window: tuple[float, float] | None):
    """Return (sliced, offset_sec). ``window`` is (start_sec, end_sec)."""
    if window is None:
        return y, 0.0
    start, end = window
    a = max(0, int(round(start * sr)))
    b = min(len(y), int(round(end * sr)))
    if b <= a:
        raise AudioAnalysisError(f"Empty analysis window: {window}")
    return y[a:b], a / sr
