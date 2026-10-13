"""Тесты kw-yt update: детект установки, версии, команды, CLI. Без сети и установок.

Сеть (remote_version) и сабпроцессы (runner) — через инъекции; файловая
система — через tmp_path + monkeypatch env.
"""

import sys
from pathlib import Path

import pytest

from kw_yt_transcript import cli as cli_mod
from kw_yt_transcript import update as update_mod

ROOT = Path(__file__).parent.parent


def _exe(tmp_path, *parts):
    p = tmp_path.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("#!/bin/sh\n", encoding="utf-8")
    return str(p)


def test_detect_pipx(tmp_path, monkeypatch):
    exe = _exe(tmp_path, "pipx", "venvs", "kw-yt-transcript", "bin", "python")
    monkeypatch.setattr(sys, "executable", exe)
    monkeypatch.setenv("PIPX_HOME", str(tmp_path / "pipx"))
    monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path / "tools"))
    assert update_mod.detect_install() == {"kind": "pipx", "detail": "kw-yt-transcript"}


def test_detect_uv_tool(tmp_path, monkeypatch):
    exe = _exe(tmp_path, "tools", "kw-yt-transcript", "bin", "python")
    monkeypatch.setattr(sys, "executable", exe)
    monkeypatch.setenv("PIPX_HOME", str(tmp_path / "pipx"))
    monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path / "tools"))
    assert update_mod.detect_install() == {"kind": "uv-tool", "detail": "kw-yt-transcript"}


def test_detect_source_in_real_repo():
    info = update_mod.detect_install()
    assert info["kind"] == "source"
    assert Path(info["detail"]).name == "kw-yt-transcript"


