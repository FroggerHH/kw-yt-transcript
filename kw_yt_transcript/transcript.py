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


def _detect_origin(api: Any, video_id: str, langs: list[str]) -> str:
    """origin через list().find_transcript().is_generated; неизвестно → 'manual'.

    fetch() предпочитает ручные субтитры, поэтому 'manual' — честный дефолт,
    если список недоступен, а fetch сработал.
    """
    try:
        transcript = _first_available(api.list(video_id), langs)
    except Exception:
        transcript = None
    if transcript is None:
        return "manual"
    return _origin_of(transcript)


def get_transcript(
    video_id: str,
    languages: tuple[str, ...] | list[str] = ("ru", "en"),
    api_factory: Callable[[], Any] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Получить субтитры видео.

    :param video_id: id видео YouTube.
    :param languages: языки по приоритету.
    :param api_factory: callable() -> объект с методами
        ``fetch(video_id, languages=[...])`` (результат — с ``to_raw_data()``)
        и ``list(video_id)`` (результат — с ``find_transcript()``,
        итерируемый, элементы — с ``is_generated`` и ``fetch()``).
        По умолчанию — реальный ``YouTubeTranscriptApi()``; в тестах — stub.
    :return: (segments [{text, start, duration}], origin 'manual'|'auto').
    :raises NoTranscriptError: субтитров нет ни на одном языке.
    """
    if api_factory is None:
        from youtube_transcript_api import YouTubeTranscriptApi

        api_factory = YouTubeTranscriptApi
    api = api_factory()
    langs = list(languages)

    try:
        segments = _normalize(api.fetch(video_id, languages=langs).to_raw_data())
    except Exception:
        # Запрошенных языков нет — берём первый доступный из списка.
        try:
            transcript = _first_available(api.list(video_id), langs)
        except Exception as e:
            raise NoTranscriptError(
                f"Для видео {video_id!r} субтитры не найдены. "
                "Распознавание речи (Whisper) появится в Фазе 3."
            ) from e
        if transcript is None:
            raise NoTranscriptError(
                f"Для видео {video_id!r} субтитры не найдены. "
                "Распознавание речи (Whisper) появится в Фазе 3."
            )
        try:
            segments = _normalize(transcript.fetch().to_raw_data())
        except Exception as e:
            raise NoTranscriptError(
                f"Не удалось загрузить субтитры видео {video_id!r}: {e}"
            ) from e
        return segments, _origin_of(transcript)

    return segments, _detect_origin(api, video_id, langs)
