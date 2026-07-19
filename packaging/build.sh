#!/usr/bin/env bash
# Build UVProTermBT packages: .deb, .rpm, .AppImage for the current arch.
#
# Usage:
#   packaging/build.sh                # build all 3 formats
#   packaging/build.sh deb            # just .deb
#   packaging/build.sh rpm            # just .rpm
#   packaging/build.sh appimage       # just .AppImage
#   packaging/build.sh bundle         # just the PyInstaller onedir (no package)
#
# Prerequisites (the CI image has these; for local builds install them):
#   python3, python3-venv, python3-dbus, python3-gi  (system, for --system-site-packages)
#   pyinstaller  (pip — installed into the build venv below)
#   fpm          (gem install fpm) — .deb and .rpm packager
#   appimagetool (downloaded on demand by this script if missing)
#   imagemagick  (convert — for resizing the icon to hicolor sizes)
#   gzip         (for the manpage)
#
# Output: dist/uvprotermbt-<version>-<arch>.{deb,rpm,AppImage}
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
cd "$root"

# ---- config ---------------------------------------------------------------
VERSION="$(python3 -c 'import sys; sys.path.insert(0, "."); from uvprotermbt import __version__; print(__version__)')"
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)  DEB_ARCH=amd64;   RPM_ARCH=x86_64;  APPIMG_ARCH=x86_64  ;;
    aarch64) DEB_ARCH=arm64;   RPM_ARCH=aarch64; APPIMG_ARCH=aarch64 ;;
    *)       DEB_ARCH="$ARCH"; RPM_ARCH="$ARCH"; APPIMG_ARCH="$ARCH" ;;
esac

DIST="$root/dist"
BUILD="$root/build/pkg"
VENV="$root/.venv-build"
ICON_SRC="$root/uvprotermbt/gui/resources/icon.png"

# What to build. Default: all three.
TARGETS=()
if [ $# -gt 0 ]; then
    for t in "$@"; do
        case "$t" in
            deb|rpm|appimage|bundle) TARGETS+=("$t") ;;
            all) TARGETS=(deb rpm appimage) ;;
            *) echo "unknown target: $t" >&2; exit 2 ;;
        esac
    done
else
    TARGETS=(deb rpm appimage)
fi

echo "==> UVProTermBT $VERSION on $ARCH ($DEB_ARCH/$RPM_ARCH)"
echo "    targets: ${TARGETS[*]}"

# ---- 1. build venv + install deps ----------------------------------------
ensure_venv() {
    if [ -x "$VENV/bin/python" ] && [ -x "$VENV/bin/pyinstaller" ]; then
        return
    fi
    echo "==> Creating build venv (--system-site-packages for dbus/gi)"
    python3 -m venv --system-site-packages "$VENV"
    "$VENV/bin/pip" install --upgrade pip
    "$VENV/bin/pip" install -r requirements.txt
    "$VENV/bin/pip" install pyinstaller
    # SSTV receive decoder (optional in the app, but bundle it so RX works
    # out of the box in the packaged version).
    "$VENV/bin/pip" install "git+https://github.com/colaclanth/sstv.git" \
        || echo "!! colaclanth/sstv install failed — SSTV receive won't work in the bundle" >&2
}

# ---- 2. run PyInstaller ---------------------------------------------------
build_bundle() {
    echo "==> PyInstaller onedir build"
    rm -rf "$DIST/uvprotermbt"
    "$VENV/bin/pyinstaller" packaging/uvprotermbt.spec --noconfirm --clean \
        --distpath "$DIST" --workpath "$root/build/pyi"
    echo "    bundle: $DIST/uvprotermbt/"
}

