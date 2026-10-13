"""Тесты serve: живой GET в потоке + валидация CLI. Без внешней сети."""

import threading
import urllib.request

from kw_yt_transcript import cli as cli_mod
from kw_yt_transcript.serve import make_server, serve_dir


def test_live_get_index_200(tmp_path):
    root = tmp_path / "out"
    root.mkdir()
    marker = "Каталог-маркер-12345"
    (root / "index.html").write_text(f"<html><body>{marker}</body></html>", "utf-8")
    server = make_server(root, 0)
    assert server.server_address[0] == "127.0.0.1"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        assert port != 0
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
            assert resp.status == 200
            assert marker in resp.read().decode("utf-8")
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_serve_dir_ctrl_c_clean_exit(tmp_path, monkeypatch, capsys):
    calls = {}

    class FakeServer:
        server_address = ("127.0.0.1", 8765)

        def serve_forever(self):
            calls["served"] = True
            raise KeyboardInterrupt

        def server_close(self):
            calls["closed"] = True

    monkeypatch.setattr("kw_yt_transcript.serve.make_server", lambda *a, **k: FakeServer())
    assert serve_dir(tmp_path, 8765) == 0
    assert calls == {"served": True, "closed": True}
    out = capsys.readouterr().out
    assert "http://127.0.0.1:8765/" in out


def test_serve_dir_missing_dir_exit_2(tmp_path):
    assert serve_dir(tmp_path / "нет", 8000) == 2


def test_cli_serve_bad_port_exit_2(tmp_path):
    assert cli_mod.main(["serve", str(tmp_path), "--port", "zzz"]) == 2
    assert cli_mod.main(["serve", str(tmp_path), "--port", "99999"]) == 2


def test_cli_serve_missing_dir_exit_2(tmp_path):
    assert cli_mod.main(["serve", str(tmp_path / "нет")]) == 2
