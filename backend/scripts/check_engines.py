"""Standalone engine-connectivity check.

Usage:
    cd backend && python -m scripts.check_engines
"""
from __future__ import annotations

import sys

from app.config import get_settings
from app.services import omr_engine, stem_splitter


def main() -> int:
    settings = get_settings()
    print(f"app_env         : {settings.app_env}")
    print(f"storage_path    : {settings.storage_path}")
    print(f"torch_device    : {settings.torch_device}")
    print("-" * 60)

    ok = True

    available, engine, path = stem_splitter.engine_available(settings)
    print(f"[stemdeck] configured : {available}")
    print(f"[stemdeck] resolved   : {engine} -> {path}")
    print(f"[stemdeck] version    : {stem_splitter.probe_version(settings)}")
    if not available:
        ok = False
        print("  ! set STEMDECK_BIN, or STEM_FALLBACK=demucs with demucs installed")
    print("-" * 60)

    omr_ok, omr_path = omr_engine.engine_available(settings)
    print(f"[audiveris] configured : {omr_ok}")
    print(f"[audiveris] resolved   : {omr_path}")
    print(f"[audiveris] version    : {omr_engine.probe_version(settings)}")
    if not omr_ok:
        ok = False
        print("  ! set AUDIVERIS_BIN to the Audiveris launcher path")
    print("-" * 60)

    try:
        import music21  # noqa: F401

        print("[music21]  import      : ok")
    except ImportError:
        ok = False
        print("[music21]  import      : MISSING (pip install -r requirements.txt)")

    print("=" * 60)
    print("RESULT:", "ALL ENGINES READY" if ok else "SOME ENGINES NOT CONFIGURED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
