"""Запись результатов, index.json (Фаза 3).

Только локальные файлы, без сети. Частичные ошибки batch не валят:
неуспешные видео фиксируются в index.json с текстом ошибки.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from kw_yt_transcript.formats import FORMATS

#: Имя формата -> имя файла транскрипта.
TRANSCRIPT_FILENAMES = {
    "srt": "transcript.srt",
    "vtt": "transcript.vtt",
    "json": "transcript.json",
    "txt": "transcript.txt",
    "md": "transcript.md",
}

#: Транслитерация кириллицы для slug (строчные; остальное вычищается regex).
_RU_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

#: Максимальная длина slug.
SLUG_MAX_LEN = 60


def slug(title: str | None, video_id: str) -> str:
    """Заголовок -> безопасное имя папки: транслит, [a-z0-9-], обрезка 60.

    Пустой результат -> video_id.
    """
    base = "".join(_RU_MAP.get(ch, ch) for ch in (title or "").lower())
    base = re.sub(r"[\s_]+", "-", base)
    base = re.sub(r"[^a-z0-9-]", "", base)
    base = re.sub(r"-{2,}", "-", base).strip("-")
    base = base[:SLUG_MAX_LEN].rstrip("-")
    return base or video_id


def _resolve_formats(formats_sel: str) -> list[str]:
    if formats_sel == "all":
        return list(FORMATS)
    if formats_sel in FORMATS:
        return [formats_sel]
    raise ValueError(
        f"Неизвестный формат: {formats_sel!r}. Доступны: all, {', '.join(FORMATS)}."
    )


def write_video(
    out_dir: str | Path,
    meta: dict[str, Any],
    segments: list[dict[str, Any]],
    origin: str,
    formats_sel: str = "all",
) -> dict[str, str]:
    """Записать папку ``<slug>_<video_id>/``: meta.json + файлы транскрипта.

    :return: словарь путей {dir, meta, srt?, vtt?, json?, txt?, md?} (строки).
    """
    video_id = meta.get("video_id") or "noid"
    video_dir = Path(out_dir) / f"{slug(meta.get('title'), video_id)}_{video_id}"
    video_dir.mkdir(parents=True, exist_ok=True)

    record = dict(meta)
    record["origin"] = origin
    meta_path = video_dir / "meta.json"
    meta_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    md_meta = dict(meta)
    md_meta["origin"] = origin
    paths: dict[str, str] = {"dir": str(video_dir), "meta": str(meta_path)}
    for name in _resolve_formats(formats_sel):
        content = FORMATS[name](segments, md_meta)
        file_path = video_dir / TRANSCRIPT_FILENAMES[name]
        file_path.write_text(content, encoding="utf-8")
        paths[name] = str(file_path)
    return paths


def write_index(
    out_dir: str | Path,
    results: list[dict[str, Any]],
    playlist_url: str | None = None,
) -> Path:
    """Записать сводный index.json: {_type, entries, failed}.

    :param results: список {meta|None, dir|None (имя папки), origin|None, error|None}.
    :param playlist_url: задан -> _type 'playlist', иначе 'batch'.
    """
    entries = []
    for r in results:
        meta = r.get("meta") or {}
        entries.append(
            {
                "video_id": meta.get("video_id"),
                "title": meta.get("title"),
                "dir": r.get("dir"),
                "origin": r.get("origin"),
                "error": r.get("error"),
            }
        )
    index = {
        "_type": "playlist" if playlist_url else "batch",
        "entries": entries,
        "failed": sum(1 for r in results if r.get("error")),
    }
    index_path = Path(out_dir) / "index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path
