"""Запись результатов, index.json (Фаза 3 + v0.2 Волна 7).

Локальные файлы + best-effort скачивание обложки (thumbnail.jpg) по URL
из метаданных: неудача молча пропускается (видео всё равно пишется).
Частичные ошибки batch не валят: неуспешные видео фиксируются
в index.json с текстом ошибки.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kw_yt_transcript import __version__
from kw_yt_transcript.formats import FORMATS
from kw_yt_transcript.report import render_index, render_report
from kw_yt_transcript.stats import compute_stats

#: Имя формата -> имя файла транскрипта.
TRANSCRIPT_FILENAMES = {
    "srt": "transcript.srt",
    "vtt": "transcript.vtt",
    "json": "transcript.json",
    "txt": "transcript.txt",
    "md": "transcript.md",
    "jsonl": "transcript.jsonl",
    "csv": "transcript.csv",
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


def _is_complete(video_dir: Path) -> bool:
    """Готовая папка: meta.json (со stats и origin) + transcript.json + report.html."""
    if not ((video_dir / "transcript.json").is_file() and (video_dir / "report.html").is_file()):
        return False
    try:
        record = json.loads((video_dir / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    return (
        isinstance(record, dict)
        and isinstance(record.get("stats"), dict)
        and bool(record.get("origin"))
    )


def find_ready(out_dir: str | Path, video_id: str | None) -> Path | None:
    """Найти готовую папку видео ``*_<video_id>`` (для --resume).

    Готовая = meta.json (со stats и origin) + transcript.json + report.html.

    :return: путь к папке или None.
    """
    if not video_id:
        return None
    base = Path(out_dir)
    try:
        if not base.is_dir():
            return None
        for cand in sorted(base.glob(f"*_{video_id}")):
            if cand.is_dir() and (cand / "meta.json").is_file() and _is_complete(cand):
                return cand
    except Exception:
        return None
    return None


def _resolve_formats(formats_sel: str) -> list[str]:
    if formats_sel == "all":
        return list(FORMATS)
    if formats_sel in FORMATS:
        return [formats_sel]
    raise ValueError(
        f"Неизвестный формат: {formats_sel!r}. Доступны: all, {', '.join(FORMATS)}."
    )


def _atomic_write_text(path: Path, content: str) -> None:
    """Атомарная запись: сначала *.tmp, затем os.replace; мусор чистим."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


#: Лимит размера обложки: 5 МБ (защита от мусора по URL).
_THUMB_MAX_BYTES = 5 * 1024 * 1024


def _best_thumbnail_url(thumbnails: Any) -> str | None:
    """Выбрать URL наибольшей обложки (по width, иначе последняя с url)."""
    if not isinstance(thumbnails, list):
        return None
    best: str | None = None
    best_w = -1
    for t in thumbnails:
        if not isinstance(t, dict) or not t.get("url"):
            continue
        try:
            w = int(t.get("width") or 0)
        except Exception:
            w = 0
        if w >= best_w:
            best_w = w
            best = str(t["url"])
    return best


def fetch_thumbnail(url: str, dest: Path, opener=None, timeout: float = 20.0) -> bool:
    """Скачать обложку по URL в dest. Только image/*, лимит размера.

    :param opener: инъекция для тестов ``(url, timeout) -> bytes``.
    :return: True если файл записан (атомарно), иначе False (тихо).
    """
    try:
        if opener is not None:
            data = opener(url, timeout)
        else:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                ctype = (resp.headers.get_content_type() if hasattr(resp, "headers") else "") or ""
                if ctype and not ctype.startswith("image/"):
                    return False
                data = resp.read(_THUMB_MAX_BYTES + 1)
        if not isinstance(data, (bytes, bytearray)) or not data:
            return False
        if len(data) > _THUMB_MAX_BYTES:
            return False
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_bytes(bytes(data))
        os.replace(tmp, dest)
        return True
    except Exception:
        try:
            dest.with_name(dest.name + ".tmp").unlink(missing_ok=True)
        except OSError:
            pass
        return False


