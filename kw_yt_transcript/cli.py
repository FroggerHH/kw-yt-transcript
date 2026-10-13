"""CLI kw-yt: разбор аргументов и пакетная загрузка (Фаза 3 + v0.2 Волна 2).

Полный цикл: parse_inputs → get_metadata → get_transcript
(или Whisper-fallback) → write_video + index.json.
Субкоманды: `search` (поиск по корпусу), `serve` (просмотр корпуса),
`export` (сводный файл корпуса + summary.json), `stats` (сводка корпуса).
Иначе — старое fetch-поведение. Импорты yt-dlp/transcript/whisper — лениво,
поэтому --help работает без сети и опциональных зависимостей.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from kw_yt_transcript import __version__, asr, metadata, outputs, transcript
from kw_yt_transcript import config as config_mod
from kw_yt_transcript import export as export_mod
from kw_yt_transcript import search as search_mod
from kw_yt_transcript import serve as serve_mod
from kw_yt_transcript import storage as storage_mod
from kw_yt_transcript.inputs import parse_inputs_with_errors
from kw_yt_transcript.metadata import MetadataError
from kw_yt_transcript.transcript import NoTranscriptError

#: Языки --langs после нормализации: латиница/дефис, 2–12 символов.
_LANG_RE = re.compile(r"^[a-z-]{2,12}$")

#: Блокировка потокобезопасного прогресса batch.
_PRINT_LOCK = threading.Lock()

#: Whisper разом — не больше двух (скачивание аудио + транскрибация тяжёлые),
#: остальной batch идёт параллельно без ограничений.
_WHISPER_SEM = threading.Semaphore(2)

#: Диапазон --jobs.
_JOBS_MIN, _JOBS_MAX = 1, 16

#: ANSI-коды цвета (только stdlib, без зависимостей).
_RED, _GREEN, _BOLD = "31", "32", "1"

#: --no-color текущего прогона (выставляется в _init_color до parse_args,
#: т.к. подсветка help происходит внутри argparse).
_NO_COLOR = False


def _init_color(argv: list[str] | None) -> None:
    """Запомнить --no-color из сырых аргументов (до parse_args)."""
    global _NO_COLOR
    _NO_COLOR = "--no-color" in list(argv or [])


def _supports_color(file=None) -> bool:
    """Цвета разрешены: TTY + нет --no-color/NO_COLOR/TERM=dumb."""
    if _NO_COLOR:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    stream = file if file is not None else sys.stdout
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def _c(text: str, code: str, file=None) -> str:
    """Обернуть текст в ANSI-цвет (без цвета — вернуть как есть)."""
    if not _supports_color(file):
        return text
    return f"\033[{code}m{text}\033[0m"


def _error(text: str) -> None:
    """Ошибка в stderr с красным префиксом (без TTY — plain)."""
    print(f"{_c('Ошибка:', _RED, file=sys.stderr)} {text}", file=sys.stderr, flush=True)


class _ColorHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """--help с подсветкой: usage + заголовки секций + строки опций (только TTY)."""

    def __init__(self, *args, **kwargs):
        # Python 3.14+: stdlib красит help сам (тема argparse) — гасим его,
        # когда наши цвета выключены (--no-color/NO_COLOR/не TTY).
        try:
            super().__init__(*args, color=_supports_color(), **kwargs)
        except TypeError:
            super().__init__(*args, **kwargs)  # Python < 3.14: параметра color нет

    def _set_color(self, color):
        # Python 3.14+: ArgumentParser перевыставляет цвет форматтера
        # из своего self.color ПОСЛЕ __init__ — глушим здесь же, чтобы
        # --no-color/NO_COLOR/не-TTY гасили и stdlib-тему тоже.
        try:
            super()._set_color(bool(color) and _supports_color())
        except AttributeError:
            pass  # Python < 3.14: _set_color нет, красим вручную ниже

    def format_usage(self, usage, actions, groups, prefix):
        if prefix is None:
            prefix = "usage: "
        return super().format_usage(usage, actions, groups, _c(prefix, _BOLD))

    def start_section(self, heading):
        if heading is not None:
            heading = _c(heading, _BOLD)
        return super().start_section(heading)

    def _format_action_invocation(self, action):
        return _c(super()._format_action_invocation(action), _GREEN)

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

   kw-yt --jobs 8 --resume dQw4w9WgXcQ 9bZkp7q19f0
       Параллельно, готовые папки пропускаются.

   kw-yt search "ключевое слово" --in ./out
       Поиск по сохранённым транскриптам.

   kw-yt serve ./out --port 8000
       Просмотр корпуса в браузере.

   kw-yt export --in ./out
       Сводный корпус (corpus.jsonl + summary.json) для RAG и анализа.

   kw-yt stats --in ./out
       Сводная статистика корпуса (таблица или --json).

   kw-yt library
       Список библиотеки (собственное хранилище, размеры, источники).

   kw-yt clean dQw4w9WgXcQ --cache
       Удалить видео из библиотеки + вычистить кэш метаданных.
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kw-yt",
        description="Скачивание метаданных и транскриптов видео YouTube.",
        epilog=EXAMPLES,
        formatter_class=_ColorHelpFormatter,
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
        default=None,
        help="Папка для результатов (по умолчанию библиотека или из конфига).",
    )
    p.add_argument(
        "--langs",
        metavar="ЯЗЫКИ",
        default=None,
        help="Языки субтитров через запятую, по приоритету "
        "(по умолчанию ru,en или из конфига).",
    )
    p.add_argument(
        "--format",
        choices=["srt", "vtt", "json", "txt", "md", "jsonl", "csv", "all"],
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
        default=None,
        help="Модель Whisper для fallback (по умолчанию small или из конфига).",
    )
    p.add_argument(
        "--jobs",
        "-j",
        metavar="N",
        default=None,
        help="Параллельных загрузок (1–16, по умолчанию 4 или из конфига).",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="Пропускать видео, чья папка уже готова (сеть не вызывается).",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Показать версию и выйти.",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Отключить цвета в выводе (то же, что NO_COLOR=1).",
    )
    return p


def build_search_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kw-yt search",
        description="Поиск по сохранённым транскриптам корпуса.",
        formatter_class=_ColorHelpFormatter,
    )
    p.add_argument(
        "query",
        nargs="+",
        help="Запрос (несколько слов — в кавычках или без).",
    )
    p.add_argument(
        "--in",
        dest="in_dir",
        metavar="ПАПКА",
        default=None,
        help="Корень корпуса (по умолчанию библиотека или из конфига).",
    )
    p.add_argument(
        "--context",
        metavar="СЕК",
        default=None,
        help="Контекст: соседние реплики в ±секундах (по умолчанию 15).",
    )
    p.add_argument(
        "--limit",
        metavar="N",
        default=None,
        help="Максимум видео в выдаче (по умолчанию 20).",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Отключить цвета в выводе (то же, что NO_COLOR=1).",
    )
    return p


def build_serve_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kw-yt serve",
        description="Раздавать готовый корпус (index.html/report.html) по HTTP.",
        formatter_class=_ColorHelpFormatter,
    )
    p.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="Корень корпуса (по умолчанию библиотека или из конфига).",
    )
    p.add_argument(
        "--port",
        metavar="N",
        default=None,
        help="Порт (по умолчанию 8000, 0 — выбрать автоматически).",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Отключить цвета в выводе (то же, что NO_COLOR=1).",
    )
    return p


def build_export_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kw-yt export",
        description="Сводный экспорт корпуса в один файл (для RAG и анализа).",
        formatter_class=_ColorHelpFormatter,
    )
    p.add_argument(
        "--in",
        dest="in_dir",
        metavar="ПАПКА",
        default=None,
        help="Корень корпуса (по умолчанию библиотека или из конфига).",
    )
    p.add_argument(
        "--format",
        choices=["jsonl", "csv"],
        default="jsonl",
        help="Формат сводного файла (по умолчанию jsonl).",
    )
    p.add_argument(
        "--out",
        metavar="ФАЙЛ",
        default=None,
        help="Куда писать корпус (по умолчанию <корень>/corpus.{jsonl|csv}).",
    )
    p.add_argument(
        "--summary",
        metavar="ФАЙЛ",
        default=None,
        help="Куда писать summary.json (по умолчанию <корень>/summary.json).",
    )
    p.add_argument(
        "--no-summary",
        action="store_true",
        help="Не писать summary.json.",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Отключить цвета в выводе (то же, что NO_COLOR=1).",
    )
    return p


def build_stats_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kw-yt stats",
        description="Сводная статистика корпуса (без скачивания).",
        formatter_class=_ColorHelpFormatter,
    )
    p.add_argument(
        "--in",
        dest="in_dir",
        metavar="ПАПКА",
        default=None,
        help="Корень корпуса (по умолчанию библиотека или из конфига).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Вывести сводку JSON вместо таблицы.",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Отключить цвета в выводе (то же, что NO_COLOR=1).",
    )
    return p


def build_library_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kw-yt library",
        description="Список библиотеки: видео с размерами и источниками.",
        formatter_class=_ColorHelpFormatter,
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Вывести список JSON вместо таблицы.",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Отключить цвета в выводе (то же, что NO_COLOR=1).",
    )
    return p


def build_clean_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kw-yt clean",
        description="Удалить видео из библиотеки и/или кэш метаданных.",
        formatter_class=_ColorHelpFormatter,
    )
    p.add_argument(
        "ids",
        nargs="*",
        help="Video id для удаления (точное совпадение папки *_<id>).",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Удалить все видео библиотеки (требует также --yes).",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Подтвердить удаление всех (--all без --yes — отказ).",
    )
    p.add_argument(
        "--older-than",
        metavar="DAYS",
        default=None,
        help="Удалить видео старше N дней (по времени папки).",
    )
    p.add_argument(
        "--cache",
        action="store_true",
        help="Вычистить также XDG-кэш метаданных.",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Отключить цвета в выводе (то же, что NO_COLOR=1).",
    )
    return p


def expand_playlist(url: str, ydl_factory=None) -> list[dict[str, Any]]:
    """Flat-развёртка плейлиста -> [{url|None, error|None}].

    Пропущенные записи (non-dict, без id/URL) не теряются: возвращаются
    с error, чтобы число элементов равнялось числу записей плейлиста.

    :param ydl_factory: инъекция для тестов (как в metadata.get_metadata).
    """
    if ydl_factory is None:
        import yt_dlp

        ydl_factory = yt_dlp.YoutubeDL
    try:
        with ydl_factory({"quiet": True, "skip_download": True, "extract_flat": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise MetadataError(f"Не удалось прочитать плейлист {url!r}: {e}") from e
    entries = (info or {}).get("entries") or []
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            out.append({"url": None, "error": f"Запись плейлиста {url!r} пропущена: не объект."})
            continue
        entry_url = entry.get("url") or ""
        if "://" in entry_url:
            out.append({"url": entry_url, "error": None})
        elif entry.get("id"):
            out.append({"url": f"https://www.youtube.com/watch?v={entry['id']}", "error": None})
        else:
            out.append(
                {"url": None, "error": f"Запись плейлиста {url!r} пропущена: нет video id/URL."}
            )
    return out


def _process_video(
    source: str,
    hint_id: str | None,
    langs: list[str],
    use_whisper: bool,
    whisper_model: str,
    out_dir: Path,
    formats_sel: str,
) -> dict[str, Any]:
    """Одно видео: метаданные → субтитры (или Whisper) → файлы.

    Не бросает исключений: неуспех возвращается как result с ``error``.
    При падении get_metadata в entries сохраняется hint (video_id/url).
    """
    meta: dict[str, Any] | None = None
    try:
        meta = metadata.get_metadata(source)
        video_id = meta.get("video_id") or hint_id
        if not video_id:
            raise MetadataError(f"yt-dlp не вернул video id для {source!r}.")
        try:
            segments, origin, lang = transcript.get_transcript(video_id, languages=langs)
        except NoTranscriptError:
            if not use_whisper:
                raise
            with _WHISPER_SEM:
                segments, origin = asr.transcribe_whisper(
                    meta.get("url") or source, model_name=whisper_model
                )
            lang = None
        paths = outputs.write_video(
            out_dir,
            meta,
            segments,
            origin,
            formats_sel,
            transcript_lang=lang,
            asr_model=whisper_model if origin == "whisper" else None,
        )
        return {
            "meta": meta,
            "dir": Path(paths["dir"]).name,
            "origin": origin,
            "transcript_lang": lang,
            "error": None,
        }
    except Exception as e:
        if meta is None:
            meta = {"video_id": hint_id, "url": source, "title": None}
        return {
            "meta": meta,
            "dir": None,
            "origin": None,
            "transcript_lang": None,
            "error": str(e),
        }


def _guess_video_id(source: str | None, hint_id: str | None) -> str | None:
    """video id для --resume без сети: hint или id из URL."""
    if hint_id:
        return hint_id
    if not source:
        return None
    for pat in (
        r"[?&]v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})",
    ):
        m = re.search(pat, source)
        if m:
            return m.group(1)
    return None


def _load_ready_record(video_dir: Path) -> dict[str, Any]:
    try:
        record = json.loads((video_dir / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    return record if isinstance(record, dict) else {}


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Коды: 0 — всё ок, 1 — частичные ошибки/не найдено, 2 — usage.

    Субкоманды `search`/`serve`/`export`/`stats`/`library`/`clean` — по argv[1],
    иначе fetch-поведение (скачивание в библиотеку по умолчанию).
    Fetch пишет в stderr, stdout пуст; search печатает результаты в stdout;
    serve печатает URL в stdout; export печатает сводку в stdout; stats — таблицу/JSON.
    """
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "search":
        return _main_search(argv)
    if argv and argv[0] == "serve":
        return _main_serve(argv)
    if argv and argv[0] == "export":
        return _main_export(argv)
    if argv and argv[0] == "stats":
        return _main_stats(argv)
    if argv and argv[0] == "library":
        return _main_library(argv)
    if argv and argv[0] == "clean":
        return _main_clean(argv)
    return _main_fetch(argv)


