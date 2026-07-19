#!/usr/bin/env bash
# Shared distro-detection helpers for install.sh and preflight.sh.
# Sourced, not executed. Provides:
#   distro_detect         — sets PKMGR + DISTRO variables
#   distro_install <pkg…> — install system packages via the detected pkgr
#   distro_have <cmd>     — 0 if the given command is available, 1 otherwise
#
# The package-name mapping (apt/dnf/pacman/zypper) for each dep is kept here so
# install.sh and preflight.sh never go out of sync about what a distro calls
# "the BlueZ D-Bus bindings" or "the SBC codec".

distro_detect() {
    if command -v apt >/dev/null 2>&1; then
        PKMGR=apt; DISTRO=debian
    elif command -v dnf >/dev/null 2>&1; then
        PKMGR=dnf; DISTRO=fedora
    elif command -v pacman >/dev/null 2>&1; then
        PKMGR=pacman; DISTRO=arch
    elif command -v zypper >/dev/null 2>&1; then
        PKMGR=zypper; DISTRO=suse
    else
        PKMGR=unknown; DISTRO=unknown
    fi
}

# distro_pkg <logical name> — echo the distro-specific package name.
# Logical names: dbus, gi, venv, ax25-tools, ax25-apps, libax25, sbc, sndfile,
#                polkit
distro_pkg() {
    case "$1" in
        dbus)        case "$PKMGR" in apt) echo python3-dbus;; dnf) echo python3-dbus;; pacman) echo python-dbus;; zypper) echo python3-dbus;; esac ;;
        gi)          case "$PKMGR" in apt) echo python3-gi;; dnf) echo python3-gi;; pacman) echo python-gobject;; zypper) echo python3-gi;; esac ;;
        venv)        case "$PKMGR" in apt) echo python3-venv;; dnf) echo python3-devel;; pacman) echo python-virtualenv;; zypper) echo python3-virtualenv;; esac ;;
        ax25-tools)  case "$PKMGR" in apt) echo ax25-tools;; dnf) echo ax25-tools;; pacman) echo ax25-tools;; zypper) echo ax25-tools;; esac ;;
        ax25-apps)   case "$PKMGR" in apt) echo ax25-apps;; dnf) echo ax25-apps;; pacman) echo ax25-apps;; zypper) echo ax25-apps;; esac ;;
        libax25)     case "$PKMGR" in apt) echo libax25;; dnf) echo libax25;; pacman) echo libax25;; zypper) echo libax25;; esac ;;
        sbc)         case "$PKMGR" in apt) echo libsbc1;; dnf) echo libsbc1;; pacman) echo sbc;; zypper) echo libsbc1;; esac ;;
        sndfile)     case "$PKMGR" in apt) echo libsndfile1;; dnf) echo libsndfile1;; pacman) echo libsndfile;; zypper) echo libsndfile1;; esac ;;
        polkit)      case "$PKMGR" in apt) echo policykit-1;; dnf) echo polkit;; pacman) echo polkit;; zypper) echo polkit;; esac ;;
        *) echo "" ;;
    esac
}

# distro_install <logical-name…> — resolve names + install via the detected
# package manager. Skips names that resolve to "" (e.g. a distro that rolls
# libax25 into ax25-tools). Prints a clear message if the pkgr is unknown.
distro_install() {
    if [ "$PKMGR" = "unknown" ]; then
        echo "!! Unknown package manager. Install these manually, then re-run:" >&2
        for name in "$@"; do echo "      - $name" >&2; done
        return 1
    fi
    local pkgs=()
    for name in "$@"; do
        local p
        p="$(distro_pkg "$name")"
        [ -n "$p" ] && pkgs+=("$p")
    done
    if [ ${#pkgs[@]} -eq 0 ]; then
        echo "(no packages to install for this distro)"
        return 0
    fi
    echo "==> Installing via $PKMGR: ${pkgs[*]}"
    case "$PKMGR" in
        apt)    sudo apt-get update && sudo apt-get install -y "${pkgs[@]}" ;;
        dnf)    sudo dnf install -y "${pkgs[@]}" ;;
        pacman) sudo pacman -S --needed --noconfirm "${pkgs[@]}" ;;
        zypper) sudo zypper install -y "${pkgs[@]}" ;;
    esac
}
