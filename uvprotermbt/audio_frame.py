"""Framing for the UV-Pro's Generic Audio RFCOMM channel.

The audio channel ("BS AOC", UUID 39144315-...) carries HDLC-style frames:

  0x7e  <command>  <payload...>  0x7e

- 0x7e is the frame flag (start and end; a single 0x7e both closes one frame and
  opens the next). Runs of 0x7e are empty frames and are skipped.
- 0x7d is the escape byte: a literal 0x7d or 0x7e in the payload is sent as
  0x7d followed by (byte XOR 0x20). Decode reverses it (next byte XOR 0x20).
- The first un-escaped byte of a frame is the command; the rest is the payload.

Command bytes (see docs/GAIA_AUDIO_SSTV.md):
  0x00 / 0x03  received audio (payload = concatenated SBC frames)
  0x01         audio end
  0x02         audio ACK
  0x09         transmit-audio echo (our own TX looped back for metering)

Reverse-engineered from chengmania/HTCommander's audio_engine.dart. Kept
dependency-free and streaming (bytes arrive in arbitrary chunks per RFCOMM read),
mirroring kiss.py so it's unit-testable without the radio.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

FLAG = 0x7E
ESC = 0x7D
ESC_XOR = 0x20

CMD_RX_AUDIO = 0x00
CMD_RX_AUDIO_ALT = 0x03
CMD_AUDIO_END = 0x01
CMD_AUDIO_ACK = 0x02
CMD_TX_ECHO = 0x09


def encode_frame(command: int, payload: bytes = b"") -> bytes:
    """Build a 0x7e-delimited, 0x7d-escaped audio frame."""
    out = bytearray()
    out.append(FLAG)
    for b in bytes([command & 0xFF]) + payload:
        if b == FLAG or b == ESC:
            out.append(ESC)
            out.append(b ^ ESC_XOR)
        else:
            out.append(b)
    out.append(FLAG)
    return bytes(out)


@dataclass
class AudioFrame:
    command: int
    payload: bytes


class _State(Enum):
    WAIT_FLAG = auto()   # discard anything before the first 0x7e
    IN_FRAME = auto()
    ESCAPED = auto()


class AudioFrameDecoder:
    """Streaming decoder: feed() raw RFCOMM bytes, get complete AudioFrames."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._state = _State.WAIT_FLAG
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[AudioFrame]:
        out: list[AudioFrame] = []
        for b in data:
            self._push_byte(b, out)
        return out

    def _finish(self, out: list[AudioFrame]) -> None:
        # A 0x7e closes the current frame and opens the next (shared flag).
        if self._buffer:  # non-empty: first byte is the command
            out.append(AudioFrame(command=self._buffer[0],
                                  payload=bytes(self._buffer[1:])))
        self._buffer = bytearray()

    def _push_byte(self, b: int, out: list[AudioFrame]) -> None:
        if self._state == _State.WAIT_FLAG:
            if b == FLAG:
                self._buffer = bytearray()
                self._state = _State.IN_FRAME
            return

        if self._state == _State.IN_FRAME:
            if b == FLAG:
                self._finish(out)          # close, and stay ready for the next
                return
            if b == ESC:
                self._state = _State.ESCAPED
                return
            self._buffer.append(b)
            return

        # ESCAPED
        if b == FLAG:
            # Escape immediately followed by a flag: malformed frame; resync.
            self._buffer = bytearray()
            self._state = _State.IN_FRAME
            return
        self._buffer.append(b ^ ESC_XOR)
        self._state = _State.IN_FRAME


# Send verbatim to tell the radio to stop transmitting (audio_engine's
# _endAudioFrame). Already fully framed (leading/trailing 0x7e).
END_AUDIO_FRAME = bytes([0x7E, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7E])