def _main_fetch(argv: list[str]) -> int:
    """Классический прогон: скачать метаданные и транскрипты."""
    _init_color(argv)
    args = build_parser().parse_args(argv)
    cfg = config_mod.load_config()

    try:
        jobs, input_errors = parse_inputs_with_errors(args.inputs, from_file=args.from_file)
    except ValueError as e:
        _error(f"{e}")
        return 2

    if not jobs and not input_errors and args.from_file is None:
        _error(
            "не указаны входные данные. "
            "Передайте video id / URL или используйте --from-file. "
            "См. kw-yt --help."
        )
        return 2

    # Ранняя валидация до любой сети: языки, модель, jobs. Приоритет CLI > конфиг.
    langs_raw = args.langs if args.langs is not None else cfg.get("langs", "ru,en")
    langs = [lang.strip().lower() for lang in str(langs_raw).split(",") if lang.strip()]
    if not langs:
        langs = ["ru", "en"]
    bad_langs = [lang for lang in langs if not _LANG_RE.match(lang)]
    if bad_langs:
        _error(
            f"неверные языки в --langs: {', '.join(bad_langs)}. "
            "Ожидаются коды вида 'ru', 'en', 'en-us' (латиница/дефис, 2–12 символов)."
        )
        return 2
    whisper_model = str(
        args.whisper_model
        if args.whisper_model is not None
        else cfg.get("whisper_model", "small")
    ).strip()
    if not whisper_model:
        _error("--whisper-model не должен быть пустым.")
        return 2
    jobs_raw = args.jobs if args.jobs is not None else cfg.get("jobs", 4)
    try:
        jobs_n = int(str(jobs_raw).strip())
    except (TypeError, ValueError):
        jobs_n = 0
    if not (_JOBS_MIN <= jobs_n <= _JOBS_MAX):
        _error(
            f"--jobs должен быть целым числом от {_JOBS_MIN} до {_JOBS_MAX}, "
            f"получено {jobs_raw!r}."
        )
        return 2
    use_whisper = not args.no_fallback_whisper

    # Корень: флаг > конфиг > библиотека. Папку создаём только когда точно
    # есть работа (ниже), чтобы ошибочные прогоны не трогали диск.
    out_dir = storage_mod.resolve_root(args.out, cfg)

    if not jobs and not input_errors:
        # Пустой --from-file: только комменты/пустые строки — пустой index, exit 2.
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            outputs.write_index(out_dir, [], None)
        except OSError as e:
            _error(f"не могу записать index.json: {e}")
        print(
            "Предупреждение: во входах нет видео — нечего обрабатывать.",
            file=sys.stderr,
            flush=True,
        )
        return 2

    # Мусорные токены: позиций в потоке входов inputs-модуль не сохраняет,
    # поэтому их error-записи идут первыми; всё позиционируемое — строго
    # по порядку входов через plan/слоты ниже.
    leading: list[dict[str, Any]] = []
    for err in input_errors:
        leading.append(
            {"meta": None, "dir": None, "origin": None, "transcript_lang": None, "error": err}
        )
        print(f"вход: {_c('FAIL', _RED, file=sys.stderr)}: {err}", file=sys.stderr)
    if not jobs:
        return 2

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _error(f"не могу создать папку {out_dir!r}: {e}")
        return 2

    # План в порядке входов: ("video", (source, hint)) или ("done", result).
    # Ошибки expand плейлиста и пропущенные записи — записями "done" на месте
    # плейлиста, а не префиксом: порядок index.json повторяет порядок входов.
    # Плейлисты разворачиваем последовательно; неуспешный expand — ошибка-запись.
    plan: list[tuple[str, Any]] = []
    playlist_urls: list[str] = []
    has_video_jobs = False
    for job in jobs:
        if job["kind"] == "playlist":
            url = job.get("url") or job.get("raw", "")
            playlist_urls.append(url)
            try:
                items = expand_playlist(url)
            except Exception as e:
                plan.append(
                    (
                        "done",
                        {
                            "meta": None,
                            "dir": None,
                            "origin": None,
                            "transcript_lang": None,
                            "error": str(e),
                        },
                    )
                )
                print(f"плейлист {url}: {_c('FAIL', _RED, file=sys.stderr)}: {e}", file=sys.stderr)
                continue
            for item in items:
                if item.get("error") or not item.get("url"):
                    plan.append(
                        (
                            "done",
                            {
                                "meta": None,
                                "dir": None,
                                "origin": None,
                                "transcript_lang": None,
                                "error": item.get("error")
                                or f"Запись плейлиста {url!r} пропущена.",
                            },
                        )
                    )
                    print(
                        f"плейлист {url}: SKIP: {plan[-1][1]['error']}", file=sys.stderr
                    )
                else:
                    plan.append(("video", (item["url"], None)))
        else:
            has_video_jobs = True
            plan.append(
                (
                    "video",
                    (
                        job.get("url") or job.get("video_id") or job.get("raw", ""),
                        job.get("video_id"),
                    ),
                )
            )

    # 'playlist' — только если вход ровно один плейлист и все задачи из него, иначе 'batch'.
    index_playlist_url = (
        playlist_urls[0] if len(playlist_urls) == 1 and not has_video_jobs else None
    )

    if not plan and not leading:
        _error("по заданным входам видео не найдено.")
        try:
            outputs.write_index(out_dir, [], index_playlist_url)
        except OSError as e:
            _error(f"не могу записать index.json: {e}")
        return 2

    # --resume: готовые папки (meta+transcript+report) — в слоты без сети.
    slots: dict[int, dict[str, Any]] = {}
    for p, item in enumerate(plan):
        if item[0] == "done":
            slots[p] = item[1]
    video_order = [p for p, item in enumerate(plan) if item[0] == "video"]
    vnums = {p: k + 1 for k, p in enumerate(video_order)}
    n_videos = len(video_order)
    if args.resume:
        for p in video_order:
            if p in slots:
                continue
            source, hint_id = plan[p][1]
            vid = _guess_video_id(source, hint_id)
            ready = outputs.find_ready(out_dir, vid)
            if ready is None:
                continue
            record = _load_ready_record(ready)
            meta_ready = dict(record)
            if not meta_ready.get("video_id"):
                meta_ready["video_id"] = vid
            slots[p] = {
                "meta": meta_ready,
                "dir": ready.name,
                "origin": record.get("origin"),
                "transcript_lang": record.get("transcript_lang"),
                "error": None,
                "skipped": True,
            }
            label = hint_id or source
            with _PRINT_LOCK:
                print(
                    f"[{vnums[p]}/{n_videos}] {label} ... skip (уже готово)",
                    file=sys.stderr,
                )

    # Параллельная обработка; index стабилен: результаты — по слотам плана.
    need = [(p, plan[p][1][0], plan[p][1][1]) for p in video_order if p not in slots]

    def _run(task: tuple[int, str, str | None]) -> dict[str, Any]:
        _, source, hint_id = task
        return _process_video(
            source, hint_id, langs, use_whisper, whisper_model, out_dir, args.format
        )

    if need:
        with ThreadPoolExecutor(max_workers=jobs_n) as executor:
            futures = {executor.submit(_run, t): t for t in need}
            for future in as_completed(futures):
                p, source, hint_id = futures[future]
                try:
                    result = future.result()
                except Exception as e:  # _process_video не бросает, но перестрахуемся
                    result = {
                        "meta": {"video_id": hint_id, "url": source, "title": None},
                        "dir": None,
                        "origin": None,
                        "transcript_lang": None,
                        "error": f"Внутренняя ошибка обработки: {e}",
                    }
                slots[p] = result
                label = hint_id or source
                with _PRINT_LOCK:
                    if result["error"]:
                        print(
                            f"[{vnums[p]}/{n_videos}] {label} ... "
                            f"{_c('FAIL', _RED, file=sys.stderr)}: {result['error']}",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            f"[{vnums[p]}/{n_videos}] {result['meta'].get('video_id')} ... "
                            f"{_c('ok', _GREEN, file=sys.stderr)}",
                            file=sys.stderr,
                        )

    results: list[dict[str, Any]] = list(leading)
    results.extend(slots[p] for p in range(len(plan)))

    try:
        outputs.write_index(out_dir, results, index_playlist_url)
    except OSError as e:
        _error(f"не могу записать index.json: {e}")
        return 2

    failed = sum(1 for r in results if r["error"])
    ok = len(results) - failed
    print(
        f"Готово: {ok}/{len(results)}, ошибок: {failed}. Папка: {out_dir}.",
        file=sys.stderr,
    )
    return 1 if failed else 0


