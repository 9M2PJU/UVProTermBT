"""Tests for the UV-Pro audio-channel framer (uvprotermbt/audio_frame.py)."""

from __future__ import annotations

from uvprotermbt.audio_frame import (
    CMD_AUDIO_END, CMD_RX_AUDIO, END_AUDIO_FRAME, ESC, FLAG, AudioFrame,
    AudioFrameDecoder, encode_frame,
)


def _decode_all(data: bytes) -> list[AudioFrame]:
    return AudioFrameDecoder().feed(data)


def test_roundtrip_simple():
    frame = encode_frame(CMD_RX_AUDIO, b"\x9c\x11\x22\x33")
    frames = _decode_all(frame)
    assert frames == [AudioFrame(command=CMD_RX_AUDIO, payload=b"\x9c\x11\x22\x33")]


def test_escaping_of_flag_and_esc_in_payload():
    payload = bytes([FLAG, ESC, 0x00, FLAG, 0xAA])
    wire = encode_frame(CMD_RX_AUDIO, payload)
    # The raw flag/esc must not appear un-escaped inside the frame body.
    assert wire[0] == FLAG and wire[-1] == FLAG
    assert FLAG not in wire[1:-1]
    # 0x7e -> 0x7d 0x5e, 0x7d -> 0x7d 0x5d
    assert bytes([ESC, FLAG ^ 0x20]) in wire
    assert bytes([ESC, ESC ^ 0x20]) in wire
    # ...and it decodes back exactly.
    assert _decode_all(wire) == [AudioFrame(CMD_RX_AUDIO, payload)]


def test_command_byte_preserved():
    for cmd in (0x00, 0x01, 0x02, 0x03, 0x09):
        assert _decode_all(encode_frame(cmd, b"\x01\x02"))[0].command == cmd


def test_streaming_split_across_chunks():
    wire = encode_frame(CMD_RX_AUDIO, bytes([FLAG, ESC, 0x42]))
    dec = AudioFrameDecoder()
    got: list[AudioFrame] = []
    for i in range(len(wire)):  # feed one byte at a time
        got += dec.feed(wire[i:i + 1])
    assert got == [AudioFrame(CMD_RX_AUDIO, bytes([FLAG, ESC, 0x42]))]


def test_two_back_to_back_frames_shared_flag():
    # ...7e A 7e B 7e...  the middle 7e closes A and opens B.
    wire = bytes([FLAG, 0x00, 0xAA, FLAG, 0x03, 0xBB, FLAG])
    assert _decode_all(wire) == [AudioFrame(0x00, b"\xAA"), AudioFrame(0x03, b"\xBB")]


def test_empty_frames_and_leading_garbage_skipped():
    wire = bytes([0x11, 0x22, FLAG, FLAG, FLAG, 0x00, 0xAB, FLAG])
    assert _decode_all(wire) == [AudioFrame(0x00, b"\xAB")]


def test_end_audio_frame_decodes_as_audio_end():
    frames = _decode_all(END_AUDIO_FRAME)
    assert len(frames) == 1
    assert frames[0].command == CMD_AUDIO_END