# ---- 3. generate hicolor icons + manpage ----------------------------------
prepare_assets() {
    echo "==> Preparing icons + manpage"
    rm -rf "$BUILD"
    mkdir -p "$BUILD/icons/hicolor/48x48/apps" \
             "$BUILD/icons/hicolor/128x128/apps" \
             "$BUILD/icons/hicolor/256x256/apps" \
             "$BUILD/icons/hicolor/scalable/apps" \
             "$BUILD/man/man1" \
             "$BUILD/applications" \
             "$BUILD/bin"

    if command -v convert >/dev/null 2>&1; then
        convert "$ICON_SRC" -resize 48x48  "$BUILD/icons/hicolor/48x48/apps/uvprotermbt.png"
        convert "$ICON_SRC" -resize 128x128 "$BUILD/icons/hicolor/128x128/apps/uvprotermbt.png"
        convert "$ICON_SRC" -resize 256x256 "$BUILD/icons/hicolor/256x256/apps/uvprotermbt.png"
    else
        echo "!! ImageMagick 'convert' missing — copying the 1254px icon to all sizes" >&2
        cp "$ICON_SRC" "$BUILD/icons/hicolor/48x48/apps/uvprotermbt.png"
        cp "$ICON_SRC" "$BUILD/icons/hicolor/128x128/apps/uvprotermbt.png"
        cp "$ICON_SRC" "$BUILD/icons/hicolor/256x256/apps/uvprotermbt.png"
    fi

    # manpage (gzip'd)
    cp packaging/uvprotermbt.1 "$BUILD/man/man1/uvprotermbt.1"
    gzip -9 -f "$BUILD/man/man1/uvprotermbt.1"

    # desktop entry
    cp packaging/uvprotermbt.desktop "$BUILD/applications/uvprotermbt.desktop"

    # /usr/bin wrapper
    cp packaging/uvprotermbt-wrapper.sh "$BUILD/bin/uvprotermbt"
    chmod 755 "$BUILD/bin/uvprotermbt"
}

# ---- 4. .deb via fpm ------------------------------------------------------
build_deb() {
    echo "==> Building .deb"
    # fpm assembles: the PyInstaller onedir -> /opt/uvprotermbt, plus the
    # desktop/icon/man/wrapper assets -> their FHS locations, plus maintainer
    # scripts. Depends pull in the system packages we deliberately didn't bundle.
    fpm --force \
        --input-type dir --output-type deb \
        --name uvprotermbt --version "$VERSION" \
        --architecture "$DEB_ARCH" \
        --maintainer "Greg (KC3SMW) <noreply@chengmania.com>" \
        --description "AX.25 packet messenger + terminal for the BTech UV-Pro / VGC VR-N76 over Bluetooth KISS TNC" \
        --url "https://github.com/9M2PJU/UVProTermBT" \
        --license "GPL-3.0-only" \
        --category net \
        --depends "python3-dbus" \
        --depends "python3-gi" \
        --depends "libsbc1" \
        --depends "libsndfile1" \
        --depends "bluez" \
        --depends "policykit-1" \
        --recommends "ax25-tools" \
        --recommends "ax25-apps" \
        --recommends "libax25-0" \
        --after-install packaging/postinst \
        --before-remove packaging/prerm \
        --deb-compression xz \
        --package "$DIST/uvprotermbt-${VERSION}-${DEB_ARCH}.deb" \
        "$DIST/uvprotermbt/=/opt/uvprotermbt" \
        "$BUILD/bin/uvprotermbt=/usr/bin/uvprotermbt" \
        "$BUILD/applications/uvprotermbt.desktop=/usr/share/applications/uvprotermbt.desktop" \
        "$BUILD/icons/hicolor/48x48/apps/uvprotermbt.png=/usr/share/icons/hicolor/48x48/apps/uvprotermbt.png" \
        "$BUILD/icons/hicolor/128x128/apps/uvprotermbt.png=/usr/share/icons/hicolor/128x128/apps/uvprotermbt.png" \
        "$BUILD/icons/hicolor/256x256/apps/uvprotermbt.png=/usr/share/icons/hicolor/256x256/apps/uvprotermbt.png" \
        "$BUILD/man/man1/uvprotermbt.1.gz=/usr/share/man/man1/uvprotermbt.1.gz" \
        "README.md=/usr/share/doc/uvprotermbt/README.md" \
        "LICENSE=/usr/share/doc/uvprotermbt/LICENSE" \
        "docs/PROTOCOL.md=/usr/share/doc/uvprotermbt/PROTOCOL.md" \
        "docs/GAIA_AUDIO_SSTV.md=/usr/share/doc/uvprotermbt/GAIA_AUDIO_SSTV.md" \
        "docs/UVPRO_N76_KISS_LINUX.md=/usr/share/doc/uvprotermbt/UVPRO_N76_KISS_LINUX.md" \
        "docs/WINLINK_PAT.md=/usr/share/doc/uvprotermbt/WINLINK_PAT.md"
    echo "    -> $DIST/uvprotermbt-${VERSION}-${DEB_ARCH}.deb"
}

