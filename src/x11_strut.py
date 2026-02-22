"""
X11: set window type to DOCK and struts so the window manager reserves space for our bar.
Other app windows are then pushed into the remaining area (not drawn under the bar).
Uses Qt's X11 display when available (PySide6) so the WM sees struts on the same connection.
Only used on X11; no-op on Wayland.
"""
from __future__ import annotations

import logging
import os
import sys
from ctypes import CDLL, byref, c_ulong, cast, create_string_buffer, c_void_p
from ctypes.util import find_library
from typing import Optional

logger = logging.getLogger(__name__)


def is_wayland() -> bool:
    """True if session is Wayland (struts/work-area shrink not supported)."""
    return bool(os.environ.get("WAYLAND_DISPLAY")) or os.environ.get("XDG_SESSION_TYPE") == "wayland"


# Only try on Linux and when not Wayland
if sys.platform != "linux":
    _X11_AVAILABLE = False
else:
    _X11_AVAILABLE = bool(os.environ.get("DISPLAY")) and not is_wayland()

XA_ATOM = 4
XA_CARDINAL = 6
PropModeReplace = 0


def get_qt_x11_display() -> Optional[c_void_p]:
    """
    Return Qt's X11 Display pointer for use with Xlib, or None.
    Requires PySide6 and a running QGuiApplication on X11; used so struts are set
    on the same connection that created the bar window (WM then honors them).
    """
    if not _X11_AVAILABLE:
        return None
    try:
        from PySide6.QtGui import QGuiApplication, QNativeInterface

        # QX11Application is under QNativeInterface in PySide6
        QX11Application = getattr(QNativeInterface, "QX11Application", None)
        if QX11Application is None:
            return None
        app = QGuiApplication.instance()
        if not app:
            return None
        ni = app.nativeInterface(QX11Application)
        if not ni:
            return None
        d = ni.display()
        if d is None:
            return None
        return c_void_p(d)
    except Exception:
        return None


def set_strut_partial(
    win_id: int,
    position: str,
    bar_height: int,
    bar_width: int,
    screen_x: int,
    screen_width: int,
    display: Optional[c_void_p] = None,
) -> bool:
    """
    Tell the X11 window manager to reserve space for our bar so other windows are pushed below it.
    Sets: _NET_WM_WINDOW_TYPE=DOCK, _NET_WM_STRUT (4 values), _NET_WM_STRUT_PARTIAL (12 values).
    If display is provided (e.g. from get_qt_x11_display()), uses that connection and does not close it.
    """
    if not _X11_AVAILABLE:
        return False
    lib = find_library("X11")
    if not lib:
        lib = "libX11.so.6"
    try:
        x11 = CDLL(lib)
    except (OSError, TypeError):
        return False
    x11.XOpenDisplay.restype = c_void_p
    x11.XOpenDisplay.argtypes = [c_void_p]
    x11.XCloseDisplay.argtypes = [c_void_p]
    x11.XInternAtom.argtypes = [c_void_p, c_void_p, c_ulong]
    x11.XInternAtom.restype = c_ulong
    if hasattr(x11, "XFlush"):
        x11.XFlush.argtypes = [c_void_p]

    own_display = False
    if display is None:
        disp = x11.XOpenDisplay(None)
        if not disp:
            return False
        own_display = True
    else:
        disp = display if isinstance(display, c_void_p) else c_void_p(display)

    try:
        # 1) Set _NET_WM_WINDOW_TYPE = _NET_WM_WINDOW_TYPE_DOCK so WM treats this as a panel
        type_atom = create_string_buffer(b"_NET_WM_WINDOW_TYPE")
        dock_atom_name = create_string_buffer(b"_NET_WM_WINDOW_TYPE_DOCK")
        atom_type = x11.XInternAtom(disp, type_atom, 0)
        atom_dock = x11.XInternAtom(disp, dock_atom_name, 0)
        if atom_type and atom_dock:
            x11.XChangeProperty(
                disp, win_id, atom_type, XA_ATOM, 32,
                PropModeReplace, byref(c_ulong(atom_dock)), 1,
            )

        # 2) _NET_WM_STRUT (4 CARDINALs: left, right, top, bottom) - some WMs only read this
        strut4 = (c_ulong * 4)()
        if position == "top":
            strut4[0], strut4[1], strut4[2], strut4[3] = 0, 0, bar_height, 0
        else:
            strut4[0], strut4[1], strut4[2], strut4[3] = 0, 0, 0, bar_height
        atom_strut = x11.XInternAtom(disp, create_string_buffer(b"_NET_WM_STRUT"), 0)
        if atom_strut:
            x11.XChangeProperty(
                disp, win_id, atom_strut, XA_CARDINAL, 32,
                PropModeReplace, cast(byref(strut4), c_void_p), 4,
            )

        # 3) _NET_WM_STRUT_PARTIAL (12 CARDINALs) for partial edge reservation
        partial = (c_ulong * 12)()
        if position == "top":
            partial[2] = bar_height
            partial[8] = screen_x
            partial[9] = screen_x + screen_width
        else:
            partial[3] = bar_height
            partial[10] = screen_x
            partial[11] = screen_x + screen_width
        atom_partial = x11.XInternAtom(disp, create_string_buffer(b"_NET_WM_STRUT_PARTIAL"), 0)
        if atom_partial:
            x11.XChangeProperty(
                disp, win_id, atom_partial, XA_CARDINAL, 32,
                PropModeReplace, cast(byref(partial), c_void_p), 12,
            )

        if hasattr(x11, "XFlush"):
            x11.XFlush(disp)
        return True
    except Exception as e:
        logger.debug("X11 strut failed: %s", e)
        return False
    finally:
        if own_display and disp:
            x11.XCloseDisplay(disp)
