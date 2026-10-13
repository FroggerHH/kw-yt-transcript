"""Тесты `kw-yt completion bash`: генерация из парсеров, bash -n, кандидаты.

Скрипт генерируется из argparse-парсеров (cli.render_bash_completion),
contrib/kw-yt-completion.bash — зафиксированный вывод той же функции.
Всё локально, без сети. Bash-проверки скипаются, если нет bash.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from kw_yt_transcript import cli as cli_mod

SUBCOMMANDS = ("search", "serve", "export", "stats", "library", "clean", "completion")
CONTRIB = Path(__file__).parent.parent / "contrib" / "kw-yt-completion.bash"
BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(BASH is None, reason="нет bash")


def _script(capsys):
    assert cli_mod.main(["completion", "bash"]) == 0
    return capsys.readouterr().out


def test_completion_bash_exit_0_and_complete_line(capsys):
    script = _script(capsys)
    assert script.startswith("#")
    assert script.rstrip().endswith("complete -F _kw_yt kw-yt")


def test_completion_default_shell_is_bash(capsys):
    assert cli_mod.main(["completion"]) == 0
    assert "complete -F _kw_yt kw-yt" in capsys.readouterr().out


def test_completion_bad_shell_exit_2(capsys):
    with pytest.raises(SystemExit) as e:
        cli_mod.main(["completion", "zsh"])
    assert e.value.code == 2
    capsys.readouterr()


def test_completion_covers_subcommands_and_flags(capsys):
    script = _script(capsys)
    for sub in SUBCOMMANDS:
        assert sub in script, sub
    for flag in (
        "--jobs",
        "--resume",
        "--from",
        "--to",
        "--no-color",
        "--color",
        "--from-file",
        "--langs",
        "--format",
        "--whisper-model",
        "--in",
        "--context",
        "--limit",
        "--port",
        "--json",
        "--no-summary",
        "always",
        "auto",
        "never",
        "jsonl",
        "csv",
        "bash",
    ):
        assert flag in script, flag


def test_completion_flags_match_parsers(capsys):
    """Каждый флаг из парсеров есть в скрипте (источник истины — argparse)."""
    script = _script(capsys)
    known: set[str] = set()
    for p in cli_mod._completion_parsers().values():
        for a in p._actions:
            known.update(a.option_strings)
    known -= {"-h", "--help"}
    assert known, "парсеры без флагов?"
    for flag in known:
        assert flag in script, flag


def test_completion_matches_contrib(capsys):
    assert CONTRIB.is_file()
    assert CONTRIB.read_text(encoding="utf-8") == _script(capsys)


@needs_bash
def test_completion_bash_syntax_n(tmp_path, capsys):
    f = tmp_path / "kw-yt-completion.bash"
    f.write_text(_script(capsys), encoding="utf-8")
    r = subprocess.run([BASH, "-n", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@needs_bash
def test_completion_source_and_candidates(tmp_path, capsys):
    f = tmp_path / "kw-yt-completion.bash"
    f.write_text(_script(capsys), encoding="utf-8")
    probe = (
        f'source "{f}"\n'
        "complete -p kw-yt\n"
        'COMP_WORDS=(kw-yt ""); COMP_CWORD=1; _kw_yt; echo "TOP:${COMPREPLY[*]}"\n'
        'COMP_WORDS=(kw-yt search --color ""); COMP_CWORD=3;'
        ' _kw_yt; echo "COLOR:${COMPREPLY[*]}"\n'
        'COMP_WORDS=(kw-yt export --format ""); COMP_CWORD=3;'
        ' _kw_yt; echo "FMT:${COMPREPLY[*]}"\n'
    )
    r = subprocess.run([BASH, "-c", probe], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "complete -F _kw_yt kw-yt" in r.stdout
    top = next(line for line in r.stdout.splitlines() if line.startswith("TOP:"))
    for sub in SUBCOMMANDS:
        assert sub in top, sub
    color = next(line for line in r.stdout.splitlines() if line.startswith("COLOR:"))
    for mode in ("auto", "always", "never"):
        assert mode in color, mode
    fmt = next(line for line in r.stdout.splitlines() if line.startswith("FMT:"))
    assert "jsonl" in fmt and "csv" in fmt
