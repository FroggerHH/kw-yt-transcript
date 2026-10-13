"""Тесты metadata.get_metadata на фикстурах: без сети, HOME, yt-dlp (stub через ydl_factory)."""

import json
import sys
from pathlib import Path

import pytest

from kw_yt_transcript.metadata import MetadataError, get_metadata

FIXTURES = Path(__file__).parent / "fixtures"


def load_info():
    return json.loads((FIXTURES / "info.json").read_text(encoding="utf-8"))


class StubYDL:
    """Минимальный двойник yt_dlp.YoutubeDL: context manager + extract_info/sanitize_info."""

    def __init__(self, info=None, error=None):
        self._info = info
        self._error = error
        self.seen_opts = None
        self.seen_url = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        self.seen_url = url
        if self._error is not None:
            raise self._error
        return self._info

    def sanitize_info(self, info):
        return info


def make_factory(stub):
    return lambda opts: (setattr(stub, "seen_opts", opts) or stub)


def test_full_mapping():
    stub = StubYDL(info=load_info())
    meta = get_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ydl_factory=make_factory(stub))
    assert meta["video_id"] == "dQw4w9WgXcQ"
    assert meta["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert meta["title"] == "Тестовое видео про транскрипты"
    assert meta["channel"] == "Тестовый канал"
    assert meta["author"] == "Тестовый автор"
    assert meta["channel_id"] == "UC1234567890abcdef123456"
    assert meta["duration"] == 372
    assert meta["upload_date"] == "20260115"
    assert meta["view_count"] == 123456
    assert meta["like_count"] == 7890
    assert meta["description"].startswith("Описание тестового видео.")
    assert meta["chapters"] == [
        {"start_time": 0.0, "end_time": 60.0, "title": "Вступление"},
        {"start_time": 60.0, "end_time": 372.0, "title": "Основная часть"},
    ]
    assert meta["thumbnails"][0]["url"].startswith("https://i.ytimg.com/")
    assert meta["tags"] == ["тест", "транскрипт"]
    assert meta["categories"] == ["Education"]
    assert meta["subtitles_keys"] == ["ru"]
    assert meta["automatic_captions_keys"] == ["en"]


def test_bare_id_normalized_to_watch_url():
    stub = StubYDL(info=load_info())
    get_metadata("dQw4w9WgXcQ", ydl_factory=make_factory(stub))
    assert stub.seen_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_default_opts_passed():
    stub = StubYDL(info=load_info())
    get_metadata("dQw4w9WgXcQ", ydl_factory=make_factory(stub))
    assert stub.seen_opts["quiet"] is True
    assert stub.seen_opts["skip_download"] is True
    assert stub.seen_opts["noplaylist"] is True


def test_missing_optional_fields_default_to_empty():
    stub = StubYDL(info={"id": "dQw4w9WgXcQ", "title": "Без полей"})
    meta = get_metadata("dQw4w9WgXcQ", ydl_factory=make_factory(stub))
    assert meta["chapters"] == []
    assert meta["thumbnails"] == []
    assert meta["tags"] == []
    assert meta["categories"] == []
    assert meta["subtitles_keys"] == []
    assert meta["automatic_captions_keys"] == []
    assert meta["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_playlist_type_raises_clean_error():
    info = load_info()
    info["_type"] = "playlist"
    stub = StubYDL(info=info)
    with pytest.raises(MetadataError, match="плейлист"):
        get_metadata("https://www.youtube.com/playlist?list=PL123", ydl_factory=make_factory(stub))


def test_ydl_error_wrapped_in_russian():
    stub = StubYDL(error=RuntimeError("ERROR: Video unavailable"))
    with pytest.raises(MetadataError, match="Не удалось получить метаданные"):
        get_metadata("dQw4w9WgXcQ", ydl_factory=make_factory(stub))


def test_empty_info_raises():
    stub = StubYDL(info=None)
    with pytest.raises(MetadataError):
        get_metadata("dQw4w9WgXcQ", ydl_factory=make_factory(stub))


def test_no_real_ytdlp_imported():
    assert "yt_dlp" not in sys.modules
