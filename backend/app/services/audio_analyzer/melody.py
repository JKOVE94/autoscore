"""Melody note extraction from the vocal stem.

Backends, in preference order:
  1. basic-pitch — Spotify's polyphonic note transcription (note_events)
  2. librosa.pyin — monophonic f0 tracking, segmented into notes
"""
from __future__ import annotations

from app.core.exceptions import AudioAnalysisError
from app.core.logging import get_logger

from .backends import melody_backend
from .types import NoteEvent

logger = get_logger(__name__)


def extract_melody(
    y_vocal,
    sr: int,
    *,
    fmin_hz: float = 65.41,
    fmax_hz: float = 1046.5,
    min_note_sec: float = 0.08,
    prefer_backends: bool = True,
) -> tuple[list[NoteEvent], str]:
    backend = melody_backend(prefer_backends)

    if backend == "basic_pitch":
        try:
            return _basic_pitch_melody(y_vocal, sr, min_note_sec), "basic_pitch"
        except Exception as exc:  # noqa: BLE001
            logger.warning("basic-pitch failed (%s); falling back to pyin", exc)
            backend = "librosa_pyin"

    if backend == "librosa_pyin":
        return _pyin_melody(y_vocal, sr, fmin_hz, fmax_hz, min_note_sec), "librosa_pyin"

    raise AudioAnalysisError("No melody backend available (install librosa or basic-pitch)")


# --------------------------------------------------------------------------- #
def _basic_pitch_melody(y, sr, min_note_sec):  # pragma: no cover - heavy dep
    import numpy as np
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict

    # basic-pitch resamples internally; it wants a file or an array + sr.
    _, _, note_events = predict(np.asarray(y, dtype=np.float32), sr, ICASSP_2022_MODEL_PATH)
    notes: list[NoteEvent] = []
    for start, end, pitch, amplitude, *_ in note_events:
        if end - start < min_note_sec:
            continue
        notes.append(
            NoteEvent(
                start_sec=float(start),
                end_sec=float(end),
                midi=int(pitch),
                velocity=float(min(max(amplitude, 0.1), 1.0)),
                confidence=float(min(max(amplitude, 0.0), 1.0)),
            )
        )
    notes.sort(key=lambda n: n.start_sec)
    return notes


# --------------------------------------------------------------------------- #
def _pyin_melody(y, sr, fmin_hz, fmax_hz, min_note_sec):
    import librosa
    import numpy as np

    y = np.asarray(y, dtype=float)
    hop = 256
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y, fmin=fmin_hz, fmax=fmax_hz, sr=sr, hop_length=hop, fill_na=np.nan
    )
    times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop)

    midi = np.full(len(f0), np.nan)
    ok = voiced_flag & np.isfinite(f0)
    midi[ok] = np.round(librosa.hz_to_midi(f0[ok]))
    midi = _median_filter(midi, 5)

    frame_dt = hop / sr
    notes: list[NoteEvent] = []
    run_pitch: float | None = None
    run_start = 0.0
    run_conf: list[float] = []

    def flush(end_t: float):
        nonlocal run_pitch, run_conf
        if run_pitch is not None and end_t - run_start >= min_note_sec:
            notes.append(
                NoteEvent(
                    start_sec=float(run_start),
                    end_sec=float(end_t),
                    midi=int(run_pitch),
                    velocity=0.8,
                    confidence=float(np.mean(run_conf) if run_conf else 0.5),
                )
            )
        run_pitch = None
        run_conf = []

    for i, t in enumerate(times):
        p = midi[i]
        if not np.isfinite(p):
            flush(t)
            continue
        if run_pitch is None:
            run_pitch, run_start = p, t
            run_conf = [float(voiced_prob[i])]
        elif p == run_pitch:
            run_conf.append(float(voiced_prob[i]))
        else:
            flush(t)
            run_pitch, run_start = p, t
            run_conf = [float(voiced_prob[i])]
    flush(times[-1] + frame_dt if len(times) else 0.0)

    return _merge_adjacent(notes, max_gap_sec=frame_dt * 2)


def _median_filter(arr, k: int):
    import numpy as np

    if k <= 1 or len(arr) < k:
        return arr
    pad = k // 2
    padded = np.pad(arr, pad, mode="edge")
    out = arr.copy()
    for i in range(len(arr)):
        window = padded[i : i + k]
        finite = window[np.isfinite(window)]
        out[i] = np.median(finite) if finite.size else np.nan
    return out


def _merge_adjacent(notes: list[NoteEvent], max_gap_sec: float) -> list[NoteEvent]:
    if not notes:
        return notes
    merged = [notes[0]]
    for nxt in notes[1:]:
        cur = merged[-1]
        if nxt.midi == cur.midi and nxt.start_sec - cur.end_sec <= max_gap_sec:
            cur.end_sec = nxt.end_sec
            cur.confidence = (cur.confidence + nxt.confidence) / 2
        else:
            merged.append(nxt)
    return merged
