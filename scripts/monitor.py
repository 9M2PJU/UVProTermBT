#!/usr/bin/env python3
"""Phase 2 hardware smoke test: connect to the UV-Pro over RFCOMM and print
decoded KISS frames as they arrive. Not part of the app proper.

Usage: python3 scripts/monitor.py AA:BB:CC:DD:EE:FF [channel]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from uvprotermbt.kiss import KissDecoder
from uvprotermbt.link import DEFAULT_CHANNEL, RfcommKissLink


def main() -> None:
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} AA:BB:CC:DD:EE:FF [channel]")
        sys.exit(1)
    address = sys.argv[1]
    channel = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CHANNEL

    decoder = KissDecoder()
    link = RfcommKissLink(address, channel)

    def on_receive(data: bytes) -> None:
        print(f"RX {len(data)} raw bytes: {data.hex()}")
        for frame in decoder.feed(data):
            print(
                f"KISS frame: port={frame.port} cmd={frame.command} "
                f"len={len(frame.payload)}: {frame.payload.hex()}"
            )

    link.on_receive(on_receive)
    link.begin()

    print(f"Connecting to {address} channel {channel} ... (Ctrl-C to stop)")
    last_connected = False
    try:
        while True:
            if link.is_connected() != last_connected:
                last_connected = link.is_connected()
                print(f"[link] connected={last_connected}")
            link.poll()
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        link.stop()


if __name__ == "__main__":
    main()
