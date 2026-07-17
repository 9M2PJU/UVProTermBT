"""Bluetooth device discovery via BlueZ D-Bus, for the setup wizard / Radio
menu. Kept separate from the link so the UI can enumerate radios without
opening a KISS connection. Import-guarded like link.py so the package still
loads without the D-Bus bindings.
"""

from __future__ import annotations

from dataclasses import dataclass

try:  # pragma: no cover - availability depends on the host
    import dbus

    _DBUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _DBUS_AVAILABLE = False

_BLUEZ = "org.bluez"
_ADAPTER_IFACE = "org.bluez.Adapter1"
_DEVICE_IFACE = "org.bluez.Device1"
# Heuristic: names of the radios this app targets (Benshi family).
_RADIO_HINTS = ("UV-PRO", "UVPRO", "VR-N", "GA-5WB", "GMRS-PRO", "BENSHI")


@dataclass
class BtDevice:
    mac: str
    name: str
    paired: bool

    @property
    def looks_like_radio(self) -> bool:
        n = self.name.upper()
        return any(h in n for h in _RADIO_HINTS)

    def label(self) -> str:
        tag = "  ✓ paired" if self.paired else "  — not paired (will pair on select)"
        return f"{self.name or '(unknown)'}  [{self.mac}]{tag}"


def available() -> bool:
    return _DBUS_AVAILABLE


def _open():
    """A PRIVATE system-bus connection. Never use the shared dbus.SystemBus()
    singleton here: if we create it (with no main loop) before link.py sets up
    its GLib main loop, the link's profile registration fails with 'D-Bus
    connections must be attached to a main loop'. Callers must close() it."""
    return dbus.SystemBus(private=True)


def list_devices() -> list[BtDevice]:
    """Return BlueZ-known devices (paired + previously seen) without starting a
    scan — fast and non-blocking. Radios sort first."""
    if not _DBUS_AVAILABLE:
        return []
    bus = _open()
    try:
        mgr = dbus.Interface(bus.get_object(_BLUEZ, "/"),
                             "org.freedesktop.DBus.ObjectManager")
        out: list[BtDevice] = []
        for _path, ifaces in mgr.GetManagedObjects().items():
            dev = ifaces.get(_DEVICE_IFACE)
            if not dev:
                continue
            out.append(BtDevice(
                mac=str(dev.get("Address", "")),
                name=str(dev.get("Name", dev.get("Alias", ""))),
                paired=bool(dev.get("Paired", False)),
            ))
    finally:
        bus.close()
    out.sort(key=lambda d: (not d.looks_like_radio, not d.paired, d.name.lower()))
    return out


def _adapter_path(bus) -> str | None:
    mgr = dbus.Interface(bus.get_object(_BLUEZ, "/"),
                         "org.freedesktop.DBus.ObjectManager")
    for path, ifaces in mgr.GetManagedObjects().items():
        if _ADAPTER_IFACE in ifaces:
            return path
    return None


def _device_path(bus, mac: str) -> str | None:
    mgr = dbus.Interface(bus.get_object(_BLUEZ, "/"),
                         "org.freedesktop.DBus.ObjectManager")
    for path, ifaces in mgr.GetManagedObjects().items():
        dev = ifaces.get(_DEVICE_IFACE)
        if dev and str(dev.get("Address", "")).upper() == mac.upper():
            return path
    return None


def is_paired(mac: str) -> bool:
    if not _DBUS_AVAILABLE:
        return False
    bus = _open()
    try:
        path = _device_path(bus, mac)
        if path is None:
            return False
        props = dbus.Interface(bus.get_object(_BLUEZ, path),
                               "org.freedesktop.DBus.Properties")
        return bool(props.Get(_DEVICE_IFACE, "Paired"))
    except dbus.DBusException:
        return False
    finally:
        bus.close()


_PAIR_ERRORS = {
    "AuthenticationRejected": "the radio rejected pairing — put it in Pairing "
                              "mode (Settings → Pairing) and try again",
    "AuthenticationTimeout": "pairing timed out — is the radio in Pairing mode?",
    "AuthenticationFailed": "pairing failed — put the radio in Pairing mode and retry",
    "ConnectionAttemptFailed": "couldn't reach the radio — is it on and in range?",
    "NoReply": "the radio didn't respond — put it in Pairing mode and try again",
    "AlreadyExists": "",  # already paired — treat as success
}


def pair(mac: str, timeout: float = 30.0) -> tuple[bool, str]:
    """Pair + trust a radio so the KISS link can authenticate. The radio must
    be in its Pairing mode. Returns (ok, message). Relies on the desktop's
    Bluetooth agent (KDE/GNOME) for the Just-Works confirmation."""
    if not _DBUS_AVAILABLE:
        return False, "Bluetooth D-Bus bindings unavailable"
    bus = _open()
    try:
        path = _device_path(bus, mac)
        if path is None:
            return False, "radio not found — run a scan first"
        props = dbus.Interface(bus.get_object(_BLUEZ, path),
                               "org.freedesktop.DBus.Properties")
        dev = dbus.Interface(bus.get_object(_BLUEZ, path), _DEVICE_IFACE)

        already = False
        try:
            already = bool(props.Get(_DEVICE_IFACE, "Paired"))
        except dbus.DBusException:
            pass
        if not already:
            try:
                dev.Pair(timeout=timeout)
            except dbus.DBusException as e:
                short = e.get_dbus_name().rsplit(".", 1)[-1]
                msg = _PAIR_ERRORS.get(short)
                if msg is None:
                    return False, f"pairing error: {e.get_dbus_name()}"
                if msg:  # "" means AlreadyExists -> fall through as success
                    return False, msg

        # Trust so BlueZ auto-authorizes future connections (no repeat prompts).
        try:
            props.Set(_DEVICE_IFACE, "Trusted", dbus.Boolean(True))
        except dbus.DBusException:
            pass
        return True, "paired"
    finally:
        bus.close()


def set_discovery(on: bool) -> None:
    """Start/stop BlueZ discovery so newly-powered radios show up. Call
    set_discovery(True), wait a few seconds, list_devices(), then
    set_discovery(False). Best-effort; ignores 'already (not) discovering'."""
    if not _DBUS_AVAILABLE:
        return
    bus = _open()
    try:
        path = _adapter_path(bus)
        if path is None:
            return
        adapter = dbus.Interface(bus.get_object(_BLUEZ, path), _ADAPTER_IFACE)
        try:
            adapter.StartDiscovery() if on else adapter.StopDiscovery()
        except dbus.DBusException:
            pass
    finally:
        bus.close()
