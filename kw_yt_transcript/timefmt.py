"""Общий формат длительности (v0.2, Волна 3a, п.9).

Единственное место формата ``MM:SS`` (часы — ``H:MM:SS``):
используется в formats.py (MD-шапка/главы), report.py (HTML) и
search.py (CLI-вывод). Только stdlib.
"""

from __future__ import annotations


def mmss(seconds: float | None) -> str:
    """Секунды -> ``MM:SS`` (с часами — ``H:MM:SS``); None/мусор -> ``—``."""
    if seconds is None:
        return "—"
    try:
        total = max(0, int(seconds))
    except Exception:
        return "—"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
