"""Тесты asr.transcribe_whisper со stub-моделью/загрузчиком: без сети, ffmpeg, HOME."""

import importlib.util
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


def _have_ffmpeg(monkeypatch):
    monkeypatch.setattr(asr.shutil, "which", lambda name: "/usr/bin/ffmpeg")


def test_url_with_stub_downloader_not_deleted(monkeypatch, tmp_path):
    _have_ffmpeg(monkeypatch)
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
    if importlib.util.find_spec("faster_whisper") is not None:
        pytest.skip("faster_whisper установлен — тест изоляции без extra неприменим")
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


def test_custom_downloader_failure_wrapped(monkeypatch):
    _have_ffmpeg(monkeypatch)
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
    _have_ffmpeg(monkeypatch)
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


def test_ffmpeg_preflight_no_download(monkeypatch):
    monkeypatch.setattr(asr.shutil, "which", lambda name: None)
    called = []

    def downloader(url):
        called.append(url)
        return "/tmp/never.mp3"

    with pytest.raises(ASRError, match="ffmpeg"):
        transcribe_whisper(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            model_factory=stub_factory(StubModel([StubSeg("текст", 0.0, 1.0)])),
            downloader=downloader,
        )
    assert called == [], "без ffmpeg загрузчик не вызывается"


def test_no_real_faster_whisper_imported():
    assert "faster_whisper" not in sys.modules


def test_pyav_metadata_errors_fallback_to_ndarray(monkeypatch, tmp_path):
    import os

    np = pytest.importorskip("numpy")
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"fake-audio")
    calls = []
    seen = {}
    fake_samples = np.zeros(16000, dtype=np.float32)

    class AvBrokenModel:
        def transcribe(self, data, vad_filter=True):
            calls.append(data)
            if isinstance(data, str):
                raise TypeError('av.open() got an unexpected keyword argument "metadata_errors"')
            return [StubSeg("текст", 0.0, 1.5)], {"language": "ru"}

    def fake_decode(path, tmpdir):
        seen["path"] = path
        seen["tmpdir"] = tmpdir
        return fake_samples

    monkeypatch.setattr(asr, "_decode_via_ffmpeg", fake_decode)
    segments, origin = transcribe_whisper(str(audio), model_factory=lambda name: AvBrokenModel())
    assert origin == "whisper"
    assert segments == [{"text": "текст", "start": 0.0, "duration": 1.5}]
    assert len(calls) == 2
    assert isinstance(calls[0], str)
    assert not isinstance(calls[1], str)
    assert seen["path"] == str(audio)
    assert not os.path.exists(seen["tmpdir"]), "wav-папка должна чиститься"


def test_plain_typeerror_no_fallback(tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"fake-audio")
    calls = []

    class BoomModel:
        def transcribe(self, path, vad_filter=True):
            calls.append(path)
            raise TypeError("boom")

    with pytest.raises(ASRError, match="не смог распознать"):
        transcribe_whisper(str(audio), model_factory=lambda name: BoomModel())
    assert len(calls) == 1, "без metadata_errors повтора быть не должно"


def test_decode_via_ffmpeg_fake_binary(monkeypatch, tmp_path):
    import os

    np = pytest.importorskip("numpy")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "ffmpeg"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, wave\n"
        "w = wave.open(sys.argv[-1], 'wb')\n"
        "w.setnchannels(1)\n"
        "w.setsampwidth(2)\n"
        "w.setframerate(16000)\n"
        "w.writeframes(bytes(range(256)) * 64)\n"
        "w.close()\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    audio = tmp_path / "in.mp3"
    audio.write_bytes(b"fake")
    samples = asr._decode_via_ffmpeg(str(audio), str(tmp_path))
    expected = (np.frombuffer(bytes(range(256)) * 64, dtype=np.int16).astype(np.float32) / 32768.0)
    assert samples.dtype == np.float32
    assert samples.shape == expected.shape
    assert np.allclose(samples, expected)


def test_decode_without_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(asr.shutil, "which", lambda name: None)
    with pytest.raises(ASRError, match="ffmpeg"):
        asr._decode_via_ffmpeg(str(tmp_path / "x.mp3"), str(tmp_path))


class VadCountingModel:
    """Возвращает [] при vad_filter=True, сегменты — при False; считает вызовы."""

    def __init__(self, segments):
        self._segments = segments
        self.calls = []

    def transcribe(self, data, vad_filter=True):
        self.calls.append(vad_filter)
        if vad_filter:
            return [], {"language": "ru"}
        return self._segments, {"language": "ru"}


def test_vad_retry_on_empty_result(tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"fake-audio")
    model = VadCountingModel([StubSeg("текст", 0.0, 1.5)])
    segments, origin = transcribe_whisper(str(audio), model_factory=lambda name: model)
    assert origin == "whisper"
    assert segments == [{"text": "текст", "start": 0.0, "duration": 1.5}]
    assert model.calls == [True, False]


def test_vad_retry_both_empty_raises(tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"fake-audio")
    model = VadCountingModel([])
    with pytest.raises(ASRError, match="пустой результат"):
        transcribe_whisper(str(audio), model_factory=lambda name: model)
    assert model.calls == [True, False]


def test_vad_no_retry_when_segments_found(tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"fake-audio")
    model = StubModel([StubSeg("текст", 0.0, 1.0)])
    calls = []
    orig_transcribe = model.transcribe

    def counting(data, vad_filter=True):
        calls.append(vad_filter)
        return orig_transcribe(data, vad_filter=vad_filter)

    model.transcribe = counting
    segments, origin = transcribe_whisper(str(audio), model_factory=lambda name: model)
    assert origin == "whisper" and len(segments) == 1
    assert calls == [True]
