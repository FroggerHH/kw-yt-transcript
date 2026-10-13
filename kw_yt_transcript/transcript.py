"""Субтитры через youtube-transcript-api (Фаза 2).

Импорт библиотеки ленивый: тесты и ``kw-yt --help`` работают без неё
(реальный API подменяется через ``api_factory``). Субтитров нет —
только исключение :class:`NoTranscriptError`; ASR-fallback сделает Фаза 3.
"""

from __future__ import annotations

from typing import Any, Callable


class NoTranscriptError(Exception):
    """У видео нет субтитров ни на одном языке."""


def _normalize(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """to_raw_data() -> [{text, start, duration}], start/duration — float."""
    return [
        {"text": str(item["text"]), "start": float(item["start"]), "duration": float(item["duration"])}
        for item in raw
    ]


def _origin_of(transcript: Any) -> str:
    return "auto" if getattr(transcript, "is_generated", False) else "manual"


def _first_available(tlist: Any, langs: list[str]) -> Any | None:
    """Транскрипт на первом подходящем языке, иначе первый доступный, иначе None."""
    try:
        return tlist.find_transcript(langs)
    except Exception:
        pass
    try:
        for transcript in tlist:
            return transcript
    except Exception:
        pass
    return None


def _no_subs_message(video_id: str) -> str:
    return (
        f"Для видео {video_id!r} субтитры не найдены. "
        "Уберите --no-fallback-whisper, чтобы попробовать Whisper (pip install .[asr])."
    )


def get_transcript(
    video_id: str,
    languages: tuple[str, ...] | list[str] = ("ru", "en"),
    api_factory: Callable[[], Any] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Получить субтитры видео.

    Один вызов ``list()`` + один ``fetch()``: сначала находим транскрипт
    (заодно узнаём origin), затем качаем его сегменты — объект транскрипта
    переиспользуется, двойного запроса сегментов нет.

    :param video_id: id видео YouTube.
    :param languages: языки по приоритету.
    :param api_factory: callable() -> объект с методом ``list(video_id)``
        (результат — с ``find_transcript()``, итерируемый, элементы —
        с ``is_generated`` и ``fetch()`` с ``to_raw_data()``).
        По умолчанию — реальный ``YouTubeTranscriptApi()``; в тестах — stub.
    :return: (segments [{text, start, duration}], origin 'manual'|'auto').
    :raises NoTranscriptError: субтитров нет ни на одном языке или они пустые.
    """
    if api_factory is None:
        from youtube_transcript_api import YouTubeTranscriptApi

        api_factory = YouTubeTranscriptApi
    api = api_factory()
    langs = list(languages)

    try:
        tlist = api.list(video_id)
    except Exception as e:
        raise NoTranscriptError(_no_subs_message(video_id)) from e
    transcript_obj = _first_available(tlist, langs)
    if transcript_obj is None:
        raise NoTranscriptError(_no_subs_message(video_id))
    try:
        segments = _normalize(transcript_obj.fetch().to_raw_data())
    except Exception as e:
        raise NoTranscriptError(
            f"Не удалось загрузить субтитры видео {video_id!r}: {e}"
        ) from e
    if not segments:
        raise NoTranscriptError(f"Для видео {video_id!r} получены пустые субтитры.")
    return segments, _origin_of(transcript_obj)
