#!/usr/bin/env bash
# UVProTermBT installer for Debian/Ubuntu (incl. Kubuntu).
# Installs the system BlueZ D-Bus bindings, creates a venv that can see them,
# installs the Python deps, and adds a desktop launcher.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

echo "==> System packages — needs sudo"
# python3-dbus/gi: BlueZ D-Bus bindings (the radio transport).
# ax25-tools/ax25-apps/libax25: kissattach + friends for the Winlink kernel
#   AX.25 port. Installed upfront so Winlink is ready without a later prompt.
if command -v apt >/dev/null 2>&1; then
    sudo apt update
    # libsbc1 + libsndfile1: SSTV audio codec + decoder audio I/O.
    sudo apt install -y python3-dbus python3-gi python3-venv \
                        ax25-tools ax25-apps libax25 \
                        libsbc1 libsndfile1
else
    echo "!! Not a Debian/Ubuntu system. Install python3-dbus + python3-gi (PyGObject)"
    echo "   and ax25-tools/ax25-apps/libax25 with your package manager, then re-run,"
    echo "   or create the venv manually."
fi

echo "==> Python venv (--system-site-packages so it can see dbus/gi)"
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
# SSTV receive decoder (GitHub-only; best-effort — transmit works without it).
.venv/bin/pip install "git+https://github.com/colaclanth/sstv.git" \
    || echo "!! SSTV decoder install failed — SSTV receive will be unavailable (transmit still works)."

echo "==> Desktop launcher + icon (app menu + Desktop)"
"$here/scripts/install-desktop-entry.sh"

echo
echo "==> Preflight check"
# Report what's present (incl. Winlink extras like PAT that we don't auto-install).
"$here/scripts/preflight.sh" || true

echo
echo "Done. Launch from your app menu (\"UVProTermBT\"), or run:"
echo "    ./run.sh          # start the app"
echo "    ./run.sh --check  # re-run the preflight check any time"
echo
echo "First launch walks you through callsign + radio setup. On the radio,"
echo "enable KISS TNC (Settings -> General Settings -> KISS TNC) and pair it."
echo "Winlink also needs PAT (https://getpat.io/) — see the preflight output above."
