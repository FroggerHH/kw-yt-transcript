"""Тесты search_corpus + `kw-yt search`. Без сети, на tmp_path."""

import json

import pytest

from kw_yt_transcript import cli as cli_mod
from kw_yt_transcript.search import search_corpus


def make_video(root, dirname, video_id, title, segments):
    d = root / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "transcript.json").write_text(json.dumps(segments, ensure_ascii=False), "utf-8")
    (d / "meta.json").write_text(
        json.dumps({"video_id": video_id, "title": title}, ensure_ascii=False), "utf-8"
    )
    return d


@pytest.fixture()
def corpus(tmp_path):
    out = tmp_path / "out"
    make_video(
        out, "aaa_vid00000001", "vid00000001", "Первое видео",
        [
            {"text": "Привет, это тестовый сегмент.", "start": 0.0, "duration": 2.0},
            {"text": "Продолжение без совпадений.", "start": 5.0, "duration": 2.0},
            {"text": "Снова тестовый пример здесь.", "start": 100.0, "duration": 2.0},
        ],
    )
    make_video(
        out, "bbb_vid00000002", "vid00000002", "Второе видео",
        [
            {"text": "Один тестовый сегмент.", "start": 10.0, "duration": 2.0},
            {"text": "Что-то совсем другое.", "start": 50.0, "duration": 2.0},
        ],
    )
    return out


def test_search_finds_case_insensitive(corpus):
    res = search_corpus(corpus, "ТЕСТОВЫЙ")
    assert {r["video_id"] for r in res} == {"vid00000001", "vid00000002"}


def test_search_ranking_by_hits_desc(corpus):
    res = search_corpus(corpus, "тестовый")
    assert res[0]["video_id"] == "vid00000001"  # 2 прямых вхождения против 1
    assert len(res[0]["hits"]) >= 2


def test_search_context_neighbors(corpus):
    res = search_corpus(corpus, "тестовый", context_sec=10.0)
    by_id = {r["video_id"]: r for r in res}
    texts = [h["text"] for h in by_id["vid00000001"]["hits"]]
    assert "Продолжение без совпадений." in texts  # 5.0 в ±10с от 0.0
    assert not any("Снова" in t for t in texts if "Продолжение" in t)
    far = search_corpus(corpus, "продолжение", context_sec=1.0)
    assert all(len(r["hits"]) == 1 for r in far)


def test_search_context_zero_only_matches(corpus):
    res = search_corpus(corpus, "тестовый", context_sec=0)
    assert [len(r["hits"]) for r in res] == [2, 1]


def test_search_limit_counts_videos(corpus):
    res = search_corpus(corpus, "тестовый", limit=1)
    assert len(res) == 1 and res[0]["video_id"] == "vid00000001"


def test_search_empty_query_raises(corpus):
    with pytest.raises(ValueError, match="Пустой"):
        search_corpus(corpus, "   ")


def test_search_missing_root_no_crash(tmp_path):
    assert search_corpus(tmp_path / "нет", "тест") == []


def test_search_hit_shape(corpus):
    (res,) = search_corpus(corpus, "продолжение", context_sec=0)
    assert set(res) == {"video_id", "title", "dir", "direct_count", "hits"}
    assert res["title"] == "Первое видео"
    assert res["direct_count"] == 1
    assert res["hits"] == [
        {"start": 5.0, "text": "Продолжение без совпадений.", "direct": True}
    ]


def test_search_marks_direct_and_context(corpus):
    (res,) = search_corpus(corpus, "продолжение", context_sec=10.0)
    by_start = {h["start"]: h["direct"] for h in res["hits"]}
    assert by_start[5.0] is True
    assert by_start[0.0] is False
    assert res["direct_count"] == 1


def test_search_window_boundary_included(tmp_path):
    out = tmp_path / "out"
    d = out / "v_vid00000009"
    d.mkdir(parents=True)
    d.joinpath("transcript.json").write_text(
        json.dumps(
            [
                {"text": "маркер тут", "start": 0.0, "duration": 1.0},
                {"text": "ровно на границе", "start": 15.0, "duration": 1.0},
                {"text": "далеко", "start": 15.1, "duration": 1.0},
            ]
        ),
        encoding="utf-8",
    )
    res = search_corpus(out, "маркер", context_sec=15.0)
    assert [h["start"] for h in res[0]["hits"]] == [0.0, 15.0]
    res2 = search_corpus(out, "маркер", context_sec=14.9)
    assert [h["start"] for h in res2[0]["hits"]] == [0.0]


def test_cli_search_exit_0_and_ru_output(corpus, capsys):
    assert cli_mod.main(["search", "тестовый", "--in", str(corpus)]) == 0
    out = capsys.readouterr().out
    assert "Первое видео" in out and "Второе видео" in out
    assert "00:00" in out and "совпадений" in out
    assert "  > 00:00" in out, "прямые вхождения помечены >"
    assert "\n    00:05" in out, "контекст — без >"


def test_cli_search_exit_1_when_missing(corpus, capsys):
    assert cli_mod.main(["search", "абракадабра", "--in", str(corpus)]) == 1
    assert "не найдено" in capsys.readouterr().out


def test_cli_search_bad_dir_exit_2(tmp_path):
    assert cli_mod.main(["search", "тест", "--in", str(tmp_path / "нет")]) == 2


def test_cli_search_bad_numbers_exit_2(corpus):
    assert cli_mod.main(["search", "тест", "--in", str(corpus), "--limit", "0"]) == 2
    assert cli_mod.main(["search", "тест", "--in", str(corpus), "--context", "zzz"]) == 2
