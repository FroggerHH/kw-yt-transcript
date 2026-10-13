"""Тесты outputs: slug, write_video, write_index. Только tmp_path, без сети/HOME."""

import json
from pathlib import Path

import pytest

from kw_yt_transcript.outputs import slug, write_index, write_video

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def meta():
    # Фикстура — в форме сырого yt-dlp info; приводим к форме get_metadata().
    info = load("info.json")
    info["video_id"] = info.pop("id")
    return info


def segments():
    return load("segments.json")


def test_slug_translit():
    assert slug("Тестовое видео про транскрипты", "dQw4w9WgXcQ") == "testovoe-video-pro-transkripty"


def test_slug_latin_and_cleanup():
    assert slug("Hello, World! 2026", "vid") == "hello-world-2026"


def test_slug_truncated_to_60():
    assert slug("а" * 100, "vid") == "a" * 60


def test_slug_fallback_to_video_id():
    assert slug("!!!", "dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert slug("", "dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert slug(None, "dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_write_video_all_files(tmp_path):
    paths = write_video(tmp_path, meta(), segments(), "manual")
    video_dir = Path(paths["dir"])
    assert video_dir.name == "testovoe-video-pro-transkripty_dQw4w9WgXcQ"
    assert set(paths) == {"dir", "meta", "srt", "vtt", "json", "txt", "md"}
    for key in ("meta", "srt", "vtt", "json", "txt", "md"):
        assert Path(paths[key]).is_file(), key
    record = json.loads(Path(paths["meta"]).read_text(encoding="utf-8"))
    assert record["title"] == "Тестовое видео про транскрипты"  # ensure_ascii=False
    assert record["origin"] == "manual"
    assert "Тестовое видео про транскрипты" in Path(paths["meta"]).read_text(encoding="utf-8")
    srt = Path(paths["srt"]).read_text(encoding="utf-8")
    assert srt.startswith("1\n00:00:00,000")


def test_write_video_format_filter(tmp_path):
    paths = write_video(tmp_path, meta(), segments(), "auto", formats_sel="txt")
    assert set(paths) == {"dir", "meta", "txt"}
    assert (Path(paths["dir"]) / "transcript.txt").is_file()
    assert not (Path(paths["dir"]) / "transcript.srt").exists()


def test_write_video_bad_format(tmp_path):
    with pytest.raises(ValueError, match="Неизвестный формат"):
        write_video(tmp_path, meta(), segments(), "manual", formats_sel="docx")


def test_write_index_batch(tmp_path):
    results = [
        {"meta": meta(), "dir": "testovoe-video_dQw4w9WgXcQ", "origin": "manual", "error": None},
        {"meta": None, "dir": None, "origin": None, "error": "Не удалось получить метаданные"},
    ]
    index_path = write_index(tmp_path, results)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert set(index) == {"_type", "entries", "failed"}
    assert index["_type"] == "batch"
    assert index["failed"] == 1
    assert index["entries"][0]["video_id"] == "dQw4w9WgXcQ"
    assert index["entries"][0]["origin"] == "manual"
    assert index["entries"][1]["error"] == "Не удалось получить метаданные"


def test_write_index_playlist(tmp_path):
    index_path = write_index(
        tmp_path,
        [{"meta": meta(), "dir": "d", "origin": "auto", "error": None}],
        playlist_url="https://www.youtube.com/playlist?list=PL123",
    )
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["_type"] == "playlist"
    assert index["failed"] == 0
