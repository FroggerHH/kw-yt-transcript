"""Просмотр корпуса через stdlib HTTP-сервер (v0.2, Волна 2 + Волна 25 --host).

Только stdlib, без сети извне: ThreadingHTTPServer, корень — папка корпуса
с готовыми index.html/report.html. Дефолтный host — 127.0.0.1 (только
локально); явный не-loopback host (например 0.0.0.0) — с предупреждением,
что сервер виден всей локальной сети.
"""

from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

#: Дефолтный host: только локально.
DEFAULT_HOST = "127.0.0.1"

#: Host считается локальным — без предупреждения о видимости в LAN.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def make_server(root: str | Path, port: int = 0, host: str = DEFAULT_HOST) -> ThreadingHTTPServer:
    """Создать (не запускать) сервер корпуса. port=0 — эфемерный порт."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(Path(root)))
    return ThreadingHTTPServer((host, port), handler)


def serve_dir(root: str | Path, port: int = 0, host: str = DEFAULT_HOST) -> int:
    """Раздавать корпус, напечатать URL в stdout. Ctrl+C — чистый выход."""
    root_path = Path(root)
    if not root_path.is_dir():
        print(f"Ошибка: папка корпуса не найдена: {root}.", file=sys.stderr, flush=True)
        return 2
    if not (root_path / "index.html").is_file():
        print(
            f"Предупреждение: index.html не найден в {root_path} — раздаю как есть.",
            file=sys.stderr,
            flush=True,
        )
    if host.lower() not in LOOPBACK_HOSTS:
        print(
            f"Предупреждение: host {host} — сервер виден всей локальной сети.",
            file=sys.stderr,
            flush=True,
        )
    try:
        server = make_server(root_path, port, host)
    except OSError as e:
        print(f"Ошибка: не могу занять {host}:{port}: {e}.", file=sys.stderr, flush=True)
        return 2
    actual = server.server_address[1]
    print(f"Корпус: {root_path}. Откройте http://{host}:{actual}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print("Сервер остановлен.", flush=True)
    return 0
