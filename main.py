#!/usr/bin/env python3
"""
Linux Voice Typing — entry point. Run with: python main.py (or python3 main.py).
Use --reset-settings to reset config when the bar is off-screen.
"""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from src.app import VoiceTypingApp
from src.config import reset_to_defaults

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    if "--reset-settings" in sys.argv or "-r" in sys.argv:
        reset_to_defaults()
        print("Settings reset to defaults. Restart the app.")
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName("Linux Voice Typing")
    voice_app = VoiceTypingApp()
    return voice_app.run()


if __name__ == "__main__":
    sys.exit(main())
