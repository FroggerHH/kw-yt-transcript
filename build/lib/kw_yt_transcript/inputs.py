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

#: Ограничения --from-file (ранняя валидация, пункт G).
_MAX_FILE_BYTES = 1024 * 1024
_MAX_FILE_LINES = 10000


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
    raise ValueError(
        f"Непонятный вход: {token!r}. Ожидается video id, URL видео или URL плейлиста."
    )


def _read_list_file(from_file: str) -> list[str]:
    """Прочитать файл со списком входов: UTF-8, лимиты 1 МБ / 10000 строк."""
    path = Path(from_file)
    if not path.is_file():
        raise ValueError(f"Файл не найден: {from_file}")
    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            raise ValueError(f"Файл {from_file} слишком большой (>1 МБ).")
    except OSError as e:
        raise ValueError(f"Не могу прочитать файл {from_file}: {e}") from e
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"Файл {from_file} не в UTF-8: {e}") from e
    except OSError as e:
        raise ValueError(f"Не могу прочитать файл {from_file}: {e}") from e
    lines = text.splitlines()
    if len(lines) > _MAX_FILE_LINES:
        raise ValueError(f"Файл {from_file}: слишком много строк (>10000).")
    return lines


def _dedupe(jobs: list[dict]) -> list[dict]:
    """Дедуп по нормализованному ключу (video_id или url), порядок сохраняется."""
    seen: set[str] = set()
    out: list[dict] = []
    for job in jobs:
        key = job.get("video_id") or job.get("url") or job.get("raw", "")
        if key in seen:
            continue
        seen.add(key)
        out.append(job)
    return out


def parse_inputs_with_errors(
    items: list[str], from_file: str | None = None
) -> tuple[list[dict], list[str]]:
    """Нестрогий разбор входов: (задачи без дублей, тексты ошибок мусорных токенов).

    Ошибки уровня файла (нет файла, не UTF-8, лимиты) — исключением ValueError,
    как и раньше: это usage-ошибки, а не частичные.
    """
    tokens: list[str] = []
    for item in items or []:
        tokens.extend(t for t in _SPLIT_RE.split(item) if t)

    if from_file is not None:
        for line in _read_list_file(from_file):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tokens.extend(t for t in _SPLIT_RE.split(line) if t)

    jobs: list[dict] = []
    errors: list[str] = []
    for token in tokens:
        try:
            jobs.append(_classify(token))
        except ValueError as e:
            errors.append(str(e))
    return _dedupe(jobs), errors


def parse_inputs(items: list[str], from_file: str | None = None) -> list[dict]:
    """Разобрать входы в список задач.

    :param items: позиционные аргументы CLI (каждый может содержать
        несколько входов через запятую/пробел/точку с запятой/перенос строки).
    :param from_file: путь к файлу со списком (по одному входу на строку,
        пустые строки и строки с ``#`` пропускаются).
    :return: список задач ``{raw, kind, video_id|url}``,
        kind — ``"video"`` или ``"playlist"`` (дубли убраны).
    :raises ValueError: мусорный токен, отсутствующий файл, не UTF-8, лимиты файла.
    """
    jobs, errors = parse_inputs_with_errors(items, from_file)
    if errors:
        raise ValueError(errors[0])
    return jobs
