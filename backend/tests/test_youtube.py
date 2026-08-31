from __future__ import annotations

import pytest

from app.core.exceptions import EngineNotConfiguredError, YouTubeError
from app.services import youtube

HOSTS = ["youtube.com", "www.youtube.com", "youtu.be"]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abc123",
        "http://youtu.be/abc123",
        "https://youtube.com/watch?v=x",
    ],
)
def test_validate_url_accepts_allowed_hosts(url):
    assert youtube.validate_url(url, HOSTS) == url


@pytest.mark.parametrize(
    "url",
    [
        "ftp://youtube.com/x",
        "https://evil.example.com/watch?v=x",
        "https://youtube.com.evil.net/x",
        "not-a-url",
    ],
)
def test_validate_url_rejects_bad_input(url):
    with pytest.raises(YouTubeError):
        youtube.validate_url(url, HOSTS)


def test_fetch_audio_happy_path_with_mocked_ytdlp(tmp_settings, tmp_path, monkeypatch):
    def fake_run(url, opts):
        out = tmp_path / "job"
        out.mkdir(parents=True, exist_ok=True)
        # simulate the intermediate download + the ffmpeg-extracted wav
        (out / "source.webm").write_bytes(b"webm")
        (out / "source.wav").write_bytes(b"RIFF....WAVE")
        return {"id": "vid123", "title": "Test Song", "duration": 210}

    monkeypatch.setattr(youtube, "_run_ytdlp", fake_run)

    result = youtube.fetch_audio(
        "https://www.youtube.com/watch?v=vid123", tmp_path / "job", settings=tmp_settings
    )
    assert result.path.name == "source.wav"
    assert result.title == "Test Song"
    assert result.duration_sec == 210
    assert not (tmp_path / "job" / "source.webm").exists()  # intermediates cleaned


def test_fetch_audio_rejects_disallowed_host(tmp_settings, tmp_path):
    with pytest.raises(YouTubeError):
        youtube.fetch_audio("https://vimeo.com/123", tmp_path, settings=tmp_settings)


def test_fetch_audio_when_disabled(tmp_settings, tmp_path):
    tmp_settings.youtube_enabled = False
    with pytest.raises(EngineNotConfiguredError):
        youtube.fetch_audio(
            "https://www.youtube.com/watch?v=x", tmp_path, settings=tmp_settings
        )


def test_fetch_audio_no_wav_produced(tmp_settings, tmp_path, monkeypatch):
    monkeypatch.setattr(
        youtube, "_run_ytdlp", lambda url, opts: {"id": "x", "title": "t", "duration": 5}
    )
    with pytest.raises(YouTubeError, match="no .wav"):
        youtube.fetch_audio(
            "https://www.youtube.com/watch?v=x", tmp_path / "j", settings=tmp_settings
        )


def test_upload_url_route(tmp_settings, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    def fake_fetch(url, dest_dir, *, settings):
        from pathlib import Path

        d = Path(dest_dir)
        d.mkdir(parents=True, exist_ok=True)
        wav = d / "source.wav"
        wav.write_bytes(b"RIFF....WAVE")
        return youtube.AudioFetchResult(
            path=wav, title="Mocked", duration_sec=123.0,
            source_url=url, video_id="mock1",
        )

    monkeypatch.setattr(youtube, "fetch_audio", fake_fetch)

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: tmp_settings
    client = TestClient(app)

    resp = client.post(
        "/api/upload-url", json={"url": "https://www.youtube.com/watch?v=mock1"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "single_audio"
    assert body["kind"] == "audio"
    job_id = body["job_id"]
    assert (tmp_settings.uploads_path / job_id / "source.wav").is_file()


def test_health_lists_ytdlp_engine(tmp_settings):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: tmp_settings
    client = TestClient(app)
    engines = {e["name"] for e in client.get("/health").json()["engines"]}
    assert "yt-dlp" in engines