def test_repo_root_from_fake_tree(tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (tmp_path / "a" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert update_mod.repo_root_from(deep) is None  # pyproject без .git — не source
    (tmp_path / "a" / ".git").mkdir()
    assert update_mod.repo_root_from(deep) == tmp_path / "a"


def _neutral_env(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    monkeypatch.setenv("PIPX_HOME", str(tmp_path / "pipx"))
    monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path / "tools"))
    monkeypatch.setattr(update_mod, "__file__", str(tmp_path / "nopkg" / "mod.py"))


def test_detect_pip_via_metadata(tmp_path, monkeypatch):
    _neutral_env(tmp_path, monkeypatch)

    class FakeDist:
        version = "0.2.0"

        def locate_file(self, _):
            return "/usr/lib/python3/site-packages/kw-yt-transcript-0.2.0.dist-info"

    import importlib.metadata as md

    monkeypatch.setattr(md, "distribution", lambda _name: FakeDist())
    assert update_mod.detect_install()["kind"] == "pip"


def test_detect_unknown_without_metadata(tmp_path, monkeypatch):
    _neutral_env(tmp_path, monkeypatch)
    import importlib.metadata as md

    def boom(_name):
        raise md.PackageNotFoundError

    monkeypatch.setattr(md, "distribution", boom)
    info = update_mod.detect_install()
    assert info["kind"] == "unknown"


def test_version_compare():
    assert update_mod.compare_versions("1.2.3", "1.10.0") == -1
    assert update_mod.compare_versions("1.10.0", "1.2.3") == 1
    assert update_mod.compare_versions("0.2.0", "0.2.0") == 0
    assert update_mod.compare_versions("0.2", "0.2.0") == 0
    assert update_mod.compare_versions("abc", "1.0.0") is None
    assert update_mod.compare_versions("1.0.0", "1.0.0-rc1") is None
    assert update_mod.compare_versions("", "1.0.0") is None


def test_remote_version_fetcher_ok():
    def fetcher(_url):
        return b'[project]\nname = "kw-yt-transcript"\nversion = "9.9.9"\n'

    assert update_mod.remote_version(fetcher=fetcher) == "9.9.9"


def test_remote_version_fetcher_errors():
    def boom(_url):
        raise OSError("сеть упала")

    def garbage(_url):
        return "мусор{{{".encode()

    with pytest.raises(update_mod.UpdateError, match="не могу проверить"):
        update_mod.remote_version(fetcher=boom)
    with pytest.raises(update_mod.UpdateError, match="не могу разобрать"):
        update_mod.remote_version(fetcher=garbage)


def test_build_command_by_kind(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _b: f"/usr/bin/{_b}")
    primary, fallback = update_mod.build_command("pipx")
    assert primary == ["pipx", "upgrade", "kw-yt-transcript"]
    assert fallback == ["pipx", "install", "git+https://github.com/FroggerHH/kw-yt-transcript.git"]
    primary, fallback = update_mod.build_command("uv-tool")
    assert primary == ["uv", "tool", "upgrade", "kw-yt-transcript"]
    assert fallback[0:3] == ["uv", "tool", "install"]
    primary, fallback = update_mod.build_command("pip")
    assert primary[:3] == [sys.executable, "-m", "pip"] and fallback is None
    primary, fallback = update_mod.build_command("source", "/repo")
    assert primary == ["git", "-C", "/repo", "pull", "--ff-only"] and fallback is None
    monkeypatch.setattr("shutil.which", lambda _b: None)
    primary, _ = update_mod.build_command("pipx")
    assert primary[:3] == [sys.executable, "-m", "pip"]


def _runner(results):
    calls = []

    def run(argv):
        calls.append(argv)

        class R:
            returncode = results.pop(0) if results else 0

        return R()

    return calls, run


def test_run_update_pip_success(capsys):
    calls, run = _runner([0])
    assert update_mod.run_update("pip", "x", runner=run) == 0
    assert calls[0][:3] == [sys.executable, "-m", "pip"]
    assert "Готово" in capsys.readouterr().out


def test_run_update_pipx_fallback_on_failure(monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/pipx")
    calls, run = _runner([1, 0])
    assert update_mod.run_update("pipx", "x", runner=run) == 0
    assert calls[0][:2] == ["pipx", "upgrade"]
    assert calls[1][:2] == ["pipx", "install"]
    capsys.readouterr()


def test_run_update_all_fail_exit_1(capsys):
    calls, run = _runner([1, 1])
    assert update_mod.run_update("pipx", "x", runner=run) == 1
    assert len(calls) == 2
    capsys.readouterr()


def test_run_update_oserror_then_fallback(monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/pipx")
    seen = []

    def run(argv):
        seen.append(argv)
        if len(seen) == 1:
            raise OSError("нет бинаря")

        class R:
            returncode = 0

        return R()

    assert update_mod.run_update("pipx", "x", runner=run) == 0
    capsys.readouterr()


def test_run_update_unknown_manual_exit_1(capsys):
    assert update_mod.run_update("unknown", "/usr/bin/python") == 1
    assert "вручную" in capsys.readouterr().out


def test_run_update_source_hints_sync(capsys):
    calls, run = _runner([0])
    assert update_mod.run_update("source", "/repo", runner=run) == 0
    assert calls[0] == ["git", "-C", "/repo", "pull", "--ff-only"]
    assert "uv sync" in capsys.readouterr().out


def _stub_env(monkeypatch, remote, kind="pipx", detail="kw-yt-transcript"):
    monkeypatch.setattr(update_mod, "detect_install", lambda: {"kind": kind, "detail": detail})
    monkeypatch.setattr(update_mod, "remote_version", lambda fetcher=None: remote)


def test_cli_check_reports_update_available(monkeypatch, capsys):
    _stub_env(monkeypatch, "9.9.9")
    assert cli_mod.main(["update", "--check"]) == 0
    assert "Доступно обновление" in capsys.readouterr().out


def test_cli_check_reports_fresh(monkeypatch, capsys):
    from kw_yt_transcript import __version__

    _stub_env(monkeypatch, __version__)
    assert cli_mod.main(["update", "--check"]) == 0
    assert "Уже свежее" in capsys.readouterr().out


def test_cli_check_uncomparable_still_zero(monkeypatch, capsys):
    _stub_env(monkeypatch, "мусор")
    assert cli_mod.main(["update", "--check"]) == 0
    assert "несравнимы" in capsys.readouterr().out


def test_cli_check_network_error_exit_1(monkeypatch, capsys):
    _stub_env(monkeypatch, "9.9.9")
    monkeypatch.setattr(
        update_mod,
        "remote_version",
        lambda fetcher=None: (_ for _ in ()).throw(update_mod.UpdateError("сеть упала")),
    )
    assert cli_mod.main(["update", "--check"]) == 1
    capsys.readouterr()


def test_cli_full_update_delegates_runner(monkeypatch, capsys):
    _stub_env(monkeypatch, "9.9.9", kind="pip", detail="d")
    seen = {}
    monkeypatch.setattr(
        update_mod, "run_update", lambda k, d="", runner=None: seen.update(k=k, d=d) or 0
    )
    assert cli_mod.main(["update"]) == 0
    assert seen == {"k": "pip", "d": "d"}
    capsys.readouterr()


def test_cli_full_update_fresh_skips_runner(monkeypatch, capsys):
    from kw_yt_transcript import __version__

    _stub_env(monkeypatch, __version__)

    def boom(*a, **k):
        raise AssertionError("runner не должен вызываться")

    monkeypatch.setattr(update_mod, "run_update", boom)
    assert cli_mod.main(["update"]) == 0
    assert "Уже свежее" in capsys.readouterr().out


def test_cli_full_update_unknown_exit_1(monkeypatch, capsys):
    _stub_env(monkeypatch, "9.9.9", kind="unknown", detail="x")
    assert cli_mod.main(["update"]) == 1
    assert "вручную" in capsys.readouterr().out


def test_update_help_exit_0(capsys):
    with pytest.raises(SystemExit) as e:
        cli_mod.main(["update", "--help"])
    assert e.value.code == 0
    assert "--check" in capsys.readouterr().out


def test_readme_update_markers():
    ru = (ROOT / "README.md").read_text(encoding="utf-8")
    en = (ROOT / "README_EN.md").read_text(encoding="utf-8")
    for marker in ("kw-yt update", "--check"):
        assert marker in ru, marker
        assert marker in en, marker
