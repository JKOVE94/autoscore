"""Optional-dependency capability probing for the analysis stages."""
from __future__ import annotations

import importlib.util
from functools import lru_cache


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


@lru_cache
def probe() -> dict[str, bool]:
    """Which optional backends are importable in this environment."""
    return {
        "numpy": _has("numpy"),
        "librosa": _has("librosa"),
        "soundfile": _has("soundfile"),
        "basic_pitch": _has("basic_pitch"),
        "essentia": _has("essentia"),
        "madmom": _has("madmom"),
    }


def melody_backend(prefer: bool = True) -> str:
    caps = probe()
    if prefer and caps["basic_pitch"]:
        return "basic_pitch"
    if caps["librosa"]:
        return "librosa_pyin"
    return "none"


def rhythm_backend(prefer: bool = True) -> str:
    caps = probe()
    if prefer and caps["madmom"]:
        return "madmom"
    if caps["librosa"]:
        return "librosa_beat"
    return "none"


def harmony_backend(prefer: bool = True) -> str:
    caps = probe()
    if prefer and caps["essentia"]:
        return "essentia"
    if caps["librosa"]:
        return "chroma_template"
    return "none"


def status() -> dict[str, object]:
    return {
        "capabilities": probe(),
        "selected": {
            "melody": melody_backend(),
            "rhythm": rhythm_backend(),
            "harmony": harmony_backend(),
        },
    }