# ---- 5. .rpm via fpm ------------------------------------------------------
build_rpm() {
    echo "==> Building .rpm"
    # Same assets as .deb, but RPM-style dependency names. fpm translates most
    # of the layout; we just swap the dependency list for Fedora/RHEL/SUSE names.
    fpm --force \
        --input-type dir --output-type rpm \
        --name uvprotermbt --version "$VERSION" \
        --architecture "$RPM_ARCH" \
        --maintainer "Greg (KC3SMW) <noreply@chengmania.com>" \
        --description "AX.25 packet messenger + terminal for the BTech UV-Pro / VGC VR-N76 over Bluetooth KISS TNC" \
        --url "https://github.com/9M2PJU/UVProTermBT" \
        --license "GPL-3.0-only" \
        --category "Applications/Internet" \
        --depends "python3-dbus" \
        --depends "python3-gi" \
        --depends "libsbc1" \
        --depends "libsndfile1" \
        --depends "bluez" \
        --depends "polkit" \
        --recommends "ax25-tools" \
        --recommends "ax25-apps" \
        --after-install packaging/postinst \
        --before-remove packaging/prerm \
        --rpm-compression xz \
        --package "$DIST/uvprotermbt-${VERSION}-${RPM_ARCH}.rpm" \
        "$DIST/uvprotermbt/=/opt/uvprotermbt" \
        "$BUILD/bin/uvprotermbt=/usr/bin/uvprotermbt" \
        "$BUILD/applications/uvprotermbt.desktop=/usr/share/applications/uvprotermbt.desktop" \
        "$BUILD/icons/hicolor/48x48/apps/uvprotermbt.png=/usr/share/icons/hicolor/48x48/apps/uvprotermbt.png" \
        "$BUILD/icons/hicolor/128x128/apps/uvprotermbt.png=/usr/share/icons/hicolor/128x128/apps/uvprotermbt.png" \
        "$BUILD/icons/hicolor/256x256/apps/uvprotermbt.png=/usr/share/icons/hicolor/256x256/apps/uvprotermbt.png" \
        "$BUILD/man/man1/uvprotermbt.1.gz=/usr/share/man/man1/uvprotermbt.1.gz" \
        "README.md=/usr/share/doc/uvprotermbt/README.md" \
        "LICENSE=/usr/share/doc/uvprotermbt/LICENSE" \
        "docs/PROTOCOL.md=/usr/share/doc/uvprotermbt/PROTOCOL.md" \
        "docs/GAIA_AUDIO_SSTV.md=/usr/share/doc/uvprotermbt/GAIA_AUDIO_SSTV.md" \
        "docs/UVPRO_N76_KISS_LINUX.md=/usr/share/doc/uvprotermbt/UVPRO_N76_KISS_LINUX.md" \
        "docs/WINLINK_PAT.md=/usr/share/doc/uvprotermbt/WINLINK_PAT.md"
    echo "    -> $DIST/uvprotermbt-${VERSION}-${RPM_ARCH}.rpm"
}

