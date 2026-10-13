"""Собственное хранилище библиотеки (Волна 19, SPEC п.17).

Дефолтная папка всех команд — библиотека утилиты, а не `./out`:
``XDG_DATA_HOME/kw-yt/library`` (fallback ``~/.local/share/kw-yt/library``).
Пути читаются при вызове (XDG env, tmp_path, stubs — без сети).
Приоритет корня: явный флаг > конфиг `out` > библиотека.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any


def library_path() -> Path:
    """Путь к библиотеке с учётом XDG (читается при вызове — удобно тестам)."""
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "kw-yt" / "library"


def resolve_root(explicit: str | Path | None, cfg: dict[str, Any] | None) -> Path:
    """Корень корпуса: явный флаг > конфиг `out` > библиотека.

    Пустая строка конфига — как отсутствие (иначе тихий мусор в путях).
    """
    if explicit is not None:
        return Path(explicit)
    out = (cfg or {}).get("out")
    if isinstance(out, str) and out.strip():
        return Path(out)
    return library_path()


def _dir_size_bytes(video_dir: Path) -> int:
    """Суммарный размер файлов папки видео (без рекурсии вглубь — плоская)."""
    total = 0
    try:
        for p in video_dir.iterdir():
            try:
                if p.is_file() and not p.is_symlink():
                    total += p.stat().st_size
            except OSError:
                continue
    except OSError:
        pass
    return total


def _record_of(video_dir: Path) -> dict[str, Any] | None:
    """Запись библиотеки по папке ``*_<video_id>``; нет meta.json — None."""
    try:
        record = json.loads((video_dir / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(record, dict):
        return None
    date = record.get("upload_date") or ""
    fetched = str(record.get("fetched_at") or "")[:10]
    return {
        "dir": video_dir.name,
        "video_id": record.get("video_id"),
        "title": record.get("title"),
        "date": str(date) or fetched,
        "size_bytes": _dir_size_bytes(video_dir),
        "origin": record.get("origin"),
    }


def iter_library(root: str | Path) -> list[dict[str, Any]]:
    """Все записи библиотеки (папки с meta.json), по имени папки. Нет папки — []."""
    base = Path(root)
    try:
        if not base.is_dir():
            return []
        names = sorted(p.name for p in base.iterdir() if p.is_dir())
    except OSError:
        return []
    entries = []
    for name in names:
        rec = _record_of(base / name)
        if rec is not None:
            entries.append(rec)
    return entries


def find_video_dirs(root: str | Path, video_ids: list[str]) -> tuple[list[Path], list[str]]:
    """Папки ``*_<id>`` под точные id (суффикс ``_<id>``, без подстрок).

    :return: (найденные папки по порядку id, ненайденные id).
    """
    base = Path(root)
    try:
        names = {p.name: p for p in base.iterdir() if p.is_dir()} if base.is_dir() else {}
    except OSError:
        names = {}
    found: list[Path] = []
    missing: list[str] = []
    for vid in video_ids:
        match = None
        suffix = f"_{vid}"
        for name, path in names.items():
            if name.endswith(suffix):
                match = path
                break
        if match is None:
            missing.append(vid)
        else:
            found.append(match)
    return found, missing


def remove_dirs(dirs: list[Path]) -> tuple[list[Path], int]:
    """Удалить папки; вернуть (удадённые пути, байт освобождено, примерно)."""
    removed: list[Path] = []
    freed = 0
    for d in dirs:
        try:
            size = _dir_size_bytes(d)
            shutil.rmtree(d, ignore_errors=True)
            if d.exists():
                continue  # ignore_errors молча пропустил — не врём в отчёте
            freed += size
            removed.append(d)
        except OSError:
            continue
    return removed, freed


def clear_cache() -> tuple[int, int]:
    """Вычистить XDG-кэш метаданных (*.json); вернуть (файлов, байт)."""
    from kw_yt_transcript import cache as cache_mod

    cdir = cache_mod.cache_dir()
    count, freed = 0, 0
    try:
        if not cdir.is_dir():
            return 0, 0
        for p in sorted(cdir.iterdir()):
            try:
                if p.is_file() and p.suffix == ".json" and not p.is_symlink():
                    freed += p.stat().st_size
                    p.unlink(missing_ok=True)
                    count += 1
            except OSError:
                continue
    except OSError:
        pass
    return count, freed


def read_meta(video_dir: str | Path) -> dict[str, Any] | None:
    """Полный meta.json папки видео; нет/бит — None."""
    try:
        record = json.loads((Path(video_dir) / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    return record if isinstance(record, dict) else None


def read_segments(video_dir: str | Path) -> list[Any] | None:
    """Список сегментов transcript.json; нет/бит/не список — None."""
    try:
        segments = json.loads((Path(video_dir) / "transcript.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    return segments if isinstance(segments, list) else None


def list_files(video_dir: str | Path) -> list[dict[str, Any]]:
    """Файлы папки видео [{name, size_bytes}], по имени. Нет папки — []."""
    base = Path(video_dir)
    out = []
    try:
        names = sorted(p.name for p in base.iterdir() if p.is_file())
    except OSError:
        return []
    for name in names:
        try:
            size = (base / name).stat().st_size
        except OSError:
            continue
        out.append({"name": name, "size_bytes": size})
    return out
