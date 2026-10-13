"""Тесты фрагментов --from/--to (Волна 21): parse/clip/CLI/resume. Без сети."""

import json

import pytest

from kw_yt_transcript import cli as cli_mod
from kw_yt_transcript import outputs as outputs_mod
from kw_yt_transcript.sections import clip_segments, parse_ts, section_key

SEGS = [
    {"text": "ноль", "start": 0.0, "duration": 10.0},
    {"text": "сто", "start": 100.0, "duration": 10.0},
    {"text": "двести", "start": 200.0, "duration": 10.0},
]


def test_parse_ts_formats():
    assert parse_ts("01:30") == 90.0
    assert parse_ts("1:02:03") == 3723.0
    assert parse_ts("90") == 90.0
    assert parse_ts("1.5") == 1.5
    assert parse_ts(" 02:05 ") == 125.0


def test_parse_ts_garbage():
    for bad in ("", "  ", "abc", "1:2:3:4", "12:", ":30", "-5", "-01:00", "1:-30"):
        with pytest.raises(ValueError):
            parse_ts(bad)


def test_section_key_compact():
    assert section_key(90.0, 165.0) == "part0130-0245"
    assert section_key(0.0, 3723.0) == "part0000-10203"


def test_clip_boundaries():
    got = clip_segments(SEGS, 5.0, 105.0)
    assert [s["text"] for s in got] == ["ноль", "сто"]
    # касание границы без пересечения — мимо (пусто → ValueError)
    with pytest.raises(ValueError, match="нет реплик"):
        clip_segments(SEGS, 10.0, 100.0)
    # duration исходные, объекты те же
    got = clip_segments(SEGS, 0.0, 1000.0)
    assert got[0]["duration"] == 10.0 and got[0] is SEGS[0]


def test_clip_empty_raises():
    with pytest.raises(ValueError, match="нет реплик"):
        clip_segments(SEGS, 500.0, 600.0)
    with pytest.raises(ValueError, match="нет реплик"):
        clip_segments([], 0.0, 10.0)


def _stub_all(monkeypatch, segs):
    from kw_yt_transcript import metadata as metadata_mod
    from kw_yt_transcript import transcript as transcript_mod

    monkeypatch.setattr(
        metadata_mod,
        "get_metadata",
        lambda source: {
            "video_id": "dQw4w9WgXcQ",
            "url": source,
            "title": "Тестовое видео",
            "channel": "Канал",
            "duration": 300,
            "thumbnails": [],
        },
    )
    monkeypatch.setattr(
        transcript_mod, "get_transcript", lambda vid, languages=None: (segs, "manual", "ru")
    )


def test_cli_section_validation_exit_2(monkeypatch, tmp_path, capsys):
    out = tmp_path / "out"
    assert cli_mod.main(["dQw4w9WgXcQ", "--from", "02:00", "--to", "01:00", "-o", str(out)]) == 2
    assert cli_mod.main(["dQw4w9WgXcQ", "--from", "abc", "--to", "100", "-o", str(out)]) == 2
    assert cli_mod.main(["dQw4w9WgXcQ", "--from", "10", "-o", str(out)]) == 2
    assert cli_mod.main(["dQw4w9WgXcQ", "--to", "10", "-o", str(out)]) == 2
    assert not out.exists(), "валидация до сети и диска: папки нет"


def test_cli_fragment_folder_suffix(monkeypatch, tmp_path):
    _stub_all(monkeypatch, SEGS)
    out = tmp_path / "out"
    assert cli_mod.main(["dQw4w9WgXcQ", "--from", "01:30", "--to", "02:45", "-o", str(out)]) == 0
    dirs = [p for p in out.iterdir() if p.is_dir()]
    assert len(dirs) == 1
    assert dirs[0].name == "testovoe-video_part0130-0245_dQw4w9WgXcQ"
    record = json.loads((dirs[0] / "meta.json").read_text(encoding="utf-8"))
    assert record["section"] == {"from": 90.0, "to": 165.0}
    body = (dirs[0] / "report.html").read_text(encoding="utf-8")
    assert "Фрагмент 01:30–02:45" in body
    # в dominant-файле только реплики фрагмента
    data = json.loads((dirs[0] / "transcript.json").read_text(encoding="utf-8"))
    assert [s["text"] for s in data] == ["сто"]


def _meta(video_id="dQw4w9WgXcQ"):
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": "Тестовое видео",
        "channel": "Канал",
        "duration": 300,
        "thumbnails": [],
    }


def test_resume_full_and_fragment_separate(monkeypatch, tmp_path):
    from kw_yt_transcript import metadata as metadata_mod

    out = tmp_path / "out"
    outputs_mod.write_video(out, _meta(), SEGS, "manual")
    outputs_mod.write_video(out, _meta(), SEGS, "manual", section=(90.0, 165.0))

    def dead(source):
        raise AssertionError("сеть не должна вызываться при resume")

    monkeypatch.setattr(metadata_mod, "get_metadata", dead)
    # полный прогон находит полную папку
    assert cli_mod.main(["dQw4w9WgXcQ", "--resume", "-o", str(out)]) == 0
    # фрагмент находит только фрагмент
    assert (
        cli_mod.main(
            ["dQw4w9WgXcQ", "--resume", "--from", "01:30", "--to", "02:45", "-o", str(out)]
        )
        == 0
    )
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert index["entries"][0]["dir"].endswith("_part0130-0245_dQw4w9WgXcQ")


def test_resume_fragment_misses_full(monkeypatch, tmp_path):
    from kw_yt_transcript import metadata as metadata_mod

    out = tmp_path / "out"
    outputs_mod.write_video(out, _meta(), SEGS, "manual")  # только полный

    def dead(source):
        raise AssertionError("фрагмент не должен матчить полную папку")

    monkeypatch.setattr(metadata_mod, "get_metadata", dead)
    # resume фрагмента без готовой фрагмент-папки идёт в сеть → AssertionError наружу? нет:
    # _process_video ловит всё в error-entry, exit 1
    assert (
        cli_mod.main(
            ["dQw4w9WgXcQ", "--resume", "--from", "01:30", "--to", "02:45", "-o", str(out)]
        )
        == 1
    )
