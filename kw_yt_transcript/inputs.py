"""Входные данные: разбор CLI-входов в список задач (Фаза 1).

Чистые функции, без сети.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Разделители между несколькими входами в одном argv-элементе / строке файла.
_SPLIT_RE = re.compile(r"[,\s;]+")

#: Чистый video id YouTube: ровно 11 символов.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

#: Признаки URL плейлиста.
_PLAYLIST_MARKERS = ("/playlist", "list=")


def _extract_video_id(url: str) -> str | None:
    """Извлечь video id из распространённых форм URL. None — если не вышло."""
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    m = re.search(r"/shorts/([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    m = re.search(r"/live/([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    m = re.search(r"/embed/([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    return None


def _looks_like_url(token: str) -> bool:
    low = token.lower()
    return (
        "://" in token
        or low.startswith("www.")
        or "youtube.com" in low
        or "youtu.be" in low
        or "music.youtube.com" in low
    )


def _classify(token: str) -> dict:
    """Один токен → задача {raw, kind, video_id|url}. Мусор → ValueError."""
    if _VIDEO_ID_RE.match(token):
        return {"raw": token, "kind": "video", "video_id": token}
    if _looks_like_url(token):
        if any(m in token for m in _PLAYLIST_MARKERS):
            return {"raw": token, "kind": "playlist", "url": token}
        job: dict = {"raw": token, "kind": "video", "url": token}
        video_id = _extract_video_id(token)
        if video_id is not None:
            job["video_id"] = video_id
        return job
    raise ValueError(f"Непонятный вход: {token!r}. Ожидается video id, URL видео или URL плейлиста.")


def parse_inputs(items: list[str], from_file: str | None = None) -> list[dict]:
    """Разобрать входы в список задач.

    :param items: позиционные аргументы CLI (каждый может содержать
        несколько входов через запятую/пробел/точку с запятой/перенос строки).
    :param from_file: путь к файлу со списком (по одному входу на строку,
        пустые строки и строки с ``#`` пропускаются).
    :return: список задач ``{raw, kind, video_id|url}``,
        kind — ``"video"`` или ``"playlist"``.
    :raises ValueError: мусорный токен или отсутствующий файл.
    """
    tokens: list[str] = []
    for item in items or []:
        tokens.extend(t for t in _SPLIT_RE.split(item) if t)

    if from_file is not None:
        path = Path(from_file)
        if not path.is_file():
            raise ValueError(f"Файл не найден: {from_file}")
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tokens.extend(t for t in _SPLIT_RE.split(line) if t)

    return [_classify(t) for t in tokens]
