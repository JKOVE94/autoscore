"""Write a set of demo stem WAVs you can drop into the frontend (mode 2).

Usage:
    cd backend && python -m scripts.make_demo_stems [out_dir]

Produces vocal/bass/drums/other .wav for an 8-bar C-Am-F-G loop at 120 BPM.
"""
from __future__ import annotations

import sys
from pathlib import Path

# reuse the deterministic renderer used by the test-suite
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.synth import render_stems  # noqa: E402


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("storage") / "demo_stems"
    paths = render_stems(out)
    print(f"wrote {len(paths)} stems to {out.resolve()}:")
    for name, p in paths.items():
        print(f"  {name:6s} {p}")
    print("\nDrop these into the frontend '② 분리 Stem' tab.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
