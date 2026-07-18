# UV-Pro Audio Channel + GAIA — for SSTV (TX/RX images)

Reverse-engineered from `chengmania/HTCommander` (a Flutter port of Ylian
Saint-Hilaire's HTCommander) to add an **SSTV tab** to UVProTermBT. The radio
carries digital packet over KISS **and** an SBC audio stream over a *separate*
RFCOMM channel — the two coexist (confirmed on air: SSTV worked with KISS TNC
still enabled), so we can do audio (SSTV) without disturbing the packet link.

## Two RFCOMM channels (both classic BT, SDP-resolved by UUID)

| Channel | UUID | Carries |
|---|---|---|
| Control (SPP) | `00001101-0000-1000-8000-00805F9B34FB` | KISS (our use) **or** GAIA control frames |
| Audio ("BS AOC") | `39144315-32FA-40DB-85ED-FBFEBA2D86E6` | SBC audio, 0x7e-framed |

Both are mounted the same way we already mount KISS (BlueZ SerialPort profile,
`ConnectProfile(uuid)` → `NewConnection` fd). The audio UUID is already visible in
the radio's `bluetoothctl info` (listed "Vendor specific"). See
`uvprotermbt/audio_link.py` (audio channel) and `uvprotermbt/link.py` (generic
transport, parameterized by UUID).

## Audio channel framing (HDLC-style — `uvprotermbt/audio_frame.py`)

```
0x7e  <command>  <payload…>  0x7e
```
- **`0x7e`** = frame flag (start and end; one `0x7e` closes a frame and opens the
  next). Runs of `0x7e` are empty frames → skipped.
- **`0x7d`** = escape: a literal `0x7d`/`0x7e` in the payload is sent as `0x7d`
  then `byte XOR 0x20`. Un-escape reverses it.
- First un-escaped byte = **command**; the rest = payload.

| Command | Meaning |
|---|---|
| `0x00` / `0x03` | received audio — payload = concatenated SBC frames |
| `0x01` | audio end (RX stream finished) |
| `0x02` | audio ACK |
| `0x09` | transmit-audio echo (our own TX looped back; decode for VU, don't play) |

**Stop-transmit frame** (send verbatim to end a TX):
`7e 01 00 01 00 00 00 00 00 00 7e` (`audio_frame.END_AUDIO_FRAME`).

## SBC format (the radio's exact params — `uvprotermbt/sbc.py`)

32 kHz · 16-bit · **mono** · **blocks 16** · **subbands 8** · allocation
**loudness** · **bitpool 40** · sync byte **`0x9C`**. PCM per SBC frame =
16·8·2 = **256 bytes** (128 samples ≈ 4 ms). Codec = **libsbc** (`libsbc.so.1`);
decode reads params from each frame header, so RX needs no config. Verified:
encode→decode round-trips at these params (`tests/test_sbc.py`).

## GAIA control frames (SPP channel) — PTT / radio control

```
FF 01 <flags> <dataLen> <grp_hi grp_lo> <cmd_hi cmd_lo> <data…>
```
Big-endian; `flags=0x00` = no checksum; `dataLen` = length of `data` only.
- **Groups:** `basic = 2`, `extended = 10`.
- **PTT** = `doProgFunc` (basic cmd **66 / 0x42**) with a `PFActionType` and a
  `PFEffectType`. Effects: `mainPtt = 13`, `toggleRadioTx = 4`. Actions:
  `short=1`, `lowToHigh=6` (press), `highToLow=7` (release). Example key frame:
  `FF 01 00 02  00 02  00 42  <action> <effect>` (exact combo TBD on air).

> Note: audio TX may be **implicit** — HTCommander's engine just streams audio
> frames and sends `END_AUDIO_FRAME` to stop, without an explicit PTT command.
> M2/M3 on-air testing decides whether a GAIA PTT is needed at all.

## Confirmed vs. needs on-air

- **Confirmed from code / bench:** both UUIDs; the 0x7e/0x7d framing + command
  bytes; `END_AUDIO_FRAME`; SBC params (round-trip verified with libsbc); GAIA
  frame layout and group/command/effect values.
- **Needs the radio to confirm:** (1) does opening the audio channel stream RX
  immediately or need an enable command; (2) implicit vs explicit PTT for TX;
  (3) the outgoing TX command byte; (4) KISS + GAIA coexistence on the SPP channel.

## Build status (branch `sstv-audio`)

- **M0 done:** this doc; `audio_frame.py` (+ tests), `sbc.py` (+ tests),
  `audio_link.py`; `link.py` generalized to any RFCOMM UUID.
- **M1 tool:** `python -m uvprotermbt.audio_capture --seconds 30` — opens the
  audio channel, decodes to `uvpro-audio.wav` (+ `.sbc`) and prints stats. This
  is the make-or-break "do we get real audio off the channel" test.
- **Next:** M2 SSTV-RX → M3 PTT/TX → M4 SSTV-TX → M5 SSTV tab. Master stays on
  v0.9.0 until M5 is proven on air.
