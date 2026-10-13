"""Тесты цвета вывода: TTY/NO_COLOR/TERM/--no-color. Без сети, capsys + stubs."""

import sys

import pytest

from kw_yt_transcript import cli as cli_mod

ESC = "\033["


def _tty(monkeypatch, out=True, err=True):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: out)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: err)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")


def _plain(monkeypatch):
    _tty(monkeypatch, out=False, err=False)


def test_help_colored_on_tty(monkeypatch, capsys):
    _tty(monkeypatch)
    with pytest.raises(SystemExit) as e:
        cli_mod.main(["--help"])
    assert e.value.code == 0
    assert ESC in capsys.readouterr().out


def test_help_plain_on_pipe(monkeypatch, capsys):
    _plain(monkeypatch)
    with pytest.raises(SystemExit) as e:
        cli_mod.main(["--help"])
    assert e.value.code == 0
    assert ESC not in capsys.readouterr().out


def test_help_plain_with_no_color_flag(monkeypatch, capsys):
    _tty(monkeypatch)
    with pytest.raises(SystemExit) as e:
        cli_mod.main(["--help", "--no-color"])
    assert e.value.code == 0
    assert ESC not in capsys.readouterr().out


def test_help_plain_with_no_color_env(monkeypatch, capsys):
    _tty(monkeypatch)
    monkeypatch.setenv("NO_COLOR", "1")
    with pytest.raises(SystemExit) as e:
        cli_mod.main(["--help"])
    assert e.value.code == 0
    assert ESC not in capsys.readouterr().out


def test_help_plain_with_dumb_term(monkeypatch, capsys):
    _tty(monkeypatch)
    monkeypatch.setenv("TERM", "dumb")
    with pytest.raises(SystemExit) as e:
        cli_mod.main(["--help"])
    assert e.value.code == 0
    assert ESC not in capsys.readouterr().out


def test_error_colored_and_exit_kept(monkeypatch, capsys):
    _tty(monkeypatch)
    assert cli_mod.main([]) == 2
    err = capsys.readouterr().err
    assert ESC in err and "Ошибка:" in err
    assert cli_mod.main(["!!!"]) == 2
    err = capsys.readouterr().err
    assert ESC in err and "FAIL" in err


def test_error_plain_on_pipe(monkeypatch, capsys):
    _plain(monkeypatch)
    assert cli_mod.main([]) == 2
    err = capsys.readouterr().err
    assert ESC not in err and "Ошибка:" in err
    assert cli_mod.main(["!!!"]) == 2
    err = capsys.readouterr().err
    assert ESC not in err and "FAIL" in err


def test_progress_ok_colored_on_tty(monkeypatch, tmp_path, capsys):
    from kw_yt_transcript import asr as asr_mod
    from kw_yt_transcript import metadata as metadata_mod
    from kw_yt_transcript import transcript as transcript_mod

    monkeypatch.setattr(
        metadata_mod,
        "get_metadata",
        lambda source: {
            "video_id": "dQw4w9WgXcQ",
            "url": source,
            "title": "Видео",
            "channel": "Канал",
            "duration": 10,
            "thumbnails": [],
        },
    )
    monkeypatch.setattr(
        transcript_mod,
        "get_transcript",
        lambda video_id, languages=None: (
            [{"text": "текст", "start": 0.0, "duration": 1.0}],
            "manual",
            "ru",
        ),
    )
    monkeypatch.setattr(asr_mod, "transcribe_whisper", lambda *a, **k: ([], "whisper"))
    _tty(monkeypatch)
    out = tmp_path / "out"
    assert cli_mod.main(["dQw4w9WgXcQ", "-o", str(out)]) == 0
    err = capsys.readouterr().err
    assert ESC in err and "ok" in err
