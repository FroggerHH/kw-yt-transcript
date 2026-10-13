"""CLI kw-yt: разбор аргументов и печать задач (Фаза 1).

Реальная загрузка метаданных/транскриптов — Фазы 2–3.
Только стандартная библиотека: --help работает без сети и без опциональных зависимостей.
"""

from __future__ import annotations

import argparse

from kw_yt_transcript import __version__
from kw_yt_transcript.inputs import parse_inputs

EXAMPLES = """Примеры:
  kw-yt dQw4w9WgXcQ
      Одно видео по id.

  kw-yt https://www.youtube.com/watch?v=dQw4w9WgXcQ
      Одно видео по URL.

  kw-yt dQw4w9WgXcQ,9bZkp7q19f0 "https://youtu.be/9bZkp7q19f0"
      Несколько видео через запятую/пробел.

  kw-yt --from-file links.txt --out ./out
      Список входов из файла (по одному на строку, # — комментарий).

  kw-yt "https://www.youtube.com/playlist?list=PLxxxxxxxx" --format txt
      Плейлист целиком, только читаемый текст.
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kw-yt",
        description="Скачивание метаданных и транскриптов видео YouTube.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "inputs",
        nargs="*",
        help="Video id, URL видео или URL плейлиста. "
        "Несколько — через запятую, пробел или перенос строки.",
    )
    p.add_argument(
        "--from-file",
        metavar="ФАЙЛ",
        default=None,
        help="Файл со списком входов: по одному на строку, пустые строки и # — пропускаются.",
    )
    p.add_argument(
        "--out",
        "-o",
        metavar="ПАПКА",
        default="./out",
        help="Папка для результатов (по умолчанию ./out).",
    )
    p.add_argument(
        "--langs",
        metavar="ЯЗЫКИ",
        default="ru,en",
        help="Языки субтитров через запятую, по приоритету (по умолчанию ru,en).",
    )
    p.add_argument(
        "--format",
        choices=["srt", "vtt", "json", "txt", "md", "all"],
        default="all",
        help="Формат вывода (по умолчанию all — все форматы).",
    )
    p.add_argument(
        "--no-fallback-whisper",
        action="store_true",
        help="Не использовать Whisper, если субтитров нет (по умолчанию fallback включён).",
    )
    p.add_argument(
        "--whisper-model",
        metavar="МОДЕЛЬ",
        default="small",
        help="Модель Whisper для fallback (по умолчанию small).",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Показать версию и выйти.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Возвращает код выхода: 0 — ок, 1 — частичные ошибки, 2 — ошибка."""
    args = build_parser().parse_args(argv)

    try:
        jobs = parse_inputs(args.inputs, from_file=args.from_file)
    except ValueError as e:
        print(f"Ошибка: {e}", flush=True)
        return 2

    if not jobs:
        print(
            "Ошибка: не указаны входные данные. "
            "Передайте video id / URL или используйте --from-file. "
            "См. kw-yt --help.",
            flush=True,
        )
        return 2

    print(f"Задач: {len(jobs)}. Папка вывода: {args.out}. Языки: {args.langs}. Формат: {args.format}.")
    for i, job in enumerate(jobs, 1):
        detail = job.get("video_id") or job.get("url", "")
        print(f"  [{i}/{len(jobs)}] {job['kind']}: {detail}")

    # Фаза 1: только разбор и печать задач, загрузка — Фазы 2–3.
    print("Загрузка метаданных и транскриптов: not implemented (будет в Фаза 2–3).")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
