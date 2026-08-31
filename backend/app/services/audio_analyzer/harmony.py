"""Key detection + chord-sequence estimation.

Backends, in preference order:
  1. essentia — KeyExtractor + beat-synchronous chord detection
  2. librosa  — beat-synchronous CQT chroma + Krumhansl key profile +
     per-beat chord-template matching, merged into chord spans
"""
from __future__ import annotations

from app.core.exceptions import AudioAnalysisError
from app.core.logging import get_logger

from . import theory
from .backends import harmony_backend
from .types import NO_CHORD, BeatGrid, ChordEvent

logger = get_logger(__name__)


def estimate_harmony(
    y_harmonic,
    sr: int,
    grid: BeatGrid,
    *,
    prefer_backends: bool = True,
    change_min_beats: int = 1,
) -> tuple[str, list[ChordEvent], str]:
    backend = harmony_backend(prefer_backends)

    if backend == "essentia":
        try:
            return _essentia_harmony(y_harmonic, sr, grid, change_min_beats)
        except Exception as exc:  # noqa: BLE001
            logger.warning("essentia harmony failed (%s); falling back to chroma", exc)
            backend = "chroma_template"

    if backend == "chroma_template":
        return _chroma_harmony(y_harmonic, sr, grid, change_min_beats)

    raise AudioAnalysisError("No harmony backend available (install librosa or essentia)")


# --------------------------------------------------------------------------- #
# essentia
# --------------------------------------------------------------------------- #
def _essentia_harmony(y, sr, grid, change_min_beats):  # pragma: no cover - heavy dep
    import essentia.standard as es
    import numpy as np

    audio = np.asarray(y, dtype=np.float32)
    key, scale, strength = es.KeyExtractor()(audio)
    key_name = f"{key} {scale}"

    hpcp_frames, times = [], []
    win, hop = 4096, 2048
    spectrum, spectral_peaks, hpcp = es.Spectrum(), es.SpectralPeaks(), es.HPCP()
    w = es.Windowing(type="blackmanharris62")
    for i, frame in enumerate(es.FrameGenerator(audio, frameSize=win, hopSize=hop)):
        freqs, mags = spectral_peaks(spectrum(w(frame)))
        hpcp_frames.append(hpcp(freqs, mags))
        times.append(i * hop / sr)
    chroma = np.asarray(hpcp_frames)
    chords = _chroma_to_chords(chroma, np.asarray(times), grid, change_min_beats)
    return key_name, chords, "essentia"


# --------------------------------------------------------------------------- #
# librosa chroma-template fallback
# --------------------------------------------------------------------------- #
def _chroma_harmony(y, sr, grid, change_min_beats):
    import librosa
    import numpy as np

    y = np.asarray(y, dtype=float)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=2048)
    frame_times = librosa.frames_to_time(
        np.arange(chroma.shape[1]), sr=sr, hop_length=2048
    )

    key_name, corr = theory.estimate_key(chroma.mean(axis=1))
    logger.info("librosa key: %s (r=%.2f)", key_name, corr)

    chords = _chroma_to_chords(chroma.T, frame_times, grid, change_min_beats)
    return key_name, chords, "chroma_template"


def _chroma_to_chords(chroma_ft, frame_times, grid: BeatGrid, change_min_beats: int):
    """chroma_ft: (frames, 12). Aggregate to beats, label, merge into spans."""
    beats = list(grid.beat_times)
    if len(beats) < 2:
        return []
    edges = beats + [beats[-1] + (beats[-1] - beats[-2])]

    beat_labels: list[tuple[int | None, str | None, float]] = []
    for i in range(len(beats)):
        lo, hi = edges[i], edges[i + 1]
        mask = (frame_times >= lo) & (frame_times < hi)
        if not mask.any():
            beat_labels.append((None, None, 0.0))
            continue
        vec = chroma_ft[mask].mean(axis=0)
        root, quality, score = theory.match_chord(vec)
        beat_labels.append((root, quality, score))

    # Merge consecutive beats with the same (root, quality).
    spans: list[ChordEvent] = []
    run_start = 0
    for i in range(1, len(beat_labels) + 1):
        same = (
            i < len(beat_labels)
            and beat_labels[i][:2] == beat_labels[run_start][:2]
        )
        if same:
            continue
        root, quality, score = beat_labels[run_start]
        start_t = beats[run_start]
        end_t = edges[i]
        if root is None or quality is None:
            symbol, root_pc, qual = NO_CHORD, None, None
        else:
            symbol, root_pc, qual = theory.chord_symbol(root, quality), root, quality
        spans.append(
            ChordEvent(
                start_sec=float(start_t),
                end_sec=float(end_t),
                symbol=symbol,
                root_pc=root_pc,
                quality=qual,
                confidence=float(max(score, 0.0)),
            )
        )
        run_start = i

    return _enforce_min_duration(spans, grid, change_min_beats)


def _enforce_min_duration(spans: list[ChordEvent], grid: BeatGrid, change_min_beats: int):
    if change_min_beats <= 1 or len(spans) < 2:
        return spans
    beat_sec = 60.0 / max(grid.bpm, 1e-6)
    min_sec = beat_sec * change_min_beats
    merged: list[ChordEvent] = [spans[0]]
    for cur in spans[1:]:
        prev = merged[-1]
        if cur.duration_sec < min_sec and cur.symbol != prev.symbol:
            # absorb the short chord into whichever neighbour is stronger
            prev.end_sec = cur.end_sec
        else:
            merged.append(cur)
    return merged
