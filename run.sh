#!/usr/bin/env bash
# Launch UVProTermBT. First run auto-installs; after that it just starts.
# Non-Python users: double-click this (or run ./run.sh) — nothing else needed.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

if [ ! -x ".venv/bin/python" ]; then
    echo "First-time setup — installing dependencies (this happens once)…"
    echo
    if ! ./install.sh; then
        echo
        echo "Setup failed. Please run ./install.sh manually and check the errors above." >&2
        # keep the window open if double-clicked from a file manager
        read -rp "Press Enter to close…" _ 2>/dev/null || true
        exit 1
    fi
    echo
fi

exec .venv/bin/python -m uvprotermbt "$@"
