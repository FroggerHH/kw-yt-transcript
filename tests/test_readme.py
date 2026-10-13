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
        "Оглавление",
        "Highlights",
        "FAQ",
        "shields.io",
        "pipx install",
        "uv tool install",
        "uv sync",
        "uv run",
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
        "kw-yt library",
        "kw-yt clean",
        "--from",
        "--to",
        "Фрагмент",
        "corpus.jsonl",
        "summary.json",
        "thumbnail.jpg",
        "10 файлов",
        "распознан ИИ",
        "report.html",
        "index.html",
        "config.toml",
        "--color",
        "kw-yt completion",
        "docs/demo/",
        "Быстрый старт",
        "Участие в разработке",
        "SKILL.md",
    ):
        assert section in text, section


def test_completion_script_exists_and_covers_cli():
    comp = Path(__file__).parent.parent / "contrib" / "kw-yt-completion.bash"
    assert comp.is_file()
    text = comp.read_text(encoding="utf-8")
    assert "complete -F _kw_yt kw-yt" in text
    for token in (
        "search",
        "serve",
        "export",
        "stats",
        "--jobs",
        "--resume",
        "--format",
        "jsonl",
        "csv",
        "--no-summary",
        "--json",
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
        cli_mod.build_library_parser(),
        cli_mod.build_clean_parser(),
    )
    return {opt for p in parsers for action in p._actions for opt in action.option_strings}


def test_readme_toc_anchors():
    """Каждый якорь из Оглавления соответствует реальному ## заголовку."""
    text = readme_text()
    toc = text.split("## Оглавление", 1)[1].split("## ", 1)[0]
    anchors = re.findall(r"\(#(.*?)\)", toc)
    assert anchors, "в Оглавлении нет якорей"

    def slug(header):
        s = header.strip().lower().replace(" ", "-")
        return re.sub(r"[(),.:;!?«»\"'—–]", "", s)

    headers = [line[3:] for line in text.splitlines() if line.startswith("## ")]
    slugs = {slug(h) for h in headers}
    for anchor in anchors:
        assert anchor in slugs, f"якорь #{anchor} без заголовка"


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


README_EN = Path(__file__).parent.parent / "README_EN.md"


def test_readme_en_exists_and_matches():
    """Английская версия: существует, не огрызок, ключевые секции и версия."""
    assert README_EN.is_file(), "README_EN.md отсутствует"
    en = README_EN.read_text(encoding="utf-8")
    ru = readme_text()
    assert len(en) > 0.6 * len(ru), f"EN слишком короткий: {len(en)} vs RU {len(ru)}"
    for marker in (
        "Installation",
        "Usage",
        "Output structure",
        "kw-yt search",
        "transcript.srt",
        "0.2.0",
        "Quick start",
        "Contributing",
        "--color",
        "completion",
        "docs/demo/",
        "SKILL.md",
    ):
        assert marker in en, marker


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


DEMO = Path(__file__).parent.parent / "docs" / "demo"
DEMO_CORPUS = "docs/demo/corpus"

HELP_CAPTURES = {
    "version.txt": ["--version"],
    "help.txt": ["--help"],
    "help-search.txt": ["search", "--help"],
    "help-serve.txt": ["serve", "--help"],
    "help-export.txt": ["export", "--help"],
    "help-stats.txt": ["stats", "--help"],
    "help-library.txt": ["library", "--help"],
    "help-clean.txt": ["clean", "--help"],
    "help-completion.txt": ["completion", "--help"],
}


def test_demo_help_captures_match_tool(monkeypatch, capsys):
    """docs/demo/*.txt — вывод реального инструмента (COLUMNS зафиксированы)."""
    assert DEMO.is_dir()
    monkeypatch.setenv("COLUMNS", "80")
    for name, argv in HELP_CAPTURES.items():
        f = DEMO / name
        assert f.is_file(), name
        with pytest.raises(SystemExit) as e:
            cli_mod.main(argv)
        assert e.value.code == 0, name
        assert f.read_text(encoding="utf-8") == capsys.readouterr().out, name


def test_demo_corpus_offline_stats_search_export(monkeypatch, tmp_path, capsys):
    """Демо-корпус: stats/search/export работают без сети, как в quick start."""
    monkeypatch.chdir(Path(__file__).parent.parent)
    assert cli_mod.main(["stats", "--in", DEMO_CORPUS]) == 0
    stats_out = capsys.readouterr().out
    assert "реплик 6" in stats_out
    assert (DEMO / "quickstart-stats.txt").read_text(encoding="utf-8") == stats_out
    assert cli_mod.main(["search", "привет", "--in", DEMO_CORPUS]) == 0
    search_out = capsys.readouterr().out
    assert "вхождений 2" in search_out
    assert (DEMO / "quickstart-search.txt").read_text(encoding="utf-8") == search_out
    assert cli_mod.main(["search", "zz-небывалое-слово", "--in", DEMO_CORPUS]) == 1
    capsys.readouterr()
    out = tmp_path / "corpus.jsonl"
    assert cli_mod.main(["export", "--in", DEMO_CORPUS, "--out", str(out), "--no-summary"]) == 0
    capsys.readouterr()
    assert out.is_file() and "DEMOdemo011" in out.read_text(encoding="utf-8")


def test_readme_quotes_demo_outputs():
    """Quick start в README цитирует захваченные выводы дословно."""
    ru = readme_text()
    en = (Path(__file__).parent.parent / "README_EN.md").read_text(encoding="utf-8")
    for name in ("quickstart-stats.txt", "quickstart-search.txt"):
        captured = (DEMO / name).read_text(encoding="utf-8").strip()
        assert captured in ru, name
        assert captured in en, name
