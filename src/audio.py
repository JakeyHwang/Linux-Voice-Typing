"""
Microphone capture at 16 kHz mono for Vosk. Uses sounddevice.
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

import sounddevice as sd

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
# Vosk likes chunks of ~0.5s; 8000 samples = 0.5s at 16kHz
CHUNK_SAMPLES = 8000


def capture_loop(
    *,
    out_queue: queue.Queue[bytes],
    stop_event: threading.Event,
    device: int | None = None,
) -> None:
    """Run audio capture in current thread; put raw bytes (int16) into out_queue until stop_event."""
    def callback(indata, frames: int, time_info: object, status: sd.CallbackFlags) -> None:
        if status:
            logger.debug("Audio status: %s", status)
        try:
            # indata may be numpy array or cffi buffer; bytes() works for both
            out_queue.put(bytes(indata), block=False)
        except queue.Full:
            pass

    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=CHUNK_SAMPLES,
            device=device,
            callback=callback,
        ) as stream:
            stop_event.wait()
    except Exception as e:
        logger.exception("Audio capture error: %s", e)
        out_queue.put(None)  # signal error to consumer


def list_input_devices() -> list[tuple[int, str]]:
    """Return list of (index, name) for input devices."""
    devices = sd.query_devices()
    out: list[tuple[int, str]] = []
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            out.append((i, dev["name"]))
    return out
