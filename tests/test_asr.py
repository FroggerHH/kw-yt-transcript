"""Тесты asr.transcribe_whisper со stub-моделью/загрузчиком: без сети, ffmpeg, HOME."""

import sys

import pytest

from kw_yt_transcript import asr
from kw_yt_transcript.asr import ASRError, transcribe_whisper


class StubSeg:
    def __init__(self, text, start, end):
        self.text = text
        self.start = start
        self.end = end


class StubModel:
    def __init__(self, segments):
        self._segments = segments
        self.seen = {}

    def transcribe(self, path, vad_filter=True):
        self.seen = {"path": path, "vad_filter": vad_filter}
        return self._segments, {"language": "ru"}


def stub_factory(model, expected_name="small"):
    def factory(model_name):
        assert model_name == expected_name, model_name
        return model

    return factory


def test_local_file_with_stub_model(tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"fake-audio")
    model = StubModel([StubSeg(" привет ", 0.0, 2.5), StubSeg("мир", 3.0, 4.0)])
    segments, origin = transcribe_whisper(str(audio), model_factory=stub_factory(model))
    assert origin == "whisper"
    assert segments == [
        {"text": "привет", "start": 0.0, "duration": 2.5},
        {"text": "мир", "start": 3.0, "duration": 1.0},
    ]
    assert model.seen["path"] == str(audio)
    assert model.seen["vad_filter"] is True
    assert audio.is_file(), "свой файл не удаляем"


def test_url_with_stub_downloader_not_deleted(tmp_path):
    audio = tmp_path / "dl.mp3"
    audio.write_bytes(b"fake-audio")
    seen = {}

    def downloader(url):
        seen["url"] = url
        return str(audio)

    model = StubModel([StubSeg("текст", 1.0, 2.0)])
    segments, origin = transcribe_whisper(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        model_factory=stub_factory(model),
        downloader=downloader,
    )
    assert seen["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert segments[0]["duration"] == pytest.approx(1.0)
    assert origin == "whisper"
    assert audio.is_file(), "файл загрузчика не удаляем"


def test_missing_faster_whisper_russian_error(tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"fake-audio")

    def no_lib_factory(model_name):
        raise ImportError("No module named 'faster_whisper'")

    with pytest.raises(ASRError, match=r"pip install kw-yt-transcript\[asr\]"):
        transcribe_whisper(str(audio), model_factory=no_lib_factory)


def test_default_factory_without_extra_raises_asr_error(tmp_path):
    assert "faster_whisper" not in sys.modules
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"fake-audio")
    with pytest.raises(ASRError, match="faster-whisper"):
        transcribe_whisper(str(audio))


def test_transcribe_failure_wrapped(tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"fake-audio")

    class DeadModel:
        def transcribe(self, path, vad_filter=True):
            raise RuntimeError("CUDA OOM")

    with pytest.raises(ASRError, match="не смог распознать"):
        transcribe_whisper(str(audio), model_factory=lambda name: DeadModel())


def test_custom_downloader_failure_wrapped():
    def dead_downloader(url):
        raise RuntimeError("ERROR: Private video")

    with pytest.raises(ASRError, match="Не удалось скачать аудио"):
        transcribe_whisper(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            model_factory=stub_factory(StubModel([StubSeg("текст", 0.0, 1.0)])),
            downloader=dead_downloader,
        )


def test_empty_result_raises(tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"fake-audio")
    with pytest.raises(ASRError, match="пустой результат"):
        transcribe_whisper(str(audio), model_factory=stub_factory(StubModel([])))


def test_default_download_tmpdir_cleaned(monkeypatch, tmp_path):
    created = []
    real_mktemp = asr.tempfile.mkdtemp

    def tracking_mktemp(*a, **k):
        d = real_mktemp(*a, **k)
        created.append(d)
        return d

    monkeypatch.setattr(asr.tempfile, "mkdtemp", tracking_mktemp)

    audio = tmp_path / "dl.mp3"
    audio.write_bytes(b"fake-audio")
    monkeypatch.setattr(asr, "_download_bestaudio", lambda url, tmpdir: str(audio))

    model = StubModel([StubSeg("текст", 0.0, 1.0)])
    transcribe_whisper("dQw4w9WgXcQ", model_factory=stub_factory(model))
    assert created, "временная папка должна создаваться для скачивания"
    import os

    assert not os.path.exists(created[0]), "временное аудио должно чиститься"


def test_no_real_faster_whisper_imported():
    assert "faster_whisper" not in sys.modules
