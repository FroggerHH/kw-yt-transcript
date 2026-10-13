"""Тесты library-навигатора (Волна 27): список с [i], детали, транскрипт, open, tui.

Без сети: фиктивная библиотека в tmp (XDG_DATA_HOME), opener/input — инъекции.
"""

import json
from pathlib import Path

from kw_yt_transcript import cli as cli_mod
from kw_yt_transcript import storage as storage_mod

SEGS = [
    {"text": "Привет мир", "start": 0.0, "duration": 2.0},
    {"text": "Вторая реплика", "start": 3.0, "duration": 2.0},
]


def _xdg(monkeypatch, tmp_path):
    data = tmp_path / "xdg-data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    return data / "kw-yt" / "library"


def _video(lib, dirname, video_id, title="Видео", extras_noreport=False):
    d = lib / dirname
    d.mkdir(parents=True)
    meta = {
        "video_id": video_id,
        "title": title,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "channel": "Канал",
        "upload_date": "20260115",
        "duration": 125,
        "origin": "manual",
        "transcript_lang": "ru",
        "stats": {"words": 48, "reading_time_min": 0.3},
    }
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (d / "transcript.json").write_text(json.dumps(SEGS, ensure_ascii=False), encoding="utf-8")
    (d / "transcript.txt").write_text("Привет мир\n", encoding="utf-8")
    if not extras_noreport:
        (d / "report.html").write_text("<html></html>", encoding="utf-8")
    return d


def _lib2(monkeypatch, tmp_path):
    lib = _xdg(monkeypatch, tmp_path)
    _video(lib, "b_vtoroe_id2", "id2", title="Второе")
    _video(lib, "a_pervoe_id1", "id1", title="Первое")
    return lib


def test_list_indexed_deterministic(monkeypatch, tmp_path, capsys):
    _lib2(monkeypatch, tmp_path)
    assert cli_mod.main(["library"]) == 0
    out = capsys.readouterr().out
    assert "видео 2" in out
    assert "- [1] Первое [id1]" in out
    assert "- [2] Второе [id2]" in out
    assert out.index("[1]") < out.index("[2]")
    assert "КБ" in out or "МБ" in out


