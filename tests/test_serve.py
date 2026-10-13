"""Тесты serve: живой GET в потоке + валидация CLI. Без внешней сети."""

import threading
import urllib.request

from kw_yt_transcript import cli as cli_mod
from kw_yt_transcript.serve import DEFAULT_HOST, make_server, serve_dir


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


def test_serve_warns_without_index(tmp_path, monkeypatch, capsys):
    served = {}

    class FakeServer:
        server_address = ("127.0.0.1", 8123)

        def serve_forever(self):
            served["yes"] = True
            raise KeyboardInterrupt

        def server_close(self):
            served["closed"] = True

    monkeypatch.setattr("kw_yt_transcript.serve.make_server", lambda *a, **k: FakeServer())
    assert serve_dir(tmp_path, 8123) == 0
    err = capsys.readouterr().err
    assert "редупреждение" in err and "index.html" in err


def test_cli_serve_bad_port_exit_2(tmp_path):
    assert cli_mod.main(["serve", str(tmp_path), "--port", "zzz"]) == 2
    assert cli_mod.main(["serve", str(tmp_path), "--port", "99999"]) == 2


def test_cli_serve_missing_dir_exit_2(tmp_path):
    assert cli_mod.main(["serve", str(tmp_path / "нет")]) == 2


def test_make_server_binds_host_and_serves_loopback(tmp_path):
    assert DEFAULT_HOST == "127.0.0.1"
    root = tmp_path / "out"
    root.mkdir()
    marker = "host-маркер-67890"
    (root / "index.html").write_text(f"<html><body>{marker}</body></html>", "utf-8")
    server = make_server(root, 0, "0.0.0.0")
    assert server.server_address[0] == "0.0.0.0"
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


class _FakeHostServer:
    def __init__(self, host, port):
        self.server_address = (host, port)

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        pass


def test_serve_dir_warns_on_lan_host(tmp_path, monkeypatch, capsys):
    seen = {}

    def fake_make(root, port=0, host="127.0.0.1"):
        seen["host"] = host
        return _FakeHostServer(host, port)

    monkeypatch.setattr("kw_yt_transcript.serve.make_server", fake_make)
    assert serve_dir(tmp_path, 8124, "0.0.0.0") == 0
    assert seen["host"] == "0.0.0.0"
    res = capsys.readouterr()
    assert "http://0.0.0.0:8124/" in res.out
    assert "виден всей локальной сети" in res.err


def test_serve_dir_no_warning_on_loopback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "kw_yt_transcript.serve.make_server",
        lambda root, port=0, host="127.0.0.1": _FakeHostServer(host, port),
    )
    assert serve_dir(tmp_path, 8125) == 0
    res = capsys.readouterr()
    assert "http://127.0.0.1:8125/" in res.out
    assert "локальной сети" not in res.err


def test_cli_serve_bad_host_exit_2_no_bind(tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("bind не должен вызываться при мусорном host")

    monkeypatch.setattr("kw_yt_transcript.serve.make_server", boom)
    assert cli_mod.main(["serve", str(tmp_path), "--host", "!!!"]) == 2
    assert cli_mod.main(["serve", str(tmp_path), "--host", ""]) == 2
    res = capsys.readouterr()
    assert "host" in res.err


def test_cli_serve_host_passthrough(tmp_path, monkeypatch, capsys):
    seen = {}

    def fake_make(root, port=0, host="127.0.0.1"):
        seen.update(host=host, port=port)
        return _FakeHostServer(host, port)

    monkeypatch.setattr("kw_yt_transcript.serve.make_server", fake_make)
    assert cli_mod.main(["serve", str(tmp_path), "--host", "0.0.0.0"]) == 0
    assert seen["host"] == "0.0.0.0"
    capsys.readouterr()
    assert cli_mod.main(["serve", str(tmp_path)]) == 0
    assert seen["host"] == "127.0.0.1"
    capsys.readouterr()
