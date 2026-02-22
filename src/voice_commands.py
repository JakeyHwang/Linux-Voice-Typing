"""
Voice command detection: sleep (mute/deactivate) and wake (unmute/activate) from transcript text.
Commands are only triggered when the user speaks only the command (and nothing else);
if other words are present, it's treated as normal speech, not a command.
"""
from __future__ import annotations

import logging
import re
from typing import Sequence

logger = logging.getLogger(__name__)

# Optional leading/trailing words that don't count as "other words" (e.g. "please activate")
_OPTIONAL_POLITE = frozenset({"please", "ok", "okay", "yes", "hey"})


def normalize_for_command(text: str) -> str:
    """Lowercase, collapse all whitespace, and strip for matching."""
    if not text:
        return ""
    # Normalize unicode/spaces: replace any whitespace with ascii space, then collapse
    s = re.sub(r"\s+", " ", text.replace("\xa0", " ").replace("\r", " ").replace("\n", " "))
    s = " ".join(s.lower().strip().split())
    # Strip leading/trailing punctuation
    return s.strip(".,!?;:")


def _strip_optional_polite(normalized: str) -> str:
    """Remove leading/trailing optional polite words so 'please activate' -> 'activate'."""
    words = normalized.split()
    while words and words[0] in _OPTIONAL_POLITE:
        words = words[1:]
    while words and words[-1] in _OPTIONAL_POLITE:
        words = words[:-1]
    return " ".join(words)


def _is_exact_command(normalized: str, phrases: str | Sequence[str]) -> bool:
    """
    True only if the transcript is exactly one of the phrases (or phrase + optional please/ok).
    If any other words are present, returns False (user is speaking normally, not commanding).
    """
    phrases_list = [phrases] if isinstance(phrases, str) else list(phrases)
    phrase_set = {p.lower().strip() for p in phrases_list if p}
    if not phrase_set:
        return False
    # Exact match
    if normalized in phrase_set:
        return True
    # After stripping optional leading/trailing polite words
    stripped = _strip_optional_polite(normalized)
    return stripped in phrase_set


def is_sleep_command(text: str, sleep_phrases: str | Sequence[str]) -> bool:
    """Return True only if transcript is solely a sleep command (no other words)."""
    if not text:
        return False
    normalized = normalize_for_command(text)
    return _is_exact_command(normalized, sleep_phrases)


def is_wake_command(text: str, wake_phrases: Sequence[str]) -> bool:
    """Return True only if transcript is solely a wake command (no other words)."""
    if not text:
        return False
    normalized = normalize_for_command(text)
    return _is_exact_command(normalized, wake_phrases)


def strip_voice_command_from_text(
    text: str,
    sleep_phrases: str | Sequence[str],
    wake_phrases: Sequence[str],
) -> str:
    """
    If the utterance is only a sleep or wake command (exact match), return empty string
    so we don't type it. Otherwise return original text.
    """
    if not text:
        return text
    normalized = normalize_for_command(text)
    stripped = _strip_optional_polite(normalized)
    phrases = [sleep_phrases] if isinstance(sleep_phrases, str) else list(sleep_phrases)
    all_commands = {p.lower().strip() for p in phrases + list(wake_phrases) if p}
    if normalized in all_commands or stripped in all_commands:
        return ""
    return text
