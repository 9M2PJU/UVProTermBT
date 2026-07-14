"""Classic Bluetooth RFCOMM transport to the UV-Pro.

Mirrors AXTermPuter's RadioLink interface: implementations move raw bytes
(already KISS-framed) to/from the radio; callers handle KISS
encoding/decoding themselves (see kiss.py). Connection/reconnect state is
owned entirely by the implementation.
"""

from __future__ import annotations

import queue
import socket
import threading
import time
from typing import Callable, Optional

ReceiveCallback = Callable[[bytes], None]

# RFCOMM channel 1 carries the real KISS/TNC data (confirmed live: WoAD's
# captured HCI traffic showed genuine KISS framing here, and we've
# connected to it directly from Linux). The SDP-advertised "SPP Dev" /
# Serial Port (0x1101) service on channel 4 looked like the "proper"
# discoverable target but is a red herring — it accepts a bare socket
# connection but isn't the real TNC data path. See docs/PROTOCOL.md §2.
DEFAULT_CHANNEL = 1

_INITIAL_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 30.0
_CONNECT_TIMEOUT_S = 5.0


class RfcommKissLink:
    def __init__(self, address: str, channel: int = DEFAULT_CHANNEL) -> None:
        self._address = address
        self._channel = channel
        self._sock: Optional[socket.socket] = None
        self._connected = threading.Event()
        self._stop = threading.Event()
        self._rx_queue: "queue.Queue[bytes]" = queue.Queue()
        self._on_receive: Optional[ReceiveCallback] = None
        self._thread: Optional[threading.Thread] = None
        self._backoff_s = _INITIAL_BACKOFF_S
        self._sock_lock = threading.Lock()

    def begin(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="rfcomm-kiss-link", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        sock = self._sock
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def is_connected(self) -> bool:
        return self._connected.is_set()

    def send(self, data: bytes) -> None:
        with self._sock_lock:
            sock = self._sock
            connected = self.is_connected()
        if not connected or sock is None:
            return
        try:
            sock.sendall(data)
        except OSError as e:
            print(f"[link] send failed: {type(e).__name__}: {e}")
            self._handle_disconnect()

    def on_receive(self, callback: ReceiveCallback) -> None:
        self._on_receive = callback

    def poll(self) -> None:
        """Drain received chunks and invoke the callback in the caller's
        thread. Call this regularly from the UI/main loop."""
        if self._on_receive is None:
            return
        while True:
            try:
                chunk = self._rx_queue.get_nowait()
            except queue.Empty:
                break
            self._on_receive(chunk)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._connect_and_read()
            except ConnectionRefusedError as e:
                print(f"[link] connection refused (check bluetoothd headset-profile "
                      f"contention / bonding state): {e}")
            except TimeoutError as e:
                print(f"[link] connect timed out after {_CONNECT_TIMEOUT_S}s: {e}")
            except OSError as e:
                print(f"[link] connect error: {type(e).__name__}: {e}")
            self._handle_disconnect()
            if self._stop.is_set():
                break
            time.sleep(self._backoff_s)
            self._backoff_s = min(self._backoff_s * 2, _MAX_BACKOFF_S)

    def _connect_and_read(self) -> None:
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        sock.settimeout(_CONNECT_TIMEOUT_S)
        sock.connect((self._address, self._channel))
        sock.settimeout(None)
        self._sock = sock
        self._connected.set()
        self._backoff_s = _INITIAL_BACKOFF_S
        while not self._stop.is_set():
            data = sock.recv(1024)
            if not data:
                break
            self._rx_queue.put(data)

    def _handle_disconnect(self) -> None:
        with self._sock_lock:
            self._connected.clear()
            sock = self._sock
            self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
