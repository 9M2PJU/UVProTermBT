import socket
import time

from uvprotermbt.kiss_tcp import KissTcpServer


class FakeLink:
    def __init__(self):
        self.sent = []

    def send(self, data):
        self.sent.append(data)

    def is_connected(self):
        return True


def _wait(pred, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_bridge_relays_both_directions():
    link = FakeLink()
    srv = KissTcpServer(link, port=0)  # OS-assigned free port
    srv.start()
    # discover the bound port
    port = srv._srv.getsockname()[1]
    try:
        client = socket.create_connection(("127.0.0.1", port), timeout=2)
        assert _wait(srv.client_connected)

        # PAT -> radio
        client.sendall(b"\xc0\x00hello\xc0")
        assert _wait(lambda: link.sent == [b"\xc0\x00hello\xc0"])

        # radio -> PAT
        srv.feed_from_radio(b"\xc0\x00world\xc0")
        client.settimeout(2)
        assert client.recv(64) == b"\xc0\x00world\xc0"
    finally:
        client.close()
        srv.stop()
    assert not srv.is_running()


def test_client_disconnect_clears_state():
    srv = KissTcpServer(FakeLink(), port=0)
    srv.start()
    port = srv._srv.getsockname()[1]
    client = socket.create_connection(("127.0.0.1", port), timeout=2)
    assert _wait(srv.client_connected)
    client.close()
    assert _wait(lambda: not srv.client_connected())
    srv.stop()


def test_feed_with_no_client_is_noop():
    srv = KissTcpServer(FakeLink(), port=0)
    srv.start()
    srv.feed_from_radio(b"\xc0\x00x\xc0")  # no client -> must not raise
    srv.stop()
