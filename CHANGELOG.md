# Changelog

All notable changes to UVProTermBT are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) for the
release tags (note: the in-app `__version__` is a "0.x.y" beta series and may
move more freely than SemVer would strictly require during the 0.x line).

## [Unreleased]

### Added
- **Packaging**: `.deb`, `.rpm`, `.AppImage` builds for **amd64 and arm64**,
  produced by `packaging/build.sh` and the `release.yml` GitHub Actions
  workflow. Native-package build container is `ubuntu:20.04` (glibc 2.31)
  for broad distro compatibility; arm64 uses native `ubuntu-24.04-arm`
  runners (no QEMU). Packaging by **9M2PJU**.
- `pyproject.toml` (PEP 517 metadata, entry point `uvprotermbt`). The package
  is now pip-installable as a real package, not just clone-and-run.
- PyInstaller spec (`packaging/uvprotermbt.spec`, onedir) bundling PyQt6 +
  WebEngine, pysstv, colaclanth/sstv, PIL, and the app. System-tied `dbus`/
  `gi` are deliberately excluded; the frozen app's new
  `_add_system_dist_packages()` shim imports them from the host at runtime.
- `packaging/uvprotermbt.desktop` (with `Keywords=`, `StartupWMClass`,
  `Categories=Network;HamRadio;Qt;`), hicolor icons (48/128/256), a manpage
  (`packaging/uvprotermbt.1`), `postinst`/`prerm` maintainer scripts, and an
  `AppRun` that checks for the host `dbus`/`gi`/`libsbc` and prints
  distro-correct install hints if missing.
- `.github/workflows/ci.yml` — pytest on push/PR, both amd64 and arm64.
- `.github/workflows/release.yml` — on `v*` tags, builds 6 artifacts and
  attaches them to a GitHub Release with auto-generated notes.
- `scripts/distro.sh` — shared distro-detection (apt/dnf/pacman/zypper) with a
  logical-name → distro-package mapping. `install.sh` and `preflight.sh` now
  work on Debian/Ubuntu, Fedora/RHEL, Arch, and openSUSE instead of being
  apt-only.
- `CHANGELOG.md` (this file).
- `ruff` config in `pyproject.toml` for consistent style across modules.

### Changed
- `requirements.txt` is now **exact-pinned** (`PyQt6==6.8.1`,
  `PyQt6-WebEngine==6.8.1`, `pysstv==0.5.8`, `pytest==8.4.2`). PyQt6 and
  PyQt6-WebEngine MUST share the same Qt major.minor — floating them
  independently is a known source of ABI crashes. Bump together, deliberately.
- `install.sh` and `scripts/preflight.sh` are now distro-portable via
  `scripts/distro.sh`. The preflight header now shows the detected
  distro/package-manager and prints the correct install command per missing
  dependency.
- `LOG.txt` (the 61 KB dev journal) moved to `docs/dev/LOG.txt` — it was noise
  in the repo root for users; it lives with the other dev docs now.

### Fixed
- `preflight.sh` no longer tells Fedora/Arch/openSUSE users to "run apt
  install" — it prints the distro-correct command for each missing dep.

## [0.9.5] — 2026-07-19

### Added
- **SSTV tab** — send and receive images over the radio's Bluetooth audio
  channel. Robot36 and more; TX via `pysstv`, RX via `colaclanth/sstv`.
  Reverse-engineered from HTCommander; see `docs/GAIA_AUDIO_SSTV.md`.
  - Split into Receive / Transmit sub-tabs; RX mode auto-detected from the
    VIS header.
  - Auto-fit image to the chosen mode's dimensions before encoding.
  - Received images save to `~/.local/share/uvprotermbt/sstv/`.
- Two RFCOMM channels in parallel: KISS on the SPP UUID, SBC audio on the
  vendor "BS AOC" UUID. `link.py` generalized to any RFCOMM UUID; new
  `audio_link.py`, `audio_frame.py`, `audio_capture.py`, `audio_tx.py`,
  `sbc.py`, `gaia.py`/`gaia_probe.py`.
- `link.send()` now handles `EAGAIN`/partial writes (required for audio
  streaming, not just tiny KISS frames).
- README screenshots (Chat / BBS / Winlink / SSTV / APRS-via-direwolf).
- Documented supported SSTV modes (TX offers 17, RX decodes 7, the overlap is
  Robot36 + Martin M1/M2 + Scottie S1/S2/DX).

### Fixed
- SBC allocation must be Loudness (0x00), not SNR — `sbc.py` had the libsbc
  constant backwards; the radio rejected `9c 73…` frames (wants `9c 71…`).
- Audio frames must be small (~4 SBC frames / ~352 B), like HTCommander —
  we were sending 50-SBC-frame (~4400 B) frames the radio ignored.
- `link.py`: connect our SPP profile specifically via
  `Device1.ConnectProfile(SPP_UUID)`, not the blanket `Device1.Connect()` —
  the latter no-ops when the device is already ACL-connected via the
  Handsfree/Audio-Gateway profile (the "KDE shows connected, app sits at ○ BT"
  wedge).

## [0.9.0] — 2026-07-16

### Added
- Winlink via PAT: a KISS-over-TCP bridge (`kiss_tcp.py`) re-serves the
  radio's KISS stream; PAT does the AX.25 + Winlink B2F. App TX is paused
  while bridging.
- Embedded PAT web UI in the Winlink tab (`gui/pat_panel.py`,
  QWebEngineView). Falls back to opening PAT in the system browser if
  PyQt6-WebEngine isn't loadable.
- One-click Winlink Bridge: `pty_bridge.py` + `kissattach` automated via
  `pkexec` (with a PolicyKit password prompt).
- `install.sh` installs `ax25-tools`/`ax25-apps`/`libax25` upfront so Winlink
  is ready without a later prompt.
- `scripts/preflight.sh` ("doctor") — read-only check of everything the app
  and Winlink rely on.
- `--version` / `-V` flag and an About dialog.
- GPL-3.0 license file.

### Fixed
- `__main__.py` startup shims for the PyQt6-WebEngine split-install problem
  (Qt6/lib on `LD_LIBRARY_PATH`, `QTWEBENGINEPROCESS_PATH` located,
  `AA_ShareOpenGLContexts` set before `QApplication`, Chromium sandbox
  disabled).
- Clean shutdown when closing the window mid-`pkexec`.

## Earlier phases

The full development narrative (Phases 1–7, KISS codec → RFCOMM link →
AX.25 → APRS → connected-mode BBS → PyQt6 GUI → settings/polish) is in
[`docs/dev/LOG.txt`](docs/dev/LOG.txt). Headline milestones:

- **Phase 2 (2026-07-14):** first live end-to-end AX.25 decode through the
  rewritten `RfcommKissLink` — real Mic-E beacons decoded. The key finding:
  the radio only serves KISS through its SerialPort *profile* (UUID 0x1101),
  reached via BlueZ's `org.bluez.Profile1`, NOT a raw socket. See
  `docs/PROTOCOL.md §3`.
- **Phase 3 (2026-07-14):** AX.25 UI frame encoder validated on-air via
  direwolf.
- **Phase 5:** AX.25 connected-mode state machine (`ax25_conn.py`,
  stop-and-wait, window k=1) wired into the BBS tab; `/connect`, stream,
  `/bye` verified end-to-end headlessly.
