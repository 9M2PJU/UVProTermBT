# Winlink via PAT — using UVProTermBT as the KISS-over-TCP bridge

The UV-Pro's KISS TNC is only reachable over Bluetooth through BlueZ's
SerialPort profile — so the usual Winlink recipe (`kissattach /dev/rfcomm0`)
**does not work** with this radio. UVProTermBT solves that by re-serving the
radio's KISS stream on a **local TCP port**, so [PAT](https://getpat.io/) can
drive the UV-Pro through it.

We do **no** Winlink protocol ourselves — PAT does all of it (AX.25 + B2F). We
just bridge the bytes.

## What you need

- **PAT with built-in AX.25** — the **pat-gensio** build (PAT's own AX.25 stack
  over `gensio`). Grab it from the pat-users group / releases. (Mainline PAT's
  kernel-AX.25 path needs a serial device and won't see our TCP KISS directly
  without extra glue; pat-gensio talks KISS-over-TCP natively.)
- UVProTermBT connected to your radio (● BT green).

## Steps

1. In UVProTermBT, go to the **Winlink** tab and click **Start Winlink Bridge**.
   It listens on `127.0.0.1:8001` and shows the config string:
   `kiss,tcp,127.0.0.1,8001`.
   While the bridge runs, **PAT drives the radio** and UVProTermBT's own
   transmit is paused (one radio, one master).

2. Configure PAT (pat-gensio) to use that KISS-TCP endpoint. In your Pat config
   the AX.25/gensio connection gensio is:
   ```
   kiss,tcp,localhost,8001
   ```
   (Set your callsign in Pat too.) See the pat-gensio docs for exactly where the
   gensio string goes in your `config.json` / the `gax25` transport.

3. Start Pat's web UI and connect to an RMS:
   ```
   pat http
   ```
   Open the browser it points to, pick your RMS gateway, and connect. Pat runs
   the AX.25 session + Winlink B2F over our bridge; you'll see the RF exchange.

4. When done, **Stop Winlink Bridge** in UVProTermBT to hand the radio back to
   Chat/APRS/BBS.

## Notes & troubleshooting

- **Port already in use:** the Winlink tab will say so. Another program (or a
  leftover bridge) has `8001`. Close it and try again.
- **PAT can't connect to the port:** make sure the bridge shows "listening" and
  that Pat's gensio host/port match (`localhost` / `8001`).
- **Slow transfers / retries:** connected-mode over 1200-baud packet is slow by
  nature, and channel contention (beacons) hurts. Pat's AX.25 handles the
  retries; keep the frequency quiet.
- **Speed:** because Pat's own (mature) AX.25 stack runs the link — not our
  simple stop-and-wait — larger B2F transfers are handled well.
