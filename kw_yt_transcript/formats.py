"""Форматы вывода SRT/VTT/JSON/TXT/MD (Фаза 2).

Собственная реализация (без ``youtube_transcript_api.formatters``): форматтерам
нужны объекты FetchedTranscript, а у нас плоские dict-сегменты; таймкоды
совпадают с их форматом (``HH:MM:SS,mmm`` / ``HH:MM:SS.mmm``). Своя реализация
также детерминирована и не тянет зависимость в тесты.
"""

from __future__ import annotations

import json
from typing import Any

#: Пауза между сегментами (сек), начинающая новый абзац.
PARAGRAPH_GAP = 2.0

#: Длина абзаца (символов), после которой начинается новый абзац.
PARAGRAPH_MAX_LEN = 800

_ORIGIN_LABELS = {"manual": "ручные субтитры", "auto": "автосубтитры", "whisper": "Whisper ASR"}


def _ms_total(seconds: float) -> int:
    return max(0, int(round(seconds * 1000)))


def _split_ts(total_ms: int) -> tuple[int, int, int, int]:
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return h, m, s, ms


def _srt_ts(seconds: float) -> str:
    h, m, s, ms = _split_ts(_ms_total(seconds))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _vtt_ts(seconds: float) -> str:
    h, m, s, ms = _split_ts(_ms_total(seconds))
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _mmss(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def paragraphs(segments: list[dict[str, Any]]) -> list[str]:
    """Склейка сегментов в абзацы: разрыв при паузе >2с или длине >800 символов."""
    result: list[str] = []
    current: list[str] = []
    current_len = 0
    prev_end: float | None = None
    for seg in segments:
        gap = seg["start"] - prev_end if prev_end is not None else 0.0
        if current and (gap > PARAGRAPH_GAP or current_len > PARAGRAPH_MAX_LEN):
            result.append(" ".join(current))
            current = []
            current_len = 0
        current.append(seg["text"])
        current_len += len(seg["text"]) + 1
        prev_end = seg["start"] + seg["duration"]
    if current:
        result.append(" ".join(current))
    return result


def to_srt(segments: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> str:
    """SRT с таймкодами ``HH:MM:SS,mmm``. Пусто → ``""``."""
    del meta  # meta для SRT не нужна, аргумент — ради единого интерфейса
    cues = []
    for i, seg in enumerate(segments, 1):
        cues.append(
            f"{i}\n{_srt_ts(seg['start'])} --> {_srt_ts(seg['start'] + seg['duration'])}\n{seg['text']}"
        )
    return "\n\n".join(cues) + ("\n" if cues else "")


def to_vtt(segments: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> str:
    """VTT: ``WEBVTT``-заголовок + ``HH:MM:SS.mmm``. Пусто → только заголовок."""
    del meta
    out = ["WEBVTT", ""]
    for seg in segments:
        out.append(f"{_vtt_ts(seg['start'])} --> {_vtt_ts(seg['start'] + seg['duration'])}")
        out.append(seg["text"])
        out.append("")
    return "\n".join(out)


def to_json(segments: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> str:
    """JSON: list[{start, duration, text}]. Пусто → ``"[]"`` (валидный JSON)."""
    del meta
    return json.dumps(
        [{"start": s["start"], "duration": s["duration"], "text": s["text"]} for s in segments],
        ensure_ascii=False,
        indent=2,
    )


def to_txt(segments: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> str:
    """Читаемый текст: абзацы через пустую строку. Пусто → ``""``."""
    del meta
    return "\n\n".join(paragraphs(segments))


def to_md(segments: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> str:
    """Markdown: header (title/автор/дата/длительность/источник) + главы + абзацы."""
    if not segments:
        return ""
    meta = meta or {}
    origin = _ORIGIN_LABELS.get(str(meta.get("origin", "")), str(meta.get("origin", "") or "—"))
    lines = [
        f"# {meta.get('title') or 'Транскрипт'}",
        "",
        f"- Автор: {meta.get('channel') or meta.get('author') or '—'}",
        f"- Дата: {meta.get('upload_date') or '—'}",
        f"- Длительность: {_mmss(meta.get('duration'))}"
        if meta.get("duration") is not None
        else "- Длительность: —",
        f"- Источник текста: {origin}",
        "",
    ]
    chapters = meta.get("chapters") or []
    if chapters:
        lines += ["## Главы", ""]
        lines += [f"- [{_mmss(ch.get('start_time'))}] {ch.get('title')}" for ch in chapters]
        lines += [""]
    lines.append("\n\n".join(paragraphs(segments)))
    return "\n".join(lines) + "\n"


#: Имя формата -> функция (пригодится batch-записи в Фазе 3).
FORMATS = {"srt": to_srt, "vtt": to_vtt, "json": to_json, "txt": to_txt, "md": to_md}
