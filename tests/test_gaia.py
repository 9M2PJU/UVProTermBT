"""Tests for the GAIA control-frame codec (uvprotermbt/gaia.py)."""

from __future__ import annotations

from uvprotermbt import gaia


def test_encode_getdevinfo_layout():
    frame = gaia.encode(gaia.GROUP_BASIC, gaia.CMD_GET_DEV_INFO)
    # FF 01 00 00  00 02  00 04
    assert frame == bytes([0xFF, 0x01, 0x00, 0x00, 0x00, 0x02, 0x00, 0x04])


def test_encode_with_data_sets_length():
    frame = gaia.encode(gaia.GROUP_BASIC, 0x11, b"\xaa\xbb\xcc")
    assert frame[3] == 3  # data length only
    assert frame.endswith(b"\xaa\xbb\xcc")


def test_roundtrip_decode():
    wire = gaia.encode(gaia.GROUP_BASIC, gaia.CMD_GET_DEV_ID, b"\x01\x02")
    frames = gaia.GaiaDecoder().feed(wire)
    assert len(frames) == 1
    f = frames[0]
    assert f.group == gaia.GROUP_BASIC and f.command == gaia.CMD_GET_DEV_ID
    assert f.data == b"\x01\x02"


def test_response_bit_stripped():
    # A reply ORs the command with 0x8000.
    wire = gaia.encode(gaia.GROUP_BASIC, gaia.CMD_GET_DEV_INFO | 0x8000, b"\x09")
    f = gaia.GaiaDecoder().feed(wire)[0]
    assert f.command == gaia.CMD_GET_DEV_INFO
    assert f.is_response is True


def test_resync_past_interleaved_bytes():
    # KISS-ish garbage (0xC0…) before and between GAIA frames must be skipped.
    a = gaia.encode(gaia.GROUP_BASIC, gaia.CMD_GET_DEV_ID)
    b = gaia.encode(gaia.GROUP_BASIC, gaia.CMD_READ_STATUS)
    stream = b"\xc0\x00\x11\xc0" + a + b"\xc0\xff\xc0" + b
    frames = gaia.GaiaDecoder().feed(stream)
    assert [f.command for f in frames] == [gaia.CMD_GET_DEV_ID, gaia.CMD_READ_STATUS]


def test_streaming_split():
    wire = gaia.encode(gaia.GROUP_BASIC, gaia.CMD_GET_DEV_INFO, b"\xde\xad\xbe\xef")
    dec = gaia.GaiaDecoder()
    got = []
    for i in range(len(wire)):
        got += dec.feed(wire[i:i + 1])
    assert len(got) == 1 and got[0].data == b"\xde\xad\xbe\xef"
