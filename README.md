# Linux Voice Typing

This is for all the people who have dreamed of using linux voice typing but could not find good ones out there.

A self-hosted, always-on voice typing app for Linux that replicates the Windows 11 / Windows 10 **Voice Typing** experience (Win+H): speak and have text typed at the focused cursor, with a minimal UI and full control over settings.

**This repository is public.** Anyone is welcome to use it, fork it, and submit changes to make it work on more setups (e.g. other distros, Wayland compositors, or different desktop environments). See [Contributing](#contributing) below.

---

## System requirements (for smooth operation)

To run the app smoothly:

| Requirement | Notes |
|-------------|--------|
| **Display** | Works on **X11** and **Wayland**. The transcription bar is a normal application window you can drag and position anywhere. |
| **GUI stack** | **PySide6** (Python Qt bindings). |
| **Text input** | **X11:** `xdotool`. **Wayland:** `ydotool`. The install script installs the right one for your session where possible. |
| **Audio** | Microphone; PortAudio/ALSA and PulseAudio or PipeWire (usual on desktop Linux). |
| **Optional** | **Bar width** in Settings (0 = auto) sets the bar’s initial width when the app starts or when you click Apply. Drag the bar to move it. |

Details and environment detection are in [docs/DISPLAY_ENVIRONMENT.md](docs/DISPLAY_ENVIRONMENT.md).

---

## Quick start

```bash
./install.sh
./run.sh
```

Or `.venv/bin/python main.py` if you don't use Conda/Miniconda. If you use Conda and see `GLIBCXX_3.4.32 not found` when loading PortAudio, use **`./run.sh`** (it runs the app without Conda's library path so system libs are used).

Then click the transcription bar to open **Settings**. Say **"mute"** or **"deactivate"** to sleep; say **"unmute"** or **"activate"** (or **"wake"** / **"resume"**) to wake.

**If you need to reset settings:** run `./run.sh --reset-settings`, then start the app again with `./run.sh`. You can also use **Reset to defaults** in the Settings window.

---

## Overview

- **Goal:** Replicate Windows speech-to-text: always listening when active, text inserted at the text cursor, minimal bar showing live transcription, and easy on/off and settings.
- **Self-hosted & offline-capable:** All processing runs on your machine. No cloud APIs. Optional “better accuracy” mode uses a heavier local model; default is a lightweight model for low CPU use.
- **CPU-only friendly:** Designed for users without a GPU; uses lightweight and quantized models.

---

## Feature Summary

| Feature | Description |
|--------|-------------|
| **Always listening (when active)** | Continuously captures microphone and transcribes; no push-to-talk required. |
| **Type into focus** | Injects transcribed text at the current text cursor (X11: xdotool, Wayland: ydotool). Optional clipboard mode. |
| **Transcription bar** | A normal, draggable window showing live transcription. Drag it by the title bar; click the content to open Settings. |
| **Sleep mode** | Say **"mute"** or **"deactivate"** to sleep; **"unmute"** or **"activate"** (or **"wake"** / **"resume"**) to wake. Bar or settings for manual on/off. |
| **Manual on/off** | User can turn listening on/off via tray/bar button or settings. |
| **Settings GUI** | Dedicated settings window: bar width, STT mode, input method (type vs clipboard), emit every N words, etc. |
| **Echo cancellation** | Relies on system PipeWire/PulseAudio echo cancellation (documented); no in-app AEC. |
| **Two STT tiers** | Default: lightweight/offline (e.g. Vosk). Optional: better accuracy (e.g. faster-whisper small, still self-hosted). |

---

## Technical Specification

### Architecture (high level)

1. **Single main process** (or app + tiny daemon):  
   - Captures microphone (PulseAudio/PipeWire).  
   - Runs chosen STT engine (Vosk and/or faster-whisper) locally on CPU.  
   - Shows the narrow bar and settings UI.  
   - Injects text via xdotool (X11) or ydotool (Wayland).

2. **Audio:**  
   - Default mic; system handles echo cancellation (PipeWire/PulseAudio).  
   - Sample rate and chunk size chosen to match STT engines (e.g. 16 kHz for Vosk).

3. **Models:**  
   - Stored locally (bundled or one-time download).  
   - No network required for default (offline) mode.

### STT (Speech-to-Text)

- **Tier 1 – Lightweight / offline:**  
  - Vosk: streaming, CPU-friendly, small per-language models (~50 MB).  
  - Good latency and battery/CPU; accuracy good but not best.

- **Tier 2 – Better accuracy (optional, still self-hosted):**  
  - faster-whisper with small (or medium) model, quantized (e.g. int8) for CPU.  
  - Selectable in settings; no cloud, still local.

