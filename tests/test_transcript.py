"""Тесты transcript.get_transcript: без сети, HOME, transcript-библиотеки (stub через api_factory)."""

import json
import sys
from pathlib import Path

import pytest

from kw_yt_transcript.transcript import NoTranscriptError, get_transcript

FIXTURES = Path(__file__).parent / "fixtures"
SEGMENTS = json.loads((FIXTURES / "segments.json").read_text(encoding="utf-8"))


class StubFetched:
    def __init__(self, raw):
        self._raw = raw

    def to_raw_data(self):
        return self._raw


class StubTranscript:
    def __init__(self, language_code, is_generated, raw):
        self.language_code = language_code
        self.is_generated = is_generated
        self._raw = raw

    def fetch(self):
        return StubFetched(self._raw)


class StubTranscriptList:
    def __init__(self, transcripts):
        self._transcripts = transcripts
        self.seen_languages = None

    def find_transcript(self, langs):
        self.seen_languages = list(langs)
        for lang in langs:
            for t in self._transcripts:
                if t.language_code == lang:
                    return t
        raise LookupError(f"Нет субтитров на языках: {langs}")

    def __iter__(self):
        return iter(self._transcripts)


class StubApi:
    """Двойник YouTubeTranscriptApi: list() -> find_transcript() -> fetch()."""

    def __init__(self, by_lang, generated):
        self._by_lang = by_lang
        self._generated = generated
        self.last_list = None

    def list(self, video_id):
        self.last_list = StubTranscriptList(
            [StubTranscript(lang, self._generated.get(lang, False), raw) for lang, raw in self._by_lang.items()]
        )
        return self.last_list


def ru_en_api():
    return StubApi({"ru": SEGMENTS, "en": SEGMENTS}, {"ru": False, "en": True})


def test_ru_priority_and_manual_origin():
    api = ru_en_api()
    segments, origin = get_transcript("dQw4w9WgXcQ", api_factory=lambda: api)
    assert api.last_list.seen_languages == ["ru", "en"]
    assert segments == [
        {"text": s["text"], "start": float(s["start"]), "duration": float(s["duration"])} for s in SEGMENTS
    ]
    assert all(isinstance(s["start"], float) for s in segments)
    assert origin == "manual"


def test_custom_languages_passed_through():
    api = StubApi({"en": SEGMENTS}, {"en": True})
    segments, origin = get_transcript("dQw4w9WgXcQ", languages=("en",), api_factory=lambda: api)
    assert api.last_list.seen_languages == ["en"]
    assert len(segments) == len(SEGMENTS)
    assert origin == "auto"


def test_fallback_to_first_available():
    api = StubApi({"en": SEGMENTS}, {"en": True})
    segments, origin = get_transcript("dQw4w9WgXcQ", languages=("ru", "de"), api_factory=lambda: api)
    assert len(segments) == len(SEGMENTS)
    assert origin == "auto"


def test_no_transcripts_raises_russian():
    api = StubApi({}, {})
    with pytest.raises(NoTranscriptError, match="субтитры"):
        get_transcript("dQw4w9WgXcQ", api_factory=lambda: api)


def test_empty_subtitles_raise():
    api = StubApi({"ru": []}, {"ru": False})
    with pytest.raises(NoTranscriptError, match="пустые"):
        get_transcript("dQw4w9WgXcQ", api_factory=lambda: api)


def test_list_failure_raises_no_transcript():
    class DeadApi(StubApi):
        def list(self, video_id):
            raise RuntimeError("TranscriptsDisabled")

    with pytest.raises(NoTranscriptError, match="субтитры"):
        get_transcript("dQw4w9WgXcQ", api_factory=lambda: DeadApi({}, {}))


def test_no_real_library_imported():
    assert "youtube_transcript_api" not in sys.modules
