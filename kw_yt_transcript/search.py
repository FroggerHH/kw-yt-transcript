"""Поиск по корпусу сохранённых транскриптов (v0.2, Волна 2).

Только stdlib, без сети. Читает ``*/transcript.json`` (+ ``meta.json``
для названий) под корнем корпуса.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _mmss(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    try:
        total = max(0, int(seconds))
    except Exception:
        return "—"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _load_segments(tpath: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(tpath.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                {
                    "text": str(item.get("text", "")),
                    "start": float(item.get("start", 0.0)),
                }
            )
        except Exception:
            continue
    return out


def _meta_for(video_dir: Path) -> tuple[str | None, str]:
    """(video_id, title) из meta.json; fallback — имя папки."""
    try:
        record = json.loads((video_dir / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        record = {}
    title = record.get("title") if isinstance(record, dict) else None
    video_id = record.get("video_id") if isinstance(record, dict) else None
    name = video_dir.name
    if video_id is None and "_" in name:
        video_id = name.rsplit("_", 1)[-1] or None
    return video_id, str(title or name)


def format_ts(seconds: float) -> str:
    """Таймкод реплики для CLI-вывода (mm:ss)."""
    return _mmss(seconds)


def search_corpus(
    root: str | Path,
    query: str,
    context_sec: float = 15.0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Найти вхождения подстроки в транскриптах корпуса.

    :param root: корень корпуса (папка с ``index.json`` и папками видео).
    :param query: запрос; регистронезависимо, пробелы по краям игнорируются.
    :param context_sec: соседние реплики в ±секундах добавляются к хитам.
    :param limit: максимум видео в выдаче.
    :return: [{video_id, title, dir, hits: [{start, text}]}], видео —
        по числу прямых вхождений (desc), лимит — по числу видео.
    :raises ValueError: пустой запрос, плохой limit.
    """
    q = (query or "").strip()
    if not q:
        raise ValueError("Пустой поисковый запрос: укажите слово или фразу.")
    try:
        lim = int(limit)
    except Exception:
        raise ValueError(f"Неверный лимит: {limit!r}.") from None
    if lim < 1:
        raise ValueError(f"Неверный лимит: {limit!r} (нужен >= 1).")
    try:
        ctx = max(0.0, float(context_sec))
    except Exception:
        raise ValueError(f"Неверный контекст: {context_sec!r}.") from None

    qfold = q.casefold()
    root_path = Path(root)
    try:
        tpaths = sorted(root_path.glob("*/transcript.json"))
    except Exception:
        return []
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for tpath in tpaths:
        video_dir = tpath.parent
        segments = _load_segments(tpath)
        if not segments:
            continue
        direct = [i for i, s in enumerate(segments) if qfold in s["text"].casefold()]
        if not direct:
            continue
        starts = [s["start"] for s in segments]
        keep: set[int] = set(direct)
        for i in direct:
            for j, st in enumerate(starts):
                if j != i and abs(st - starts[i]) <= ctx:
                    keep.add(j)
        hits = [
            {"start": segments[j]["start"], "text": segments[j]["text"]}
            for j in sorted(keep, key=lambda j: starts[j])
        ]
        video_id, title = _meta_for(video_dir)
        scored.append(
            (
                len(direct),
                title.casefold(),
                {
                    "video_id": video_id,
                    "title": title,
                    "dir": video_dir.name,
                    "hits": hits,
                },
            )
        )
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [entry for _, _, entry in scored[:lim]]
