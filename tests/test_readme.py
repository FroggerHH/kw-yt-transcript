"""Проверки README: существует, на русском, команды/флаги соответствуют реальному CLI.

Только локальное: --help/--version (exit 0), graceful exit 2 без сети.
Живой прогон на YouTube — user-side шаг из README, здесь не выполняется.
"""

import re
from pathlib import Path

import pytest

from kw_yt_transcript import cli as cli_mod

README = Path(__file__).parent.parent / "README.md"


def readme_text():
    return README.read_text(encoding="utf-8")


def test_readme_exists_and_russian():
    assert README.is_file()
    text = readme_text()
    assert len(text) > 1000
    for marker in ("Установка", "Использование", "коды выхода", "установки", "видео"):
        assert marker in text, marker


def test_readme_required_sections():
    text = readme_text()
    for section in (
        "Требования",
        "Установка",
        "Использование",
        "Выходная структура",
        "Ошибки и коды выхода",
        "pipx install",
        "uv tool install",
        "pip install -e",
        "[asr]",
        "--from-file",
        "--langs",
        "--format",
        "--no-fallback-whisper",
        "--out",
        "index.json",
        "meta.json",
        "transcript.srt",
        "API-ключ",
        "ffmpeg",
    ):
        assert section in text, section


def test_readme_flags_exist_in_parser():
    """Каждый --флаг из kw-yt-примеров README обязан существовать в argparse."""
    parser = cli_mod.build_parser()
    known = {opt for action in parser._actions for opt in action.option_strings}
    flags = set()
    for line in readme_text().splitlines():
        if "kw-yt" in line:
            flags.update(re.findall(r"--[\w-]+", line))
    assert flags, "в README нет ни одного флага kw-yt"
    unknown = flags - known
    assert not unknown, f"флаги из README без парсера: {sorted(unknown)}"


def test_help_and_version_exit_0():
    with pytest.raises(SystemExit) as e:
        cli_mod.main(["--help"])
    assert e.value.code == 0
    with pytest.raises(SystemExit) as e:
        cli_mod.main(["--version"])
    assert e.value.code == 0


def test_graceful_usage_errors_without_network():
    assert cli_mod.main([]) == 2
    assert cli_mod.main(["!!!"]) == 2
    assert cli_mod.main(["--from-file", "/nonexistent/links.txt"]) == 2
