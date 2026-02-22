"""
Whisper (faster-whisper) STT: buffers 16 kHz mono chunks into segments, transcribes each, yields (text, is_final).
No true streaming partials; each segment yields one (text, True). Better accuracy than Vosk, more CPU.
"""
from __future__ import annotations

import logging
from typing import Any, Iterator

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
# Segment length in seconds before we run transcription (balance latency vs accuracy)
SEGMENT_SEC = 2.0
SEGMENT_BYTES = int(SAMPLE_RATE * SEGMENT_SEC * 2)  # 16-bit = 2 bytes per sample


def load_model(model_size: str, device: str = "cpu", compute_type: str = "int8") -> Any:
    """Load faster-whisper model by size (e.g. tiny.en, base.en)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError("Install faster-whisper: pip install faster-whisper") from None
    logger.info("Loading Whisper model %s (device=%s, compute_type=%s)", model_size, device, compute_type)
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def _bytes_to_float32(chunk: bytes) -> np.ndarray:
    """Convert raw PCM int16 bytes to float32 in [-1, 1]."""
    data = np.frombuffer(chunk, dtype=np.int16)
    return data.astype(np.float32) / 32768.0


def recognize_stream(
    model: Any,
    audio_chunks: Iterator[bytes],
) -> Iterator[tuple[str, bool]]:
    """
    Buffer chunks into SEGMENT_SEC-second segments, transcribe each, yield (text, True).
    Consumes raw PCM 16 kHz mono int16 bytes. Yields one (text, True) per segment (no partials).
    """
    buffer = bytearray()
    for chunk in audio_chunks:
        if chunk is None or len(chunk) == 0:
            continue
        buffer.extend(chunk)
        while len(buffer) >= SEGMENT_BYTES:
            segment_bytes = bytes(buffer[:SEGMENT_BYTES])
            del buffer[:SEGMENT_BYTES]
            audio_f32 = _bytes_to_float32(segment_bytes)
            try:
                segments, _ = model.transcribe(audio_f32, language="en", vad_filter=True)
                parts = [s.text.strip() for s in segments if s.text and s.text.strip()]
                text = " ".join(parts).strip()
                if text:
                    yield (text, True)
            except Exception as e:
                logger.debug("Whisper segment failed: %s", e)
    # Flush remainder
    if len(buffer) > SAMPLE_RATE // 2:  # at least 0.5 s
        audio_f32 = _bytes_to_float32(bytes(buffer))
        try:
            segments, _ = model.transcribe(audio_f32, language="en", vad_filter=True)
            parts = [s.text.strip() for s in segments if s.text and s.text.strip()]
            text = " ".join(parts).strip()
            if text:
                yield (text, True)
        except Exception as e:
            logger.debug("Whisper flush failed: %s", e)
