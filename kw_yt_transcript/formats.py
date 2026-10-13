"""Форматы вывода SRT/VTT/JSON/TXT/MD/JSONL/CSV (Фаза 2 + v0.2 Волна 4).

Собственная реализация (без ``youtube_transcript_api.formatters``): форматтерам
нужны объекты FetchedTranscript, а у нас плоские dict-сегменты; таймкоды
совпадают с их форматом (``HH:MM:SS,mmm`` / ``HH:MM:SS.mmm``). Своя реализация
также детерминирована и не тянет зависимость в тесты.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from kw_yt_transcript.timefmt import mmss as _mmss

#: Пауза между сегментами (сек), начинающая новый абзац.
PARAGRAPH_GAP = 2.0

#: Длина абзаца (символов), после которой начинается новый абзац.
PARAGRAPH_MAX_LEN = 800

_ORIGIN_LABELS = {"manual": "ручные субтитры", "auto": "автосубтитры", "whisper": "Whisper ASR"}

#: Источники машинного слуха — к их текстам добавляется AI-предупреждение.
_AI_ORIGINS = ("auto", "whisper")

#: Предупреждение о машинном распознавании (report/MD/TXT).
_AI_WARNING = (
    "⚠ Текст распознан ИИ (автосубтитры/Whisper), возможны ошибки — сверьте важное с аудио."
)


def _ai_warning_line(meta: dict[str, Any] | None) -> str:
    """Строка AI-предупреждения, если origin машинный; иначе ``""``."""
    if isinstance(meta, dict) and meta.get("origin") in _AI_ORIGINS:
        return _AI_WARNING
    return ""


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
        start = _srt_ts(seg["start"])
        end = _srt_ts(seg["start"] + seg["duration"])
        cues.append(f"{i}\n{start} --> {end}\n{seg['text']}")
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
    """Читаемый текст: абзацы через пустую строку. Пусто → ``""``.

    При машинном origin (auto/whisper) первая строка — AI-предупреждение.
    """
    body = "\n\n".join(paragraphs(segments))
    warn = _ai_warning_line(meta)
    if warn and body:
        return warn + "\n\n" + body
    return body


def to_jsonl(segments: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> str:
    """JSON Lines: по объекту ``{video_id, title, start, duration, text}`` на строку.

    Удобно для RAG-корпусов (потоковое чтение). Пусто → ``""`` (ноль строк).
    """
    meta = meta or {}
    lines = [
        json.dumps(
            {
                "video_id": meta.get("video_id"),
                "title": meta.get("title"),
                "start": s["start"],
                "duration": s["duration"],
                "text": s["text"],
            },
            ensure_ascii=False,
        )
        for s in segments
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def to_csv(segments: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> str:
    """CSV: шапка ``video_id,title,start,duration,text`` + строки (stdlib csv).

    Пусто → только шапка.
    """
    meta = meta or {}
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["video_id", "title", "start", "duration", "text"])
    for s in segments:
        writer.writerow(
            [meta.get("video_id"), meta.get("title"), s["start"], s["duration"], s["text"]]
        )
    return buf.getvalue()


def to_md(segments: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> str:
    """Markdown: header (title/автор/дата/длительность/источник/статистика) + главы + абзацы."""
    if not segments:
        return ""
    meta = meta or {}
    origin = _ORIGIN_LABELS.get(str(meta.get("origin", "")), str(meta.get("origin", "") or "—"))
    stats = meta.get("stats")
    if not isinstance(stats, dict) or "words" not in stats:
        try:
            from kw_yt_transcript.stats import compute_stats

            stats = compute_stats(segments, meta.get("duration"))
        except Exception:
            stats = {}
    words = stats.get("words", 0) if isinstance(stats, dict) else 0
    reading = stats.get("reading_time_min", 0.0) if isinstance(stats, dict) else 0.0
    try:
        reading_s = f"{float(reading):.1f}"
    except Exception:
        reading_s = "0.0"
    top = stats.get("top_keywords", []) if isinstance(stats, dict) else []
    top3 = ", ".join(str(k.get("word", "")) for k in top[:3] if isinstance(k, dict)) or "—"
    lines = [
        f"# {meta.get('title') or 'Транскрипт'}",
        "",
    ]
    warn = _ai_warning_line(meta)
    if warn:
        lines += [warn, ""]
    lines += [
        f"- Автор: {meta.get('channel') or meta.get('author') or '—'}",
        f"- Дата: {meta.get('upload_date') or '—'}",
        f"- Длительность: {_mmss(meta.get('duration'))}"
        if meta.get("duration") is not None
        else "- Длительность: —",
        f"- Источник текста: {origin}",
        f"- Слов: {words}",
        f"- Время чтения: {reading_s} мин",
        f"- Ключевые слова: {top3}",
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
FORMATS = {
    "srt": to_srt,
    "vtt": to_vtt,
    "json": to_json,
    "txt": to_txt,
    "md": to_md,
    "jsonl": to_jsonl,
    "csv": to_csv,
}
