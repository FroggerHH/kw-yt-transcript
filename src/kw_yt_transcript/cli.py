"""CLI kw-yt: разбор аргументов и пакетная загрузка (Фаза 3 + v0.2 Волна 2).

Полный цикл: parse_inputs → get_metadata → get_transcript
(или Whisper-fallback) → write_video + index.json.
Субкоманды: `search` (поиск по корпусу), `serve` (просмотр корпуса),
`export` (сводный файл корпуса + summary.json), `stats` (сводка корпуса),
`library`/`clean` (собственное хранилище), `completion` (bash-completion),
`update` (самообновление тем же способом установки).
Иначе — старое fetch-поведение. Импорты yt-dlp/transcript/whisper — лениво,
поэтому --help работает без сети и опциональных зависимостей.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from kw_yt_transcript import __version__, asr, metadata, outputs, transcript
from kw_yt_transcript import config as config_mod
from kw_yt_transcript import export as export_mod
from kw_yt_transcript import formats as formats_mod
from kw_yt_transcript import search as search_mod
from kw_yt_transcript import sections as sections_mod
from kw_yt_transcript import serve as serve_mod
from kw_yt_transcript import stats as stats_mod
from kw_yt_transcript import storage as storage_mod
from kw_yt_transcript import update as update_mod
from kw_yt_transcript.inputs import parse_inputs_with_errors
from kw_yt_transcript.metadata import MetadataError
from kw_yt_transcript.timefmt import mmss as _mmss
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

#: --color текущего прогона (выставляется в _init_color до parse_args,
#: т.к. подсветка help происходит внутри argparse). auto — как раньше
#: (TTY + нет NO_COLOR/TERM=dumb); --no-color — то же, что never.
_COLOR_MODE = "auto"

#: Допустимые значения --color (единственный список для парсеров и completion).
COLOR_MODES = ("auto", "always", "never")


def _init_color(argv: list[str] | None) -> None:
    """Запомнить --color/--no-color из сырых аргументов (до parse_args)."""
    global _COLOR_MODE
    mode = "auto"
    args = list(argv or [])
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--no-color":
            mode = "never"
        elif arg == "--color" and i + 1 < len(args):
            if args[i + 1] in COLOR_MODES:
                mode = args[i + 1]
            i += 1
        elif arg.startswith("--color="):
            if arg.split("=", 1)[1] in COLOR_MODES:
                mode = arg.split("=", 1)[1]
        i += 1
    _COLOR_MODE = mode


def _add_color_args(p: argparse.ArgumentParser) -> None:
    """Общие флаги цвета во все парсеры: --color + legacy --no-color."""
    p.add_argument(
        "--color",
        choices=list(COLOR_MODES),
        default="auto",
        help="Цвета в выводе: auto (по TTY), always, never (по умолчанию auto).",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Отключить цвета в выводе (то же, что --color never / NO_COLOR=1).",
    )


def _supports_color(file=None) -> bool:
    """Цвета разрешены. Приоритет: флаг --color > NO_COLOR > TTY."""
    if _COLOR_MODE == "always":
        return True
    if _COLOR_MODE == "never":
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

   kw-yt completion bash
       Bash-completion в stdout: eval "$(kw-yt completion bash)".

   kw-yt update
       Обновить тем же способом, каким установлено (или --check без обновления).
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
        help="Языки субтитров через запятую, по приоритету (по умолчанию ru,en или из конфига).",
    )
    p.add_argument(
        "--format",
        choices=["srt", "vtt", "json", "txt", "md", "jsonl", "csv", "all"],
        default="all",
        help="Формат вывода (по умолчанию all — все форматы).",
    )
    p.add_argument(
        "--from",
        dest="from_ts",
        metavar="SEC",
        default=None,
        help="Начало фрагмента (mm:ss или секунды; нужен и --to).",
    )
    p.add_argument(
        "--to",
        dest="to_ts",
        metavar="SEC",
        default=None,
        help="Конец фрагмента (mm:ss или секунды; нужен и --from).",
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
    _add_color_args(p)
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
    _add_color_args(p)
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
        "--host",
        metavar="HOST",
        default=None,
        help="Хост (по умолчанию 127.0.0.1 — только локально; "
        "0.0.0.0 — виден всей локальной сети).",
    )
    _add_color_args(p)
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
    _add_color_args(p)
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
    _add_color_args(p)
    return p


def build_library_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kw-yt library",
        description="Навигатор библиотеки: список, детали видео, транскрипт, report.",
        formatter_class=_ColorHelpFormatter,
    )
    p.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Номер [i] из списка или video id — детали одного видео.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Вывести JSON вместо текста (список или детали одного видео).",
    )
    p.add_argument(
        "--transcript",
        action="store_true",
        help="Напечатать транскрипт видео (формат — --format, по умолчанию txt).",
    )
    p.add_argument(
        "--format",
        choices=["txt", "md", "srt"],
        default="txt",
        help="Формат транскрипта с --transcript (по умолчанию txt).",
    )
    p.add_argument(
        "--open",
        action="store_true",
        help="Открыть report.html видео в браузере.",
    )
    p.add_argument(
        "--tui",
        action="store_true",
        help="Простой построчный интерфейс-навигатор (не полноэкранный TUI).",
    )
    _add_color_args(p)
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
    _add_color_args(p)
    return p


def build_completion_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kw-yt completion",
        description="Сгенерировать bash-completion для kw-yt (в stdout).",
        formatter_class=_ColorHelpFormatter,
    )
    p.add_argument(
        "shell",
        nargs="?",
        default="bash",
        choices=["bash"],
        help="Оболочка (пока только bash).",
    )
    _add_color_args(p)
    return p


def build_update_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kw-yt update",
        description="Обновить kw-yt тем же способом, каким установлено.",
        formatter_class=_ColorHelpFormatter,
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Только проверить: способ установки и свежесть версии, без обновления.",
    )
    _add_color_args(p)
    return p


def _completion_parsers() -> dict[str, argparse.ArgumentParser]:
    """Субкоманда -> парсер. Единственный источник флагов для completion."""
    return {
        "": build_parser(),
        "search": build_search_parser(),
        "serve": build_serve_parser(),
        "export": build_export_parser(),
        "stats": build_stats_parser(),
        "library": build_library_parser(),
        "clean": build_clean_parser(),
        "completion": build_completion_parser(),
        "update": build_update_parser(),
    }


def _flags_of(parser: argparse.ArgumentParser) -> list[str]:
    """Все опции парсера (источник истины — argparse, не руками)."""
    return sorted({opt for a in parser._actions for opt in a.option_strings})


def _value_flags(parsers: list[argparse.ArgumentParser]) -> list[str]:
    """Опции, принимающие значение (nargs != 0 без choices): кандидатов нет."""
    out: set[str] = set()
    for p in parsers:
        for a in p._actions:
            if a.option_strings and a.nargs != 0 and not getattr(a, "choices", None):
                out.update(a.option_strings)
    return sorted(out)


def _choices_of(parser: argparse.ArgumentParser, flag: str) -> list[str]:
    """Значения choices для флага (например --format/--color)."""
    for a in parser._actions:
        if flag in a.option_strings:
            choices = getattr(a, "choices", None)
            if choices:
                return sorted(str(c) for c in choices)
    return []


def render_bash_completion() -> str:
    """Сгенерировать bash-completion из argparse-парсеров.

    Подход (зафиксирован в ARCHITECTURE.md): скрипт не правится руками —
    единственный источник истины — парсеры выше; файл
    ``contrib/kw-yt-completion.bash`` — зафиксированный вывод этой функции.
    """
    parsers = _completion_parsers()
    flags = {name: _flags_of(p) for name, p in parsers.items()}
    fetch_fmt = _choices_of(parsers[""], "--format")
    export_fmt = _choices_of(parsers["export"], "--format")
    color_modes = _choices_of(parsers[""], "--color")
    value_flags = _value_flags(list(parsers.values()))
    subs = sorted(k for k in parsers if k)
    top = sorted(set(subs) | set(flags[""]))
    lines = [
        "# Bash-completion для kw-yt. Сгенерировано `kw-yt completion bash` — не править вручную.",
        '# Установка: eval "$(kw-yt completion bash)"',
        "# или: kw-yt completion bash > ~/.local/share/bash-completion/completions/kw-yt",
        "_kw_yt() {",
        "    local cur prev sub",
        "    COMPREPLY=()",
        '    cur="${COMP_WORDS[COMP_CWORD]}"',
        '    prev="${COMP_WORDS[COMP_CWORD-1]}"',
        '    sub="${COMP_WORDS[1]}"',
        "",
        '    case "$prev" in',
        "        --format)",
        '            case "$sub" in',
        f'                export) COMPREPLY=( $(compgen -W "{" ".join(export_fmt)}"'
        ' -- "$cur") ); return 0 ;;',
        f'                *) COMPREPLY=( $(compgen -W "{" ".join(fetch_fmt)}"'
        ' -- "$cur") ); return 0 ;;',
        "            esac",
        "            ;;",
        "        --color)",
        f'            COMPREPLY=( $(compgen -W "{" ".join(color_modes)}" -- "$cur") )',
        "            return 0",
        "            ;;",
        f"        {'|'.join(value_flags)})",
        "            return 0",
        "            ;;",
        "    esac",
        "",
        '    case "$sub" in',
    ]
    for name in subs:
        words = "bash" if name == "completion" else " ".join(flags[name])
        lines += [
            f"        {name})",
            f'            COMPREPLY=( $(compgen -W "{words}" -- "$cur") )',
            "            return 0",
            "            ;;",
        ]
    lines += [
        '        "")',
        f'            COMPREPLY=( $(compgen -W "{" ".join(top)}" -- "$cur") )',
        "            return 0",
        "            ;;",
        "    esac",
        "",
        f'    COMPREPLY=( $(compgen -W "{" ".join(flags[""])}" -- "$cur") )',
        "    return 0",
        "}",
        "complete -F _kw_yt kw-yt",
    ]
    return "\n".join(lines) + "\n"


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
    section: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Одно видео: метаданные → субтитры (или Whisper) → файлы.

    Не бросает исключений: неуспех возвращается как result с ``error``.
    При падении get_metadata в entries сохраняется hint (video_id/url).
    Фрагмент (section) фильтрует реплики после получения, папка и meta
    получают суффикс/поле section.
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
        if section is not None:
            segments = sections_mod.clip_segments(segments, section[0], section[1])
        paths = outputs.write_video(
            out_dir,
            meta,
            segments,
            origin,
            formats_sel,
            transcript_lang=lang,
            asr_model=whisper_model if origin == "whisper" else None,
            section=section,
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

    Субкоманды `search`/`serve`/`export`/`stats`/`library`/`clean`/`completion`/
    `update` — по argv[1], иначе fetch-поведение (скачивание в библиотеку
    по умолчанию).
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
    if argv and argv[0] == "completion":
        return _main_completion(argv)
    if argv and argv[0] == "update":
        return _main_update(argv)
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
        args.whisper_model if args.whisper_model is not None else cfg.get("whisper_model", "small")
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
            f"--jobs должен быть целым числом от {_JOBS_MIN} до {_JOBS_MAX}, получено {jobs_raw!r}."
        )
        return 2
    use_whisper = not args.no_fallback_whisper

    # Фрагмент: обе границы сразу, до любой сети. Субтитры/аудио берутся
    # целиком, реплики фильтруются после (Whisper качает всё аудио — честно).
    section: tuple[float, float] | None = None
    if args.from_ts is not None or args.to_ts is not None:
        if args.from_ts is None or args.to_ts is None:
            _error("фрагмент задаётся парой: укажите и --from, и --to.")
            return 2
        try:
            frm = sections_mod.parse_ts(args.from_ts)
        except ValueError as e:
            _error(str(e))
            return 2
        try:
            to = sections_mod.parse_ts(args.to_ts)
        except ValueError as e:
            _error(str(e))
            return 2
        if not frm < to:
            _error(f"--from ({args.from_ts}) должен быть меньше --to ({args.to_ts}).")
            return 2
        section = (frm, to)

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
                    print(f"плейлист {url}: SKIP: {plan[-1][1]['error']}", file=sys.stderr)
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
    for p, entry in enumerate(plan):
        if entry[0] == "done":
            slots[p] = entry[1]
    video_order = [p for p, entry in enumerate(plan) if entry[0] == "video"]
    vnums = {p: k + 1 for k, p in enumerate(video_order)}
    n_videos = len(video_order)
    if args.resume:
        section_key = sections_mod.section_key(*section) if section is not None else None
        for p in video_order:
            if p in slots:
                continue
            source, hint_id = plan[p][1]
            vid = _guess_video_id(source, hint_id)
            ready = outputs.find_ready(out_dir, vid, section_key)
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
            source,
            hint_id,
            langs,
            use_whisper,
            whisper_model,
            out_dir,
            args.format,
            section,
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
    host = "127.0.0.1" if args.host is None else str(args.host).strip()
    if not host:
        _error("--host не должен быть пустым.")
        return 2
    try:
        socket.getaddrinfo(host, port)
    except (OSError, UnicodeError):
        _error(f"непонятный host {args.host!r}: не резолвится.")
        return 2
    return serve_mod.serve_dir(root, port, host)


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
    print(
        f"Корпус: {root} — видео {summary['n_videos']}, реплик {summary['n_segments']}, "
        f"слов {summary['total_words']}, минут {summary['total_minutes']}."
    )
    origins = ", ".join(f"{k}: {v}" for k, v in sorted(summary["by_origin"].items()))
    langs = ", ".join(f"{k}: {v}" for k, v in sorted(summary["by_lang"].items()))
    print(f"Источники: {origins or '—'}. Языки: {langs or '—'}.")
    if summary["skipped"]:
        print(f"Пропущено папок без транскрипта: {summary['skipped']}.")
    for v in summary["videos"]:
        title = v.get("title") or v.get("video_id") or "—"
        print(
            f"- {title} [{v.get('video_id') or '—'}]: "
            f"{v['segments']} реплик, {v['words']} слов, {v['seconds']} с."
        )
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


def _library_entries(root: Path) -> list[dict[str, Any]]:
    """Записи библиотеки с index (с 1, порядок — по имени папки)."""
    entries = storage_mod.iter_library(root)
    for i, e in enumerate(entries, 1):
        e["index"] = i
    return entries


def _print_library_list(root: Path, entries: list[dict[str, Any]]) -> None:
    print(f"Библиотека: {root} — видео {len(entries)}.")
    for e in entries:
        title = e.get("title") or e.get("video_id") or "—"
        print(
            f"- [{e['index']}] {title} [{e.get('video_id') or '—'}] "
            f"{e.get('date') or '—'} {_fmt_size(e.get('size_bytes', 0))} "
            f"{e.get('origin') or '—'}"
        )


def _list_json(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": entry.get("index"),
        "video_id": entry.get("video_id"),
        "title": entry.get("title"),
        "date": entry.get("date"),
        "size_bytes": entry.get("size_bytes"),
        "origin": entry.get("origin"),
        "dir": entry.get("dir"),
    }


def _resolve_target(
    root: Path, entries: list[dict[str, Any]], target: str
) -> tuple[dict[str, Any], Path] | None:
    """(entry, папка) по номеру [i] (цифры) или video id. Нет — None."""
    if target.isdigit():
        for e in entries:
            if e.get("index") == int(target):
                return e, root / e["dir"]
        return None
    found, _ = storage_mod.find_video_dirs(root, [target])
    if not found:
        return None
    for e in entries:
        if e.get("dir") == found[0].name:
            return e, found[0]
    return None


def _video_stats(meta: dict[str, Any], segments: list[Any]) -> tuple[int, float]:
    """(слов, минут): из meta.stats, иначе посчитать по сегментам."""
    stats = meta.get("stats")
    if isinstance(stats, dict) and isinstance(stats.get("words"), (int, float)):
        try:
            minutes = round(float(stats.get("reading_time_min", 0.0)), 1)
        except (TypeError, ValueError):
            minutes = 0.0
        return int(stats["words"]), minutes
    if segments:
        try:
            comp = stats_mod.compute_stats(segments, meta.get("duration"))
            return int(comp.get("words", 0)), round(float(comp.get("reading_time_min", 0.0)), 1)
        except Exception:
            pass
    return 0, 0.0


def _detail_object(
    entry: dict[str, Any], video_dir: Path, meta: dict[str, Any], segments: list[Any]
) -> dict[str, Any]:
    """Всё для деталей: мета + слова/минуты + файлы."""
    words, minutes = _video_stats(meta, segments)
    return {
        "index": entry.get("index"),
        "video_id": entry.get("video_id"),
        "title": entry.get("title"),
        "url": meta.get("url"),
        "author": meta.get("channel") or meta.get("author"),
        "date": entry.get("date"),
        "duration_sec": meta.get("duration"),
        "origin": entry.get("origin"),
        "transcript_lang": meta.get("transcript_lang"),
        "words": words,
        "minutes": minutes,
        "files": storage_mod.list_files(video_dir),
        "dir": entry.get("dir"),
        "path": str(video_dir),
    }


def _print_details(detail: dict[str, Any]) -> None:
    dur = detail.get("duration_sec")
    dur_s = f"{dur} с ({_mmss(dur)})" if isinstance(dur, (int, float)) else "—"
    print(f"{detail.get('title') or '—'}")
    print(f"  id: {detail.get('video_id') or '—'}")
    print(f"  url: {detail.get('url') or '—'}")
    print(f"  Автор: {detail.get('author') or '—'}")
    print(f"  Дата: {detail.get('date') or '—'}")
    print(f"  Длительность: {dur_s}")
    print(
        f"  Источник: {detail.get('origin') or '—'} | Язык: {detail.get('transcript_lang') or '—'}"
    )
    print(f"  Слов: {detail.get('words')} | Минут: {detail.get('minutes')}")
    print("  Файлы:")
    for f in detail.get("files") or []:
        print(f"    - {f.get('name')} — {_fmt_size(f.get('size_bytes', 0))}")
    print(f"  Папка: {detail.get('path')}")


def _print_transcript(video_dir: Path, fmt: str) -> int:
    """Транскрипт через formats.to_* (txt/md/srt). Нет файла — exit 1."""
    segments = storage_mod.read_segments(video_dir)
    if segments is None:
        _error(f"нет transcript.json в {video_dir.name}.")
        return 1
    meta = storage_mod.read_meta(video_dir) or {}
    if fmt == "md":
        text = formats_mod.to_md(segments, meta)
    elif fmt == "srt":
        text = formats_mod.to_srt(segments, meta)
    else:
        text = formats_mod.to_txt(segments, meta)
    if text:
        print(text)
    return 0


def _open_report(report_path: str | Path, opener=None) -> bool:
    """Открыть report.html в браузере (opener-инъекция для тестов)."""
    if not Path(report_path).is_file():
        return False
    (opener if opener is not None else webbrowser.open)(f"file://{Path(report_path)}")
    return True


def _tui_ask(prompt: str = "") -> str | None:
    """Ввод построчного навигатора: пусто/EOF — None (выход)."""
    try:
        text = input(prompt)
    except EOFError:
        return None
    return text if text.strip() else None


def _tui_actions(root: Path, entry: dict[str, Any], opener, ask) -> int:
    """Меню действий видео: 0 — выйти, 1 — назад к списку."""
    video_dir = root / entry["dir"]
    while True:
        act = ask(f"[{entry['index']}] [i]нфо / [t]ранскрипт / [o]ткрыть report / [q]выход: ")
        if act is None:
            return 0
        act = act.strip().lower()
        if act in ("q", "й"):
            return 0
        if act in ("i", "и", "ш"):
            _print_details(
                _detail_object(
                    entry,
                    video_dir,
                    storage_mod.read_meta(video_dir) or {},
                    storage_mod.read_segments(video_dir) or [],
                )
            )
        elif act in ("t", "т", "е"):
            code = _print_transcript(video_dir, "txt")
            if code != 0:
                continue
        elif act in ("o", "о", "щ"):
            if not _open_report(video_dir / "report.html", opener):
                _error(f"нет report.html в {video_dir.name}.")
        else:
            print(f"Непонятно {act!r}: нужно i / t / o / q.")
            continue
        return 1


def run_tui(root: Path, entries: list[dict[str, Any]], opener=None, ask=None) -> int:
    """Простой построчный навигатор (не полноэкранный TUI). Пусто/EOF — выход 0."""
    ask = ask if ask is not None else _tui_ask
    by_num = {str(e["index"]): e for e in entries}
    while True:
        _print_library_list(root, entries)
        choice = ask("Номер видео (пусто — выход): ")
        if choice is None:
            return 0
        entry = by_num.get(choice.strip())
        if entry is None:
            print(f"Нет видео с номером {choice.strip()!r}.")
            continue
        if _tui_actions(root, entry, opener, ask) == 0:
            return 0


def _main_library(argv: list[str]) -> int:
    """Навигатор библиотеки: список / детали / транскрипт / report. Exit 0/1/2.

    Приоритет одного видео: --json > --transcript > --open > детали.
    --tui ни с чем не сочетается (exit 2).
    """
    _init_color(argv)
    args = build_library_parser().parse_args(argv[1:])
    cfg = config_mod.load_config()
    root = storage_mod.resolve_root(None, cfg)
    entries = _library_entries(root)
    if args.tui:
        if (
            args.target is not None
            or args.json
            or args.transcript
            or args.open
            or args.format != "txt"
        ):
            _error("--tui не сочетается с номером и флагами вывода (режим — отдельно).")
            return 2
        if not entries:
            print(f"Библиотека пуста: {root}. Скачайте видео: kw-yt <URL> (без --out).")
            return 0
        return run_tui(root, entries)
    if args.target is None:
        if args.json:
            print(json.dumps([_list_json(e) for e in entries], ensure_ascii=False, indent=2))
            return 0
        if not entries:
            print(f"Библиотека пуста: {root}. Скачайте видео: kw-yt <URL> (без --out).")
            return 0
        _print_library_list(root, entries)
        return 0
    resolved = _resolve_target(root, entries, args.target)
    if resolved is None:
        if args.target.isdigit():
            _error(f"нет видео с номером {args.target}: в библиотеке {len(entries)}.")
        else:
            _error(f"видео {args.target!r} нет в библиотеке.")
        return 1
    entry, video_dir = resolved
    meta = storage_mod.read_meta(video_dir) or {}
    segments = storage_mod.read_segments(video_dir) or []
    if args.json:
        print(
            json.dumps(
                _detail_object(entry, video_dir, meta, segments),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.transcript:
        return _print_transcript(video_dir, args.format)
    if args.open:
        if not _open_report(video_dir / "report.html"):
            _error(f"нет report.html в {video_dir.name}.")
            return 1
        print(f"Открываю {video_dir.name}/report.html в браузере.")
        return 0
    _print_details(_detail_object(entry, video_dir, meta, segments))
    return 0


def _main_clean(argv: list[str]) -> int:
    """Удаление видео из библиотеки и/или кэша. Exit 0/1/2."""
    _init_color(argv)
    args = build_clean_parser().parse_args(argv[1:])
    cfg = config_mod.load_config()
    root = storage_mod.resolve_root(None, cfg)

    if args.all and not args.yes:
        _error("--all удаляет ВСЮ библиотеку. Подтвердите: kw-yt clean --all --yes.")
        return 2

    days = None
    if args.older_than is not None:
        try:
            days = int(str(args.older_than).strip())
        except (TypeError, ValueError):
            days = -1
        if days < 0:
            _error(
                f"--older-than должен быть целым числом дней >= 0, получено {args.older_than!r}."
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
        _error("укажите ID, --all --yes или --older-than DAYS (см. kw-yt clean --help).")
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


def _main_completion(argv: list[str]) -> int:
    """Печать bash-completion в stdout (только локально, без сети)."""
    _init_color(argv)
    args = build_completion_parser().parse_args(argv[1:])
    if args.shell != "bash":
        _error(f"оболочка {args.shell!r} не поддерживается (пока только bash).")
        return 2
    print(render_bash_completion(), end="")
    return 0


def _main_update(argv: list[str]) -> int:
    """Самообновление: --check — детект + сравнение (exit 0 при успехе).

    Полный прогон: уже свежее — 0, обновлено — код run_update (0/1),
    несравнимое — принудительно обновить, сеть упала — 1.
    """
    _init_color(argv)
    args = build_update_parser().parse_args(argv[1:])
    info = update_mod.detect_install()
    kind, detail = info.get("kind", "unknown"), info.get("detail", "")
    try:
        remote = update_mod.remote_version()
    except update_mod.UpdateError as e:
        _error(str(e))
        return 1
    cmp = update_mod.compare_versions(__version__, remote)
    if args.check:
        print(f"Установка: {kind} ({detail}). Локально: {__version__}, сервер: {remote}.")
        if cmp is None:
            print("Версии несравнимы — считаем, что обновление доступно.")
        elif cmp < 0:
            print("Доступно обновление: kw-yt update.")
        else:
            print("Уже свежее.")
        return 0
    if cmp is not None and cmp >= 0:
        print(f"Уже свежее: {__version__} (на сервере {remote}).")
        return 0
    if cmp is None:
        print(
            f"Версии несравнимы (локально {__version__!r}, сервер {remote!r}) — "
            "обновляю принудительно."
        )
    return update_mod.run_update(kind, detail)


if __name__ == "__main__":
    raise SystemExit(main())
