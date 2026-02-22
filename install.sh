#!/usr/bin/env bash
# Linux Voice Typing — one-command install: deps, venv, Vosk model, optional desktop entry.
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/linux-voice-typing"
MODEL_DIR="$CONFIG_DIR/models"
VENV_DIR="$REPO_DIR/.venv"
MODEL_NAME="vosk-model-small-en-us-0.15"
MODEL_URL="https://alphacephei.com/vosk/models/${MODEL_NAME}.zip"

echo "=== Linux Voice Typing installer ==="
echo "Repo: $REPO_DIR"
echo "Config: $CONFIG_DIR"
echo ""

# Detect distro for system deps
if command -v apt-get &>/dev/null; then
    PKG_CMD="apt-get"
    PKG_INSTALL="sudo apt-get update && sudo apt-get install -y"
elif command -v dnf &>/dev/null; then
    PKG_CMD="dnf"
    PKG_INSTALL="sudo dnf install -y"
elif command -v pacman &>/dev/null; then
    PKG_CMD="pacman"
    PKG_INSTALL="sudo pacman -S --noconfirm --needed"
else
    echo "Unsupported package manager (apt-get, dnf, pacman). Install manually:"
    echo "  - Python 3.9+, pip, venv"
    echo "  - portaudio / libportaudio2"
    echo "  - xdotool (X11) and/or ydotool (Wayland)"
    PKG_INSTALL=""
fi

# System dependencies
echo "Checking system dependencies..."
MISSING=""
command -v python3 &>/dev/null || MISSING="$MISSING python3"
command -v pip3 &>/dev/null || command -v pip &>/dev/null || MISSING="$MISSING pip"
for cmd in xdotool; do
    command -v $cmd &>/dev/null || true
done
# ydotool is optional (Wayland); xdotool for X11
if [ -n "$WAYLAND_DISPLAY" ] || [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    command -v ydotool &>/dev/null || MISSING="$MISSING ydotool"
else
    command -v xdotool &>/dev/null || MISSING="$MISSING xdotool"
fi

if [ -n "$PKG_INSTALL" ] && [ -n "$MISSING" ]; then
    echo "Installing:$MISSING and portaudio..."
    case "$PKG_CMD" in
        apt-get) eval "$PKG_INSTALL python3 python3-pip python3-venv python3-tk libportaudio2 portaudio19-dev xdotool" ;;
        dnf)     eval "$PKG_INSTALL python3 python3-pip portaudio-devel xdotool" ;;
        pacman)  eval "$PKG_INSTALL python python-pip portaudio xdotool" ;;
    esac
    if [ -n "$WAYLAND_DISPLAY" ] || [ "$XDG_SESSION_TYPE" = "wayland" ]; then
        command -v ydotool &>/dev/null || (echo "Install ydotool for Wayland (e.g. sudo apt install ydotool)" && true)
    fi
fi

# Virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
fi
echo "Activating venv and installing Python dependencies..."
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$REPO_DIR/requirements.txt"

# Vosk model
mkdir -p "$MODEL_DIR"
if [ ! -d "$MODEL_DIR/$MODEL_NAME" ]; then
    echo "Downloading Vosk model $MODEL_NAME (one-time, ~40 MB)..."
    TMP_ZIP="$(mktemp)"
    if command -v curl &>/dev/null; then
        curl -sSL -o "$TMP_ZIP" "$MODEL_URL"
    elif command -v wget &>/dev/null; then
        wget -q -O "$TMP_ZIP" "$MODEL_URL"
    else
        echo "Need curl or wget to download the model."
        exit 1
    fi
    (cd "$MODEL_DIR" && unzip -o -q "$TMP_ZIP")
    rm -f "$TMP_ZIP"
    echo "Model installed at $MODEL_DIR/$MODEL_NAME"
else
    echo "Vosk model already present at $MODEL_DIR/$MODEL_NAME"
fi

# Ensure run.sh and launcher are executable
chmod +x "$REPO_DIR/run.sh"
chmod +x "$REPO_DIR/launch-and-log.sh"

# Wrapper in ~/.local/bin so the menu runs one executable from a standard location
BIN_WRAPPER="$HOME/.local/bin/linux-voice-typing"
mkdir -p "$(dirname "$BIN_WRAPPER")"
cat > "$BIN_WRAPPER" << WRAPEOF
#!/bin/bash
exec "$REPO_DIR/launch-and-log.sh"
WRAPEOF
chmod +x "$BIN_WRAPPER"

# Desktop entry: Exec = wrapper in ~/.local/bin (single path, no args)
DESKTOP="$HOME/.local/share/applications/linux-voice-typing.desktop"
mkdir -p "$(dirname "$DESKTOP")"
LOG_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/linux-voice-typing.log"
mkdir -p "$(dirname "$LOG_FILE")"
echo "Install at $(date -Iseconds 2>/dev/null || date)" >> "$LOG_FILE"
cat > "$DESKTOP" << EOF
[Desktop Entry]
Type=Application
Name=Linux Voice Typing
Comment=Self-hosted voice typing — say to type at cursor
Exec=$BIN_WRAPPER
Path=$REPO_DIR
Icon=audio-input-microphone
Terminal=false
Categories=Utility;Accessibility;
StartupNotify=false
EOF
chmod +x "$DESKTOP"
# Refresh menu if possible (ignored if command missing)
command -v update-desktop-database &>/dev/null && update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "Desktop entry written to $DESKTOP"
echo "Wrapper installed to $BIN_WRAPPER"
echo "If the menu entry does not start the app, check: $LOG_FILE"

echo ""
echo "=== Install complete ==="
echo "Run from repo:  $VENV_DIR/bin/python $REPO_DIR/main.py"
echo "Or from menu:   Linux Voice Typing"
echo "Say 'mute' to sleep, 'unmute' to wake. Click the bar to open settings."
echo ""
