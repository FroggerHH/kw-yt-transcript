"""Тесты report: ссылки ?t=, escape, главы, поиск, index. Без сети."""

from kw_yt_transcript.report import render_index, render_report
from kw_yt_transcript.stats import compute_stats


def _meta():
    return {
        "video_id": "dQw4w9WgXcQ",
        "title": "Тестовое видео",
        "channel": "Тестовый канал",
        "upload_date": "20260115",
        "duration": 372,
        "transcript_lang": "ru",
        "chapters": [
            {"start_time": 0.0, "end_time": 60.0, "title": "Вступление"},
            {"start_time": 60.0, "end_time": 372.0, "title": "Основная часть"},
        ],
    }


def _segs():
    return [
        {"text": "Привет, это первый сегмент.", "start": 0.0, "duration": 2.5},
        {"text": "Второй сегмент.", "start": 65.0, "duration": 2.0},
    ]


def test_report_timestamp_links():
    html = render_report(_meta(), _segs(), compute_stats(_segs(), 372), "manual")
    assert "<meta charset" in html
    assert "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=0s" in html
    assert "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=65s" in html


def test_report_chapters_links():
    html = render_report(_meta(), _segs(), compute_stats(_segs(), 372), "manual")
    assert "https://youtu.be/dQw4w9WgXcQ?t=0" in html
    assert "https://youtu.be/dQw4w9WgXcQ?t=60" in html
    assert "Вступление" in html


def test_report_escapes_script():
    meta = _meta()
    segs = [{"text": "<script>alert(1)</script>", "start": 0.0, "duration": 1.0}]
    html = render_report(meta, segs, compute_stats(segs, 1), "auto")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    # пользовательский title тоже экранируется
    meta2 = dict(meta, title="<b>заголовок</b>")
    html2 = render_report(meta2, segs, compute_stats(segs, 1), "auto")
    assert "<b>заголовок</b>" not in html2


def test_report_search_input_and_inline_assets():
    html = render_report(_meta(), _segs(), compute_stats(_segs(), 372), "manual")
    assert 'type="search"' in html and 'id="search"' in html
    assert "<style>" in html and "<script>" in html
    assert "<link" not in html and "<script src" not in html and 'src="http' not in html


def test_report_header_and_stats_ru():
    html = render_report(_meta(), _segs(), compute_stats(_segs(), 372), "manual")
    assert "Тестовое видео" in html and "Тестовый канал" in html
    assert "ручные субтитры" in html
    assert "Статистика" in html and "Слов:" in html


def test_index_table_and_links():
    entries = [
        {
            "title": "Видео один",
            "video_id": "id1",
            "dir": "video-odin_id1",
            "author": "Автор",
            "duration": 100,
            "words": 50,
            "origin": "manual",
        }
    ]
    html = render_index(entries, {"n_videos": 1, "total_words": 50, "total_min": 1.7})
    assert "<meta charset" in html
    assert "video-odin_id1/report.html" in html
    assert "<table>" in html and "Видео один" in html
    assert "Всего видео: 1" in html


def test_index_gallery_thumbnails():
    entries = [
        {
            "title": "Видео один",
            "video_id": "id1",
            "dir": "video-odin_id1",
            "author": "Автор",
            "duration": 100,
            "words": 50,
            "origin": "manual",
            "thumbnail_file": "thumbnail.jpg",
        },
        {
            "title": "Видео два",
            "video_id": "id2",
            "dir": "video-dva_id2",
            "author": "Автор",
            "duration": 200,
            "words": 70,
            "origin": "auto",
            "thumbnail_file": None,
        },
    ]
    html = render_index(entries, {"n_videos": 2, "total_words": 120, "total_min": 5.0})
    assert '<img src="video-odin_id1/thumbnail.jpg" loading="lazy"' in html
    assert "width:120px" in html
    assert html.count("<img") == 1
    assert "<table>" in html and "Видео два" in html


def test_index_without_thumbnails_no_img():
    entries = [
        {
            "title": "Видео <один>",
            "video_id": "id1",
            "dir": "video-odin_id1",
            "author": "Автор",
            "duration": 100,
            "words": 50,
            "origin": "manual",
        }
    ]
    html = render_index(entries, {"n_videos": 1, "total_words": 50, "total_min": 1.7})
    assert "<img" not in html
    assert "<table>" in html
    assert "Видео &lt;один&gt;" in html


def test_report_ai_banner_origins():
    for origin, expect in (("manual", False), ("auto", True), ("whisper", True)):
        html = render_report(_meta(), _segs(), compute_stats(_segs(), 372), origin)
        assert ("распознан ИИ" in html) == expect, origin
    html = render_report(_meta(), _segs(), compute_stats(_segs(), 372), None)
    assert "распознан ИИ" not in html


def test_report_prose_before_timed():
    html = render_report(_meta(), _segs(), compute_stats(_segs(), 372), "manual")
    assert "<h2>Текст</h2>" in html
    assert html.index("<h2>Текст</h2>") < html.index('class="seg"')
    assert "Привет, это первый сегмент." in html


def test_report_files_hub_links():
    files = [
        "meta.json",
        "report.html",
        "thumbnail.jpg",
        "transcript.srt",
        "transcript.vtt",
        "transcript.json",
        "transcript.jsonl",
        "transcript.csv",
        "transcript.txt",
        "transcript.md",
    ]
    html = render_report(_meta(), _segs(), compute_stats(_segs(), 372), "manual", files=files)
    assert "<h2>Файлы</h2>" in html or "Файлы (" in html
    for name in files:
        assert f'href="{name}"' in html, name
    assert "download" in html


def test_report_file_url_fitness():
    files = ["meta.json", "transcript.srt", "transcript.txt"]
    html = render_report(_meta(), _segs(), compute_stats(_segs(), 372), "manual", files=files)
    assert "/tmp" not in html and "/home" not in html
    import re

    for url in re.findall(r'https?://[^"\s<>]+', html):
        assert url.startswith("https://www.youtube.com/") or url.startswith("https://youtu.be/"), (
            url
        )


def test_report_search_covers_prose():
    html = render_report(_meta(), _segs(), compute_stats(_segs(), 372), "manual")
    assert ".prose-text" in html
