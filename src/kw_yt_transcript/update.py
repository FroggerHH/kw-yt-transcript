"""Самообновление kw-yt (v0.2 Волна 26).

Детект способа установки по путям/маркерам (pipx → uv-tool → source →
pip → unknown), чтение свежей версии с GitHub (только сеть модуля) и
обновление тем же каналом (pipx/uv/pip из официальных источников, git pull
для исходников). Всё тестируется без сети: fetcher версий и runner команд
инжектируются.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

#: Имя пакета и репозиторий (единственный источник обновлений).
PKG_NAME = "kw-yt-transcript"
REPO_URL = "https://github.com/FroggerHH/kw-yt-transcript.git"
PYPROJECT_URL = "https://raw.githubusercontent.com/FroggerHH/kw-yt-transcript/main/pyproject.toml"

#: Дефолт detect_install: только локально.
DEFAULT_KIND = "unknown"


class UpdateError(Exception):
    """Не удалось проверить/выполнить обновление (русский текст внутри)."""


def repo_root_from(start: Path) -> Path | None:
    """Корень репо от точки старта вверх: первый каталог с pyproject + .git."""
    cur = start if start.is_dir() else start.parent
    for parent in [cur, *cur.parents]:
        if (parent / "pyproject.toml").is_file() and (parent / ".git").exists():
            return parent
    return None


def _under(exe_abs: str, base: str) -> str | None:
    """Первый компонент пути exe относительно base (exe строго внутри)."""
    prefix = base.rstrip(os.sep) + os.sep
    if exe_abs.startswith(prefix):
        rest = exe_abs[len(prefix) :]
        return rest.split(os.sep)[0] if rest else None
    return None


def detect_install() -> dict[str, str]:
    """Способ установки: {kind, detail}. Порядок: pipx, uv-tool, source, pip, unknown.

    source определяется по .git рядом с кодом вне зависимости от venv;
    pip — по метаданным importlib.metadata (dist-info обычно в site-packages).
    """
    exe = os.path.abspath(os.path.expanduser(sys.executable or ""))
    home = os.path.expanduser("~")
    pipx_home = os.path.abspath(
        os.environ.get("PIPX_HOME", os.path.join(home, ".local", "share", "pipx"))
    )
    under_venvs = _under(exe, os.path.join(pipx_home, "venvs"))
    if under_venvs:
        return {"kind": "pipx", "detail": under_venvs}
    tool_base = os.path.abspath(
        os.environ.get("UV_TOOL_DIR", os.path.join(home, ".local", "share", "uv", "tools"))
    )
    under_tools = _under(exe, tool_base)
    if under_tools:
        return {"kind": "uv-tool", "detail": under_tools}
    root = repo_root_from(Path(__file__).resolve())
    if root is not None:
        return {"kind": "source", "detail": str(root)}
    try:
        import importlib.metadata as md

        dist = md.distribution(PKG_NAME)
        location = str(dist.locate_file(""))
    except Exception:
        dist = None
        location = ""
    if dist is not None and "site-packages" in location:
        return {"kind": "pip", "detail": f"{dist.version} @ {location}"}
    return {"kind": DEFAULT_KIND, "detail": exe}


def _default_fetch(url: str) -> bytes:
    """Скачать URL (таймаут 20). Только сеть модуля."""
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "kw-yt update"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def remote_version(fetcher: Callable[[str], bytes] | None = None) -> str:
    """Версия из pyproject.toml на main. Ошибки → UpdateError по-русски."""
    fetch = fetcher if fetcher is not None else _default_fetch
    try:
        data = fetch(PYPROJECT_URL)
    except Exception as e:
        raise UpdateError(f"не могу проверить обновления: {e}") from e
    try:
        import tomllib

        ver = tomllib.loads(data.decode("utf-8"))["project"]["version"]
    except Exception as e:
        raise UpdateError(f"не могу разобрать версию на сервере: {e}") from e
    return str(ver).strip()


def parse_version(v: str) -> tuple[int, ...] | None:
    """Строго цифры через точку (1.10.0 ✓). Мусор → None."""
    chunks = str(v).strip().split(".")
    if not chunks or not all(ch.isdigit() for ch in chunks):
        return None
    return tuple(int(ch) for ch in chunks)


def compare_versions(local: str, remote: str) -> int | None:
    """-1 local<remote, 0 равны, 1 local>remote; несравнимые → None."""
    left, right = parse_version(local), parse_version(remote)
    if left is None or right is None:
        return None
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    return (left > right) - (left < right)


def build_command(kind: str, detail: str = "") -> tuple[list[str], list[str] | None]:
    """(основная команда, fallback|None). Бинаря нет в PATH — сразу установка из git."""
    git_src = f"git+{REPO_URL}"
    if kind == "pipx":
        if shutil.which("pipx") is None:
            return ([sys.executable, "-m", "pip", "install", git_src], None)
        return (["pipx", "upgrade", PKG_NAME], ["pipx", "install", git_src])
    if kind == "uv-tool":
        if shutil.which("uv") is None:
            return ([sys.executable, "-m", "pip", "install", git_src], None)
        return (
            ["uv", "tool", "upgrade", PKG_NAME],
            ["uv", "tool", "install", "--force", git_src],
        )
    if kind == "pip":
        return ([sys.executable, "-m", "pip", "install", "-U", git_src], None)
    if kind == "source":
        return (["git", "-C", detail, "pull", "--ff-only"], None)
    return ([], None)


def _default_runner(argv: list[str]) -> Any:
    return subprocess.run(argv, check=False)


def run_update(
    kind: str, detail: str = "", runner: Callable[[list[str]], Any] | None = None
) -> int:
    """Выполнить обновление (0 — ок, 1 — ошибка). unknown — инструкция, exit 1."""
    run = runner if runner is not None else _default_runner
    if kind == DEFAULT_KIND:
        print(
            "Не могу определить способ установки — обновите вручную: "
            f"pipx upgrade {PKG_NAME} | uv tool upgrade {PKG_NAME} | "
            f"pip install -U git+{REPO_URL} (было: {detail or 'неизвестно'})."
        )
        return 1
    primary, fallback = build_command(kind, detail)
    for argv in [primary] + ([fallback] if fallback is not None else []):
        print(f"Выполняю ({kind}): {' '.join(argv)}")
        try:
            res = run(argv)
        except OSError as e:
            print(f"Ошибка: не запускается {' '.join(argv)}: {e}", file=sys.stderr)
            continue
        if res.returncode == 0:
            if kind == "source":
                print("Готово. Обновите окружение: uv sync.")
            else:
                print("Готово. Проверьте: kw-yt --version.")
            return 0
        print(
            f"Ошибка: команда завершилась с кодом {res.returncode}.",
            file=sys.stderr,
        )
    return 1
