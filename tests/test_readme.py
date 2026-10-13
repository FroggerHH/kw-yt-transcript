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
        "--whisper-model",
        "--version",
        "--in",
        "--context",
        "--limit",
        "--port",
        "--summary",
        "--no-summary",
        "--json",
        "из конфига",
        "--out",
        "index.json",
        "meta.json",
        "transcript.srt",
        "transcript.jsonl",
        "kw-yt-completion",
        "API-ключ",
        "ffmpeg",
        "--jobs",
        "--resume",
        "kw-yt search",
        "kw-yt serve",
        "kw-yt export",
        "kw-yt stats",
        "corpus.jsonl",
        "summary.json",
        "thumbnail.jpg",
        "10 файлов",
        "report.html",
        "index.html",
        "config.toml",
    ):
        assert section in text, section


def test_completion_script_exists_and_covers_cli():
    comp = Path(__file__).parent.parent / "contrib" / "kw-yt-completion.bash"
    assert comp.is_file()
    text = comp.read_text(encoding="utf-8")
    assert "complete -F _kw_yt kw-yt" in text
    for token in (
        "search", "serve", "export", "stats", "--jobs", "--resume", "--format",
        "jsonl", "csv", "--no-summary", "--json",
    ):
        assert token in text, token


def test_version_is_0_2_0(capsys):
    with pytest.raises(SystemExit) as e:
        cli_mod.main(["--version"])
    assert e.value.code == 0
    assert "0.2.0" in capsys.readouterr().out


def _all_option_strings():
    parsers = (
        cli_mod.build_parser(),
        cli_mod.build_search_parser(),
        cli_mod.build_serve_parser(),
        cli_mod.build_export_parser(),
        cli_mod.build_stats_parser(),
    )
    return {opt for p in parsers for action in p._actions for opt in action.option_strings}


def test_readme_flags_exist_in_parser():
    """Каждый --флаг из kw-yt-примеров README обязан существовать в argparse."""
    known = _all_option_strings()
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