### Better STT accuracy (optional)

The default **Vosk small** model is lightweight and good for CPU; accuracy is decent but not best. For **lighter and more accurate** options without changing code:

- **Larger Vosk model (same API):**  
  Download a bigger English model, e.g. [vosk-model-en-us-0.22](https://alphacephei.com/vosk/models) (~1.8 GB), extract into `~/.config/linux-voice-typing/models/vosk-model-en-us-0.22`, then set `vosk_model_name` in settings (or in `~/.config/linux-voice-typing/settings.json`) to `vosk-model-en-us-0.22`. Better accuracy, more RAM/CPU.

- **Whisper.cpp (future):**  
  For best CPU accuracy (e.g. base.en ~92%), a future option is to add a Whisper.cpp backend (C++ binary, no Python STT process). Today you can improve accuracy by using a larger Vosk model as above.

### Text insertion

- **Primary:** Type into focused window (simulate keyboard).  
  - X11: `xdotool`.  
  - Wayland: `ydotool`.  
- **Optional:** Copy to clipboard instead of typing (settings toggle).  
- Session type (X11 vs Wayland) detected at runtime to pick the right tool.

### User interface

- **Transcription bar:**  
  - A **normal application window** with a title bar: you can **drag it** anywhere and resize it like any other window.  
  - Starts at the top of the screen by default; **Bar width** in Settings (0 = auto) sets its initial width. Drag the bar to move it.  
  - Shows current/live transcription and state (listening / sleep). Text is typed in chunks (default 10 words; see Emit every N words in Settings).  
  - Click the bar content to open Settings.

- **Settings window (GUI):**  
  - **Listening:** Master on/off (enable/disable listening).  
  - **Sleep mode:** Toggle or hotkey to enter/exit sleep.  
  - **Bar:** Width (0 = auto). Drag to move.  
  - **Input:** Type-into-focus vs clipboard.  
  - **Emit every N words:** Chunk size (default 10) so text is typed sooner.  
  - **STT:** Mode (lightweight vs better accuracy), language.  
  - **Hotkeys:** Optional global hotkey to toggle listening or sleep (e.g. similar to Win+H).  
  - **Audio:** Microphone device selection if multiple devices.

- **Manual turn-off:**  
  - Via bar button (“Stop listening”) and/or settings “Listening: Off”.  
  - Optional system tray icon: quit app or only stop listening (per design choice).

### Installation (easy install)

- **Mechanism:** One-command install via a **bash script** (e.g. `install.sh` or `install-linux-voice-typing.sh`).  
- **Script responsibilities:**  
  1. Detect distro (e.g. Ubuntu/Debian, Fedora, Arch).  
  2. Install system dependencies: Python 3, pip, PortAudio/ALSA, PulseAudio or PipeWire (usually present), `xdotool` (X11), `ydotool` (Wayland), and any other required libs.  
  3. Create a virtual environment (recommended) or use `--user` and install Python dependencies (Vosk, faster-whisper, PyAudio, GUI stack, etc.).  
  4. Optionally install a desktop entry and/or autostart so the app can be launched from the app menu and, if desired, start at login.  
  5. Print next steps: e.g. “Run `linux-voice-typing` (or the chosen command) to start.”  

- **User experience:**  
  - User downloads repo (or a release tarball) and runs:  
    `./install.sh`  
  - Or:  
    `curl -sSL <url-to-install-script> | bash`  
  - After that, the app runs immediately (e.g. from menu or terminal).  
  - No manual dependency hunting; script should be idempotent where possible.

- **Optional later:**  
  - AppImage or .deb for “double-click” install; the bash script remains the primary, simple path.

---

## Out of scope (for initial version)

- Cloud or third-party STT APIs.  
- In-app echo cancellation (rely on system).  
- GPU-specific optimizations (CPU-first).

---

## Summary

Linux Voice Typing aims to mirror Windows Voice Typing: always-on (when not in sleep), type-into-focus, narrow bar at the top, and a settings GUI for on/off, bar width, STT mode, and input method. Installation is a single bash script; the app is fully self-hosted and works offline with an optional higher-accuracy local model.

---

## Contributing

This repo is **public and open for community improvements.** If you run on a different distro, Wayland compositor, or desktop environment and something doesn’t work (e.g. bar placement, text injection, or STT), you are encouraged to open issues or submit pull requests to make Linux Voice Typing more universal. Ideas: Wayland layer-shell support where available, better defaults for other WMs, packaging (e.g. AppImage, Flatpak), or accessibility and i18n.
