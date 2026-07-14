"""KISS framing/deframing.

Port of AXTermPuter's lib/kiss/kiss_codec.{h,cpp} (native-tested C++). Same
design decisions apply here:
- FEND FEND (an empty frame) is silently skipped, never emitted as a
  zero-length Frame.
- FESC followed by anything other than TFEND/TFESC is a protocol
  violation: the in-progress frame is discarded and decoding resyncs on
  the next FEND.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD

CMD_DATA = 0x00


def encode_frame(payload: bytes, port: int = 0, command: int = CMD_DATA) -> bytes:
    out = bytearray()
    out.append(FEND)
    out.append(((port & 0x0F) << 4) | (command & 0x0F))
    for b in payload:
        if b == FEND:
            out.append(FESC)
            out.append(TFEND)
        elif b == FESC:
            out.append(FESC)
            out.append(TFESC)
        else:
            out.append(b)
    out.append(FEND)
    return bytes(out)


@dataclass
class Frame:
    port: int
    command: int
    payload: bytes


class _State(Enum):
    WAIT_FEND = auto()
    IN_FRAME = auto()
    ESCAPED = auto()


class KissDecoder:
    """Streaming KISS decoder.

    Bytes arrive in arbitrarily-sized chunks (e.g. one per RFCOMM read)
    across possibly many feed() calls; complete frames are returned as
    soon as they're recognized.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._state = _State.WAIT_FEND
        self._buffer = bytearray()
        self._have_command_byte = False
        self._command_byte = 0

    def feed(self, data: bytes) -> list[Frame]:
        out: list[Frame] = []
        for b in data:
            self._push_byte(b, out)
        return out

    def _begin_frame(self) -> None:
        self._buffer = bytearray()
        self._have_command_byte = False
        self._command_byte = 0
        self._state = _State.IN_FRAME

    def _abort_frame(self) -> None:
        self._state = _State.WAIT_FEND

    def _finish_frame(self, out: list[Frame]) -> None:
        if self._have_command_byte:
            port = (self._command_byte >> 4) & 0x0F
            command = self._command_byte & 0x0F
            out.append(Frame(port=port, command=command, payload=bytes(self._buffer)))
        self._state = _State.WAIT_FEND

    def _push_byte(self, b: int, out: list[Frame]) -> None:
        if self._state == _State.WAIT_FEND:
            if b == FEND:
                self._begin_frame()
            return

        if self._state == _State.IN_FRAME:
            if b == FEND:
                self._finish_frame(out)
                return
            if b == FESC:
                self._state = _State.ESCAPED
                return
            self._append_data_byte(b)
            return

        if self._state == _State.ESCAPED:
            if b == TFEND:
                self._append_data_byte(FEND)
                self._state = _State.IN_FRAME
                return
            if b == TFESC:
                self._append_data_byte(FESC)
                self._state = _State.IN_FRAME
                return
            # Protocol violation: discard and resync on the next FEND.
            self._abort_frame()
            return

    def _append_data_byte(self, b: int) -> None:
        if not self._have_command_byte:
            self._have_command_byte = True
            self._command_byte = b
            return
        self._buffer.append(b)
