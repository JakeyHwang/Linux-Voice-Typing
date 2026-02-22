#!/usr/bin/env python3
"""
Linux Voice Typing — entry point. Run with: python main.py (or python3 main.py).
Use --reset-settings to reset config when the bar is off-screen.
Single-instance: only one process runs; second launch asks the first to raise its window.
"""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from src.app import VoiceTypingApp
from src.config import reset_to_defaults
from src import single_instance

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

    acquired, socket_path = single_instance.try_acquire_lock()
    if not acquired:
        single_instance.request_raise(socket_path)
        return 0
    single_instance.start_raise_listener(socket_path)

    app = QApplication(sys.argv)
    app.setApplicationName("Linux Voice Typing")
    voice_app = VoiceTypingApp()
    return voice_app.run()


if __name__ == "__main__":
    sys.exit(main())
