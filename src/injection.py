"""
Inject transcribed text at the focused window (xdotool on X11, ydotool on Wayland)
or copy to clipboard.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def _is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY")) or os.environ.get("XDG_SESSION_TYPE") == "wayland"


def _has_xdotool() -> bool:
    return shutil.which("xdotool") is not None


def _has_ydotool() -> bool:
    return shutil.which("ydotool") is not None


def get_injection_method() -> Optional[str]:
    """Return 'xdotool', 'ydotool', or None if unavailable."""
    if _is_wayland():
        if _has_ydotool():
            return "ydotool"
        logger.warning("Wayland detected but ydotool not found; install ydotool for type-into-focus")
        return None
    if _has_xdotool():
        return "xdotool"
    logger.warning("X11 detected but xdotool not found; install xdotool for type-into-focus")
    return None


def type_text(text: str, method: Optional[str] = None) -> bool:
    """
    Type the given text at the current focus. Escapes special characters for shell.
    Returns True if injection was attempted successfully.
    """
    if not text:
        return True
    method = method or get_injection_method()
    if not method:
        return False

    # Escape for shell: single-quote style (escape ' as '\'')
    escaped = "'" + text.replace("'", "'\\''") + "'"

    if method == "xdotool":
        try:
            subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--", text],
                check=True,
                timeout=5,
                capture_output=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.debug("xdotool type failed: %s", e)
            return False

    if method == "ydotool":
        # ydotool expects stdin by default: echo "text" | ydotool type --file -
        try:
            proc = subprocess.Popen(
                ["ydotool", "type", "--file", "-"],
                stdin=subprocess.PIPE,
                timeout=5,
            )
            proc.communicate(input=text.encode("utf-8"), timeout=5)
            return proc.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
            logger.debug("ydotool type failed: %s", e)
            return False

    return False


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using xclip or xsel (X11) or wl-copy (Wayland)."""
    if not text:
        return True
    if _is_wayland():
        exe = shutil.which("wl-copy")
        if exe:
            try:
                subprocess.run([exe], input=text.encode("utf-8"), check=True, timeout=2, capture_output=True)
                return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass
        return False
    for cmd in ["xclip", "xsel"]:
        exe = shutil.which(cmd)
        if not exe:
            continue
        try:
            if "xclip" in exe:
                subprocess.run([exe, "-selection", "clipboard"], input=text.encode("utf-8"), check=True, timeout=2, capture_output=True)
            else:
                subprocess.run([exe, "--clipboard", "--input"], input=text.encode("utf-8"), check=True, timeout=2, capture_output=True)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    logger.warning("No clipboard tool (wl-copy, xclip, xsel) found")
    return False
