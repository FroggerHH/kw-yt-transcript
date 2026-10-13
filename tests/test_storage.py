"""Тесты библиотеки (Волна 19, SPEC п.17): storage + library/clean.

Без сети: XDG_DATA_HOME=tmp, meta.json ручной сборки, сеть не вызывается.
"""

import json
import os
import time
from pathlib import Path

from kw_yt_transcript import cache as cache_mod
from kw_yt_transcript import cli as cli_mod
from kw_yt_transcript import config as config_mod
from kw_yt_transcript import storage as storage_mod


def _video(lib, dirname, video_id, title="Видео", origin="manual"):
    d = lib / dirname
    d.mkdir(parents=True)
    (d / "meta.json").write_text(
        json.dumps(
            {
                "video_id": video_id,
                "title": title,
                "upload_date": "20260115",
                "origin": origin,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (d / "transcript.json").write_text("[]", encoding="utf-8")
    return d


def _xdg(monkeypatch, tmp_path):
    data = tmp_path / "xdg-data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    return data


def test_library_path_xdg_and_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "d"))
    assert storage_mod.library_path() == tmp_path / "d" / "kw-yt" / "library"
    monkeypatch.delenv("XDG_DATA_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert storage_mod.library_path() == (
        tmp_path / "home" / ".local" / "share" / "kw-yt" / "library"
    )


def test_resolve_root_priority(monkeypatch, tmp_path):
    lib = _xdg(monkeypatch, tmp_path) / "kw-yt" / "library"
    assert storage_mod.resolve_root(tmp_path / "exp", {}) == tmp_path / "exp"
    assert storage_mod.resolve_root(None, {"out": "./cfg-out"}) == Path("./cfg-out")
    assert storage_mod.resolve_root(None, {"out": "   "}) == lib
    assert storage_mod.resolve_root(None, {"out": None}) == lib
    assert storage_mod.resolve_root(None, {}) == lib


def test_config_out_defaults_to_none():
    assert config_mod.DEFAULTS.get("out", "MISSING") == "MISSING"
    assert config_mod.load_config("/nonexistent/kw-yt-config.toml")["out"] is None


def test_iter_library_entries_and_sizes(monkeypatch, tmp_path):
    lib = _xdg(monkeypatch, tmp_path)
    _video(lib, "a_id1", "id1", title="Первое")
    _video(lib, "b_id2", "id2", title="Второе", origin="whisper")
    (lib / "мусор").mkdir()  # без meta.json — не запись
    entries = storage_mod.iter_library(lib)
    assert [e["video_id"] for e in entries] == ["id1", "id2"]
    assert entries[0]["title"] == "Первое" and entries[0]["origin"] == "manual"
    assert entries[1]["origin"] == "whisper"
    assert all(e["size_bytes"] > 0 for e in entries)
    assert storage_mod.iter_library(lib / "нет") == []


def test_find_video_dirs_exact_match(monkeypatch, tmp_path):
    lib = _xdg(monkeypatch, tmp_path)
    _video(lib, "video_abc", "abc")
    _video(lib, "video_abc2", "abc2")
    found, missing = storage_mod.find_video_dirs(lib, ["abc"])
    assert [p.name for p in found] == ["video_abc"]
    assert missing == []
    found, missing = storage_mod.find_video_dirs(lib, ["abc", "нет"])
    assert [p.name for p in found] == ["video_abc"]
    assert missing == ["нет"]


def test_library_empty_exit_0(monkeypatch, tmp_path, capsys):
    _xdg(monkeypatch, tmp_path)
    assert cli_mod.main(["library"]) == 0
    out = capsys.readouterr().out
    assert "пуста" in out.lower()


def test_library_table_and_json(monkeypatch, tmp_path, capsys):
    lib = _xdg(monkeypatch, tmp_path) / "kw-yt" / "library"
    _video(lib, "pervoe_id1", "id1", title="Первое")
    assert cli_mod.main(["library"]) == 0
    out = capsys.readouterr().out
    assert "Первое" in out and "id1" in out and "manual" in out
    assert cli_mod.main(["library", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["video_id"] == "id1" and data[0]["size_bytes"] > 0


def test_clean_ids_exact_and_missing(monkeypatch, tmp_path, capsys):
    lib = _xdg(monkeypatch, tmp_path) / "kw-yt" / "library"
    _video(lib, "video_abc", "abc")
    _video(lib, "video_abc2", "abc2")
    assert cli_mod.main(["clean", "abc"]) == 0
    assert not (lib / "video_abc").exists()
    assert (lib / "video_abc2").exists(), "abc2 не должен удаляться по id abc"
    assert "Удалено" in capsys.readouterr().out
    assert cli_mod.main(["clean", "нет"]) == 1
    err = capsys.readouterr().err
    assert "Не найдено" in err


def test_clean_all_requires_yes(monkeypatch, tmp_path, capsys):
    lib = _xdg(monkeypatch, tmp_path) / "kw-yt" / "library"
    _video(lib, "video_abc", "abc")
    assert cli_mod.main(["clean", "--all"]) == 2
    assert (lib / "video_abc").exists(), "--all без --yes ничего не удаляет"
    assert "--yes" in capsys.readouterr().err
    assert cli_mod.main(["clean", "--all", "--yes"]) == 0
    assert not (lib / "video_abc").exists()


def test_clean_older_than(monkeypatch, tmp_path):
    lib = _xdg(monkeypatch, tmp_path) / "kw-yt" / "library"
    old = _video(lib, "old_id1", "id1")
    new = _video(lib, "new_id2", "id2")
    ancient = time.time() - 30 * 86400
    os.utime(old, (ancient, ancient))
    assert cli_mod.main(["clean", "--older-than", "7"]) == 0
    assert not old.exists()
    assert new.exists()
    assert cli_mod.main(["clean", "--older-than", "zzz"]) == 2
    assert cli_mod.main(["clean"]) == 2


def test_clean_cache(monkeypatch, tmp_path, capsys):
    _xdg(monkeypatch, tmp_path)
    cache_mod.cache_set("dQw4w9WgXcQ", {"video_id": "dQw4w9WgXcQ"})
    assert cache_mod.cache_get("dQw4w9WgXcQ") is not None
    assert cli_mod.main(["clean", "--cache"]) == 0
    assert cache_mod.cache_get("dQw4w9WgXcQ") is None
    assert "кэш" in capsys.readouterr().out.lower()


def test_read_meta_segments_edge_cases(tmp_path):
    d = tmp_path / "v_id9"
    d.mkdir()
    (d / "meta.json").write_text("[1, 2]", encoding="utf-8")
    assert storage_mod.read_meta(d) is None
    (d / "meta.json").write_text("{битый", encoding="utf-8")
    assert storage_mod.read_meta(d) is None
    (d / "transcript.json").write_text('{"a": 1}', encoding="utf-8")
    assert storage_mod.read_segments(d) is None
    (d / "transcript.json").write_text("[]", encoding="utf-8")
    assert storage_mod.read_segments(d) == []
    assert [f["name"] for f in storage_mod.list_files(d)] == [
        "meta.json",
        "transcript.json",
    ]
    assert all(f["size_bytes"] > 0 for f in storage_mod.list_files(d))