def _main_search(argv: list[str]) -> int:
    """Поиск по корпусу: группы «заголовок + mm:ss текст», exit 0/1."""
    _init_color(argv)
    args = build_search_parser().parse_args(argv[1:])
    cfg = config_mod.load_config()
    root = storage_mod.resolve_root(args.in_dir, cfg)
    if not Path(root).is_dir():
        _error(f"папка корпуса не найдена: {root}.")
        return 2
    try:
        context_sec = 15.0 if args.context is None else float(str(args.context).strip())
    except (TypeError, ValueError):
        _error(f"--context должен быть числом секунд, получено {args.context!r}.")
        return 2
    if context_sec < 0:
        _error("--context не должен быть отрицательным.")
        return 2
    try:
        limit = 20 if args.limit is None else int(str(args.limit).strip())
    except (TypeError, ValueError):
        _error(f"--limit должен быть целым числом, получено {args.limit!r}.")
        return 2
    if limit < 1:
        _error("--limit должен быть >= 1.")
        return 2
    query = " ".join(args.query).strip()
    try:
        found = search_mod.search_corpus(root, query, context_sec=context_sec, limit=limit)
    except ValueError as e:
        _error(f"{e}")
        return 2
    if not found:
        print(f"По запросу «{query}» ничего не найдено.", flush=True)
        return 1
    total_direct = sum(v.get("direct_count", len(v["hits"])) for v in found)
    print(f"Результаты поиска «{query}»: видео {len(found)}, вхождений {total_direct}.")
    for entry in found:
        title = entry.get("title") or entry.get("video_id") or "—"
        print(
            f"\nВидео: {title} [{entry.get('video_id') or '—'}] "
            f"— совпадений: {entry.get('direct_count', len(entry['hits']))}"
        )
        for hit in entry["hits"]:
            mark = ">" if hit.get("direct") else " "
            print(f"  {mark} {search_mod.format_ts(hit.get('start'))} {hit.get('text', '')}")
    return 0


