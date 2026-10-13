"""Тесты команды stats (Волна 6). Без сети: tmp_path + фиктивный корпус."""

import json

from kw_yt_transcript import cli as cli_mod


def _corpus(root):
    a = root / "a_first"
    a.mkdir(parents=True)
    (a / "transcript.json").write_text(
        json.dumps(
            [
                {"text": "раз два", "start": 0.0, "duration": 60.0},
                {"text": "три", "start": 61.0, "duration": 60.0},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (a / "meta.json").write_text(
        json.dumps(
            {"video_id": "id1", "title": "Первое", "origin": "manual", "transcript_lang": "ru"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    b = root / "b_second"
    b.mkdir(parents=True)
    (b / "transcript.json").write_text(
        json.dumps([{"text": "четыре", "start": 0.0, "duration": 30.0}], ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "c_empty").mkdir(parents=True)
    return root


def test_stats_table_and_counts(tmp_path, capsys):
    root = _corpus(tmp_path / "out")
    assert cli_mod.main(["stats", "--in", str(root)]) == 0
    out = capsys.readouterr().out
    assert "видео 2" in out
    assert "слов 4" in out
    assert "Первое" in out and "id1" in out
    assert "manual: 1" in out
    assert "Пропущено папок без транскрипта: 1." in out


def test_stats_json_parses(tmp_path, capsys):
    root = _corpus(tmp_path / "out")
    assert cli_mod.main(["stats", "--in", str(root), "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["n_videos"] == 2
    assert summary["total_words"] == 4
    assert summary["by_lang"] == {"ru": 1, "unknown": 1}
    assert summary["skipped"] == 1
    assert summary["videos"][0]["video_id"] == "id1"


def test_stats_empty_and_missing(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cli_mod.main(["stats", "--in", str(empty)]) == 1
    assert cli_mod.main(["stats", "--in", str(tmp_path / "missing")]) == 2
