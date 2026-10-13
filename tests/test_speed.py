"""Тесты скорости/надёжности (Волна 2): jobs, resume, cache, config.

Без сети: мокиget_metadata/transcript, tmp XDG_* через env.
"""

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from kw_yt_transcript import asr as asr_mod
from kw_yt_transcript import cache as cache_mod
from kw_yt_transcript import cli as cli_mod
from kw_yt_transcript import config as config_mod
from kw_yt_transcript import metadata as metadata_mod
from kw_yt_transcript import outputs as outputs_mod
from kw_yt_transcript import transcript as transcript_mod
from kw_yt_transcript.metadata import MetadataError
from kw_yt_transcript.transcript import NoTranscriptError

VIDS = ["dQw4w9WgXcQ", "9bZkp7q19f0", "M7lc1UVf-VE"]
SEGMENTS = json.loads(
    (Path(__file__).parent / "fixtures" / "segments.json").read_text(encoding="utf-8")
)


@pytest.fixture(autouse=True)
def _isolated_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


def make_meta(video_id):
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": f"Видео {video_id}",
        "channel": "Канал",
        "author": "Автор",
        "channel_id": "UC1",
        "duration": 100,
        "upload_date": "20260101",
        "view_count": 10,
        "like_count": 1,
        "description": "",
        "chapters": [],
        "thumbnails": [],
        "tags": [],
        "categories": [],
        "subtitles_keys": ["ru"],
        "automatic_captions_keys": [],
    }


def patch_all(monkeypatch, calls=None):
    def fake_meta(source):
        if calls is not None:
            calls["meta"] += 1
        hit = next((v for v in VIDS if v in source), None)
        if hit is None:
            raise MetadataError(f"Нет видео {source}")
        return make_meta(hit)

    def fake_transcript(video_id, languages=None):
        if calls is not None:
            calls["transcript"] += 1
        return SEGMENTS, "manual", "ru"

    def fake_whisper(*a, **k):
        if calls is not None:
            calls["whisper"] += 1
        return SEGMENTS, "whisper"

    monkeypatch.setattr(metadata_mod, "get_metadata", fake_meta)
    monkeypatch.setattr(transcript_mod, "get_transcript", fake_transcript)
    monkeypatch.setattr(asr_mod, "transcribe_whisper", fake_whisper)


# --- jobs ---


def test_jobs_parallel_order_stable(monkeypatch, tmp_path):
    patch_all(monkeypatch)
    out = tmp_path / "out"
    assert cli_mod.main(VIDS + ["--jobs", "4", "-o", str(out)]) == 0
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert [e["video_id"] for e in index["entries"]] == VIDS
    assert index["failed"] == 0


def test_playlist_error_keeps_input_position(monkeypatch, tmp_path):
    patch_all(monkeypatch)

    def dead_expand(url):
        raise MetadataError("Не удалось прочитать плейлист")

    monkeypatch.setattr(cli_mod, "expand_playlist", dead_expand)
    out = tmp_path / "out"
    url = "https://www.youtube.com/playlist?list=PLDEAD"
    assert cli_mod.main([VIDS[0], url, VIDS[1], "-o", str(out)]) == 1
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert [e["video_id"] for e in index["entries"]] == [VIDS[0], None, VIDS[1]]
    assert "плейлист" in index["entries"][1]["error"].lower()


def test_garbage_errors_lead_entries(monkeypatch, tmp_path):
    # Мусорные токены без позиций: их записи — первыми (ограничение inputs).
    patch_all(monkeypatch)
    out = tmp_path / "out"
    assert cli_mod.main([VIDS[0], "!!!", VIDS[1], "-o", str(out)]) == 1
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert index["entries"][0]["error"] and "Непонятный вход" in index["entries"][0]["error"]
    assert [e["video_id"] for e in index["entries"][1:]] == [VIDS[0], VIDS[1]]


