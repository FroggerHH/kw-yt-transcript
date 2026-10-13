"""Конфиг kw-yt (v0.2, Волна 2).

Только stdlib (tomllib — Python 3.11+). Файл
``XDG_CONFIG_HOME/kw-yt/config.toml`` (fallback ``~/.config/kw-yt/config.toml``).
Отсутствие/битый файл → дефолты + русское предупреждение в stderr, не падение.
Приоритет значений: CLI-флаги > конфиг > дефолты (применяет cli.py).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

#: Значения по умолчанию (совпадают со старыми дефолтами CLI).
DEFAULTS: dict[str, Any] = {
    "langs": "ru,en",
    "out": "./out",
    "jobs": 4,
    "whisper_model": "small",
}


def config_path() -> Path:
    """Путь к config.toml с учётом XDG (читается при вызове — удобно тестам)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "kw-yt" / "config.toml"


def _coerce(section: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    langs = section.get("langs", DEFAULTS["langs"])
    if isinstance(langs, list):
        langs = ",".join(str(x) for x in langs)
    if isinstance(langs, str) and langs.strip():
        cfg["langs"] = langs
    out = section.get("out", DEFAULTS["out"])
    if isinstance(out, str) and out.strip():
        cfg["out"] = out
    jobs = section.get("jobs", DEFAULTS["jobs"])
    if isinstance(jobs, bool):
        pass
    elif isinstance(jobs, int):
        cfg["jobs"] = jobs
    elif isinstance(jobs, str) and jobs.strip().lstrip("+-").isdigit():
        cfg["jobs"] = int(jobs.strip())
    model = section.get("whisper_model", DEFAULTS["whisper_model"])
    if isinstance(model, str) and model.strip():
        cfg["whisper_model"] = model
    return cfg


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Прочитать конфиг. Всегда возвращает полный словарь, не падает."""
    cfg_path = Path(path) if path is not None else config_path()
    try:
        raw = cfg_path.read_bytes()
    except OSError:
        print(
            f"Предупреждение: конфиг не найден ({cfg_path}), "
            "используются значения по умолчанию.",
            file=sys.stderr,
            flush=True,
        )
        return dict(DEFAULTS)
    try:
        import tomllib

        data = tomllib.loads(raw.decode("utf-8"))
    except Exception as e:
        print(
            f"Предупреждение: не могу прочитать конфиг {cfg_path}: {e}. "
            "Используются значения по умолчанию.",
            file=sys.stderr,
            flush=True,
        )
        return dict(DEFAULTS)
    section: dict[str, Any] = {}
    if isinstance(data, dict):
        tool = data.get("tool")
        if isinstance(tool, dict) and isinstance(tool.get("defaults"), dict):
            section = tool["defaults"]
        elif isinstance(data.get("defaults"), dict):
            section = data["defaults"]
        else:
            section = {k: v for k, v in data.items() if k in DEFAULTS}
    if not isinstance(section, dict):
        section = {}
    return _coerce(section)
