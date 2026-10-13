"""Проверки SKILL.md: Agent Skills frontmatter + покрытие команд.

Файл — в корне (спецификация Agent Skills): YAML-frontmatter с name
(lowercase-hyphen) и description, дальше инструкции по CLI.
"""

import re
from pathlib import Path

SKILL = Path(__file__).parent.parent / "SKILL.md"


def skill_text():
    return SKILL.read_text(encoding="utf-8")


def _frontmatter():
    text = skill_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md без YAML-frontmatter (---)"
    return m.group(1)


def test_skill_exists_and_frontmatter_name():
    assert SKILL.is_file()
    front = _frontmatter()
    m = re.search(r"^name:\s*(\S+)\s*$", front, re.M)
    assert m, "во frontmatter нет name"
    assert re.fullmatch(r"[a-z0-9-]+", m.group(1)), m.group(1)


def test_skill_description_keywords():
    front = _frontmatter()
    m = re.search(r"^description:\s*(.+?)\s*$", front, re.M)
    assert m, "во frontmatter нет description"
    desc = m.group(1).lower()
    for kw in ("транскрипт", "корпус", "rag", "поиск"):
        assert kw in desc, kw


def test_skill_covers_commands():
    text = skill_text()
    for cmd in (
        "kw-yt search",
        "kw-yt serve",
        "kw-yt export",
        "kw-yt stats",
        "kw-yt library",
        "kw-yt clean",
        "kw-yt completion",
        "--from",
        "--to",
        "--jobs",
        "--resume",
        "jsonl",
        "origin",
    ):
        assert cmd in text, cmd


def test_skill_covers_rules():
    text = skill_text()
    for marker in ("0", "1", "2", "API-ключ", "библиотек"):
        assert marker in text, marker
