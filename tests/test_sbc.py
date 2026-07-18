"""Tests for the libsbc binding (uvprotermbt/sbc.py), fixed to the radio format."""

from __future__ import annotations

import math
import struct

import pytest

sbc = pytest.importorskip("uvprotermbt.sbc")

try:
    _HAVE_LIBSBC = bool(sbc.SbcEncoder() and True)
except Exception:  # libsbc not installed on this host
    _HAVE_LIBSBC = False

pytestmark = pytest.mark.skipif(not _HAVE_LIBSBC, reason="libsbc not available")


def _sine_pcm(frames: int, enc) -> bytes:
    n = enc.pcm_bytes_per_frame // 2 * frames
    return b"".join(
        struct.pack("<h", int(12000 * math.sin(2 * math.pi * 1000 * i / 32000)))
        for i in range(n))


def test_codesize_matches_radio_format():
    enc = sbc.SbcEncoder()
    # blocks(16) * subbands(8) * mono(1) * 2 bytes = 256
    assert enc.pcm_bytes_per_frame == 256


def test_encode_produces_sbc_sync_byte():
    enc = sbc.SbcEncoder()
    out = enc.encode(_sine_pcm(4, enc))
    assert out and out[0] == 0x9C  # standard SBC sync


def test_roundtrip_length_preserved():
    enc = sbc.SbcEncoder()
    pcm = _sine_pcm(30, enc)
    encoded = enc.encode(pcm)
    decoded = sbc.SbcDecoder().feed(encoded)
    assert len(decoded) == len(pcm)


def test_decoder_buffers_partial_frames():
    enc = sbc.SbcEncoder()
    encoded = enc.encode(_sine_pcm(10, enc))
    dec = sbc.SbcDecoder()
    # Feed one byte at a time — frames only emerge once fully arrived.
    out = bytearray()
    for i in range(len(encoded)):
        out += dec.feed(encoded[i:i + 1])
    assert len(out) == 10 * enc.pcm_bytes_per_frame
