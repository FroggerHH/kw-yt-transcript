"""Статистика текста транскрипта (v0.2, Волна 1).

Только stdlib. Без сети.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

#: Токены-кандидаты в ключевые слова: буквы ru/en длиной >= 3.
_TOKEN_RE = re.compile(r"[a-zа-яё]{3,}", re.IGNORECASE)

#: Слов чтения в минуту (оценка времени чтения).
READING_WPM = 180

#: Встроенные стоп-слова (русские).
RU_STOPWORDS = frozenset(
    """
    это этот эта эти того этого такой такая такое такие
    как что или для при про без над под уже даже если тоже
    себя всего всех всем всё все весь вся сам сами там тут здесь
    где когда тогда потом теперь сегодня вчера завтра сейчас
    меня тебе себя нас вас них него неё ему ей им они она оно
    был была было были будет будут есть нет да нет ну вот же ли бы
    его её ваш наша ваше наши мои твой свой своя своё свои ко на по
    над меж между через надо можно нельзя очень просто только лишь
    """.split()
)

#: Встроенные стоп-слова (английские).
EN_STOPWORDS = frozenset(
    """
    the and for with that this from have has had been were was are
    you your yours they them their theirs our ours his her hers its
    she him his not but are was were has have had does did doing
    can could shall should will would may might must ought than then
    than so such only just about into over after before between
    where when what which who whom whose why how all any both each
    few more most other some such only own same than too very can
    will just don should now one two also back there here out who
    """.split()
)

_STOPWORDS = RU_STOPWORDS | EN_STOPWORDS


def compute_stats(
    segments: list[dict[str, Any]],
    duration_sec: float | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """Посчитать статистику по сегментам [{text, start, duration}].

    :param segments: сегменты транскрипта.
    :param duration_sec: длительность видео (пока не используется для wpm,
        оставлен для совместимости/будущих метрик).
    :param top_n: сколько ключевых слов вернуть.
    :return: {words, chars, reading_time_min, speaking_wpm|None,
        top_keywords: [{word, count}]}.
    """
    del duration_sec  # wpm считается по спану сегментов (см. SPEC п.7)
    words = 0
    chars = 0
    freq: Counter[str] = Counter()
    starts: list[float] = []
    ends: list[float] = []
    for seg in segments or []:
        try:
            text = seg.get("text", "") if isinstance(seg, dict) else ""
        except Exception:
            text = ""
        if not isinstance(text, str):
            text = str(text)
        chars += len(text)
        words += len(text.split())
        try:
            start = float(seg.get("start", 0.0))
            duration = float(seg.get("duration", 0.0))
        except Exception:
            continue
        starts.append(start)
        ends.append(start + max(0.0, duration))
        for tok in _TOKEN_RE.findall(text.lower()):
            if tok not in _STOPWORDS:
                freq[tok] += 1

    reading_time_min = words / READING_WPM if words else 0.0
    speaking_wpm: float | None = None
    if starts and ends:
        span = max(ends) - min(starts)
        if span > 0 and words:
            speaking_wpm = words / (span / 60.0)

    top = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[: max(0, top_n)]
    return {
        "words": words,
        "chars": chars,
        "reading_time_min": reading_time_min,
        "speaking_wpm": speaking_wpm,
        "top_keywords": [{"word": w, "count": c} for w, c in top],
    }
