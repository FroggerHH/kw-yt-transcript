"""Просмотр корпуса через stdlib HTTP-сервер (v0.2, Волна 2).

Только stdlib, без сети извне: ThreadingHTTPServer на 127.0.0.1,
корень — папка корпуса с готовыми index.html/report.html.
"""

from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def make_server(root: str | Path, port: int = 0) -> ThreadingHTTPServer:
    """Создать (не запускать) сервер корпуса. port=0 — эфемерный порт."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(Path(root)))
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def serve_dir(root: str | Path, port: int = 0) -> int:
    """Раздавать корпус, напечатать URL в stdout. Ctrl+C — чистый выход."""
    root_path = Path(root)
    if not root_path.is_dir():
        print(f"Ошибка: папка корпуса не найдена: {root}.", file=sys.stderr, flush=True)
        return 2
    try:
        server = make_server(root_path, port)
    except OSError as e:
        print(f"Ошибка: не могу занять порт {port}: {e}.", file=sys.stderr, flush=True)
        return 2
    actual = server.server_address[1]
    print(f"Корпус: {root_path}. Откройте http://127.0.0.1:{actual}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print("Сервер остановлен.", flush=True)
    return 0