# ---- 6. .AppImage ---------------------------------------------------------
build_appimage() {
    echo "==> Building .AppImage"
    # AppDir layout: AppRun at the root, the frozen bundle under usr/bin/,
    # resources under usr/share/. appimagetool packs it into a single file.
    APPDIR="$BUILD/AppDir"
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
             "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
             "$APPDIR/usr/share/doc/uvprotermbt"

    # The PyInstaller onedir tree goes under usr/ (AppImage convention).
    # The frozen binary itself is dist/uvprotermbt/uvprotermbt; move the whole
    # onedir folder so its sibling libs/Qt plugins stay next to it.
    cp -a "$DIST/uvprotermbt/." "$APPDIR/usr/bin/"
    # AppRun expects the binary at usr/bin/uvprotermbt — it's already there
    # (the onedir's top-level executable is named uvprotermbt).

    cp packaging/AppRun "$APPDIR/AppRun"
    chmod 755 "$APPDIR/AppRun"
    cp packaging/uvprotermbt.desktop "$APPDIR/uvprotermbt.desktop"
    # AppImage wants the root .desktop to match the binary name.
    cp "$BUILD/icons/hicolor/256x256/apps/uvprotermbt.png" "$APPDIR/uvprotermbt.png"
    cp "$BUILD/icons/hicolor/256x256/apps/uvprotermbt.png" \
       "$APPDIR/usr/share/icons/hicolor/256x256/apps/uvprotermbt.png"
    cp packaging/uvprotermbt.desktop "$APPDIR/usr/share/applications/uvprotermbt.desktop"
    cp README.md LICENSE docs/PROTOCOL.md docs/GAIA_AUDIO_SSTV.md \
       docs/UVPRO_N76_KISS_LINUX.md docs/WINLINK_PAT.md \
       "$APPDIR/usr/share/doc/uvprotermbt/" 2>/dev/null || true

    # Fetch appimagetool if missing. Pin a known release; don't float.
    AIT="$BUILD/appimagetool"
    if [ ! -x "$AIT" ]; then
        echo "    downloading appimagetool"
        case "$APPIMG_ARCH" in
            x86_64)  AIT_URL="https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage" ;;
            aarch64) AIT_URL="https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-aarch64.AppImage" ;;
            *) echo "!! no appimagetool build for $APPIMG_ARCH" >&2; exit 3 ;;
        esac
        curl -fsSL "$AIT_URL" -o "$AIT"
        chmod 755 "$AIT"
        # appimagetool is itself an AppImage — extract once so it runs in
        # containers without FUSE (CI builds run --appimage-extract-and-run).
        if [ -n "${APPIMAGE_EXTRACT_AND_RUN:-}" ] || ! "$AIT" --version >/dev/null 2>&1; then
            "$AIT" --appimage-extract >/dev/null 2>&1 || true
            AIT="$BUILD/squashfs-root/AppRun"
        fi
    fi

    OUT="$DIST/uvprotermbt-${VERSION}-${APPIMG_ARCH}.AppImage"
    ARCH="$APPIMG_ARCH" "$AIT" "$APPDIR" "$OUT" --no-appstream
    echo "    -> $OUT"
}

# ---- run ------------------------------------------------------------------
need_bundle=0
for t in "${TARGETS[@]}"; do
    case "$t" in deb|rpm|appimage|bundle) need_bundle=1 ;; esac
done
if [ "$need_bundle" -eq 1 ]; then
    ensure_venv
    build_bundle
    prepare_assets
fi
for t in "${TARGETS[@]}"; do
    case "$t" in
        bundle)   echo "==> bundle only — done: $DIST/uvprotermbt/" ;;
        deb)      build_deb ;;
        rpm)      build_rpm ;;
        appimage) build_appimage ;;
    esac
done

echo
echo "==> Done. Artifacts in $DIST/:"
ls -1 "$DIST"/uvprotermbt-* 2>/dev/null || true