def test_whisper_semaphore_limits_concurrency(monkeypatch, tmp_path):
    state = {"cur": 0, "max": 0}
    lock = threading.Lock()

    def fake_meta(source):
        hit = next(v for v in VIDS if v in source)
        return make_meta(hit)

    def fake_transcript(video_id, languages=None):
        raise NoTranscriptError("нет субтитров")

    def fake_whisper(*a, **k):
        with lock:
            state["cur"] += 1
            state["max"] = max(state["max"], state["cur"])
        try:
            time.sleep(0.05)
        finally:
            with lock:
                state["cur"] -= 1
        return SEGMENTS, "whisper"

    monkeypatch.setattr(metadata_mod, "get_metadata", fake_meta)
    monkeypatch.setattr(transcript_mod, "get_transcript", fake_transcript)
    monkeypatch.setattr(asr_mod, "transcribe_whisper", fake_whisper)
    out = tmp_path / "out"
    assert cli_mod.main(VIDS + ["--jobs", "4", "-o", str(out)]) == 0
    assert state["max"] <= 2, f"конкурентных whisper: {state['max']}"
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert index["failed"] == 0
    assert [e["origin"] for e in index["entries"]] == ["whisper"] * 3


def test_jobs_bad_values_exit_2(monkeypatch, tmp_path):
    patch_all(monkeypatch)
    out = tmp_path / "out"
    for bad in ("0", "17", "abc"):
        assert cli_mod.main([VIDS[0], "--jobs", bad, "-o", str(out)]) == 2


# --- resume ---


