#!/usr/bin/env bash
# Launcher for menu/desktop entry: ensures log dir exists, logs startup, runs app.
LOG_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/linux-voice-typing.log"
mkdir -p "$(dirname "$LOG_FILE")"
echo "=== $(date -Iseconds 2>/dev/null || date) launch-and-log.sh started ===" >> "$LOG_FILE"
set -e
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$REPO_DIR/run.sh" "$@" 2>&1 | tee -a "$LOG_FILE"
