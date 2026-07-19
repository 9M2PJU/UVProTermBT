# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for UVProTermBT (onedir).
#
# Build:
#   pyinstaller packaging/uvprotermbt.spec --noconfirm --clean
#
# Output: dist/uvprotermbt/  (a folder — onedir, NOT onefile. onefile is slow
# to start and PyQt6-WebEngine has known issues unpacking its helper process
# from a onefile bundle.)
#
# What's bundled: PyQt6 + PyQt6-WebEngine (Chromium), pysstv, colaclanth/sstv
# (numpy/scipy/soundfile), PIL, the app's own modules, and the icon resource.
#
# What's NOT bundled (deliberately — see packaging/AppRun and the runtime shim
# in uvprotermbt/__main__.py:_add_system_dist_packages):
#   - dbus / gi (PyGObject): system packages tied to the host's BlueZ/libdbus
#     ABI. Bundling them means dragging in .typelib files and hoping the host's
#     libgobject matches — fragile across distros. Instead the frozen app adds
#     the host's dist-packages to sys.path at startup and imports them from
#     there. The .deb/.rpm declare them as Depends/Requires; AppRun checks.
#   - libsbc: loaded via ctypes.util.find_library("sbc") at runtime from the
#     host. Declared as Depends/Requires.
#
# Hidden imports: things PyInstaller's static analysis can't see because they're
# imported lazily (inside try/except, behind feature flags, or via __import__).

from PyInstaller.building.api import PYZ, EXE, COLLECT
from PyInstaller.building.build_main import Analysis
import os

# SPECPATH is the spec file's directory (packaging/). The project root is one
# level up — resolve all source paths relative to that so the spec works
# regardless of the CWD PyInstaller was invoked from.
_ROOT = os.path.dirname(os.path.abspath(SPECPATH))

# Resources: the app icon (referenced by gui/main_window.py:ICON_PATH and the
# desktop entry). Keep the package-relative path so ICON_PATH still resolves.
datas = [
    (os.path.join(_ROOT, "uvprotermbt/gui/resources/icon.png"),
     "uvprotermbt/gui/resources"),
]

hiddenimports = [
    # PyQt6-WebEngine is imported lazily in gui/pat_panel.py (only when the
    # Winlink tab is built), so PyInstaller won't see it by default.
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineQuick",
    # pysstv loads its mode classes dynamically via MODES lists in submodules;
    # make sure both submodules are collected (pysstv.color + pysstv.grayscale).
    "pysstv.color",
    "pysstv.grayscale",
    # colaclanth/sstv (optional, may be absent — Analysis tolerates missing
    # hiddenimports if the module isn't installed; the app guards with
    # DECODE_AVAILABLE).
    "sstv",
    "sstv.common",
    "sstv.decode",
    "sstv.spec",
    # PIL.ImageOps is imported inside sstv.fit_image(); PIL itself is pulled in
    # by pysstv, but the ImageOps submodule needs an explicit nudge.
    "PIL.ImageOps",
]

# Keep system-tied packages OUT of the bundle — they must come from the host
# (see the spec header comment and __main__.py:_add_system_dist_packages).
excludes = [
    "dbus",
    "gi",
    "gi.repository",
    # Test/dev only — no reason to ship.
    "pytest",
    "_pytest",
]

a = Analysis(
    [os.path.join(_ROOT, "packaging/entry.py")],
    pathex=[_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="uvprotermbt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # GUI app — no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(_ROOT, "uvprotermbt/gui/resources/icon.png") if os.path.exists(
        os.path.join(_ROOT, "uvprotermbt/gui/resources/icon.png")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="uvprotermbt",
)
