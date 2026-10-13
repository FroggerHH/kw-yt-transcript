"""CLI kw-yt: разбор аргументов и пакетная загрузка (Фаза 3).

Полный цикл: parse_inputs → get_metadata → get_transcript
(или Whisper-fallback) → write_video + index.json.
Импорты только stdlib + свои модули: --help работает без сети
и без опциональных зависимостей (yt-dlp/transcript/whisper — лениво).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from kw_yt_transcript import __version__, asr, metadata, outputs, transcript
from kw_yt_transcript.inputs import parse_inputs
from kw_yt_transcript.metadata import MetadataError
from kw_yt_transcript.transcript import NoTranscriptError

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


def expand_playlist(url: str, ydl_factory=None) -> list[str]:
    """Flat-развёртка плейлиста в список URL видео (ленивый yt-dlp).

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
            continue
        entry_url = entry.get("url") or ""
        if "://" in entry_url:
            out.append(entry_url)
        elif entry.get("id"):
            out.append(f"https://www.youtube.com/watch?v={entry['id']}")
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
    """
    meta: dict[str, Any] | None = None
    try:
        meta = metadata.get_metadata(source)
        video_id = meta.get("video_id") or hint_id
        if not video_id:
            raise MetadataError(f"yt-dlp не вернул video id для {source!r}.")
        try:
            segments, origin = transcript.get_transcript(video_id, languages=langs)
        except NoTranscriptError:
            if not use_whisper:
                raise
            segments, origin = asr.transcribe_whisper(
                meta.get("url") or source, model_name=whisper_model
            )
        paths = outputs.write_video(out_dir, meta, segments, origin, formats_sel)
        return {"meta": meta, "dir": Path(paths["dir"]).name, "origin": origin, "error": None}
    except Exception as e:
        return {"meta": meta, "dir": None, "origin": None, "error": str(e)}


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Коды: 0 — всё ок, 1 — частичные ошибки, 2 — usage/фатальное."""
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

    out_dir = Path(args.out)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Ошибка: не могу создать папку {args.out!r}: {e}", flush=True)
        return 2

    langs = [lang.strip() for lang in args.langs.split(",") if lang.strip()] or ["ru", "en"]
    use_whisper = not args.no_fallback_whisper

    # Плейлисты разворачиваем в видео; неуспешный expand — ошибка-запись, batch идёт дальше.
    video_tasks: list[tuple[str, str | None]] = []
    playlist_url: str | None = None
    results: list[dict[str, Any]] = []
    for job in jobs:
        if job["kind"] == "playlist":
            url = job.get("url") or job.get("raw", "")
            if playlist_url is None:
                playlist_url = url
            try:
                entries = expand_playlist(url)
            except Exception as e:
                results.append({"meta": None, "dir": None, "origin": None, "error": str(e)})
                print(f"плейлист {url}: FAIL: {e}", file=sys.stderr)
                continue
            for entry_url in entries:
                video_tasks.append((entry_url, None))
        else:
            video_tasks.append(
                (job.get("url") or job.get("video_id") or job.get("raw", ""), job.get("video_id"))
            )

    if not video_tasks and not results:
        print("Ошибка: по заданным входам видео не найдено.", flush=True)
        return 2

    total = len(video_tasks)
    for i, (source, hint_id) in enumerate(video_tasks, 1):
        label = hint_id or source
        result = _process_video(
            source, hint_id, langs, use_whisper, args.whisper_model, out_dir, args.format
        )
        results.append(result)
        if result["error"]:
            print(f"[{i}/{total}] {label} ... FAIL: {result['error']}", file=sys.stderr)
        else:
            print(
                f"[{i}/{total}] {result['meta'].get('video_id')} ... ok", file=sys.stderr
            )

    try:
        index_path = outputs.write_index(out_dir, results, playlist_url)
    except OSError as e:
        print(f"Ошибка: не могу записать index.json: {e}", flush=True)
        return 2

    failed = sum(1 for r in results if r["error"])
    ok = len(results) - failed
    print(f"Готово: {ok}/{len(results)}, ошибок: {failed}. Папка: {out_dir}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
