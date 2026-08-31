"""Music-theory helpers: key profiles, chord templates, pitch-class naming.

Pure numpy + stdlib. No audio dependencies — trivially unit-testable.
"""
from __future__ import annotations

import numpy as np

PITCH_CLASS_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# Krumhansl-Kessler key profiles (major / minor), rotated per candidate tonic.
_KK_MAJOR = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_KK_MINOR = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

# quality -> semitone offsets from the root
CHORD_INTERVALS: dict[str, tuple[int, ...]] = {
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
    "dom7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "min7": (0, 3, 7, 10),
    "min7b5": (0, 3, 6, 10),
    "sus4": (0, 5, 7),
    "sus2": (0, 2, 7),
}

# quality -> chord-symbol suffix
_QUALITY_SUFFIX = {
    "maj": "",
    "min": "m",
    "dim": "dim",
    "aug": "aug",
    "dom7": "7",
    "maj7": "maj7",
    "min7": "m7",
    "min7b5": "m7b5",
    "sus4": "sus4",
    "sus2": "sus2",
}


def pc_name(pc: int) -> str:
    return PITCH_CLASS_NAMES[pc % 12]


def chord_symbol(root_pc: int, quality: str) -> str:
    return f"{pc_name(root_pc)}{_QUALITY_SUFFIX.get(quality, quality)}"


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def estimate_key(chroma_mean: np.ndarray) -> tuple[str, float]:
    """Return ("<Tonic> <mode>", correlation) for a 12-vector chroma average."""
    chroma_mean = np.asarray(chroma_mean, dtype=float).reshape(12)
    best_name, best_corr = "C major", -1.0
    for tonic in range(12):
        maj = _pearson(chroma_mean, np.roll(_KK_MAJOR, tonic))
        if maj > best_corr:
            best_name, best_corr = f"{pc_name(tonic)} major", maj
        minr = _pearson(chroma_mean, np.roll(_KK_MINOR, tonic))
        if minr > best_corr:
            best_name, best_corr = f"{pc_name(tonic)} minor", minr
    return best_name, best_corr


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else v


def _chord_templates() -> list[tuple[int, str, np.ndarray]]:
    """(root_pc, quality, L2-normalised 12-vector) for every root x quality."""
    templates: list[tuple[int, str, np.ndarray]] = []
    for quality, intervals in CHORD_INTERVALS.items():
        base = np.zeros(12)
        for iv in intervals:
            base[iv % 12] = 1.0
        base = _unit(base)
        for root in range(12):
            templates.append((root, quality, np.roll(base, root)))
    return templates


_TEMPLATES = _chord_templates()

# Prefer triads over 7ths on a near-tie so noisy chroma doesn't over-label.
_QUALITY_BIAS = {
    "maj": 0.02, "min": 0.02, "dim": 0.0, "aug": -0.02,
    "dom7": 0.0, "maj7": 0.0, "min7": 0.0, "min7b5": -0.01,
    "sus4": -0.02, "sus2": -0.02,
}


def match_chord(
    chroma_vec: np.ndarray, *, min_energy: float = 1e-3, min_score: float = 0.5
) -> tuple[int | None, str | None, float]:
    """Best (root_pc, quality, cosine_score) for a 12-vector chroma frame.

    Returns (None, None, 0.0) when the frame has no tonal energy or no template
    clears ``min_score`` (treated as "no chord").
    """
    v = np.asarray(chroma_vec, dtype=float).reshape(12)
    if v.sum() <= min_energy:
        return None, None, 0.0
    v = _unit(np.clip(v, 0.0, None))
    best = (None, None, -1.0)
    for root, quality, tpl in _TEMPLATES:
        score = float(np.dot(v, tpl)) + _QUALITY_BIAS.get(quality, 0.0)
        if score > best[2]:
            best = (root, quality, score)
    if best[2] < min_score:
        return None, None, 0.0
    return best  # type: ignore[return-value]


def hz_to_midi(freq: np.ndarray) -> np.ndarray:
    freq = np.asarray(freq, dtype=float)
    out = np.full(freq.shape, np.nan)
    pos = freq > 0
    out[pos] = 69.0 + 12.0 * np.log2(freq[pos] / 440.0)
    return out
