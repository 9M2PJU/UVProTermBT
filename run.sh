#!/usr/bin/env bash
# Launch UVProTermBT. First run auto-installs; after that it just starts.
# Non-Python users: double-click this (or run ./run.sh) — nothing else needed.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

# `./run.sh --check` runs the preflight/doctor report instead of launching.
if [ "${1:-}" = "--check" ]; then
    exec "$here/scripts/preflight.sh"
fi

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

# After an update (`git pull`), refresh Python deps if requirements.txt changed,
# so a plain `git pull && ./run.sh` picks up anything a new release added.
if [ -x ".venv/bin/python" ] && [ requirements.txt -nt ".venv/.reqs-stamp" ]; then
    echo "Dependencies changed — updating…"
    if .venv/bin/pip install -q -r requirements.txt; then
        touch ".venv/.reqs-stamp"
    else
        echo "  (dependency update failed — launching with existing deps)"
    fi
    echo
fi

exec .venv/bin/python -m uvprotermbt "$@"
