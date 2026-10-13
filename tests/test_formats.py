"""Тесты formats: таймкоды SRT/VTT, абзацы TXT/MD, header MD. Без сети, на фикстурах."""

import json
import re
from pathlib import Path

from kw_yt_transcript import formats
from kw_yt_transcript.formats import paragraphs, to_json, to_md, to_srt, to_txt, to_vtt

FIXTURES = Path(__file__).parent / "fixtures"
SEGMENTS = json.loads((FIXTURES / "segments.json").read_text(encoding="utf-8"))
INFO = json.loads((FIXTURES / "info.json").read_text(encoding="utf-8"))

SRT_TS = re.compile(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}")
VTT_TS = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}")


def meta_with_origin():
    m = dict(INFO)
    m["origin"] = "manual"
    return m


def test_srt_structure_and_timestamps():
    out = to_srt(SEGMENTS)
    assert SRT_TS.search(out), "SRT-таймкоды вида HH:MM:SS,mmm"
    assert out.startswith("1\n00:00:00,000 --> 00:00:02,500\n")
    assert out.count("-->") == len(SEGMENTS)
    assert "Привет, это первый сегмент" in out


def test_vtt_header_and_timestamps():
    out = to_vtt(SEGMENTS)
    assert out.startswith("WEBVTT")
    assert VTT_TS.search(out), "VTT-таймкоды вида HH:MM:SS.mmm"
    assert "00:00:00.000 --> 00:00:02.500" in out


def test_hour_timestamps():
    segs = [{"text": "x", "start": 3723.456, "duration": 1.5}]
    assert "01:02:03,456 --> 01:02:04,956" in to_srt(segs)
    assert "01:02:03.456 --> 01:02:04.956" in to_vtt(segs)


def test_json_roundtrip():
    data = json.loads(to_json(SEGMENTS))
    assert data == [
        {"start": s["start"], "duration": s["duration"], "text": s["text"]} for s in SEGMENTS
    ]


def test_txt_paragraphs_on_pause():
    out = to_txt(SEGMENTS)
    assert "\n\n" in out, "пауза 4.4с должна разорвать абзац"
    assert "Привет" in out and "Финальный сегмент" in out


def test_txt_paragraph_on_length():
    segs = [
        {"text": "а" * 900, "start": 0.0, "duration": 2.0},
        {"text": "б" * 100, "start": 2.1, "duration": 2.0},
    ]
    assert "\n\n" in to_txt(segs), "абзац длиннее 800 символов разрывается"


def test_md_header_chapters_paragraphs():
    out = to_md(SEGMENTS, meta_with_origin())
    assert out.startswith("# Тестовое видео про транскрипты")
    assert "Тестовый канал" in out
    assert "20260115" in out
    assert "ручные субтитры" in out
    assert "## Главы" in out
    assert "Вступление" in out and "Основная часть" in out
    assert "\n\n" in out, "абзацы в MD"


def test_md_without_meta():
    out = to_md(SEGMENTS)
    assert out.startswith("# Транскрипт")
    assert "\n\n" in out


def test_empty_segments():
    assert to_srt([]) == ""
    assert to_json([]) == "[]"
    assert json.loads(to_json([])) == []
    assert to_txt([]) == ""
    assert to_md([]) == ""
    assert to_vtt([]).startswith("WEBVTT")


def test_formats_registry_covers_all():
    assert set(formats.FORMATS) == {"srt", "vtt", "json", "txt", "md", "jsonl", "csv"}


def test_jsonl_round_trip_with_meta():
    import json as _json

    segs = [
        {"text": "привет, мир", "start": 1.5, "duration": 2.0},
        {"text": 'сказал "пока"', "start": 6.0, "duration": 1.0},
    ]
    meta = {"video_id": "dQw4w9WgXcQ", "title": "Тест"}
    rows = [ _json.loads(line) for line in formats.to_jsonl(segs, meta).splitlines()]
    assert [r["text"] for r in rows] == ["привет, мир", 'сказал "пока"']
    assert all(r["video_id"] == "dQw4w9WgXcQ" and r["title"] == "Тест" for r in rows)
    assert [r["start"] for r in rows] == [1.5, 6.0]
    assert formats.to_jsonl([]) == ""
    assert formats.to_jsonl([], None).splitlines() == []


def test_csv_quoting_and_header():
    import csv as _csv
    import io as _io

    segs = [
        {"text": "a,b", "start": 0.0, "duration": 1.0},
        {"text": 'c"d\ne', "start": 2.0, "duration": 1.5},
    ]
    out = formats.to_csv(segs, {"video_id": "id1", "title": "T"})
    rows = list(_csv.reader(_io.StringIO(out)))
    assert rows[0] == ["video_id", "title", "start", "duration", "text"]
    assert rows[1][4] == "a,b" and rows[1][0] == "id1"
    assert rows[2][4] == 'c"d\ne'
    assert len(list(_csv.reader(_io.StringIO(formats.to_csv([]))))) == 1


def test_paragraphs_edge_cases():
    assert paragraphs([]) == []
    single = [{"text": "один", "start": 0.0, "duration": 1.0}]
    assert paragraphs(single) == ["один"]
    # Перекрытие (отрицательная пауза) — тот же абзац.
    overlap = [
        {"text": "а", "start": 0.0, "duration": 5.0},
        {"text": "б", "start": 3.0, "duration": 1.0},
    ]
    assert paragraphs(overlap) == ["а б"]
    # Ровно 2.0с — не разрыв (нужно строго >).
    exact = [
        {"text": "а", "start": 0.0, "duration": 1.0},
        {"text": "б", "start": 3.0, "duration": 1.0},
    ]
    assert paragraphs(exact) == ["а б"]
    # Нулевая длительность не ломает склейку.
    zero = [
        {"text": "а", "start": 0.0, "duration": 0.0},
        {"text": "б", "start": 0.0, "duration": 1.0},
    ]
    assert paragraphs(zero) == ["а б"]


def test_ai_warning_md_txt_origins():
    for origin, expect in (("manual", False), ("auto", True), ("whisper", True)):
        m = dict(INFO)
        m["origin"] = origin
        assert ("распознан ИИ" in to_md(SEGMENTS, m)) == expect, origin
        assert ("распознан ИИ" in to_txt(SEGMENTS, m)) == expect, origin
    assert "распознан ИИ" not in to_md(SEGMENTS)
    assert "распознан ИИ" not in to_txt(SEGMENTS)
    assert "распознан ИИ" not in to_md(SEGMENTS, meta_with_origin())
    m = dict(INFO)
    m["origin"] = "auto"
    assert to_txt(SEGMENTS, m).startswith("⚠")
    lines = to_md(SEGMENTS, m).splitlines()
    assert lines[0].startswith("#") and "распознан ИИ" in lines[2]
