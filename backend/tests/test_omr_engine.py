from __future__ import annotations

import subprocess
import zipfile

import pytest

from app.core.exceptions import EngineNotConfiguredError, OMRProcessingError
from app.services import omr_engine

MINIMAL_MUSICXML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN"
 "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
    </measure>
    <measure number="2">
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
    </measure>
  </part>
</score-partwise>
"""


def test_run_omr_raises_when_engine_missing(tmp_settings, tmp_path):
    img = tmp_path / "score.png"
    img.write_bytes(b"\x89PNG\r\n")
    with pytest.raises(EngineNotConfiguredError):
        omr_engine.run_omr(img, "job1", settings=tmp_settings)


def test_run_omr_no_export_raises(tmp_settings, tmp_path, monkeypatch):
    fake_bin = tmp_path / "audiveris"
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    tmp_settings.audiveris_bin = str(fake_bin)

    monkeypatch.setattr(
        omr_engine.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "", ""),
    )
    img = tmp_path / "score.png"
    img.write_bytes(b"\x89PNG\r\n")
    with pytest.raises(OMRProcessingError):
        omr_engine.run_omr(img, "job1", settings=tmp_settings)


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("music21") is None,
    reason="music21 not installed",
)
def test_run_omr_happy_path_with_fake_cli(tmp_settings, tmp_path, monkeypatch):
    fake_bin = tmp_path / "audiveris"
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    tmp_settings.audiveris_bin = str(fake_bin)

    def fake_run(cmd, capture_output, text, timeout):
        out_dir = tmp_settings.outputs_path / "jobM"
        out_dir.mkdir(parents=True, exist_ok=True)
        mxl = out_dir / "score.mxl"
        with zipfile.ZipFile(mxl, "w") as zf:
            zf.writestr("score.xml", MINIMAL_MUSICXML)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(omr_engine.subprocess, "run", fake_run)

    img = tmp_path / "score.png"
    img.write_bytes(b"\x89PNG\r\n")
    result = omr_engine.run_omr(img, "jobM", settings=tmp_settings)
    assert result.measure_count == 2
    assert result.part_count == 1
