"""Сводный экспорт корпуса (v0.2 Волна 5).

Склеивает ``*/transcript.json`` корпуса в один ``corpus.jsonl``/``corpus.csv``
для RAG и анализа + пишет ``summary.json`` со счётчиками. Только stdlib,
без сети. Запись атомарная (``*.tmp`` + ``os.replace``), как в outputs/cache.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kw_yt_transcript import __version__
from kw_yt_transcript.formats import to_jsonl
from kw_yt_transcript.stats import compute_stats

#: Форматы сводного экспорта.
EXPORT_FORMATS = ("jsonl", "csv")


def collect_corpus(root: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Собрать видео корпуса: ([{video_id,title,dir,segments,origin,...}], [skipped]).

    Порядок детерминирован (по имени папки). Папка без ``transcript.json``
    или с битым JSON — в ``skipped`` с текстом ошибки, а не падением.
    """
    root_path = Path(root)
    videos: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for child in sorted(root_path.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        tpath = child / "transcript.json"
        if not tpath.is_file():
            skipped.append({"dir": child.name, "error": "нет transcript.json"})
            continue
        try:
            segments = json.loads(tpath.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            skipped.append({"dir": child.name, "error": f"transcript.json не читается: {e}"})
            continue
        if not isinstance(segments, list):
            skipped.append({"dir": child.name, "error": "transcript.json — не список"})
            continue
        meta: dict[str, Any] = {}
        mpath = child / "meta.json"
        if mpath.is_file():
            try:
                loaded = json.loads(mpath.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    meta = loaded
            except (OSError, ValueError):
                pass
        videos.append(
            {
                "video_id": meta.get("video_id"),
                "title": meta.get("title"),
                "dir": child.name,
                "origin": meta.get("origin"),
                "transcript_lang": meta.get("transcript_lang"),
                "segments": segments,
            }
        )
    return videos, skipped


def export_corpus(root: str | Path, out_path: str | Path, fmt: str = "jsonl") -> dict[str, Any]:
    """Склеить корпус в один файл. Возвращает summary (см. ``write_summary``)."""
    if fmt not in EXPORT_FORMATS:
        raise ValueError(
            f"Неизвестный формат экспорта: {fmt!r}. Доступны: {', '.join(EXPORT_FORMATS)}."
        )
    videos, skipped = collect_corpus(root)
    if not videos:
        raise ValueError("В корпусе нет транскриптов (*/transcript.json). Нечего экспортировать.")
    out = Path(out_path)
    if fmt == "jsonl":
        chunks = [
            to_jsonl(
                v["segments"],
                {"video_id": v["video_id"], "title": v["title"]},
            )
            for v in videos
        ]
        content = "".join(chunks)
    else:
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["video_id", "title", "start", "duration", "text"])
        for v in videos:
            for s in v["segments"]:
                writer.writerow([v["video_id"], v["title"], s["start"], s["duration"], s["text"]])
        content = buf.getvalue()
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(out)
    n_segments = sum(len(v["segments"]) for v in videos)
    total_words = 0
    by_origin: dict[str, int] = {}
    video_rows = []
    for v in videos:
        try:
            words = int(compute_stats(v["segments"], None).get("words", 0))
        except Exception:
            words = 0
        total_words += words
        origin = str(v.get("origin") or "unknown")
        by_origin[origin] = by_origin.get(origin, 0) + 1
        video_rows.append(
            {
                "video_id": v["video_id"],
                "title": v["title"],
                "dir": v["dir"],
                "segments": len(v["segments"]),
                "words": words,
                "origin": v.get("origin"),
            }
        )
    return {
        "tool": f"kw-yt {__version__}",
        "created_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "corpus_file": out.name,
        "format": fmt,
        "n_videos": len(videos),
        "n_segments": n_segments,
        "total_words": total_words,
        "by_origin": by_origin,
        "skipped": skipped,
        "videos": video_rows,
    }


def write_summary(summary: dict[str, Any], path: str | Path) -> Path:
    """Записать summary.json атомарно. Возвращает путь."""
    out = Path(path)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    return out
