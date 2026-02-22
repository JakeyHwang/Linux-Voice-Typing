"""
Load/save user settings. Stored under ~/.config/linux-voice-typing/.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))) / "linux-voice-typing"
CONFIG_FILE = CONFIG_DIR / "settings.json"

# Default model dir: next to repo or under config
def _default_model_dir() -> str:
    # Prefer same dir as repo for development; else config
    base = Path(__file__).resolve().parent.parent
    if (base / "models").exists():
        return str(base / "models")
    return str(CONFIG_DIR / "models")


DEFAULTS: dict[str, Any] = {
    "bar_width": 0,  # 0 = auto (use screen width); else width in px
    "listening": True,
    "input_method": "type",  # "type" | "clipboard"
    "stt_mode": "vosk",  # "vosk" (lightweight) | "faster_whisper" (future)
    "language": "en",
    "model_path": "",  # empty = auto (use MODEL_DIR)
    "vosk_model_name": "vosk-model-small-en-us-0.15",  # subdir or name for download
    "sleep_phrase": "mute",  # legacy single phrase
    "sleep_phrases": ["mute", "on mute", "go mute", "put on mute", "stop listening", "deactivate", "deactive", "deactivate speech"],
    "wake_phrases": ["unmute", "un mute", "on unmute", "wake", "wake up", "start listening", "resume", "activate", "activate speech"],
    "emit_word_limit": 10,  # type in chunks of N words so text appears sooner (no need to wait for long pause)
}


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict[str, Any]:
    """Load settings from disk; merge with defaults."""
    out = dict(DEFAULTS)
    if not CONFIG_FILE.exists():
        logger.debug("No config file at %s, using defaults", CONFIG_FILE)
        return out
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k not in out:
                continue
            # Merge phrase lists with defaults so new commands (e.g. "activate") are always available
            if k == "wake_phrases" and isinstance(v, list):
                out[k] = list(set(DEFAULTS["wake_phrases"]) | set(v))
            elif k == "sleep_phrases" and isinstance(v, list):
                out[k] = list(set(DEFAULTS["sleep_phrases"]) | set(v))
            else:
                out[k] = v
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to load config: %s", e)
    return out


def save(settings: dict[str, Any]) -> None:
    """Persist settings to disk."""
    _ensure_config_dir()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError as e:
        logger.warning("Failed to save config: %s", e)


def get_model_dir() -> Path:
    """Directory where Vosk (and optional other) models are stored."""
    p = CONFIG_DIR / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def reset_to_defaults() -> None:
    """Overwrite config with defaults. Use when the bar is off-screen or settings are broken."""
    save(DEFAULTS)
    logger.info("Settings reset to defaults")
