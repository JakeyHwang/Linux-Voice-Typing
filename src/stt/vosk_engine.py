"""
Vosk streaming STT: consumes raw 16 kHz mono bytes, yields partial and final transcripts.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator

from vosk import KaldiRecognizer, Model

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000


def load_model(model_path: str | Path) -> Model:
    """Load Vosk model from directory."""
    path = Path(model_path)
    if not path.is_dir():
        raise FileNotFoundError(f"Vosk model path is not a directory: {path}")
    logger.info("Loading Vosk model from %s", path)
    return Model(str(path))


def recognize_stream(
    model: Model,
    audio_chunks: Iterator[bytes],
) -> Iterator[tuple[str, bool]]:
    """
    Consume chunks of raw PCM (16 kHz, mono, int16); yield (text, is_final).
    Empty string for partial results that are not yet final.
    """
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(True)

    for chunk in audio_chunks:
        if chunk is None or len(chunk) == 0:
            continue
        if not rec.AcceptWaveform(chunk):
            # Partial result
            partial = rec.PartialResult()
            if partial:
                try:
                    data = json.loads(partial)
                    text = (data.get("partial") or "").strip()
                    if text:
                        yield (text, False)
                except (json.JSONDecodeError, KeyError):
                    pass
            continue
        # Final result
        result = rec.Result()
        if result:
            try:
                data = json.loads(result)
                text = (data.get("text") or "").strip()
                if text:
                    yield (text, True)
            except (json.JSONDecodeError, KeyError):
                pass

    # Flush remaining
    final = rec.FinalResult()
    if final:
        try:
            data = json.loads(final)
            text = (data.get("text") or "").strip()
            if text:
                yield (text, True)
        except (json.JSONDecodeError, KeyError):
            pass
