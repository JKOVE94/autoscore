"""Tempo / beat / downbeat estimation.

Backends, in preference order:
  1. madmom  — RNN downbeat tracking (beats + downbeats + meter)
  2. librosa — beat_track for tempo+beats, then phase-search downbeats using the
     drums onset envelope (or the harmonic mix when no drums stem is available)
"""
from __future__ import annotations

from app.core.exceptions import AudioAnalysisError
from app.core.logging import get_logger

from .backends import rhythm_backend
from .types import BeatGrid

logger = get_logger(__name__)

_METER_CANDIDATES = (4, 3)


def estimate_rhythm(
    y_harmonic,
    sr: int,
    *,
    y_drums=None,
    prefer_backends: bool = True,
    beats_per_bar: int = 4,
    beat_unit: int = 4,
) -> tuple[BeatGrid, str]:
    """Estimate tempo, beats and downbeats.

    madmom (when installed) detects the meter itself; the librosa fallback trusts
    the ``beats_per_bar`` hint and only searches for the downbeat phase, since
    beat-synchronous meter guessing from a single onset envelope is unreliable.
    """
    backend = rhythm_backend(prefer_backends)
    if backend == "madmom":
        try:
            return _madmom_rhythm(y_drums if y_drums is not None else y_harmonic, sr, beat_unit)
        except Exception as exc:  # noqa: BLE001 - degrade to librosa
            logger.warning("madmom rhythm failed (%s); falling back to librosa", exc)
            backend = "librosa_beat"

    if backend == "librosa_beat":
        return _librosa_rhythm(y_harmonic, sr, y_drums, beats_per_bar, beat_unit)

    raise AudioAnalysisError("No rhythm backend available (install librosa or madmom)")


def _madmom_rhythm(y, sr: int, beat_unit: int) -> tuple[BeatGrid, str]:  # pragma: no cover
    import numpy as np
    from madmom.features.downbeats import (
        DBNDownBeatTrackingProcessor,
        RNNDownBeatProcessor,
    )

    act = RNNDownBeatProcessor()(_as_madmom_signal(y, sr))
    proc = DBNDownBeatTrackingProcessor(beats_per_bar=list(_METER_CANDIDATES), fps=100)
    tracked = proc(act)  # (N, 2): [time, beat_position_in_bar]
    if tracked.size == 0:
        raise AudioAnalysisError("madmom returned no beats")

    beat_times = tracked[:, 0].astype(float).tolist()
    downbeat_times = tracked[tracked[:, 1] == 1][:, 0].astype(float).tolist()
    beats_per_bar = int(round(np.median(np.diff(
        np.r_[0, np.where(tracked[:, 1] == 1)[0], len(tracked)]
    )))) or 4
    bpm = _bpm_from_beats(beat_times)
    return (
        BeatGrid(bpm, beat_times, downbeat_times, beats_per_bar=beats_per_bar, beat_unit=beat_unit),
        "madmom",
    )


def _as_madmom_signal(y, sr):  # pragma: no cover - heavy dep
    from madmom.audio.signal import Signal

    return Signal(y, sample_rate=sr, num_channels=1)


def _librosa_rhythm(
    y_harmonic, sr: int, y_drums, beats_per_bar: int, beat_unit: int
) -> tuple[BeatGrid, str]:
    import librosa
    import numpy as np

    onset_src = y_drums if y_drums is not None and getattr(y_drums, "size", 0) else y_harmonic
    onset_env = librosa.onset.onset_strength(y=np.asarray(onset_src, dtype=float), sr=sr)

    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sr, trim=False, units="frames"
    )
    bpm = float(np.atleast_1d(tempo)[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).astype(float).tolist()
    if len(beat_times) < 2:
        # Degenerate signal: synthesise a grid from the tempo estimate.
        duration = len(y_harmonic) / sr
        step = 60.0 / max(bpm, 1e-6)
        beat_times = list(np.arange(0.0, max(duration, step), step))
        beat_frames = librosa.time_to_frames(np.asarray(beat_times), sr=sr)

    phase = _search_downbeat_phase(onset_env, beat_frames, beats_per_bar)
    downbeat_times = beat_times[phase::beats_per_bar]
    logger.info(
        "librosa rhythm: bpm=%.1f beats=%d meter=%d/%d phase=%d",
        bpm, len(beat_times), beats_per_bar, beat_unit, phase,
    )
    return (
        BeatGrid(bpm, beat_times, downbeat_times, beats_per_bar=beats_per_bar, beat_unit=beat_unit),
        "librosa_beat",
    )


def _search_downbeat_phase(onset_env, beat_frames, beats_per_bar: int) -> int:
    """Phase (0..beats_per_bar-1) that maximises onset energy on the downbeats."""
    import numpy as np

    if len(beat_frames) < beats_per_bar + 1:
        return 0
    strengths = np.asarray(
        [onset_env[min(int(f), len(onset_env) - 1)] for f in beat_frames], dtype=float
    )
    strengths = strengths / (strengths.max() or 1.0)

    best_phase, best_contrast = 0, -np.inf
    for phase in range(beats_per_bar):
        downs = strengths[phase::beats_per_bar]
        mask = np.ones(len(strengths), dtype=bool)
        mask[phase::beats_per_bar] = False
        others = strengths[mask]
        if downs.size == 0 or others.size == 0:
            continue
        contrast = downs.mean() - others.mean()
        if contrast > best_contrast:
            best_phase, best_contrast = phase, contrast
    return best_phase


def _bpm_from_beats(beat_times: list[float]) -> float:
    import numpy as np

    if len(beat_times) < 2:
        return 120.0
    diffs = np.diff(np.asarray(beat_times, dtype=float))
    med = float(np.median(diffs))
    return 60.0 / med if med > 0 else 120.0
