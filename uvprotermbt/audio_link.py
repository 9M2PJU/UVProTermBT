"""Transport for the UV-Pro's Generic Audio RFCOMM channel.

The radio exposes a second classic-BT RFCOMM service — vendor "BS AOC",
UUID 39144315-32FA-40DB-85ED-FBFEBA2D86E6 — carrying an SBC audio stream, framed
0x7e/0x7d (see uvprotermbt/audio_frame.py). It is independent of the KISS TNC
channel (SPP), so it can be opened *alongside* the packet link — that coexistence
is what makes an in-app SSTV feature possible without disturbing KISS.

This is just RfcommKissLink pointed at the audio UUID: the BlueZ SerialPort-profile
transport is protocol-agnostic (it moves raw bytes; the caller does the framing).
See docs/GAIA_AUDIO_SSTV.md for the full protocol and the SSTV build plan.
"""

from __future__ import annotations

from .link import RfcommKissLink, _DEFAULT_ADAPTER

# Vendor "BS AOC" service that carries the SBC audio stream (from HTCommander's
# BluetoothClassicPlugin.kt). Also visible in the radio's `bluetoothctl info`.
AUDIO_UUID = "39144315-32fa-40db-85ed-fbfeba2d86e6"


class RfcommAudioLink(RfcommKissLink):
    """RFCOMM transport bound to the radio's audio service instead of SPP/KISS.

    Same public API as RfcommKissLink (begin/stop/is_connected/send/on_receive/
    poll); received bytes are the raw 0x7e-framed audio stream — feed them to
    audio_frame.AudioFrameDecoder.
    """

    def __init__(self, address: str, adapter: str = _DEFAULT_ADAPTER) -> None:
        super().__init__(address, uuid=AUDIO_UUID,
                         profile_name="UVProTermBT-Audio", adapter=adapter)
