"""Кэш метаданных видео (v0.2, Волна 2).

Только stdlib, без сети. Каталог — ``XDG_CACHE_HOME/kw-yt``
(fallback ``~/.cache/kw-yt``), файл ``{key}.json`` вида
``{saved_at, ttl, meta}``. Просрочка и любые ошибки чтения/записи —
тихий промах (miss), сеть решает вызывающий код.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

#: TTL кэша метаданных по умолчанию: сутки.
DEFAULT_TTL = 86400

_ID_PATTERNS = (
    re.compile(r"[?&]v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})"),
)
_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def cache_dir() -> Path:
    """Каталог кэша с учётом XDG (читается при каждом вызове — удобно тестам)."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "kw-yt"


def key_for(url_or_id: str) -> str:
    """Стабильный ключ кэша: video id, если извлекли, иначе санитизированный вход."""
    s = (url_or_id or "").strip()
    if _BARE_ID_RE.match(s):
        return s
    for pat in _ID_PATTERNS:
        m = pat.search(s)
        if m:
            return m.group(1)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", s).strip("_")[:100]
    return safe or "unknown"


def _path_for(key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", key or "unknown")[:100] or "unknown"
    return cache_dir() / f"{safe}.json"


def cache_get(url_or_id: str) -> dict[str, Any] | None:
    """Прочитать метаданные из кэша. Miss/просрочка/битый файл → None."""
    try:
        payload = json.loads(_path_for(key_for(url_or_id)).read_text(encoding="utf-8"))
        saved_at = float(payload["saved_at"])
        ttl = float(payload.get("ttl", DEFAULT_TTL))
        if time.time() - saved_at > ttl:
            return None
        meta = payload["meta"]
        return dict(meta) if isinstance(meta, dict) else None
    except Exception:
        return None


def cache_set(url_or_id: str, meta: dict[str, Any], ttl: float = DEFAULT_TTL) -> None:
    """Сохранить метаданные атомарно (*.tmp + os.replace). Ошибки — молча."""
    try:
        import os as _os

        path = _path_for(key_for(url_or_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"saved_at": time.time(), "ttl": ttl, "meta": dict(meta)}
        tmp = path.with_name(path.name + ".tmp")
        try:
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            _os.replace(tmp, path)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    except Exception:
        pass
