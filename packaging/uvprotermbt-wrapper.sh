#!/bin/sh
# /usr/bin/uvprotermbt — launcher installed by the .deb/.rpm.
#
# The PyInstaller onedir bundle lives in /opt/uvprotermbt/. It does NOT bundle
# dbus/gi (system-tied; see packaging/uvprotermbt.spec), so the frozen app's
# own startup shim adds the host's dist-packages to sys.path. We just exec it.
#
# We also set QTWEBENGINE_DISABLE_SANDBOX=1 (the pip-wheel WebEngine
# chrome-sandbox is usually not setuid-root and crashes the renderer; the
# embedded page is PAT's local UI on localhost — trusted). The app sets this
# too via setdefault, but exporting it here means it's correct even before
# Python starts.
export QTWEBENGINE_DISABLE_SANDBOX=1

# Some Qt platforms need this for the bundled Qt plugins to find their helpers.
APPDIR=/opt/uvprotermbt
exec "$APPDIR/uvprotermbt" "$@"
