"""Тесты сводного экспорта корпуса (Волна 5). Без сети: tmp_path + фиктивные json."""

import json

from kw_yt_transcript import cli as cli_mod
from kw_yt_transcript import export as export_mod


def _video(root, name, segs, meta):
    d = root / name
    d.mkdir(parents=True)
    (d / "transcript.json").write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return d


def _corpus(root):
    _video(
        root,
        "a_first",
        [
            {"text": "раз два", "start": 0.0, "duration": 1.0},
            {"text": "три", "start": 2.0, "duration": 1.0},
        ],
        {"video_id": "id1", "title": "Первое", "origin": "manual"},
    )
    _video(
        root,
        "b_second",
        [{"text": "четыре пять шесть", "start": 0.5, "duration": 2.0}],
        {"video_id": "id2", "title": "Второе", "origin": "auto"},
    )
    (root / "c_empty").mkdir()
    broken = root / "d_broken"
    broken.mkdir()
    (broken / "transcript.json").write_text("{не json", encoding="utf-8")
    return root


def test_collect_skips_without_transcript_and_broken(tmp_path):
    videos, skipped = export_mod.collect_corpus(_corpus(tmp_path / "out"))
    assert [v["video_id"] for v in videos] == ["id1", "id2"]
    assert {s["dir"] for s in skipped} == {"c_empty", "d_broken"}
    assert all(s["error"] for s in skipped)


def test_export_jsonl_merges_and_summary(tmp_path):
    root = _corpus(tmp_path / "out")
    out = root / "corpus.jsonl"
    summary = export_mod.export_corpus(root, out, "jsonl")
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3
    assert rows[0]["video_id"] == "id1" and rows[2]["video_id"] == "id2"
    assert summary["n_videos"] == 2
    assert summary["n_segments"] == 3
    assert summary["total_words"] == 6
    assert summary["by_origin"] == {"manual": 1, "auto": 1}
    assert len(summary["skipped"]) == 2
    assert {v["video_id"] for v in summary["videos"]} == {"id1", "id2"}


def test_export_csv_single_header(tmp_path):
    import csv as _csv
    import io as _io

    root = _corpus(tmp_path / "out")
    out = root / "corpus.csv"
    export_mod.export_corpus(root, out, "csv")
    rows = list(_csv.reader(_io.StringIO(out.read_text(encoding="utf-8"))))
    assert rows[0] == ["video_id", "title", "start", "duration", "text"]
    assert len(rows) == 4
    assert rows[1][0] == "id1" and rows[3][0] == "id2"


def test_export_bad_format_and_empty_corpus(tmp_path):
    root = _corpus(tmp_path / "out")
    try:
        export_mod.export_corpus(root, root / "x.jsonl", "xml")
    except ValueError as e:
        assert "xml" in str(e)
    else:
        raise AssertionError("ожидался ValueError")
    empty = tmp_path / "empty"
    empty.mkdir()
    try:
        export_mod.export_corpus(empty, empty / "corpus.jsonl", "jsonl")
    except ValueError as e:
        assert "нет транскриптов" in str(e).lower() or "Нечего" in str(e)
    else:
        raise AssertionError("ожидался ValueError")


def test_cli_export_writes_files_and_summary(tmp_path):
    root = _corpus(tmp_path / "out")
    assert cli_mod.main(["export", "--in", str(root)]) == 0
    assert (root / "corpus.jsonl").is_file()
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["n_videos"] == 2


def test_cli_export_csv_no_summary_and_errors(tmp_path):
    root = _corpus(tmp_path / "out")
    out = root / "all.csv"
    assert (
        cli_mod.main(
            ["export", "--in", str(root), "--format", "csv", "--out", str(out), "--no-summary"]
        )
        == 0
    )
    assert out.is_file()
    assert not (root / "summary.json").exists()
    assert cli_mod.main(["export", "--in", str(tmp_path / "missing")]) == 2
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cli_mod.main(["export", "--in", str(empty)]) == 1
