#!/usr/bin/env bash
# Install the UVProTermBT launcher into the application menu AND onto the Desktop
# as a clickable icon. Safe to re-run. Called by install.sh; can also be run on
# its own:  ./scripts/install-desktop-entry.sh
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
chmod +x "$here/run.sh"

tmp="$(mktemp)"
cat > "$tmp" <<DESKTOP
[Desktop Entry]
Type=Application
Name=UVProTermBT
Comment=AX.25 packet messenger + terminal for the UV-Pro over Bluetooth KISS TNC
Exec=$here/run.sh
Path=$here
Icon=$here/uvprotermbt/gui/resources/icon.png
Terminal=false
Categories=Network;HamRadio;
DESKTOP

# 1) Application-menu entry.
apps="$HOME/.local/share/applications"
mkdir -p "$apps"
install -m 755 "$tmp" "$apps/uvprotermbt.desktop"
update-desktop-database "$apps" >/dev/null 2>&1 || true
echo "App-menu entry:  $apps/uvprotermbt.desktop"

# 2) Desktop icon. It must be executable to launch; GNOME/Nautilus also wants a
#    "trusted" flag (gio); KDE reads the executable bit. First double-click may
#    still ask you to confirm — that's normal for launchers.
desktop_dir="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$desktop_dir" ]; then
    install -m 755 "$tmp" "$desktop_dir/uvprotermbt.desktop"
    gio set "$desktop_dir/uvprotermbt.desktop" metadata::trusted true 2>/dev/null || true
    echo "Desktop icon:    $desktop_dir/uvprotermbt.desktop"
else
    echo "(No Desktop folder at $desktop_dir — skipped the desktop icon.)"
fi

rm -f "$tmp"
