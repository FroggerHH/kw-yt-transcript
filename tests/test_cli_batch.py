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
        return SEGMENTS, "manual", "ru"

    monkeypatch.setattr(transcript_mod, "get_transcript", fake_transcript)
    monkeypatch.setattr(asr_mod, "transcribe_whisper", lambda *a, **k: (SEGMENTS, "whisper"))


def expand_ok(urls):
    """Стаб expand_playlist нового формата [{url, error}]."""
    return lambda url: [{"url": u, "error": None} for u in urls]


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
        expand_ok([f"https://www.youtube.com/watch?v={v}" for v in VIDS]),
    )
    out = tmp_path / "out"
    url = "https://www.youtube.com/playlist?list=PL123"
    assert cli_mod.main([url, "-o", str(out)]) == 0
    assert len([d for d in out.iterdir() if d.is_dir()]) == 3
    assert read_index(out)["_type"] == "playlist"


def test_multi_playlist_is_batch(monkeypatch, tmp_path):
    patch_all(monkeypatch)

    def fake_expand(url):
        v = VIDS[0] if "PL1" in url else VIDS[1]
        return [{"url": f"https://www.youtube.com/watch?v={v}", "error": None}]

    monkeypatch.setattr(cli_mod, "expand_playlist", fake_expand)
    out = tmp_path / "out"
    urls = [
        "https://www.youtube.com/playlist?list=PL1",
        "https://www.youtube.com/playlist?list=PL2",
    ]
    assert cli_mod.main(urls + ["-o", str(out)]) == 0
    index = read_index(out)
    assert index["_type"] == "batch"
    assert len(index["entries"]) == 2


def test_playlist_plus_video_is_batch(monkeypatch, tmp_path):
    patch_all(monkeypatch)
    monkeypatch.setattr(
        cli_mod,
        "expand_playlist",
        expand_ok([f"https://www.youtube.com/watch?v={VIDS[1]}"]),
    )
    out = tmp_path / "out"
    url = "https://www.youtube.com/playlist?list=PL123"
    assert cli_mod.main([url, VIDS[0], "-o", str(out)]) == 0
    index = read_index(out)
    assert index["_type"] == "batch"
    assert len(index["entries"]) == 2


def test_empty_playlist_writes_index_and_exit_2(monkeypatch, tmp_path):
    patch_all(monkeypatch)
    monkeypatch.setattr(cli_mod, "expand_playlist", lambda url: [])
    out = tmp_path / "out"
    url = "https://www.youtube.com/playlist?list=PLEMPTY"
    assert cli_mod.main([url, "-o", str(out)]) == 2
    index = read_index(out)
    assert index["_type"] == "playlist"
    assert index["entries"] == []
    assert index["failed"] == 0


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
    assert names == {"meta.json", "transcript.txt", "report.html"}


def test_exit_2_empty_and_garbage():
    assert cli_mod.main([]) == 2
    assert cli_mod.main(["!!!"]) == 2


def test_mixed_garbage_partial_exit_1(monkeypatch, tmp_path):
    patch_all(monkeypatch)
    out = tmp_path / "out"
    assert cli_mod.main([VIDS[0], "!!!", VIDS[1], "-o", str(out)]) == 1
    assert len([d for d in out.iterdir() if d.is_dir()]) == 2
    index = read_index(out)
    assert index["failed"] == 1
    assert len(index["entries"]) == 3
    assert any("Непонятный вход" in (e["error"] or "") for e in index["entries"])


def test_metadata_failure_keeps_hint_id(monkeypatch, tmp_path):
    patch_all(monkeypatch, fail_meta=("9bZkp7q19f0",))
    out = tmp_path / "out"
    assert cli_mod.main([VIDS[1], "-o", str(out)]) == 1
    index = read_index(out)
    assert index["entries"][0]["video_id"] == "9bZkp7q19f0"
    assert index["entries"][0]["error"]


def test_playlist_skipped_entries_counted(monkeypatch, tmp_path):
    patch_all(monkeypatch)
    monkeypatch.setattr(
        cli_mod,
        "expand_playlist",
        lambda url: [
            {"url": f"https://www.youtube.com/watch?v={VIDS[0]}", "error": None},
            {"url": None, "error": "Запись плейлиста пропущена: нет video id/URL."},
            {"url": None, "error": "Запись плейлиста пропущена: не объект."},
        ],
    )
    out = tmp_path / "out"
    url = "https://www.youtube.com/playlist?list=PLMIX"
    assert cli_mod.main([url, "-o", str(out)]) == 1
    index = read_index(out)
    assert len(index["entries"]) == 3, "len(entries)==len(playlist)"
    assert index["failed"] == 2