def _main_serve(argv: list[str]) -> int:
    """Просмотр корпуса через HTTP."""
    _init_color(argv)
    args = build_serve_parser().parse_args(argv[1:])
    cfg = config_mod.load_config()
    root = storage_mod.resolve_root(args.directory, cfg)
    try:
        port = 8000 if args.port is None else int(str(args.port).strip())
    except (TypeError, ValueError):
        _error(f"--port должен быть целым числом, получено {args.port!r}.")
        return 2
    if not (0 <= port <= 65535):
        _error(f"--port должен быть от 0 до 65535, получено {args.port!r}.")
        return 2
    return serve_mod.serve_dir(root, port)


def _main_export(argv: list[str]) -> int:
    """Сводный экспорт корпуса: один файл + summary.json, exit 0/1/2."""
    _init_color(argv)
    args = build_export_parser().parse_args(argv[1:])
    cfg = config_mod.load_config()
    root = storage_mod.resolve_root(args.in_dir, cfg)
    if not Path(root).is_dir():
        _error(f"папка корпуса не найдена: {root}.")
        return 2
    out_path = Path(args.out) if args.out else Path(root) / f"corpus.{args.format}"
    try:
        summary = export_mod.export_corpus(root, out_path, args.format)
    except ValueError as e:
        _error(f"{e}")
        return 1
    except OSError as e:
        _error(f"не пишется файл {out_path}: {e}")
        return 1
    if not args.no_summary:
        summary_path = Path(args.summary) if args.summary else Path(root) / "summary.json"
        try:
            export_mod.write_summary(summary, summary_path)
        except OSError as e:
            _error(f"не пишется файл {summary_path}: {e}")
            return 1
        summary_note = f", сводка {summary_path}"
    else:
        summary_note = ""
    print(
        f"Экспорт: видео {summary['n_videos']}, реплик {summary['n_segments']}, "
        f"слов {summary['total_words']} → {out_path}{summary_note}."
    )
    return 0


