"""Тесты batch-цикла cli.main: всё на моках, реальная запись только в tmp_path."""

import json
from pathlib import Path

from kw_yt_transcript import asr as asr_mod
from kw_yt_transcript import cli as cli_mod
from kw_yt_transcript import metadata as metadata_mod
from kw_yt_transcript import transcript as transcript_mod
from kw_yt_transcript.metadata import MetadataError
from kw_yt_transcript.transcript import NoTranscriptError

VIDS = ["dQw4w9WgXcQ", "9bZkp7q19f0", "M7lc1UVf-VE"]
SEGMENTS = json.loads(
    (Path(__file__).parent / "fixtures" / "segments.json").read_text(encoding="utf-8")
)


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


def patch_all(monkeypatch, fail_meta=(), no_subs=()):
    monkeypatch.setattr(
        metadata_mod,
        "get_metadata",
        lambda source: (_ for _ in ()).throw(MetadataError(f"Нет видео {source}"))
        if any(v in source for v in fail_meta)
        else make_meta(next(v for v in VIDS if v in source)),
    )

    def fake_transcript(video_id, languages=None):
        if video_id in no_subs:
            raise NoTranscriptError("нет субтитров")
        return SEGMENTS, "manual"

    monkeypatch.setattr(transcript_mod, "get_transcript", fake_transcript)
    monkeypatch.setattr(asr_mod, "transcribe_whisper", lambda *a, **k: (SEGMENTS, "whisper"))


def read_index(out):
    return json.loads((out / "index.json").read_text(encoding="utf-8"))


def test_batch_all_ok_exit_0(monkeypatch, tmp_path, capsys):
    patch_all(monkeypatch)
    out = tmp_path / "out"
    assert cli_mod.main(VIDS + ["-o", str(out)]) == 0
    dirs = [d for d in out.iterdir() if d.is_dir()]
    assert len(dirs) == 3
    index = read_index(out)
    assert index["_type"] == "batch"
    assert index["failed"] == 0
    assert len(index["entries"]) == 3
    err = capsys.readouterr().err
    assert "[1/3]" in err and "[3/3]" in err and "ok" in err


def test_batch_partial_exit_1(monkeypatch, tmp_path):
    patch_all(monkeypatch, fail_meta=("9bZkp7q19f0",))
    out = tmp_path / "out"
    assert cli_mod.main(VIDS + ["-o", str(out)]) == 1
    assert len([d for d in out.iterdir() if d.is_dir()]) == 2
    index = read_index(out)
    assert index["failed"] == 1
    assert sum(1 for e in index["entries"] if e["error"]) == 1


def test_playlist_expands_to_videos(monkeypatch, tmp_path):
    patch_all(monkeypatch)
    monkeypatch.setattr(
        cli_mod,
        "expand_playlist",
        lambda url: [f"https://www.youtube.com/watch?v={v}" for v in VIDS],
    )
    out = tmp_path / "out"
    url = "https://www.youtube.com/playlist?list=PL123"
    assert cli_mod.main([url, "-o", str(out)]) == 0
    assert len([d for d in out.iterdir() if d.is_dir()]) == 3
    assert read_index(out)["_type"] == "playlist"


def test_whisper_fallback_used(monkeypatch, tmp_path):
    patch_all(monkeypatch, no_subs=("9bZkp7q19f0",))
    out = tmp_path / "out"
    assert cli_mod.main(VIDS[:2] + ["-o", str(out)]) == 0
    index = read_index(out)
    by_id = {e["video_id"]: e for e in index["entries"]}
    assert by_id["9bZkp7q19f0"]["origin"] == "whisper"


def test_no_fallback_whisper_fails_video(monkeypatch, tmp_path):
    patch_all(monkeypatch, no_subs=("9bZkp7q19f0",))
    out = tmp_path / "out"
    assert cli_mod.main(VIDS[:2] + ["--no-fallback-whisper", "-o", str(out)]) == 1
    index = read_index(out)
    assert index["failed"] == 1


def test_format_filter(monkeypatch, tmp_path):
    patch_all(monkeypatch)
    out = tmp_path / "out"
    assert cli_mod.main([VIDS[0], "--format", "txt", "-o", str(out)]) == 0
    (video_dir,) = [d for d in out.iterdir() if d.is_dir()]
    names = {p.name for p in video_dir.iterdir()}
    assert names == {"meta.json", "transcript.txt"}


def test_exit_2_empty_and_garbage():
    assert cli_mod.main([]) == 2
    assert cli_mod.main(["!!!"]) == 2
