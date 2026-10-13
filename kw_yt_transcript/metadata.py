"""Метаданные видео через yt-dlp (Фаза 2).

Сеть — только здесь (и в transcript.py/asr.py). Импорт yt-dlp ленивый,
чтобы ``kw-yt --help`` работал без зависимостей, а тесты — без сети
(реальный YoutubeDL подменяется через ``ydl_factory``).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

#: Голый video id (без URL) нормализуем в watch-URL перед передачей в yt-dlp.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_DEFAULT_OPTS: dict[str, Any] = {"quiet": True, "skip_download": True, "noplaylist": True}


class MetadataError(Exception):
    """Не удалось получить метаданные видео."""


from kw_yt_transcript import cache as cache_mod


def _default_ydl_factory(opts: dict[str, Any]):
    try:
        import yt_dlp
    except ImportError as e:
        raise MetadataError(
            "Нет модуля yt-dlp. Установите его: pip install yt-dlp "
            "(при установке через pipx/uv зависимости ставятся сами)."
        ) from e
    return yt_dlp.YoutubeDL(opts)


def _to_url(url_or_id: str) -> str:
    if _VIDEO_ID_RE.match(url_or_id):
        return f"https://www.youtube.com/watch?v={url_or_id}"
    return url_or_id


def _chapters(info: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for ch in info.get("chapters") or []:
        out.append(
            {
                "start_time": ch.get("start_time"),
                "end_time": ch.get("end_time"),
                "title": ch.get("title"),
            }
        )
    return out


def get_metadata(
    url_or_id: str,
    ydl_factory: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Получить метаданные одиночного видео.

    :param url_or_id: URL видео или голый video id.
    :param ydl_factory: callable(opts) -> context manager с методами
        ``extract_info(url, download=False)`` и ``sanitize_info(info)``.
        По умолчанию — реальный ``yt_dlp.YoutubeDL``; в тестах — stub без сети.
    :raises MetadataError: ошибка yt-dlp, пустой ответ или ``_type == playlist``
        (плейлисты разбираются в Фазе 3, здесь — только single video).
    """
    factory = ydl_factory or _default_ydl_factory
    url = _to_url(url_or_id)
    try:
        hit = cache_mod.cache_get(url_or_id)
    except Exception:
        hit = None
    if isinstance(hit, dict) and hit.get("video_id"):
        return hit
    try:
        with factory(dict(_DEFAULT_OPTS)) as ydl:
            info = ydl.extract_info(url, download=False)
            sanitize = getattr(ydl, "sanitize_info", lambda x: x)
            info = sanitize(info)
    except MetadataError:
        raise
    except Exception as e:
        raise MetadataError(f"Не удалось получить метаданные видео {url_or_id!r}: {e}") from e

    if not info:
        raise MetadataError(f"Пустой ответ yt-dlp для {url_or_id!r}.")
    if info.get("_type") == "playlist":
        raise MetadataError(
            f"Вход {url_or_id!r} — это плейлист, а не одиночное видео. "
            "Используйте URL плейлиста как batch-вход."
        )

    video_id = info.get("id")
    result = {
        "video_id": video_id,
        "url": info.get("webpage_url") or url,
        "title": info.get("title"),
        "channel": info.get("channel"),
        "author": info.get("uploader"),
        "channel_id": info.get("channel_id"),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "description": info.get("description"),
        "chapters": _chapters(info),
        "thumbnails": info.get("thumbnails") or [],
        "tags": info.get("tags") or [],
        "categories": info.get("categories") or [],
        "subtitles_keys": list(info.get("subtitles") or {}),
        "automatic_captions_keys": list(info.get("automatic_captions") or {}),
    }
    try:
        cache_mod.cache_set(url_or_id, result)
    except Exception:
        pass
    return result
