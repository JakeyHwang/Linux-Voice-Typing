"""
Settings window: listening on/off, bar width, input method, etc.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.config import DEFAULTS, save, VOSK_MODEL_SMALL

logger = logging.getLogger(__name__)

# STT model choices for UI (lighter models only)
VOSK_CHOICES = [
    (VOSK_MODEL_SMALL, "Small (40 MB)"),
]
WHISPER_CHOICES = [
    ("tiny.en", "tiny.en (fastest)"),
    ("base.en", "base.en (balanced)"),
]


class SettingsWindow(QDialog):
    """Settings dialog; reads/writes a settings dict and calls on_apply(settings)."""

    def __init__(
        self,
        settings: dict[str, Any],
        on_apply: Callable[[dict[str, Any]], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._settings = dict(settings)
        self._on_apply = on_apply
        self.setWindowTitle("Linux Voice Typing — Settings")
        self.setMinimumWidth(360)
        self.setup_ui()

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._listening_cb = QCheckBox("Listening (master on/off)")
        self._listening_cb.setChecked(self._settings.get("listening", True))
        form.addRow("", self._listening_cb)

        self._stt_engine = QComboBox()
        self._stt_engine.addItems(["Vosk", "Whisper"])
        self._stt_engine.setCurrentText(
            "Whisper" if self._settings.get("stt_engine") == "whisper" else "Vosk"
        )
        self._stt_engine.setToolTip("Vosk: lightweight, low latency. Whisper: better accuracy, more CPU. Changing STT requires restarting the app.")
        self._stt_engine.currentTextChanged.connect(self._on_stt_engine_changed)
        form.addRow("STT engine", self._stt_engine)

        self._stt_model = QComboBox()
        self._update_stt_model_combo()
        self._stt_model.setToolTip("Vosk Small or Whisper tiny.en/base.en. Restart app after changing.")
        form.addRow("STT model", self._stt_model)

        self._bar_width = QSpinBox()
        self._bar_width.setRange(0, 7680)
        self._bar_width.setValue(self._settings.get("bar_width", 0))
        self._bar_width.setSuffix(" px")
        self._bar_width.setSpecialValueText("Auto")
        self._bar_width.setToolTip("Initial bar width in pixels. 0 = auto. Drag the bar to move it.")
        form.addRow("Bar width", self._bar_width)

        self._input_method = QComboBox()
        self._input_method.addItems(["type", "clipboard"])
        self._input_method.setCurrentText(self._settings.get("input_method", "type"))
        form.addRow("Input method", self._input_method)

        self._emit_word_limit = QSpinBox()
        self._emit_word_limit.setRange(1, 50)
        self._emit_word_limit.setValue(self._settings.get("emit_word_limit", 10))
        self._emit_word_limit.setToolTip("Type in chunks of this many words so text appears sooner (no need to wait for long pause).")
        form.addRow("Emit every N words", self._emit_word_limit)

        layout.addLayout(form)

        hint = QLabel("Voice: say only the command (e.g. \"activate\", \"activate speech\", \"deactivate\", \"mute\"). Extra words = normal speech.")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        reset_btn = QPushButton("Reset to defaults")
        reset_btn.setToolTip("Restore default settings.")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)

        buttons = QHBoxLayout()
        buttons.addStretch()
        quit_btn = QPushButton("Quit app")
        quit_btn.clicked.connect(self._quit_app)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply)
        apply_btn.setDefault(True)
        buttons.addWidget(quit_btn)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(apply_btn)
        layout.addLayout(buttons)

        self.setLayout(layout)

    def _on_stt_engine_changed(self) -> None:
        self._update_stt_model_combo()

    def _update_stt_model_combo(self) -> None:
        engine = "whisper" if self._stt_engine.currentText() == "Whisper" else "vosk"
        self._stt_model.clear()
        if engine == "vosk":
            for value, label in VOSK_CHOICES:
                self._stt_model.addItem(label, value)
            current = self._settings.get("vosk_model_name", VOSK_MODEL_SMALL)
            idx = self._stt_model.findData(current)
            if idx >= 0:
                self._stt_model.setCurrentIndex(idx)
            else:
                self._stt_model.setCurrentIndex(0)
        else:
            for value, label in WHISPER_CHOICES:
                self._stt_model.addItem(label, value)
            current = self._settings.get("whisper_model_size", "base.en")
            idx = self._stt_model.findData(current)
            if idx >= 0:
                self._stt_model.setCurrentIndex(idx)
            else:
                self._stt_model.setCurrentIndex(0)

    def _quit_app(self) -> None:
        self.reject()
        QApplication.instance().quit()

    def _reset_to_defaults(self) -> None:
        """Save defaults and apply so the bar updates."""
        save(DEFAULTS)
        self._settings = dict(DEFAULTS)
        self._listening_cb.setChecked(DEFAULTS.get("listening", True))
        self._stt_engine.setCurrentText("Whisper" if DEFAULTS.get("stt_engine") == "whisper" else "Vosk")
        self._update_stt_model_combo()
        self._bar_width.setValue(DEFAULTS.get("bar_width", 0))
        self._input_method.setCurrentText(DEFAULTS.get("input_method", "type"))
        self._emit_word_limit.setValue(DEFAULTS.get("emit_word_limit", 10))
        self._on_apply(self._settings)

    def _apply(self) -> None:
        self._settings["listening"] = self._listening_cb.isChecked()
        self._settings["stt_engine"] = "whisper" if self._stt_engine.currentText() == "Whisper" else "vosk"
        if self._settings["stt_engine"] == "vosk":
            self._settings["vosk_model_name"] = self._stt_model.currentData()
        else:
            self._settings["whisper_model_size"] = self._stt_model.currentData()
        self._settings["bar_width"] = self._bar_width.value()
        self._settings["input_method"] = self._input_method.currentText()
        self._settings["emit_word_limit"] = self._emit_word_limit.value()
        self._on_apply(self._settings)
        self.accept()
