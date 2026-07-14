# UVProTermBT — Protocol Notes

Living document. Update with evidence when hardware findings change anything.
Carries over confirmed findings from the AXTermPuter project's Phase 2
investigation (2026-07-13) — see that repo's `docs/PROTOCOL.md` and
`LOG.txt` for the full narrative of how these were discovered.

## 1. KISS Framing

- FEND = 0xC0, FESC = 0xDB, TFEND = 0xDC, TFESC = 0xDD
- Frame: FEND, type byte, payload (escaped), FEND
- Type 0x00 = data on port 0 (only port used with UV-Pro)
- Escaping: 0xC0 → 0xDB 0xDC; 0xDB → 0xDB 0xDD
- The RFCOMM socket delivers arbitrary-sized chunks: the decoder MUST
  reassemble across reads and tolerate back-to-back FENDs / empty frames.

Decoder design decisions (`uvprotermbt/kiss.py`, ported from AXTermPuter's
native-tested `lib/kiss/kiss_codec.{h,cpp}` — not reverse-engineered
findings, implementation choices where the KISS spec is silent):
- Back-to-back `FEND FEND` (empty frame) is silently skipped, never
  emitted as a zero-length `Frame`.
- `FESC` followed by anything other than `TFEND`/`TFESC` is treated as a
  protocol violation: the in-progress frame is discarded and decoding
  resyncs on the next `FEND`.

## 2. UV-Pro Bluetooth Link — classic BT RFCOMM, NOT BLE

This is the single most important finding from the AXTermPuter
investigation and the whole reason this project exists on this platform:

- The UV-Pro is a dual-mode (BR/EDR + BLE) radio. It exposes a BLE GATT
  service (`00000001-ba2a-46c9-ae49-01b0961f68bb`, write char `...0002`,
  notify char `...0003`) that looks exactly like a serial/KISS transport
  — but writing well-formed KISS frames to it produces **zero RF
  activity** (verified against direwolf monitoring the channel live).
- Captured real Bluetooth HCI traffic (via an Android bugreport's
  embedded btsnoop log) from two different Android apps talking to the
  radio in TNC mode:
  - The official BTech companion app: classic BT `Create Connection`,
    classic pairing (Link Key Request/Reply), RFCOMM multiplexer
    (channel 0), then a data channel on **RFCOMM channel 4**.
  - A second app ("WoAD"): same classic BT connection pattern, data on
    **RFCOMM channel 1** this time. Direwolf, listening live on the
    frequency, cleanly decoded a real AX.25 SABM frame
    (`KC3SMW-15>KC3SMW-10:(SABM cmd, p=1)`) transmitted during this
    session.
  - Confirmed genuine KISS framing on channel 1: captured payload bytes
    included `C0 00` immediately at the start of a UIH frame — FEND
    followed by command byte 0x00 (data, port 0), exactly matching
    `kiss.py`/`kiss_codec.h`.
- **Conclusion: the UV-Pro's real KISS/TNC data path is classic Bluetooth
  RFCOMM (SPP), not BLE GATT.** The BLE service that looks like a serial
  transport is a red herring for this purpose (its actual function is
  unconfirmed — maybe firmware update, maybe unused in current firmware).
- **SDP records confirmed directly from Linux (2026-07-13)** via `sdptool
  records <addr>` (note: `sdptool browse <addr>` comes back empty —
  `records` is the form that works) after a fresh classic-BT pair
  (`bluetoothctl pair`, no PIN prompt — Just Works style):
  - `PnP Information` (`0x1200`) — no RFCOMM channel (info record only)
  - `"BS AOC"` (custom UUID `39144315-32fa-40db-85ed-fbfeba2d86e6`) →
    RFCOMM channel 2
  - `Voice Gateway` (Handsfree Audio Gateway `0x111f`) → RFCOMM channel 3
  - `"SPP Dev"` (Serial Port, `0x1101`) → RFCOMM channel 4
  - **Correction, superseding the channel-4 recommendation below:**
    channel 4 is SDP-discoverable and accepts a bare socket connection,
    but it is a **red herring** — a generic advertised serial profile,
    not the real TNC data path (see the `benlink` findings just below for
    why). Channel 1, which does *not* appear in this SDP table at all,
    is the one that actually matters.
