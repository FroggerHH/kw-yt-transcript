"""Unit-тесты inputs.parse_inputs: без сети, без HOME (только tmp_path)."""

import pytest

from kw_yt_transcript.inputs import parse_inputs

VID1 = "dQw4w9WgXcQ"
VID2 = "9bZkp7q19f0"


def test_single_id():
    jobs = parse_inputs([VID1])
    assert jobs == [{"raw": VID1, "kind": "video", "video_id": VID1}]


def test_single_watch_url():
    url = f"https://www.youtube.com/watch?v={VID1}"
    jobs = parse_inputs([url])
    assert len(jobs) == 1
    assert jobs[0]["kind"] == "video"
    assert jobs[0]["video_id"] == VID1
    assert jobs[0]["url"] == url


def test_youtu_be_url():
    jobs = parse_inputs([f"https://youtu.be/{VID2}"])
    assert jobs[0]["kind"] == "video"
    assert jobs[0]["video_id"] == VID2


def test_shorts_url():
    jobs = parse_inputs([f"https://www.youtube.com/shorts/{VID1}"])
    assert jobs[0]["kind"] == "video"
    assert jobs[0]["video_id"] == VID1


def test_music_url():
    jobs = parse_inputs([f"https://music.youtube.com/watch?v={VID2}"])
    assert jobs[0]["kind"] == "video"
    assert jobs[0]["video_id"] == VID2


def test_multi_comma_in_one_arg():
    jobs = parse_inputs([f"{VID1},{VID2}"])
    assert [j["video_id"] for j in jobs] == [VID1, VID2]


def test_multi_space_and_newline():
    jobs = parse_inputs([VID1, VID2, f"{VID1} {VID2}\n{VID1}"])
    assert len(jobs) == 5
    assert all(j["kind"] == "video" for j in jobs)


def test_multi_semicolon():
    jobs = parse_inputs([f"{VID1};{VID2}"])
    assert [j["video_id"] for j in jobs] == [VID1, VID2]


def test_from_file(tmp_path):
    f = tmp_path / "links.txt"
    f.write_text(
        f"# комментарий\n\n{VID1}\nhttps://youtu.be/{VID2}\n",
        encoding="utf-8",
    )
    jobs = parse_inputs([], from_file=str(f))
    assert len(jobs) == 2
    assert jobs[0]["video_id"] == VID1
    assert jobs[1]["video_id"] == VID2


def test_from_file_missing():
    with pytest.raises(ValueError):
        parse_inputs([], from_file="/nonexistent/links.txt")


def test_playlist_url():
    url = "https://www.youtube.com/playlist?list=PL1234567890abcdef"
    jobs = parse_inputs([url])
    assert jobs == [{"raw": url, "kind": "playlist", "url": url}]


def test_watch_with_playlist_param():
    url = f"https://www.youtube.com/watch?v={VID1}&list=PL1234567890abcdef"
    jobs = parse_inputs([url])
    assert jobs[0]["kind"] == "playlist"


def test_garbage_raises():
    with pytest.raises(ValueError):
        parse_inputs(["!!!"])


def test_empty_returns_empty():
    assert parse_inputs([]) == []
