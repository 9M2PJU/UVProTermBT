# UVProTermBT — Roadmap

## Phase 0 — Scaffold
- [x] Project structure: `uvprotermbt/` package, `tests/`, docs, venv
- [ ] Repo init, push to github.com/chengmania/UVProTermBT
- [ ] `requirements.txt` / packaging metadata
- [ ] GitHub Actions workflow skeleton (Linux build; Windows stretch goal)

## Phase 1 — KISS Codec
- [x] `kiss.py`: encode/decode, FEND/FESC/TFEND/TFESC escaping (ported
      from AXTermPuter's native-tested C++ version)
- [x] Stream reassembly (partial frames across arbitrary-sized reads)
- [x] Unit tests incl. malformed-frame fuzz case (pytest, 8/8 passing)

## Phase 2 — Classic Bluetooth RFCOMM Link to UV-Pro
- [x] Confirm SDP-advertised RFCOMM channels from Linux directly
      (`sdptool records <addr>` — `browse` comes back empty). Found
      channels 2/3/4 via SDP, but see below: none of those are actually
      the right one.
- [x] `RfcommKissLink`: connect via `socket.AF_BLUETOOTH`/`BTPROTO_RFCOMM`,
      background RX thread feeding a queue, `send()`/`onReceive()` like
      AXTermPuter's `RadioLink` interface
- [x] Reconnect logic (backoff) in `RfcommKissLink`
- [x] Identified the real channel: **RFCOMM channel 1** (not SDP-
      discoverable, not the channel-4 "SPP Dev" service we initially
      targeted) via the `khusmann/benlink` reference project + our own
      byte-level analysis of captured traffic. See docs/PROTOCOL.md §2.
- [x] Connected live to channel 1 from Linux (confirmed twice)
- [ ] BT status surfaced in the UI (no UI yet — Phase 6/7)
- [ ] HARDWARE TEST: decode a real live KISS/AX.25 frame end-to-end
      through `RfcommKissLink` — transport connects, but we haven't yet
      caught it during live RF traffic. Classic-BT connection has been
      flaky to reproduce on demand this session; see docs/PROTOCOL.md §2
      "known issue" note.

## Phase 3 — AX.25 UI Frames + APRS RX
- [ ] AX.25 address encode/decode (callsign-SSID, digi path, H-bits)
- [ ] UI frame build/parse
- [ ] APRS packet classifier: position, status, message
- [ ] Heard-stations list view (call, last heard, type)

## Phase 4 — APRS Messaging
- [ ] Message encode (`:ADDRESSEE:text{NN`), 67-char enforcement
- [ ] Ack send on RX; retry queue with backoff on TX
- [ ] Conversation UI: per-station threads, unread indicator, compose
- [ ] Optional periodic status/position beacon (off by default)
- [ ] ON-AIR TEST: two-way message with another station / digipeater

## Phase 5 — AX.25 Connected Mode
- [ ] LAPB-ish state machine: SABM/UA, I-frames, RR/RNR, REJ, DISC
- [ ] Window size 1 first (simplest), then k>1 if stable
- [ ] Retry/T1 timer tuning for 1200-baud AFSK realities
- [ ] Unit tests with scripted frame exchanges

## Phase 6 — Terminal Mode UI
- [ ] Connect dialog (target call, digi path)
- [ ] Session view: scrollback buffer, line input, disconnect key
- [ ] ON-AIR TEST: connect to ChengmaniaBPQ, read messages on the BBS

## Phase 7 — Settings & Polish
- [ ] Settings screen: callsign/SSID, path, BT target, beacon
- [ ] JSON config persistence (user config dir)
- [ ] README with usage guide
- [ ] PyInstaller executables (Linux primary, Windows stretch) via GitHub
      Actions release workflow

## Future / Post-v1
- [ ] LoRa-APRS backend behind the same link interface, if ever relevant
- [ ] Meshtastic↔APRS bridge experiments
- [ ] Export heard log / messages to a field server
- [ ] Radio-control features (battery level, channel switching, position)
      via the `khusmann/benlink` library's structured GaiaFrame protocol —
      not needed for core APRS/terminal functionality, but a good fit for
      a "radio status" panel later
