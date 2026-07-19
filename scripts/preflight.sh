#!/usr/bin/env bash
# UVProTermBT preflight / "doctor" — reports the status of everything the app and
# its Winlink integration rely on. READ-ONLY and non-fatal: it never installs or
# changes anything, it just tells you what's present and how to fix what isn't.
#
#   ./scripts/preflight.sh      (or:  ./run.sh --check)
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
missing=0

say_ok()   { printf '  \033[32m\xe2\x9c\x93\033[0m %s\n' "$1"; }
say_bad()  { printf '  \033[31m\xe2\x9c\x97\033[0m %s\n' "$1"; missing=$((missing + 1)); }
say_info() { printf '  \033[33m\xe2\x84\xb9\033[0m %s\n' "$1"; }

echo "UVProTermBT preflight check"
echo
echo "Core (Chat / APRS / BBS):"
if [ -x "$here/.venv/bin/python" ]; then
    if "$here/.venv/bin/python" -c 'import PyQt6.QtWidgets, dbus, gi' 2>/dev/null; then
        say_ok "Python + BlueZ deps (PyQt6, dbus, gi) importable"
    else
        say_bad "Python/BlueZ deps not importable — run ./install.sh"
    fi
    # Mirror the app's startup shim (uvprotermbt/__main__._ensure_qt_lib_path):
    # put PyQt6's Qt6/lib on LD_LIBRARY_PATH so this check reflects what the app
    # actually does, not a bare import that fails on a split install.
    qtlib="$("$here/.venv/bin/python" -c 'import PyQt6, os; print(os.path.join(os.path.dirname(PyQt6.__file__), "Qt6", "lib"))' 2>/dev/null)"
    if LD_LIBRARY_PATH="${qtlib}:${LD_LIBRARY_PATH:-}" "$here/.venv/bin/python" \
            -c 'import PyQt6.QtWebEngineWidgets' 2>/dev/null; then
        say_ok "PyQt6-WebEngine present (Winlink embeds PAT in-window)"
    else
        say_info "PyQt6-WebEngine not loadable — Winlink will open PAT in your browser instead"
    fi
else
    say_bad ".venv not found — run ./install.sh"
fi

echo
echo "Winlink (optional — only needed for the Winlink tab):"
if command -v kissattach >/dev/null 2>&1; then
    say_ok "ax25-tools (kissattach) present"
else
    say_info "ax25-tools not installed — Start Winlink Bridge will offer to install it"
fi
if command -v pkexec >/dev/null 2>&1; then
    say_ok "pkexec present"
else
    say_bad "pkexec missing — install it:  sudo apt install policykit-1"
fi
if pgrep -f 'polkit.*authentication-agent|polkit-kde|polkit-gnome|polkit-mate|lxpolkit|xfce-polkit' >/dev/null 2>&1; then
    say_ok "PolicyKit agent running (the graphical password prompt will appear)"
else
    say_info "No PolicyKit agent detected — the graphical sudo prompt may not show (KDE/GNOME provide one)"
fi
if command -v pat >/dev/null 2>&1; then
    say_ok "PAT present ($(pat version 2>/dev/null | head -1))"
else
    say_bad "PAT not installed — Winlink needs it. Install from https://getpat.io/ (Debian/Ubuntu .deb)"
fi

echo
echo "SSTV (optional — the SSTV tab):"
if [ -x "$here/.venv/bin/python" ] && "$here/.venv/bin/python" -c 'import ctypes.util,sys; sys.exit(0 if ctypes.util.find_library("sbc") else 1)' 2>/dev/null; then
    say_ok "libsbc present (audio codec)"
else
    say_bad "libsbc missing — install:  sudo apt install libsbc1"
fi
if [ -x "$here/.venv/bin/python" ] && "$here/.venv/bin/python" -c 'import pysstv' 2>/dev/null; then
    say_ok "pysstv present (SSTV transmit)"
else
    say_info "pysstv not installed — SSTV transmit unavailable (pip install pysstv)"
fi
if [ -x "$here/.venv/bin/python" ] && "$here/.venv/bin/python" -c 'import sstv.decode' 2>/dev/null; then
    say_ok "SSTV decoder present (receive)"
else
    say_info "SSTV decoder not installed — SSTV receive unavailable (pip install git+https://github.com/colaclanth/sstv.git)"
fi

echo
if [ "$missing" -eq 0 ]; then
    echo "All good."
else
    echo "$missing item(s) need attention (see the marks above)."
    echo "Core Chat/APRS/BBS still work without the Winlink items."
fi
exit 0
