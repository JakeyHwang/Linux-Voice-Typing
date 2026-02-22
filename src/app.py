"""
Main application: audio -> STT -> voice commands / text injection, bar UI, settings.
"""
from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from src.audio import capture_loop, list_input_devices
from src.config import load, save, get_model_dir
from src.injection import copy_to_clipboard, get_injection_method, type_text
from src.stt.vosk_engine import load_model as load_vosk, recognize_stream as recognize_vosk
from src.stt.faster_whisper_engine import load_model as load_whisper, recognize_stream as recognize_whisper
from src import single_instance
from src.ui.bar import TranscriptionBar
from src.ui.settings import SettingsWindow
from src.voice_commands import is_sleep_command, is_wake_command, strip_voice_command_from_text

logger = logging.getLogger(__name__)


class VoiceTypingApp(QObject):
    """Orchestrates mic capture, STT (Vosk or Whisper), voice commands, injection, and UI."""

    def __init__(self) -> None:
        super().__init__()
        self._settings = load()
        self._audio_queue: queue.Queue[Optional[bytes]] = queue.Queue(maxsize=120)
        self._result_queue: queue.Queue[tuple[str, bool]] = queue.Queue()
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._model = None
        self._stt_engine: Optional[str] = None  # "vosk" | "whisper"
        self._bar: Optional[TranscriptionBar] = None
        self._injection_method: Optional[str] = None

        # State: True = listening (inject text), False = sleep (only react to wake)
        self._awake = True
        # For chunked typing: prefix we've already typed this utterance (so we don't wait for final)
        self._typed_so_far = ""

    def _ensure_model(self) -> bool:
        """Load STT model (Vosk or Whisper) from settings; return True if ready."""
        if self._model is not None:
            return True
        engine = self._settings.get("stt_engine", "vosk")
        self._stt_engine = engine
        if engine == "whisper":
            try:
                size = self._settings.get("whisper_model_size", "base.en")
                logger.info("Loading STT: Whisper %s (this may take a moment on first run)", size)
                self._model = load_whisper(size, device="cpu", compute_type="int8")
                logger.info("STT ready: Whisper %s", size)
                return True
            except Exception as e:
                logger.exception("Failed to load Whisper model: %s", e)
                return False
        # Vosk
        model_name = self._settings.get("vosk_model_name", "vosk-model-small-en-us-0.15")
        model_dir = self._settings.get("model_path") or str(get_model_dir() / model_name)
        path = Path(model_dir)
        if not path.is_dir():
            logger.error("Vosk model not found at %s. Run install script or download a model.", path)
            return False
        try:
            logger.info("Loading STT: Vosk %s", model_name)
            self._model = load_vosk(path)
            logger.info("STT ready: Vosk %s", model_name)
            return True
        except Exception as e:
            logger.exception("Failed to load Vosk model: %s", e)
            return False

    def _audio_thread_fn(self) -> None:
        capture_loop(out_queue=self._audio_queue, stop_event=self._stop_event)

    def _stt_thread_fn(self) -> None:
        def chunk_iter() -> Any:
            while not self._stop_event.is_set():
                try:
                    chunk = self._audio_queue.get(timeout=0.25)
                    if chunk is None:
                        break
                    yield chunk
                except queue.Empty:
                    continue

        if not self._ensure_model():
            return
        recognize = recognize_whisper if self._stt_engine == "whisper" else recognize_vosk
        try:
            for text, is_final in recognize(self._model, chunk_iter()):
                if self._stop_event.is_set():
                    break
                try:
                    self._result_queue.put((text, is_final))
                except queue.Full:
                    pass
        except Exception as e:
            logger.exception("STT thread error: %s", e)
        finally:
            self._result_queue.put(("", True))  # sentinel to avoid blocking

    def _type_chunk(self, chunk: str) -> None:
        """Send a chunk of text to the focused window or clipboard."""
        if not chunk or not self._awake:
            return
        input_method = self._settings.get("input_method", "type")
        if input_method == "clipboard":
            copy_to_clipboard(chunk)
        else:
            type_text(chunk, self._injection_method)

    def _process_result(self, text: str, is_final: bool) -> None:
        """Called from main thread: handle one STT result. Type in chunks of emit_word_limit."""
        sleep_phrases = self._settings.get("sleep_phrases") or [self._settings.get("sleep_phrase", "mute")]
        wake_phrases = self._settings.get("wake_phrases", ["unmute", "un mute", "on unmute", "wake", "wake up", "start listening", "resume", "activate", "activate speech"])
        word_limit = max(1, int(self._settings.get("emit_word_limit", 10)))

        if is_final:
            if is_wake_command(text, wake_phrases):
                self._awake = True
                self._typed_so_far = ""
                if self._bar:
                    self._bar.set_state("listening")
                logger.info("Wake command recognized: %s", text)
                if self._bar:
                    self._bar.set_transcription(text)
                return
            if is_sleep_command(text, sleep_phrases):
                self._awake = False
                self._typed_so_far = ""
                if self._bar:
                    self._bar.set_state("sleep")
                logger.info("Sleep command recognized: %s", text)
                if self._bar:
                    self._bar.set_transcription(text)
                return
            # Final non-command: type any remainder in chunks, then reset
            if self._awake and text:
                to_type = strip_voice_command_from_text(text, sleep_phrases, wake_phrases)
                if to_type:
                    typed_prefix = self._typed_so_far.rstrip()
                    if to_type.startswith(typed_prefix) or to_type == typed_prefix:
                        remainder = to_type[len(typed_prefix):].strip()
                        words = remainder.split()
                        while len(words) >= word_limit:
                            chunk = " ".join(words[:word_limit]) + " "
                            self._type_chunk(chunk)
                            self._typed_so_far += chunk
                            words = words[word_limit:]
                        if words:
                            self._type_chunk(" ".join(words) + " ")
                    self._typed_so_far = ""
            if self._bar:
                self._bar.set_transcription(text)
            return

        # Partial: update bar; when asleep, also check for wake command (Vosk often sends short words only as partials)
        if self._bar:
            self._bar.set_transcription(text)
        if not self._awake:
            if text and is_wake_command(text, wake_phrases):
                self._awake = True
                self._typed_so_far = ""
                if self._bar:
                    self._bar.set_state("listening")
                logger.info("Wake command recognized (partial): %s", text)
                return
            # Log when a short transcript didn't match (helps debug e.g. "activate" not recognized)
            if text and len(text) < 30:
                logger.info("Sleep mode: transcript did not match wake command: %r", text)
            return
        if not text:
            return
        typed_prefix = self._typed_so_far.rstrip()
        if not (text.startswith(typed_prefix) or text == typed_prefix):
            self._typed_so_far = ""  # recognizer corrected; avoid double-typing
            typed_prefix = ""
        remainder = text[len(typed_prefix):].strip()
        words = remainder.split()
        while len(words) >= word_limit:
            chunk = " ".join(words[:word_limit]) + " "
            self._type_chunk(chunk)
            self._typed_so_far += chunk
            words = words[word_limit:]

    def _drain_results(self) -> None:
        """Drain STT result queue and process in main thread."""
        while True:
            try:
                item = self._result_queue.get_nowait()
            except queue.Empty:
                break
            text, is_final = item
            if text == "" and is_final:
                continue
            self._process_result(text, is_final)

    def _open_settings(self) -> None:
        def on_apply(new_settings: dict[str, Any]) -> None:
            # If user changed STT engine or model, clear cached model so next run uses it (restart required)
            prev_engine = self._settings.get("stt_engine")
            prev_vosk = self._settings.get("vosk_model_name")
            prev_whisper = self._settings.get("whisper_model_size")
            self._settings = new_settings
            save(new_settings)
            stt_changed = (
                new_settings.get("stt_engine") != prev_engine
                or (prev_engine == "vosk" and new_settings.get("vosk_model_name") != prev_vosk)
                or (prev_engine == "whisper" and new_settings.get("whisper_model_size") != prev_whisper)
            )
            if stt_changed:
                self._model = None
                engine = new_settings.get("stt_engine", "vosk")
                model_name = (
                    new_settings.get("whisper_model_size", "base.en")
                    if engine == "whisper"
                    else new_settings.get("vosk_model_name", "vosk-model-small-en-us-0.15")
                )
                logger.info("STT changed to %s / %s. Restart the app for it to take effect.", engine, model_name)
                QMessageBox.information(
                    None,
                    "Linux Voice Typing",
                    f"STT is now set to {engine} / {model_name}.\n\nRestart the app for the new model to take effect.",
                )
            if self._bar:
                self._bar.set_state("sleep" if not self._awake else "listening")
                self._bar.move_to_edge(bar_width_override=new_settings.get("bar_width", 0))
            listening = new_settings.get("listening", True)
            if not listening:
                self._awake = False
                if self._bar:
                    self._bar.set_state("sleep")

        win = SettingsWindow(self._settings, on_apply, self._bar)
        win.exec()

    def run(self) -> int:
        """Build UI, start threads, run event loop. Returns exit code."""
        if not self._ensure_model():
            engine = self._settings.get("stt_engine", "vosk")
            if engine == "whisper":
                msg = "Whisper model could not be loaded. Install: pip install faster-whisper"
            else:
                msg = "Vosk model not found. Run the install script to download a model."
            QMessageBox.critical(None, "Linux Voice Typing", msg)
            return 1

        self._injection_method = get_injection_method()
        if not self._injection_method and self._settings.get("input_method") == "type":
            logger.warning("Neither xdotool nor ydotool available; type-into-focus will not work.")

        # Bar (fixed height; drag to move)
        self._bar = TranscriptionBar(
            on_click_settings=self._open_settings,
            bar_height=36,
        )
        self._bar.set_state("listening" if self._awake else "sleep")
        self._bar.move_to_edge(bar_width_override=self._settings.get("bar_width", 0))

        # Single-instance: when another launch asks to raise, show and focus the bar (schedule on main thread)
        def do_raise() -> None:
            if self._bar:
                self._bar.show()
                self._bar.raise_()
                self._bar.activateWindow()

        single_instance.set_raise_callback(lambda: QTimer.singleShot(0, do_raise))

        # Timer to drain STT results on main thread
        timer = QTimer(self)
        timer.timeout.connect(self._drain_results)
        timer.start(80)

        # Start threads
        self._stop_event.clear()
        audio_thread = threading.Thread(target=self._audio_thread_fn, daemon=True)
        audio_thread.start()
        self._threads.append(audio_thread)
        stt_thread = threading.Thread(target=self._stt_thread_fn, daemon=True)
        stt_thread.start()
        self._threads.append(stt_thread)

        # Apply initial "listening" setting
        if not self._settings.get("listening", True):
            self._awake = False
            self._bar.set_state("sleep")

        QApplication.instance().aboutToQuit.connect(self.shutdown)
        return QApplication.exec()

    def shutdown(self) -> None:
        """Stop capture and STT threads."""
        self._stop_event.set()
        try:
            self._audio_queue.put(None, block=False)
        except queue.Full:
            pass
        for t in self._threads:
            t.join(timeout=2.0)