def test_resume_skips_ready_without_network(monkeypatch, tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    outputs_mod.write_video(out, make_meta(VIDS[0]), SEGMENTS, "manual")
    calls = {"meta": 0, "transcript": 0, "whisper": 0}
    patch_all(monkeypatch, calls)
    assert cli_mod.main([VIDS[0], "--resume", "-o", str(out)]) == 0
    assert calls == {"meta": 0, "transcript": 0, "whisper": 0}
    assert "skip" in capsys.readouterr().err


def test_find_ready_helper(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert outputs_mod.find_ready(out, VIDS[0]) is None
    paths = outputs_mod.write_video(out, make_meta(VIDS[0]), SEGMENTS, "manual")
    found = outputs_mod.find_ready(out, VIDS[0])
    assert found is not None and found == Path(paths["dir"])
    assert outputs_mod.find_ready(out, "9bZkp7q19f0") is None


def test_find_ready_needs_full_bundle(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    paths = outputs_mod.write_video(out, make_meta(VIDS[1]), SEGMENTS, "manual", formats_sel="txt")
    assert outputs_mod.find_ready(out, VIDS[1]) is None, "нет transcript.json — не готово"
    weak = out / f"слабая-папка_{VIDS[2]}"
    weak.mkdir()
    record = {**make_meta(VIDS[2]), "origin": "manual", "stats": {"words": 5}}
    (weak / "meta.json").write_text(json.dumps(record, ensure_ascii=False), "utf-8")
    assert outputs_mod.find_ready(out, VIDS[2]) is None, "только meta.json — не готово"
    assert Path(paths["dir"]).name.endswith(VIDS[1])


def test_resume_weak_dir_calls_network(monkeypatch, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    weak = out / f"слабая-папка_{VIDS[0]}"
    weak.mkdir()
    record = {**make_meta(VIDS[0]), "origin": "manual", "stats": {"words": 5}}
    (weak / "meta.json").write_text(json.dumps(record, ensure_ascii=False), "utf-8")
    calls = {"meta": 0, "transcript": 0, "whisper": 0}
    patch_all(monkeypatch, calls)
    assert cli_mod.main([VIDS[0], "--resume", "-o", str(out)]) == 0
    assert calls["meta"] == 1, "неполная папка — resume не срабатывает, идёт сеть"


# --- cache ---


class StubYDL:
    def __init__(self, info):
        self._info = info

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        return self._info

    def sanitize_info(self, info):
        return info


def _info_for(video_id):
    return {"id": video_id, "title": f"Видео {video_id}", "webpage_url": url_of(video_id)}


def url_of(video_id):
    return f"https://www.youtube.com/watch?v={video_id}"


def test_cache_second_call_no_factory(tmp_path):
    calls = []

    def factory(opts):
        calls.append(opts)
        return StubYDL(_info_for(VIDS[0]))

    meta1 = metadata_mod.get_metadata(VIDS[0], ydl_factory=factory)
    meta2 = metadata_mod.get_metadata(VIDS[0], ydl_factory=factory)
    assert meta1 == meta2
    assert len(calls) == 1


def test_cache_expired_is_miss():
    cache_mod.cache_set(VIDS[1], make_meta(VIDS[1]))
    path = cache_mod.cache_dir() / f"{VIDS[1]}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["saved_at"] = 0.0
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert cache_mod.cache_get(VIDS[1]) is None


def test_cache_corrupt_is_miss_silent():
    path = cache_mod.cache_dir() / f"{VIDS[2]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{не json", encoding="utf-8")
    assert cache_mod.cache_get(VIDS[2]) is None


def test_cache_ttl_respected():
    cache_mod.cache_set(VIDS[0], make_meta(VIDS[0]), ttl=100)
    assert cache_mod.cache_get(VIDS[0])["video_id"] == VIDS[0]


# --- config ---


def _write_config(home, body):
    cfg = home / "kw-yt" / "config.toml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(body, encoding="utf-8")


def test_config_missing_gives_defaults_silent(capsys):
    cfg = config_mod.load_config()
    assert cfg == {"langs": "ru,en", "out": None, "jobs": 4, "whisper_model": "small"}
    assert capsys.readouterr().err == ""


def test_config_version_guard(monkeypatch, capsys):
    monkeypatch.setattr(sys, "version_info", (3, 10))
    cfg = config_mod.load_config()
    assert cfg == {"langs": "ru,en", "out": None, "jobs": 4, "whisper_model": "small"}
    assert "3.11" in capsys.readouterr().err


def test_config_reads_tool_defaults(tmp_path, monkeypatch):
    home = tmp_path / "cfghome"
    _write_config(
        home,
        '[tool.defaults]\nlangs = "en,ru"\nout = "./custom"\njobs = 8\nwhisper_model = "tiny"\n',
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    cfg = config_mod.load_config()
    assert cfg == {"langs": "en,ru", "out": "./custom", "jobs": 8, "whisper_model": "tiny"}


def test_config_reads_plain_defaults_section(tmp_path, monkeypatch):
    home = tmp_path / "cfghome"
    _write_config(home, '[defaults]\nlangs = "de"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    cfg = config_mod.load_config()
    assert cfg["langs"] == "de" and cfg["jobs"] == 4


def test_config_broken_gives_defaults(tmp_path, monkeypatch, capsys):
    home = tmp_path / "cfghome"
    _write_config(home, "[tool.defaults\nlangs = oops\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    assert config_mod.load_config()["langs"] == "ru,en"
    assert "редупреждение" in capsys.readouterr().err


def test_cli_flags_beat_config(monkeypatch, tmp_path):
    home = tmp_path / "cfghome"
    _write_config(home, '[tool.defaults]\nlangs = "en"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    seen = {}

    def fake_transcript(video_id, languages=None):
        seen["languages"] = list(languages)
        return SEGMENTS, "manual", "ru"

    patch_all(monkeypatch)
    monkeypatch.setattr(transcript_mod, "get_transcript", fake_transcript)
    out = tmp_path / "out"
    assert cli_mod.main([VIDS[0], "-o", str(out)]) == 0
    assert seen["languages"] == ["en"], "конфиг применяется при отсутствии флага"
    out2 = tmp_path / "out2"
    assert cli_mod.main([VIDS[0], "--langs", "ru", "-o", str(out2)]) == 0
    assert seen["languages"] == ["ru"], "CLI-флаг важнее конфига"


def test_config_jobs_used_when_flag_absent(monkeypatch, tmp_path):
    home = tmp_path / "cfghome"
    _write_config(home, "[tool.defaults]\njobs = 2\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    patch_all(monkeypatch)
    out = tmp_path / "out"
    assert cli_mod.main(VIDS[:2] + ["-o", str(out)]) == 0
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert [e["video_id"] for e in index["entries"]] == VIDS[:2]