def test_list_json_has_index_keys(monkeypatch, tmp_path, capsys):
    _lib2(monkeypatch, tmp_path)
    assert cli_mod.main(["library", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [d["index"] for d in data] == [1, 2]
    for d in data:
        assert set(d) == {
            "index",
            "video_id",
            "title",
            "date",
            "size_bytes",
            "origin",
            "dir",
        }


def test_details_by_number_and_id(monkeypatch, tmp_path, capsys):
    _lib2(monkeypatch, tmp_path)
    assert cli_mod.main(["library", "1"]) == 0
    out = capsys.readouterr().out
    for marker in (
        "Первое",
        "id: id1",
        "url: https://www.youtube.com/watch?v=id1",
        "Канал",
        "20260115",
        "125 с",
        "manual",
        "ru",
        "48",
        "transcript.txt",
        "report.html",
        "Папка:",
    ):
        assert marker in out, marker
    assert cli_mod.main(["library", "id2"]) == 0
    assert "Второе" in capsys.readouterr().out


def test_details_json_object(monkeypatch, tmp_path, capsys):
    _lib2(monkeypatch, tmp_path)
    assert cli_mod.main(["library", "id1", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["index"] == 1 and d["video_id"] == "id1"
    assert d["words"] == 48 and d["files"] and d["path"].endswith("a_pervoe_id1")


def test_target_errors_exit_1(monkeypatch, tmp_path, capsys):
    _lib2(monkeypatch, tmp_path)
    assert cli_mod.main(["library", "99"]) == 1
    assert "номером 99" in capsys.readouterr().err
    assert cli_mod.main(["library", "нет-такого"]) == 1
    assert "нет в библиотеке" in capsys.readouterr().err


def test_transcript_formats(monkeypatch, tmp_path, capsys):
    _lib2(monkeypatch, tmp_path)
    assert cli_mod.main(["library", "1", "--transcript"]) == 0
    assert "Привет мир" in capsys.readouterr().out
    assert cli_mod.main(["library", "id1", "--transcript", "--format", "md"]) == 0
    assert "# Первое" in capsys.readouterr().out
    assert cli_mod.main(["library", "1", "--transcript", "--format", "srt"]) == 0
    assert "-->" in capsys.readouterr().out


def test_transcript_missing_exit_1(monkeypatch, tmp_path, capsys):
    lib = _xdg(monkeypatch, tmp_path)
    d = _video(lib, "a_id1", "id1")
    (d / "transcript.json").unlink()
    assert cli_mod.main(["library", "1", "--transcript"]) == 1
    assert "transcript.json" in capsys.readouterr().err


def test_open_report_opener_injection(monkeypatch, tmp_path, capsys):
    lib = _xdg(monkeypatch, tmp_path)
    d = _video(lib, "a_id1", "id1")
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    assert cli_mod.main(["library", "1", "--open"]) == 0
    assert len(opened) == 1 and opened[0].endswith("report.html")
    assert "Открываю" in capsys.readouterr().out
    (d / "report.html").unlink()
    assert cli_mod.main(["library", "1", "--open"]) == 1
    assert "report.html" in capsys.readouterr().err


def test_tui_conflicts_exit_2(monkeypatch, tmp_path, capsys):
    _lib2(monkeypatch, tmp_path)
    for argv in (
        ["library", "--tui", "--json"],
        ["library", "--tui", "--transcript"],
        ["library", "--tui", "--open"],
        ["library", "--tui", "--format", "md"],
        ["library", "1", "--tui"],
    ):
        assert cli_mod.main(argv) == 2, argv
        capsys.readouterr()


def test_json_beats_transcript_priority(monkeypatch, tmp_path, capsys):
    _lib2(monkeypatch, tmp_path)
    assert cli_mod.main(["library", "1", "--json", "--transcript"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["video_id"] == "id1"


def _ask_script(answers):
    it = iter(answers)

    def ask(_prompt=""):
        return next(it, None)

    return ask


def test_tui_info_then_quit(monkeypatch, tmp_path, capsys):
    lib = _lib2(monkeypatch, tmp_path)
    entries = cli_mod._library_entries(lib)
    ask = _ask_script(["1", "i", "q"])
    assert cli_mod.run_tui(lib, entries, ask=ask) == 0
    out = capsys.readouterr().out
    assert "- [1] Первое" in out and "id: id1" in out


def test_tui_empty_exits_0(monkeypatch, tmp_path, capsys):
    lib = _lib2(monkeypatch, tmp_path)
    entries = cli_mod._library_entries(lib)
    assert cli_mod.run_tui(lib, entries, ask=_ask_script([])) == 0
    assert "- [2] Второе" in capsys.readouterr().out


def test_tui_bad_number_then_transcript(monkeypatch, tmp_path, capsys):
    lib = _lib2(monkeypatch, tmp_path)
    entries = cli_mod._library_entries(lib)
    assert cli_mod.run_tui(lib, entries, ask=_ask_script(["99", "2", "t", ""])) == 0
    out = capsys.readouterr().out
    assert "Нет видео с номером '99'" in out
    assert "Вторая реплика" in out


def test_tui_via_cli_eof_exits_0(monkeypatch, tmp_path, capsys):
    _lib2(monkeypatch, tmp_path)

    def eof(_prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert cli_mod.main(["library", "--tui"]) == 0
    assert "- [1] Первое" in capsys.readouterr().out


def test_storage_detail_helpers(monkeypatch, tmp_path):
    lib = _xdg(monkeypatch, tmp_path)
    d = _video(lib, "a_id1", "id1")
    meta = storage_mod.read_meta(d)
    assert meta and meta["title"] == "Видео"
    assert storage_mod.read_segments(d) == SEGS
    names = [f["name"] for f in storage_mod.list_files(d)]
    assert names == sorted(names) and "meta.json" in names
    assert storage_mod.read_meta(lib / "нет") is None
    assert storage_mod.read_segments(lib / "нет") is None
    assert storage_mod.list_files(lib / "нет") == []
    assert storage_mod.read_meta(Path("/nonexistent-xyz")) is None
