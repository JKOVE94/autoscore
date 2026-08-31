"""Synthetic multi-stem audio generator for analysis tests.

Renders a deterministic 8-bar, 120 BPM, 4/4 progression (C - Am - F - G) with a
stepwise vocal melody, and writes vocal/bass/drums/other WAV stems to a dir.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 22050
BPM = 120.0
BEATS_PER_BAR = 4
N_BARS = 8

_CHORDS_MIDI = {
    "C": (60, 64, 67),
    "Am": (57, 60, 64),
    "F": (53, 57, 60),
    "G": (55, 59, 62),
}
_PROGRESSION = ["C", "Am", "F", "G", "C", "Am", "F", "G"]
_MELODY_MIDI = [72, 74, 76, 77]  # one per beat, repeating


def _midi_to_hz(m: float) -> float:
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def _tone(freq: float, dur: float, *, amp: float = 0.2, sr: int = SR) -> np.ndarray:
    t = np.linspace(0.0, dur, int(sr * dur), endpoint=False)
    env = np.minimum(1.0, np.minimum(t / 0.01, (dur - t) / 0.05))
    return (amp * env * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _click(dur: float, *, amp: float, sr: int = SR) -> np.ndarray:
    n = int(sr * dur)
    noise = np.random.default_rng(0).standard_normal(n).astype(np.float32)
    env = np.exp(-np.linspace(0, 12, n)).astype(np.float32)
    return amp * noise * env


def render_stems(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    beat = 60.0 / BPM
    bar = beat * BEATS_PER_BAR
    total = bar * N_BARS
    n_total = int(SR * total)

    vocal = np.zeros(n_total, dtype=np.float32)
    bass = np.zeros(n_total, dtype=np.float32)
    other = np.zeros(n_total, dtype=np.float32)
    drums = np.zeros(n_total, dtype=np.float32)

    def place(buf: np.ndarray, sig: np.ndarray, start_sec: float) -> None:
        a = int(SR * start_sec)
        b = min(len(buf), a + len(sig))
        buf[a:b] += sig[: b - a]

    for bar_i in range(N_BARS):
        chord = _PROGRESSION[bar_i % len(_PROGRESSION)]
        bar_start = bar_i * bar

        # sustained chord pad for the whole bar
        for m in _CHORDS_MIDI[chord]:
            place(other, _tone(_midi_to_hz(m), bar, amp=0.12), bar_start)
        # bass on the root, one octave down, per beat
        root = _CHORDS_MIDI[chord][0] - 12
        for b in range(BEATS_PER_BAR):
            place(bass, _tone(_midi_to_hz(root), beat * 0.9, amp=0.25), bar_start + b * beat)
            place(
                drums,
                _click(0.12, amp=0.5 if b == 0 else 0.25),
                bar_start + b * beat,
            )
            mel = _MELODY_MIDI[b % len(_MELODY_MIDI)]
            place(vocal, _tone(_midi_to_hz(mel), beat * 0.85, amp=0.3), bar_start + b * beat)

    paths: dict[str, Path] = {}
    for name, buf in ("vocal", vocal), ("bass", bass), ("drums", drums), ("other", other):
        p = out_dir / f"{name}.wav"
        sf.write(str(p), np.clip(buf, -1.0, 1.0), SR)
        paths[name] = p
    return paths