def _main_stats(argv: list[str]) -> int:
    """Сводная статистика корпуса в stdout: таблица или JSON, exit 0/1/2."""
    _init_color(argv)
    args = build_stats_parser().parse_args(argv[1:])
    cfg = config_mod.load_config()
    root = storage_mod.resolve_root(args.in_dir, cfg)
    if not Path(root).is_dir():
        _error(f"папка корпуса не найдена: {root}.")
        return 2
    videos, skipped = export_mod.collect_corpus(root)
    if not videos:
        _error("в корпусе нет транскриптов (*/transcript.json).")
        return 1
    summary = export_mod.summarize(videos, skipped)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    print(f"Корпус: {root} — видео {summary['n_videos']}, реплик {summary['n_segments']}, "
          f"слов {summary['total_words']}, минут {summary['total_minutes']}.")
    origins = ", ".join(f"{k}: {v}" for k, v in sorted(summary["by_origin"].items()))
    langs = ", ".join(f"{k}: {v}" for k, v in sorted(summary["by_lang"].items()))
    print(f"Источники: {origins or '—'}. Языки: {langs or '—'}.")
    if summary["skipped"]:
        print(f"Пропущено папок без транскрипта: {summary['skipped']}.")
    for v in summary["videos"]:
        title = v.get("title") or v.get("video_id") or "—"
        print(f"- {title} [{v.get('video_id') or '—'}]: "
              f"{v['segments']} реплик, {v['words']} слов, {v['seconds']} с.")
    return 0


