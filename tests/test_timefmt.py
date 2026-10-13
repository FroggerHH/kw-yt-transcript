"""Тесты общего формата mm:ss. Без сети."""

from kw_yt_transcript.timefmt import mmss


def test_mmss_basic():
    assert mmss(0.0) == "00:00"
    assert mmss(5) == "00:05"
    assert mmss(65) == "01:05"
    assert mmss(372) == "06:12"


def test_mmss_hours():
    assert mmss(3600) == "1:00:00"
    assert mmss(3723.9) == "1:02:03"


def test_mmss_none_and_garbage():
    assert mmss(None) == "—"
    assert mmss("мусор") == "—"
    assert mmss(-3) == "00:00"