def test_expand_failure_goes_to_index(monkeypatch, tmp_path):
    patch_all(monkeypatch)

    def dead_expand(url):
        raise MetadataError("Не удалось прочитать плейлист")

    monkeypatch.setattr(cli_mod, "expand_playlist", dead_expand)
    out = tmp_path / "out"
    url = "https://www.youtube.com/playlist?list=PLDEAD"
    assert cli_mod.main([url, "-o", str(out)]) == 1
    index = read_index(out)
    assert index["failed"] == 1
    assert "плейлист" in index["entries"][0]["error"].lower()


def test_langs_normalized(monkeypatch, tmp_path):
    patch_all(monkeypatch)
    seen = {}

    def fake_transcript(video_id, languages=None):
        seen["languages"] = list(languages)
        return SEGMENTS, "manual", "ru"

    monkeypatch.setattr(transcript_mod, "get_transcript", fake_transcript)
    out = tmp_path / "out"
    assert cli_mod.main([VIDS[0], "--langs", " RU ,,EN ", "-o", str(out)]) == 0
    assert seen["languages"] == ["ru", "en"]


def test_langs_comma_only_defaults(monkeypatch, tmp_path):
    patch_all(monkeypatch)
    seen = {}

    def fake_transcript(video_id, languages=None):
        seen["languages"] = list(languages)
        return SEGMENTS, "manual", "ru"

    monkeypatch.setattr(transcript_mod, "get_transcript", fake_transcript)
    out = tmp_path / "out"
    assert cli_mod.main([VIDS[0], "--langs", ",,", "-o", str(out)]) == 0
    assert seen["languages"] == ["ru", "en"]


def test_bad_langs_exit_2_no_network(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        metadata_mod, "get_metadata", lambda source: calls.append(source) or make_meta(VIDS[0])
    )
    monkeypatch.setattr(cli_mod, "expand_playlist", lambda url: calls.append(url) or [])
    out = tmp_path / "out"
    assert cli_mod.main([VIDS[0], "--langs", "ru!", "-o", str(out)]) == 2
    assert calls == [], "валидация --langs обязана быть до сети"


def test_empty_whisper_model_exit_2_no_network(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        metadata_mod, "get_metadata", lambda source: calls.append(source) or make_meta(VIDS[0])
    )
    out = tmp_path / "out"
    assert cli_mod.main([VIDS[0], "--whisper-model", "  ", "-o", str(out)]) == 2
    assert calls == []


def test_from_file_bad_utf8_exit_2_no_network(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        metadata_mod, "get_metadata", lambda source: calls.append(source) or make_meta(VIDS[0])
    )
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff\xfenot-utf8\n")
    out = tmp_path / "out"
    assert cli_mod.main(["--from-file", str(bad), "-o", str(out)]) == 2
    assert calls == []
    assert not out.exists(), "папка out не создаётся при usage-ошибке"


def test_usage_errors_go_to_stderr(monkeypatch, tmp_path, capsys):
    patch_all(monkeypatch)
    assert cli_mod.main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Ошибка" in captured.err
    assert cli_mod.main(["!!!"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Непонятный вход" in captured.err


def test_empty_from_file_writes_empty_index(tmp_path):
    only_comments = tmp_path / "links.txt"
    only_comments.write_text("# один\n# два\n\n", encoding="utf-8")
    out = tmp_path / "out"
    assert cli_mod.main(["--from-file", str(only_comments), "-o", str(out)]) == 2
    index = read_index(out)
    assert index["entries"] == []
    assert index["failed"] == 0


def test_readonly_out_exit_2(monkeypatch, tmp_path):
    from pathlib import Path as _Path

    patch_all(monkeypatch)

    def dead_mkdir(self, *args, **kwargs):
        raise PermissionError("доступ запрещён")

    monkeypatch.setattr(_Path, "mkdir", dead_mkdir)
    assert cli_mod.main([VIDS[0], "-o", str(tmp_path / "out")]) == 2


def test_write_index_oserror_exit_2(monkeypatch, tmp_path):
    from kw_yt_transcript import outputs as outputs_mod

    patch_all(monkeypatch)
    monkeypatch.setattr(
        outputs_mod, "write_index", lambda *a, **k: (_ for _ in ()).throw(OSError("ROFS"))
    )
    assert cli_mod.main([VIDS[0], "-o", str(tmp_path / "out")]) == 2


def test_index_report_fields(monkeypatch, tmp_path):
    patch_all(monkeypatch)
    out = tmp_path / "out"
    assert cli_mod.main([VIDS[0], "-o", str(out)]) == 0
    index = read_index(out)
    assert index["playlist_url"] is None
    assert index["entries"][0]["transcript_lang"] == "ru"
    (video_dir,) = [d for d in out.iterdir() if d.is_dir()]
    record = json.loads((video_dir / "meta.json").read_text(encoding="utf-8"))
    assert record["transcript_lang"] == "ru"
    assert record["tool_version"]
    assert record["fetched_at"]
