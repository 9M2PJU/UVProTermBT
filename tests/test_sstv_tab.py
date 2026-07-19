"""Hermetic tests for the SSTV tab widget (uvprotermbt/gui/sstv_tab.py).

No radio: a fake KISS link records the GAIA handshake, RfcommAudioLink is stubbed,
and we drive the RX-decode trigger with a fake decoder to confirm the flow.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6.QtWidgets")

from uvprotermbt import gaia  # noqa: E402
from uvprotermbt.config import Settings  # noqa: E402
from uvprotermbt.gui import sstv_tab as st  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


class _FakeKiss:
    def __init__(self):
        self.sent = []

    def is_connected(self):
        return True

    def send(self, data: bytes):
        self.sent.append(bytes(data))


class _FakeAudio:
    def __init__(self, *_a, **_k):
        self.began = False
        self._cb = None

    def on_receive(self, cb):
        self._cb = cb

    def begin(self):
        self.began = True

    def is_connected(self):
        return True

    def poll(self):
        pass

    def stop(self):
        pass


def _make(qapp, monkeypatch):
    monkeypatch.setattr(st, "RfcommAudioLink", _FakeAudio)
    kiss = _FakeKiss()
    logs = []
    s = Settings(callsign="KC3SMW", ssid=7, bt_mac="AA:BB:CC:DD:EE:FF")
    tab = st.SstvTab(s, lambda: kiss, logs.append)
    return tab, kiss, logs


def test_enable_sends_gaia_handshake_and_opens_audio(qapp, monkeypatch):
    tab, kiss, _ = _make(qapp, monkeypatch)
    tab._enable()
    assert tab._enabled is True
    assert isinstance(tab._audio, _FakeAudio) and tab._audio.began
    # GAIA handshake frames were sent on the KISS link (start with FF 01).
    assert kiss.sent == gaia.handshake_frames()
    assert all(f[:2] == b"\xff\x01" for f in kiss.sent)


def test_disable_stops_audio(qapp, monkeypatch):
    tab, _, _ = _make(qapp, monkeypatch)
    tab._enable()
    tab._disable()
    assert tab._enabled is False and tab._audio is None


def test_short_rx_audio_is_dropped_not_decoded(qapp, monkeypatch):
    tab, _, _ = _make(qapp, monkeypatch)
    tab._enable()
    # A tiny amount of PCM well under the minimum — _maybe_decode should drop it.
    tab._rx_pcm.extend(b"\x00" * 1000)
    tab._last_audio_t = 0.0  # long ago -> "quiet" gap satisfied
    tab._maybe_decode()
    assert not tab._decoding and len(tab._rx_pcm) == 0
