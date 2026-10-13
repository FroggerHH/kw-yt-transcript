"""Whisper-fallback через faster-whisper (Фаза 3).

Импорт faster-whisper и скачивание аудио — ленивые, внутри функций:
``kw-yt --help`` и тесты работают без extra-зависимости, сети и ffmpeg
(подменяются через ``model_factory`` / ``downloader``).
PyAV ≥ 15 несовместим с faster-whisper 1.2.1 (TypeError metadata_errors):
при таком TypeError аудио декодируется системным ffmpeg в ndarray
(``_decode_via_ffmpeg``) и вызов повторяется без PyAV.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any


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


def _map_segments(raw: Any) -> list[dict[str, Any]]:
    """Сырые сегменты faster-whisper -> [{text, start, duration}]."""
    return [
        {
            "text": str(s.text).strip(),
            "start": float(s.start),
            "duration": float(s.end) - float(s.start),
        }
        for s in list(raw)
    ]


#: Таймаут декодирования аудио через ffmpeg (5 минут на файл).
_DECODE_TIMEOUT_SEC = 300


def _decode_via_ffmpeg(audio_path: str, tmpdir: str) -> Any:
    """Декодировать аудио системным ffmpeg в ndarray (float32, 16 кГц, моно).

    Обход несовместимости faster-whisper 1.2.1 с PyAV ≥ 15
    (``av.open(..., metadata_errors="ignore")`` падает с TypeError):
    модель штатно принимает ndarray вместо пути, PyAV не задействуется.

    :raises ASRError: нет ffmpeg/numpy, ffmpeg не справился, wav не читается.
    """
    if shutil.which("ffmpeg") is None:
        raise ASRError("Нет ffmpeg. Установите ffmpeg — он нужен для скачивания аудио.")
    try:
        import numpy as np
    except ImportError as e:
        raise ASRError(
            "Нет модуля numpy. Установите ASR-зависимость: pip install kw-yt-transcript[asr]"
        ) from e
    out_wav = str(Path(tmpdir) / "decode-16k-mono.wav")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(audio_path),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-f",
                "wav",
                out_wav,
            ],
            check=True,
            capture_output=True,
            timeout=_DECODE_TIMEOUT_SEC,
        )
    except FileNotFoundError as e:
        raise ASRError("Нет ffmpeg. Установите ffmpeg — он нужен для скачивания аудио.") from e
    except subprocess.TimeoutExpired as e:
        raise ASRError(
            f"ffmpeg не успел подготовить аудио за {_DECODE_TIMEOUT_SEC} с: {audio_path!r}."
        ) from e
    except subprocess.CalledProcessError as e:
        raise ASRError(
            f"ffmpeg не смог подготовить аудио {audio_path!r} (код {e.returncode})."
        ) from e
    try:
        with wave.open(out_wav, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())
    except Exception as e:
        raise ASRError(f"Не удалось прочитать wav после ffmpeg: {e}") from e
    if sampwidth != 2 or not frames:
        raise ASRError("ffmpeg вернул аудио не в формате int16 — распознавание невозможно.")
    pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        pcm = pcm.reshape(-1, n_channels).mean(axis=1)
    return pcm


def _transcribe_vad_chain(transcribe_call: Callable[[bool], Any]) -> list[dict[str, Any]]:
    """Вызов модели с цепочкой VAD: сначала ``vad_filter=True``, при пустом
    результате — повтор с ``vad_filter=False``.

    VAD Silero агрессивен на музыке (live-доказательство: 0 сегментов с VAD
    против 54 без него на том же треке) — пустой результат не приговор.
    Возможные галлюцинации без VAD покрываются маркировкой origin=whisper.
    Исключения не перехватываются — их разбирает вызывающий код.
    """
    raw, _info = transcribe_call(True)
    segments = _map_segments(raw)
    if not segments:
        raw, _info = transcribe_call(False)
        segments = _map_segments(raw)
    return segments


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
        else:
            # Аудио нет локально — понадобится скачивание, а ему нужен ffmpeg.
            if shutil.which("ffmpeg") is None:
                raise ASRError("Нет ffmpeg. Установите ffmpeg — он нужен для скачивания аудио.")
            if downloader is not None:
                try:
                    audio = downloader(str(source))  # чужой файл — не удаляем
                except Exception as e:
                    raise ASRError(f"Не удалось скачать аудио {str(source)!r}: {e}") from e
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
            segments = _transcribe_vad_chain(lambda vad: model.transcribe(audio, vad_filter=vad))
        except TypeError as e:
            if "metadata_errors" not in str(e):
                raise ASRError(f"Whisper не смог распознать аудио: {e}") from e
            # PyAV ≥ 15 несовместим с faster-whisper 1.2.1
            # (av.open(metadata_errors=...) падает): декодируем сами через
            # ffmpeg и повторяем вызов с ndarray — PyAV не задействуется.
            own_decode_dir = tmpdir is None
            decode_dir = tmpdir or tempfile.mkdtemp(prefix="kw-yt-asr-decode-")
            try:
                samples = _decode_via_ffmpeg(audio, decode_dir)
                try:
                    segments = _transcribe_vad_chain(
                        lambda vad: model.transcribe(samples, vad_filter=vad)
                    )
                except Exception as e2:
                    raise ASRError(f"Whisper не смог распознать аудио: {e2}") from e2
            finally:
                if own_decode_dir:
                    shutil.rmtree(decode_dir, ignore_errors=True)
        except Exception as e:
            raise ASRError(f"Whisper не смог распознать аудио: {e}") from e
        if not segments:
            raise ASRError("Whisper не распознал речь (пустой результат).")
        return segments, "whisper"
    finally:
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)
