"""Whisper-fallback через faster-whisper (Фаза 3).

Импорт faster-whisper и скачивание аудио — ленивые, внутри функций:
``kw-yt --help`` и тесты работают без extra-зависимости, сети и ffmpeg
(подменяются через ``model_factory`` / ``downloader``).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable


class ASRError(Exception):
    """Не удалось распознать речь."""


def _default_model_factory(model_name: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ASRError(
            "Нет модуля faster-whisper. Установите ASR-зависимость: "
            "pip install kw-yt-transcript[asr]"
        ) from e
    return WhisperModel(model_name)


def _download_bestaudio(video_url: str, tmpdir: str) -> str:
    """Скачать лучшее аудио во временную папку, вернуть путь к mp3."""
    try:
        import yt_dlp
    except ImportError as e:
        raise ASRError(f"Для скачивания аудио нужен yt-dlp: {e}") from e
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "outtmpl": str(Path(tmpdir) / "%(id)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            audio = Path(ydl.prepare_filename(info)).with_suffix(".mp3")
    except Exception as e:
        raise ASRError(f"Не удалось скачать аудио {video_url!r}: {e}") from e
    if not audio.is_file():
        raise ASRError(f"Аудиофайл не создан после скачивания {video_url!r}.")
    return str(audio)


def transcribe_whisper(
    source: str | Path,
    model_name: str = "small",
    model_factory: Callable[[str], Any] | None = None,
    downloader: Callable[[str], str] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Распознать речь: локальный аудиофайл или URL видео (скачать bestaudio).

    :param source: путь к аудиофайлу или URL/id видео.
    :param model_factory: callable(model_name) -> модель с
        ``transcribe(path, vad_filter=True)`` -> (segments, info),
        сегменты — с ``.text/.start/.end``. По умолчанию — faster-whisper.
    :param downloader: callable(video_url) -> путь к аудио (в тестах — stub).
        По умолчанию — yt-dlp bestaudio во временную папку.
    :return: (segments [{text, start, duration}], 'whisper').
    :raises ASRError: нет faster-whisper, не скачалось, не распозналось.
    """
    tmpdir: str | None = None
    try:
        if Path(source).is_file():
            audio = str(source)
        elif downloader is not None:
            audio = downloader(str(source))  # чужой файл — не удаляем
        else:
            tmpdir = tempfile.mkdtemp(prefix="kw-yt-asr-")
            audio = _download_bestaudio(str(source), tmpdir)

        factory = model_factory or _default_model_factory
        try:
            model = factory(model_name)
        except ImportError as e:
            raise ASRError(
                "Нет модуля faster-whisper. Установите ASR-зависимость: "
                "pip install kw-yt-transcript[asr]"
            ) from e
        try:
            raw_segments, _info = model.transcribe(audio, vad_filter=True)
            segments = [
                {
                    "text": str(s.text).strip(),
                    "start": float(s.start),
                    "duration": float(s.end) - float(s.start),
                }
                for s in list(raw_segments)
            ]
        except Exception as e:
            raise ASRError(f"Whisper не смог распознать аудио: {e}") from e
        return segments, "whisper"
    finally:
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)