def _fmt_size(num_bytes: int) -> str:
    """Байты -> КБ/МБ одной строкой (1024)."""
    try:
        n = int(num_bytes)
    except Exception:
        return "—"
    if n < 0:
        return "—"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} КБ"
    return f"{n / (1024 * 1024):.1f} МБ"


def _main_library(argv: list[str]) -> int:
    """Список библиотеки: таблица или JSON, exit 0 (пустая — строка, тоже 0)."""
    _init_color(argv)
    args = build_library_parser().parse_args(argv[1:])
    cfg = config_mod.load_config()
    root = storage_mod.resolve_root(None, cfg)
    entries = storage_mod.iter_library(root)
    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return 0
    if not entries:
        print(f"Библиотека пуста: {root}. Скачайте видео: kw-yt <URL> (без --out).")
        return 0
    print(f"Библиотека: {root} — видео {len(entries)}.")
    for e in entries:
        title = e.get("title") or e.get("video_id") or "—"
        print(
            f"- {title} [{e.get('video_id') or '—'}] "
            f"{e.get('date') or '—'} {_fmt_size(e.get('size_bytes', 0))} "
            f"{e.get('origin') or '—'}"
        )
    return 0


def _main_clean(argv: list[str]) -> int:
    """Удаление видео из библиотеки и/или кэша. Exit 0/1/2."""
    _init_color(argv)
    args = build_clean_parser().parse_args(argv[1:])
    cfg = config_mod.load_config()
    root = storage_mod.resolve_root(None, cfg)

    if args.all and not args.yes:
        _error(
            "--all удаляет ВСЮ библиотеку. "
            "Подтвердите: kw-yt clean --all --yes."
        )
        return 2

    days = None
    if args.older_than is not None:
        try:
            days = int(str(args.older_than).strip())
        except (TypeError, ValueError):
            days = -1
        if days < 0:
            _error(
                f"--older-than должен быть целым числом дней >= 0, "
                f"получено {args.older_than!r}."
            )
            return 2

    targets: list[Path] = []
    missing: list[str] = []
    if args.all:
        targets = [root / e["dir"] for e in storage_mod.iter_library(root)]
    elif args.ids:
        targets, missing = storage_mod.find_video_dirs(root, list(args.ids))
    elif days is not None:
        import time

        cutoff = time.time() - days * 86400
        for e in storage_mod.iter_library(root):
            d = root / e["dir"]
            try:
                if d.stat().st_mtime < cutoff:
                    targets.append(d)
            except OSError:
                continue
    elif not args.cache:
        _error(
            "укажите ID, --all --yes или --older-than DAYS "
            "(см. kw-yt clean --help)."
        )
        return 2

    removed, freed = storage_mod.remove_dirs(targets)
    cache_files = 0
    if args.cache:
        cache_files, cache_bytes = storage_mod.clear_cache()
        freed += cache_bytes
    for t in removed:
        print(f"Удалено: {t.name}")
    for m in missing:
        print(f"Не найдено: {m}", file=sys.stderr)
    note = f", кэш: файлов {cache_files}" if args.cache else ""
    print(f"Итого: папок {len(removed)}, освобождено {_fmt_size(freed)}{note}.")
    if removed or cache_files:
        return 0
    if args.cache and not missing and not targets:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
