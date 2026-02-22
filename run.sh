#!/usr/bin/env bash
# Run Linux Voice Typing, avoiding Conda/Miniconda library conflicts with
# system PortAudio (e.g. libstdc++.so.6 version mismatch).
# Use: ./run.sh   (from repo root, after ./install.sh)
set -e
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$REPO_DIR/.venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
  echo "Run ./install.sh first to create the virtual environment."
  exit 1
fi
# Avoid Conda's libstdc++ so system PortAudio/JACK load correctly
export LD_LIBRARY_PATH=""
# Force system libstdc++ (venv may use Conda's Python with RPATH to Conda libs)
for lib in /usr/lib/x86_64-linux-gnu/libstdc++.so.6 /usr/lib64/libstdc++.so.6; do
  if [ -f "$lib" ]; then
    export LD_PRELOAD="$lib"
    break
  fi
done
exec "$VENV_PYTHON" "$REPO_DIR/main.py" "$@"
