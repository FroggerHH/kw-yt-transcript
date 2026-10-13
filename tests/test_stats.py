"""Тесты stats.compute_stats. Только stdlib, без сети."""

from kw_yt_transcript.stats import EN_STOPWORDS, RU_STOPWORDS, compute_stats


def test_empty_segments_no_crash():
    s = compute_stats([], None)
    assert s["words"] == 0
    assert s["chars"] == 0
    assert s["reading_time_min"] == 0.0
    assert s["speaking_wpm"] is None
    assert s["top_keywords"] == []


def test_ru_words_and_reading_time():
    segs = [{"text": "Привет мир тестовое видео", "start": 0.0, "duration": 60.0}]
    s = compute_stats(segs, 372.0)
    assert s["words"] == 4
    assert s["chars"] == len("Привет мир тестовое видео")
    assert abs(s["reading_time_min"] - 4 / 180) < 1e-9


def test_en_keywords_and_stopwords_filtered():
    segs = [
        {"text": "the cat and the dog", "start": 0.0, "duration": 10.0},
        {"text": "Cat runs fast", "start": 10.0, "duration": 10.0},
    ]
    s = compute_stats(segs, None, top_n=10)
    words = {k["word"]: k["count"] for k in s["top_keywords"]}
    assert "the" not in words and "and" not in words
    assert words.get("cat") == 2
    assert len(RU_STOPWORDS) >= 50 and len(EN_STOPWORDS) >= 50


def test_ru_stopwords_filtered():
    segs = [{"text": "это тестовое видео и оно большое", "start": 0.0, "duration": 5.0}]
    s = compute_stats(segs, None)
    words = [k["word"] for k in s["top_keywords"]]
    assert "это" not in words and "оно" not in words
    assert "тестовое" in words


def test_speaking_wpm_by_span():
    segs = [
        {"text": "раз два три", "start": 0.0, "duration": 10.0},
        {"text": "четыре пять шесть", "start": 50.0, "duration": 10.0},
    ]
    s = compute_stats(segs, None)
    # 6 слов за 60 сек span -> 6 wpm
    assert s["speaking_wpm"] is not None
    assert abs(s["speaking_wpm"] - 6.0) < 1e-9


def test_wpm_none_without_spans():
    assert compute_stats([], 100.0)["speaking_wpm"] is None
    zero = [{"text": "а б в", "start": 5.0, "duration": 0.0}]
    assert compute_stats(zero, None)["speaking_wpm"] is None


def test_short_tokens_ignored():
    s = compute_stats([{"text": "я а б в г он", "start": 0.0, "duration": 1.0}], None)
    assert s["top_keywords"] == []
    assert s["words"] == 6
