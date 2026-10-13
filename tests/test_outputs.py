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
    assert set(paths) == {
        "dir", "meta", "srt", "vtt", "json", "txt", "md", "jsonl", "csv", "report",
    }
    for key in ("meta", "srt", "vtt", "json", "txt", "md", "jsonl", "csv", "report"):
        assert Path(paths[key]).is_file(), key
    record = json.loads(Path(paths["meta"]).read_text(encoding="utf-8"))
    assert record["title"] == "Тестовое видео про транскрипты"  # ensure_ascii=False
    assert record["origin"] == "manual"
    assert "Тестовое видео про транскрипты" in Path(paths["meta"]).read_text(encoding="utf-8")
    srt = Path(paths["srt"]).read_text(encoding="utf-8")
    assert srt.startswith("1\n00:00:00,000")


def test_write_video_format_filter(tmp_path):
    paths = write_video(tmp_path, meta(), segments(), "auto", formats_sel="txt")
    assert set(paths) == {"dir", "meta", "txt", "report"}
    assert (Path(paths["dir"]) / "transcript.txt").is_file()
    assert not (Path(paths["dir"]) / "transcript.srt").exists()


def test_write_video_bad_format(tmp_path):
    with pytest.raises(ValueError, match="Неизвестный формат"):
        write_video(tmp_path, meta(), segments(), "manual", formats_sel="docx")


def test_write_index_batch(tmp_path):
    results = [
        {
            "meta": meta(),
            "dir": "testovoe-video_dQw4w9WgXcQ",
            "origin": "manual",
            "transcript_lang": "ru",
            "error": None,
        },
        {
            "meta": None,
            "dir": None,
            "origin": None,
            "transcript_lang": None,
            "error": "Не удалось получить метаданные",
        },
    ]
    index_path = write_index(tmp_path, results)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert set(index) == {"_type", "playlist_url", "entries", "failed"}
    assert index["_type"] == "batch"
    assert index["playlist_url"] is None
    assert index["failed"] == 1
    assert index["entries"][0]["video_id"] == "dQw4w9WgXcQ"
    assert index["entries"][0]["origin"] == "manual"
    assert index["entries"][0]["transcript_lang"] == "ru"
    assert index["entries"][1]["error"] == "Не удалось получить метаданные"


def test_write_index_playlist(tmp_path):
    index_path = write_index(
        tmp_path,
        [{"meta": meta(), "dir": "d", "origin": "auto", "transcript_lang": "en", "error": None}],
        playlist_url="https://www.youtube.com/playlist?list=PL123",
    )
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["_type"] == "playlist"
    assert index["playlist_url"] == "https://www.youtube.com/playlist?list=PL123"
    assert index["failed"] == 0


def test_write_video_report_fields(tmp_path):
    from datetime import datetime

    from kw_yt_transcript import __version__

    paths = write_video(tmp_path, meta(), segments(), "manual", transcript_lang="ru")
    record = json.loads(Path(paths["meta"]).read_text(encoding="utf-8"))
    assert record["transcript_lang"] == "ru"
    assert record["tool_version"] == __version__
    datetime.fromisoformat(record["fetched_at"])
    assert "asr_model" not in record


def test_write_video_whisper_asr_model(tmp_path):
    paths = write_video(
        tmp_path, meta(), segments(), "whisper", transcript_lang=None, asr_model="small"
    )
    record = json.loads(Path(paths["meta"]).read_text(encoding="utf-8"))
    assert record["origin"] == "whisper"
    assert record["asr_model"] == "small"


def test_atomic_write_no_partial_files(tmp_path, monkeypatch):
    from pathlib import Path as _Path

    calls = []

    real_write = _Path.write_text

    def flaky(self, *args, **kwargs):
        calls.append(str(self))
        if len(calls) == 2:
            raise OSError("диск переполнен")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(_Path, "write_text", flaky)
    with pytest.raises(OSError, match="диск переполнен"):
        write_video(tmp_path, meta(), segments(), "manual")
    video_dir = tmp_path / "testovoe-video-pro-transkripty_dQw4w9WgXcQ"
    names = {p.name for p in video_dir.iterdir()} if video_dir.is_dir() else set()
    assert "transcript.srt" not in names
    assert not [n for n in names if n.endswith(".tmp")], names


def test_write_video_report_always_and_stats_in_meta(tmp_path):
    paths = write_video(tmp_path, meta(), segments(), "manual", formats_sel="txt")
    report = Path(paths["report"])
    assert report.name == "report.html" and report.is_file()
    body = report.read_text(encoding="utf-8")
    assert "<meta charset" in body and "dQw4w9WgXcQ" in body
    record = json.loads(Path(paths["meta"]).read_text(encoding="utf-8"))
    assert set(record["stats"]) == {
        "words",
        "chars",
        "reading_time_min",
        "speaking_wpm",
        "top_keywords",
    }
    assert record["stats"]["words"] > 0


def test_write_index_also_writes_html(tmp_path):
    paths = write_video(tmp_path, meta(), segments(), "manual")
    from kw_yt_transcript.outputs import write_index as _wi

    results = [
        {
            "meta": meta(),
            "dir": Path(paths["dir"]).name,
            "origin": "manual",
            "transcript_lang": "ru",
            "error": None,
        }
    ]
    index_path = _wi(tmp_path, results)
    assert index_path.is_file()
    index_html = Path(tmp_path) / "index.html"
    assert index_html.is_file()
    body = index_html.read_text(encoding="utf-8")
    assert "report.html" in body
    assert f"{Path(paths['dir']).name}/report.html" in body


def test_md_header_has_stats(tmp_path):
    from kw_yt_transcript.formats import to_md

    out = to_md(segments(), {**meta(), "origin": "manual"})
    assert "Слов:" in out and "Время чтения:" in out and "Ключевые слова:" in out
