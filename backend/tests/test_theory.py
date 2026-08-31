from __future__ import annotations

import numpy as np
import pytest

from app.services.audio_analyzer import theory


def test_pc_name_and_chord_symbol():
    assert theory.pc_name(0) == "C"
    assert theory.pc_name(13) == "C#"
    assert theory.chord_symbol(0, "maj") == "C"
    assert theory.chord_symbol(9, "min") == "Am"
    assert theory.chord_symbol(7, "dom7") == "G7"
    assert theory.chord_symbol(5, "maj7") == "Fmaj7"


def test_hz_to_midi():
    out = theory.hz_to_midi(np.array([440.0, 0.0, 880.0]))
    assert out[0] == pytest.approx(69.0)
    assert np.isnan(out[1])
    assert out[2] == pytest.approx(81.0)


@pytest.mark.parametrize(
    "tonic,mode",
    [(0, "major"), (7, "major"), (9, "minor"), (2, "minor")],
)
def test_estimate_key_recovers_ideal_profile(tonic, mode):
    profile = theory._KK_MAJOR if mode == "major" else theory._KK_MINOR
    chroma = np.roll(profile, tonic)
    name, corr = theory.estimate_key(chroma)
    assert name == f"{theory.pc_name(tonic)} {mode}"
    assert corr > 0.9


@pytest.mark.parametrize(
    "intervals,root,quality",
    [
        ((0, 4, 7), 0, "maj"),
        ((0, 3, 7), 9, "min"),
        ((0, 4, 7, 10), 7, "dom7"),
        ((0, 3, 7, 10), 2, "min7"),
    ],
)
def test_match_chord_identifies_clean_templates(intervals, root, quality):
    vec = np.zeros(12)
    for iv in intervals:
        vec[(root + iv) % 12] = 1.0
    got_root, got_quality, score = theory.match_chord(vec)
    assert got_root == root
    assert got_quality == quality
    assert score > 0


def test_match_chord_returns_none_for_silence():
    root, quality, score = theory.match_chord(np.zeros(12))
    assert (root, quality, score) == (None, None, 0.0)
