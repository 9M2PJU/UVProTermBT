"""KISS-over-TCP bridge: re-serve the UV-Pro's KISS stream on a local TCP port
so PAT (pat-gensio, built-in AX.25) — or any KISS-TCP client — can drive the
radio through our working Bluetooth link.

PAT config (pat-gensio): a connection gensio of `kiss,tcp,localhost,8001`.

This is a transparent byte pipe: PAT's KISS bytes go straight to the radio via
the link, and the radio's KISS bytes go straight to PAT. We do NOT decode or do
any AX.25 here — PAT's own stack does that. One client at a time (there is one
radio). No I/O on the GUI thread: a background accept/read loop pushes PAT→radio
via `link.send()`; the GUI feeds radio→PAT via `feed_from_radio()` from its poll.
"""

from __future__ import annotations

import socket
import threading

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001  # direwolf's conventional KISS-TCP port; PAT expects this


class KissTcpServer:
    def __init__(self, link, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self._link = link
        self.host = host
        self.port = port
        self._srv: socket.socket | None = None
        self._client: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._connected = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        """Open the listening socket. Raises OSError if the port is taken."""
        if self._thread is not None:
            return
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(1)
        srv.settimeout(0.5)
        self._srv = srv
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="kiss-tcp", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._close_client()
        if self._srv is not None:
            try:
                self._srv.close()
            except OSError:
                pass
            self._srv = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._connected.clear()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def client_connected(self) -> bool:
        return self._connected.is_set()

    # radio -> PAT (called from the GUI thread, via the app's RX poll)
    def feed_from_radio(self, data: bytes) -> None:
        with self._lock:
            client = self._client
        if client is None:
            return
        try:
            client.sendall(data)
        except OSError:
            self._close_client()

    # PAT -> radio (background thread)
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _addr = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self._close_client()  # only one client at a time
            conn.settimeout(0.5)
            with self._lock:
                self._client = conn
            self._connected.set()
            self._pump(conn)
            self._close_client()

    def _pump(self, conn: socket.socket) -> None:
        while not self._stop.is_set():
            try:
                data = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:  # PAT closed the connection
                break
            self._link.send(data)  # raw KISS bytes straight to the radio

    def _close_client(self) -> None:
        with self._lock:
            client = self._client
            self._client = None
        self._connected.clear()
        if client is not None:
            try:
                client.close()
            except OSError:
                pass
