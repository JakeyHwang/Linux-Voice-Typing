"""
Transcription bar: frameless window, draggable by the bar content. Click to open Settings.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

logger = logging.getLogger(__name__)

# If mouse moves less than this between press and release, treat as click (open Settings)
_DRAG_THRESHOLD_PX = 5


class TranscriptionBar(QFrame):
    """Frameless bar window: drag anywhere on the bar to move; click to open Settings."""

    def __init__(
        self,
        on_click_settings: Optional[Callable[[], None]] = None,
        bar_height: int = 36,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._on_click_settings = on_click_settings
        self._bar_height = bar_height
        self._state = "listening"  # "listening" | "sleep"
        self._current_text = ""
        self._drag_start_global: Optional[QPoint] = None
        self._drag_start_frame_pos: Optional[QPoint] = None
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setMinimumHeight(self._bar_height)
        self.setMaximumHeight(self._bar_height)
        # Frameless: no white title bar or min/max/close; drag by content
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setMinimumWidth(280)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet("""
            TranscriptionBar {
                background-color: #2d2d2d;
                border: none;
                border-bottom: 1px solid #1a1a1a;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(12)

        self._state_label = QLabel("Listening")
        self._state_label.setStyleSheet("color: #7fbf7f; font-weight: bold; min-width: 72px;")
        self._state_label.setFont(QFont("Sans", 10))
        layout.addWidget(self._state_label)

        self._text_label = QLabel("")
        self._text_label.setStyleSheet("color: #e0e0e0;")
        self._text_label.setFont(QFont("Sans", 11))
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._text_label.setWordWrap(False)
        layout.addWidget(self._text_label, 1)

        self.setLayout(layout)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_frame_pos = self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_start_global is not None
            and self._drag_start_frame_pos is not None
        ):
            delta = event.globalPosition().toPoint() - self._drag_start_global
            self.move(self._drag_start_frame_pos + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._drag_start_global is not None and self._on_click_settings:
                moved = (event.globalPosition().toPoint() - self._drag_start_global).manhattanLength()
                if moved < _DRAG_THRESHOLD_PX:
                    self._on_click_settings()
            self._drag_start_global = None
            self._drag_start_frame_pos = None
        super().mouseReleaseEvent(event)

    def set_state(self, state: str) -> None:
        """Set state: 'listening' or 'sleep'."""
        self._state = state
        if state == "sleep":
            self._state_label.setText("Sleep")
            self._state_label.setStyleSheet("color: #bf9f7f; font-weight: bold; min-width: 72px;")
        else:
            self._state_label.setText("Listening")
            self._state_label.setStyleSheet("color: #7fbf7f; font-weight: bold; min-width: 72px;")

    def set_transcription(self, text: str) -> None:
        """Update displayed transcription (partial or final)."""
        self._current_text = text
        self._text_label.setText(text or "—")
        self._text_label.setToolTip(text or "No transcription yet")

    def move_to_edge(self, bar_width_override: int = 0) -> None:
        """Set initial position and size; window is draggable so user can move it."""
        screen = QApplication.screenAt(QCursor.pos()) if hasattr(QApplication, "screenAt") else None
        if not screen:
            screen = QApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        screen_w = screen.size().width()
        width = min(bar_width_override, screen_w) if bar_width_override > 0 else min(available.width(), screen_w)
        width = max(320, width)
        x = available.x()
        y = available.y()
        self.resize(width, self._bar_height)
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
