"""Probe whether the radio answers GAIA on the SPP channel — the pivotal test
for SSTV *transmit* (which needs the GAIA control channel HTCommander keeps open).

Opens the SPP channel (same UUID we use for KISS), sends a few GAIA queries
(getDevId / getDevInfo / readStatus) and reports whether the radio replies in
GAIA, plus whether any KISS traffic (0xC0) appears — which speaks to whether GAIA
and KISS can share the channel.

    .venv/bin/python -m uvprotermbt.gaia_probe

Try it with the radio's KISS TNC both ON and OFF and compare. Read-only; sends a
handful of query commands, no settings are changed.
"""

from __future__ import annotations

import time

from .config import Settings
from .gaia import (CMD_GET_DEV_ID, CMD_GET_DEV_INFO, CMD_READ_STATUS,
                   GROUP_BASIC, GaiaDecoder, encode)
from .link import RfcommKissLink

_QUERIES = [
    ("getDevId", CMD_GET_DEV_ID),
    ("getDevInfo", CMD_GET_DEV_INFO),
    ("readStatus", CMD_READ_STATUS),
]


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Probe GAIA on the radio's SPP channel")
    ap.add_argument("--mac", default=None, help="radio MAC (default: from config)")
    ap.add_argument("--listen", type=float, default=5.0, help="seconds to listen for replies")
    args = ap.parse_args()

    mac = args.mac or Settings.load().bt_mac
    if not mac:
        raise SystemExit("no radio MAC — set one in the app, or pass --mac")

    dec = GaiaDecoder()
    raw = bytearray()
    gaia_frames = []

    def on_rx(data: bytes) -> None:
        raw.extend(data)
        gaia_frames.extend(dec.feed(data))

    link = RfcommKissLink(mac)  # SPP / control channel
    link.on_receive(on_rx)
    print(f"[gaia] opening SPP channel on {mac} …")
    link.begin()
    for _ in range(100):
        if link.is_connected():
            break
        link.poll()
        time.sleep(0.05)
    if not link.is_connected():
        link.stop()
        raise SystemExit("SPP channel didn't connect")

    print("[gaia] sending GAIA queries …")
    for name, cmd in _QUERIES:
        frame = encode(GROUP_BASIC, cmd)
        print(f"  -> {name}: {frame.hex(' ')}")
        link.send(frame)
        time.sleep(0.3)
        link.poll()

    end = time.monotonic() + args.listen
    while time.monotonic() < end:
        link.poll()
        time.sleep(0.05)
    link.poll()
    link.stop()

    print("\n===== GAIA probe results =====")
    print(f"raw bytes received:   {len(raw)}")
    if raw:
        print(f"first 64 bytes (hex): {bytes(raw[:64]).hex(' ')}")
    print(f"KISS FEND (0xC0) seen: {bytes(raw).count(0xC0)}")
    print(f"GAIA frames decoded:   {len(gaia_frames)}")
    for f in gaia_frames[:12]:
        tag = "resp" if f.is_response else "cmd"
        print(f"  <- {tag} group={f.group} cmd={f.command} "
              f"data[{len(f.data)}]={f.data.hex(' ')}")

    print()
    if gaia_frames:
        print("VERDICT: the radio ANSWERS GAIA on the SPP channel — the control "
              "channel is reachable. TX-via-GAIA is feasible; next, test whether "
              "it coexists with KISS.")
    elif raw:
        print("VERDICT: bytes came back but no valid GAIA frame — the channel may "
              "be in KISS mode (try with the radio's KISS TNC turned OFF).")
    else:
        print("VERDICT: no reply at all. Try again with KISS TNC OFF; if still "
              "nothing, GAIA may need a different connect/handshake.")


if __name__ == "__main__":
    main()