def write_video(
    out_dir: str | Path,
    meta: dict[str, Any],
    segments: list[dict[str, Any]],
    origin: str,
    formats_sel: str = "all",
    transcript_lang: str | None = None,
    asr_model: str | None = None,
    thumb_opener=None,
) -> dict[str, str]:
    """Записать папку ``<slug>_<video_id>/``: meta.json + файлы транскрипта.

    В meta.json дописываются transcript_lang, fetched_at (UTC ISO),
    tool_version и asr_model (только при origin 'whisper').
    Обложка thumbnail.jpg качается best-effort (неудача — тихо, без неё);
    имя фиксируется в meta.json (``thumbnail_file``).
    Все файлы пишутся атомарно (*.tmp + os.replace).

    :param thumb_opener: инъекция ``(url, timeout) -> bytes`` для тестов.
    :return: словарь путей {dir, meta, report, thumb?, srt?, vtt?, json?, txt?, md?} (строки).
    """
    video_id = meta.get("video_id") or "noid"
    video_dir = Path(out_dir) / f"{slug(meta.get('title'), video_id)}_{video_id}"
    video_dir.mkdir(parents=True, exist_ok=True)

    record = dict(meta)
    record["origin"] = origin
    record["transcript_lang"] = transcript_lang
    record["fetched_at"] = datetime.now(UTC).isoformat()
    record["tool_version"] = __version__
    if origin == "whisper" and asr_model:
        record["asr_model"] = asr_model
    try:
        record["stats"] = compute_stats(segments, record.get("duration"))
    except Exception:
        record["stats"] = {
            "words": 0,
            "chars": 0,
            "reading_time_min": 0.0,
            "speaking_wpm": None,
            "top_keywords": [],
        }
    thumb_path: Path | None = None
    thumb_url = _best_thumbnail_url(record.get("thumbnails"))
    if thumb_url:
        candidate = video_dir / "thumbnail.jpg"
        if fetch_thumbnail(thumb_url, candidate, opener=thumb_opener):
            record["thumbnail_file"] = "thumbnail.jpg"
            thumb_path = candidate
        else:
            record["thumbnail_file"] = None
    else:
        record["thumbnail_file"] = None
    meta_path = video_dir / "meta.json"
    _atomic_write_text(meta_path, json.dumps(record, ensure_ascii=False, indent=2))

    md_meta = dict(meta)
    md_meta["origin"] = origin
    md_meta["stats"] = record["stats"]
    paths: dict[str, str] = {"dir": str(video_dir), "meta": str(meta_path)}
    for name in _resolve_formats(formats_sel):
        content = FORMATS[name](segments, md_meta)
        file_path = video_dir / TRANSCRIPT_FILENAMES[name]
        _atomic_write_text(file_path, content)
        paths[name] = str(file_path)
    try:
        report_meta = dict(record)
        try:
            present = sorted(
                p.name for p in video_dir.iterdir() if p.is_file() and not p.name.endswith(".tmp")
            )
        except OSError:
            present = []
        if "report.html" not in present:
            present.append("report.html")
        report_html = render_report(report_meta, segments, record["stats"], origin, files=present)
    except Exception:
        report_html = (
            "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<title>Отчёт</title>\n</head>\n<body><p>Отчёт недоступен.</p>\n</body>\n</html>\n"
        )
    report_path = video_dir / "report.html"
    _atomic_write_text(report_path, report_html)
    paths["report"] = str(report_path)
    if thumb_path is not None:
        paths["thumb"] = str(thumb_path)
    return paths


def write_index(
    out_dir: str | Path,
    results: list[dict[str, Any]],
    playlist_url: str | None = None,
) -> Path:
    """Записать сводный index.json: {_type, playlist_url, entries, failed}.

    :param results: список {meta|None, dir|None (имя папки), origin|None,
        transcript_lang|None, error|None}.
    :param playlist_url: задан -> _type 'playlist', иначе 'batch'.
    """
    entries = []
    base = Path(out_dir)
    for r in results:
        meta = r.get("meta") or {}
        entries.append(
            {
                "video_id": meta.get("video_id"),
                "title": meta.get("title"),
                "dir": r.get("dir"),
                "origin": r.get("origin"),
                "transcript_lang": r.get("transcript_lang"),
                "thumbnail_file": _entry_thumb(base, r.get("dir")),
                "error": r.get("error"),
            }
        )
    index = {
        "_type": "playlist" if playlist_url else "batch",
        "playlist_url": playlist_url,
        "entries": entries,
        "failed": sum(1 for r in results if r.get("error")),
    }
    index_path = Path(out_dir) / "index.json"
    _atomic_write_text(index_path, json.dumps(index, ensure_ascii=False, indent=2))
    try:
        _write_index_html(Path(out_dir), results)
    except OSError:
        raise
    except Exception:
        pass
    return index_path


def _entry_thumb(out_dir: Path, dirname: str | None) -> str | None:
    """Прочитать thumbnail_file из <out>/<dir>/meta.json; нет файла -> None.

    Имя возвращается только если файл физически существует (защита от битого
    <img> после ручного удаления thumbnail.jpg).
    """
    if not dirname:
        return None
    try:
        record = json.loads((out_dir / dirname / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    thumb = record.get("thumbnail_file") if isinstance(record, dict) else None
    if not isinstance(thumb, str) or not thumb:
        return None
    try:
        if not (out_dir / dirname / thumb).is_file():
            return None
    except Exception:
        return None
    return thumb


def _entry_stats(out_dir: Path, dirname: str | None) -> tuple[Any, Any]:
    """Прочитать stats.words из <out>/<dir>/meta.json; нет файла -> (None, None)."""
    if not dirname:
        return None, None
    try:
        record = json.loads((out_dir / dirname / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        return None, None
    stats = record.get("stats") or {}
    return stats.get("words"), record.get("duration")


def _write_index_html(out_dir: Path, results: list[dict[str, Any]]) -> None:
    entries_info: list[dict[str, Any]] = []
    total_words = 0
    total_sec = 0.0
    ok = 0
    for r in results:
        meta = r.get("meta") or {}
        dirname = r.get("dir")
        words, dur = _entry_stats(out_dir, dirname)
        if words is None:
            words = "—"
        else:
            try:
                total_words += int(words)
            except Exception:
                pass
        duration = meta.get("duration")
        if duration is None:
            duration = dur
        try:
            if duration is not None and not r.get("error"):
                total_sec += float(duration)
        except Exception:
            pass
        if not r.get("error"):
            ok += 1
        entries_info.append(
            {
                "title": meta.get("title"),
                "video_id": meta.get("video_id"),
                "dir": dirname,
                "author": meta.get("channel") or meta.get("author"),
                "duration": duration,
                "words": words,
                "origin": r.get("origin"),
                "thumbnail_file": _entry_thumb(out_dir, dirname),
            }
        )
    corpus = {"n_videos": ok, "total_words": total_words, "total_min": total_sec / 60.0}
    _atomic_write_text(out_dir / "index.html", render_index(entries_info, corpus))
