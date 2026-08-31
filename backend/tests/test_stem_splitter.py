from __future__ import annotations

import subprocess

import pytest

from app.core.exceptions import EngineNotConfiguredError, StemSeparationError
from app.services import stem_splitter


def test_engine_unavailable_when_not_configured(tmp_settings):
    available, engine, path = stem_splitter.engine_available(tmp_settings)
    assert available is False
    assert engine == "stemdeck"
    assert path is None


def test_split_audio_raises_when_engine_missing(tmp_settings, tmp_path):
    src = tmp_path / "mix.wav"
    src.write_bytes(b"RIFF0000WAVE")
    with pytest.raises(EngineNotConfiguredError):
        stem_splitter.split_audio(src, "job1", settings=tmp_settings)


def test_split_audio_happy_path_with_fake_cli(tmp_settings, tmp_path, monkeypatch):
    fake_bin = tmp_path / "stemdeck"
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    tmp_settings.stemdeck_bin = str(fake_bin)

    def fake_run(cmd, capture_output, text, timeout):
        out_dir = tmp_settings.stems_path / "job42"
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in ("vocals", "drums", "bass", "other"):
            (out_dir / f"{name}.wav").write_bytes(b"RIFF")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(stem_splitter.subprocess, "run", fake_run)

    src = tmp_path / "mix.wav"
    src.write_bytes(b"RIFF0000WAVE")
    result = stem_splitter.split_audio(src, "job42", settings=tmp_settings)

    assert result.engine == "stemdeck"
    assert [t.name for t in result.tracks] == ["vocal", "drums", "bass", "other"]


def test_split_audio_reports_missing_stems(tmp_settings, tmp_path, monkeypatch):
    fake_bin = tmp_path / "stemdeck"
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)
    tmp_settings.stemdeck_bin = str(fake_bin)

    def fake_run(cmd, capture_output, text, timeout):
        out_dir = tmp_settings.stems_path / "jobX"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "vocals.wav").write_bytes(b"RIFF")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(stem_splitter.subprocess, "run", fake_run)

    src = tmp_path / "mix.wav"
    src.write_bytes(b"RIFF")
    with pytest.raises(StemSeparationError) as exc:
        stem_splitter.split_audio(src, "jobX", settings=tmp_settings)
    assert "missing" in str(exc.value).lower() or exc.value.detail