- **Found the [`khusmann/benlink`](https://github.com/khusmann/benlink)
  project (2026-07-13)** — a Python library specifically reverse-
  engineering this radio family ("Benshi" radios: BTech UV-Pro,
  RadioOddity GA-5WB, Vero VR-N76/N7500, BTech GMRS-Pro). This resolved
  several things we'd been guessing at:
  - The real BLE control service is
    `00001100-d102-11e1-9b23-00025b00a5a5` (write char `...1101`, notify
    char `...1102`) — **not** `00000001-ba2a-46c9-ae49-01b0961f68bb`,
    which we'd identified earlier and is itself a red herring, just like
    RFCOMM channel 4. We had the "which service looks like a serial
    bridge" instinct right, twice, and were wrong both times.
  - Messages are wrapped in a `Message`/`TncDataFragment` structure, and
    for RFCOMM specifically, additionally wrapped in a `GaiaFrame`
    (Qualcomm GAIA framing: starts with `0xFF 0x01` version, then a
    1-byte flags, 1-byte payload-length, then the message bytes). This is
    a real, documented control protocol — not just raw KISS on a serial
    line.
  - `benlink`'s own documented RFCOMM usage connects with **channel 1**,
    matching WoAD's channel, not channel 4.
  - Cross-checking the actual captured bytes settles which channel is
    which: the official app's channel 4 traffic ended in `...ff 01 00` —
    a GaiaFrame header. WoAD's channel 1 traffic started with `c0 00` —
    raw KISS FEND + command byte, no GaiaFrame at all. **Conclusion:
    channel 1 carries genuine raw KISS pass-through (no envelope needed),
    separate from and simpler than the structured Benshi GaiaFrame
    command protocol.** The two are distinguishable by leading byte
    (`0xFF` for a GaiaFrame command, `0xC0` for a raw KISS frame),
    suggesting channel 1 may be multiplexed to carry both, but for our
    purposes (APRS/AX.25 terminal) we only need the raw KISS half.
  - **Decision: `uvprotermbt`'s own `kiss.py` + `RfcommKissLink` remain
    the right approach for the core KISS data path — no need to adopt
    `benlink`'s `Message`/`GaiaFrame` protocol for that.** `benlink` is
    a good reference to come back to later for actual radio-control
    features (battery level, channel switching, position) that aren't
    needed for basic APRS/terminal functionality.
  - `RfcommKissLink.DEFAULT_CHANNEL` is now **1**, not 4.
- **Confirmed live from Linux, twice independently** (2026-07-13): a bare
  `socket.AF_BLUETOOTH`/`BTPROTO_RFCOMM` connect to channel 1 succeeds
  cleanly after a fresh `bluetoothctl pair`. No RF traffic happened to be
  flowing during either test window, so we haven't yet decoded a live
  AX.25 frame end-to-end from this project, but the transport-level
  connection itself works.
- **Known issue, still open: the classic-BT connection is flaky to
  reproduce on demand.** Across many attempts this session we saw, in
  no obvious pattern: clean connect, `TimeoutError`, `ConnectionRefusedError`,
  and (once) `br-connection-refused` at the BlueZ `Device1.Connect()`
  level when a stale/mismatched bond exists on one side only (e.g. we ran
  `bluetoothctl remove` locally but the radio still remembered the old
  bond — symmetric removal on both sides fixes that specific case). Some
  observations, none fully explanatory on their own:
  - The radio's own "paired device" entry for us was observed to appear
    and then disappear within a few seconds on the radio's screen,
    independent of anything we did — suggesting the ACL connection itself
    may only stay up briefly unless something actively uses it soon after
    it forms.
  - A full power cycle (battery pulled) of the radio did restore BLE
    connectivity when it had also gone flaky, suggesting the radio's BT
    stack can get into a bad state that a reset clears.
  - Holding a BLE connection open at the same time does **not** stabilize
    or help classic RFCOMM — confirmed independent by testing both at once.
  - We do not have logs from the radio's own firmware, so root-causing
    this further from software has hit its limit for now.
- TODO Phase 2 (still open): get a live end-to-end decode of a real AX.25
  frame through `RfcommKissLink` on channel 1 (transport connects, but we
  haven't yet caught it during live RF traffic), and characterize the
  connection flakiness further if it keeps blocking progress — possibly
  worth a dedicated session with more patience/time than fits in a single
  sitting, given how unpredictable the timing has been.

## 3. AX.25 Essentials

- Address field: callsign shifted left 1 bit, space-padded to 6 chars;
  SSID byte carries SSID (bits 1-4), H bit (has-been-digipeated), and the
  address-extension bit (last address sets bit 0 = 1).
- UI frame: control 0x03, PID 0xF0 (no layer 3) — all APRS traffic.
- Connected mode subset for Terminal Mode:
  - SABM (0x2F/0x3F w/ P) → expect UA
  - I-frames with N(S)/N(R), RR as ack, REJ on sequence error
  - DISC → UA to tear down
  - T1 retry timer: start ~5 s at 1200 baud w/ digi hops, back off
- FCS: handled by the TNC in KISS mode — do NOT append CRC in KISS payloads.

## 4. APRS Messaging (spec ch. 14)

- Format: `:AAAAAAAAA:message text{NNNNN`
  - Addressee exactly 9 chars, space-padded
  - Message max 67 chars
  - `{NNNNN` = up to 5-char message ID (we use numeric, incrementing)
- Ack: `:AAAAAAAAA:ackNNNNN` — send immediately on RX of ID'd message
- Reject: `rejNNNNN` (rare; handle on RX, never send in v1)
- Retry policy: resend unacked msgs at 30 s, 60 s, 120 s, 240 s, then mark
  failed.
- Default path `WIDE1-1,WIDE2-1`; make configurable (some areas prefer
  WIDE2-1 only).

## 5. Callsign Conventions

- Default station: KC3SMW, suggested SSID -7 (HT/handheld convention).
  On-air smoke testing during the AXTermPuter investigation used -10 and
  -15 for ad hoc test frames — pick real SSIDs deliberately once this
  project is doing genuine testing, don't reuse those test values as if
  they mean anything.
- Terminal mode primary target: ChengmaniaBPQ node (confirm on-air
  call/SSID of the node port before real BBS testing)

## 6. Legal Reminders

- Part 97: no content encryption on RF; ID with callsign (inherent in
  AX.25 source address); no third-party auto-forwarding shenanigans in v1.
