"""Фрагменты видео --from/--to (Волна 21, SPEC пп.3/5/18).

Только stdlib. Границы — `mm:ss`, `hh:mm:ss` или секунды (`parse_ts`);
реплики отбираются пересечением с интервалом (`clip_segments`).
"""

from __future__ import annotations

from typing import Any

from kw_yt_transcript.timefmt import mmss as _mmss


def parse_ts(s: str) -> float:
    """Строка времени -> секунды: ``mm:ss``, ``hh:mm:ss``, ``90``, ``1.5``.

    :raises ValueError: мусор, пусто, отрицательное — с русским текстом.
    """
    raw = s.strip() if isinstance(s, str) else ""
    if not raw:
        raise ValueError(f"Непонятное время {s!r}: ожидается mm:ss, hh:mm:ss или секунды.")
    if ":" in raw:
        parts = raw.split(":")
        if len(parts) not in (2, 3) or not all(p.strip() for p in parts):
            raise ValueError(f"Непонятное время {raw!r}: ожидается mm:ss, hh:mm:ss или секунды.")
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            raise ValueError(
                f"Непонятное время {raw!r}: ожидается mm:ss, hh:mm:ss или секунды."
            ) from None
        if any(n < 0 for n in nums):
            raise ValueError(f"Время не может быть отрицательным: {raw!r}.")
        if len(nums) == 2:
            minutes, seconds = nums
            return minutes * 60.0 + seconds
        hours, minutes, seconds = nums
        return hours * 3600.0 + minutes * 60.0 + seconds
    try:
        total = float(raw)
    except ValueError:
        raise ValueError(
            f"Непонятное время {raw!r}: ожидается mm:ss, hh:mm:ss или секунды."
        ) from None
    if total < 0:
        raise ValueError(f"Время не может быть отрицательным: {raw!r}.")
    return total


def clip_segments(segments: list[dict], frm: float, to: float) -> list[dict]:
    """Реплики, пересекающие интервал [frm, to): ``start < to`` и ``end > frm``.

    Реплики возвращаются как есть (duration исходные, без разрезания) —
    честнее обрезанных таймкодов. Битые записи пропускаются молча.

    :raises ValueError: в диапазоне нет ни одной реплики.
    """
    out = []
    for s in segments or []:
        if not isinstance(s, dict):
            continue
        try:
            start_raw: Any = s.get("start")
            dur_raw: Any = s.get("duration")
            start = float(start_raw)
            end = start + float(dur_raw)
        except (TypeError, ValueError):
            continue
        if start < to and end > frm:
            out.append(s)
    if not out:
        raise ValueError(f"В диапазоне {_mmss(frm)}–{_mmss(to)} нет реплик.")
    return out


def section_key(frm: float, to: float) -> str:
    """Ключ фрагмента для суффикса папки: ``part0130-0245`` (mmss без двоеточий)."""
    return f"part{_mmss(frm).replace(':', '')}-{_mmss(to).replace(':', '')}"
