# Your display environment & best options for the bar

This file summarizes what was detected on your machine and the best options for making the transcription bar reserve space (sit below the system bar and push other apps down).

---

## Your current environment

| Item | Value |
|------|--------|
| **OS** | Ubuntu 25.04 (Plucky Puffin) |
| **Display server** | **X11** (`XDG_SESSION_TYPE=x11`, `DISPLAY=:3`) |
| **Desktop** | Ubuntu GNOME (`XDG_CURRENT_DESKTOP=ubuntu:GNOME`) |
| **Compositor / WM** | **Mutter on X11** (`mutter-x11-fram`, `gnome-shell`) |
| **Monitors** | 2: primary HDMI-1 **1920×1080** at (0, 279), HDMI-0 **900×1600** at (1920, 0) |

So you are on **X11**, not Wayland. The voice-typing app’s strut code does run; the problem is that using a **second** X connection (from `x11_strut.py`) to set `_NET_WM_STRUT` / `_NET_WM_STRUT_PARTIAL` can be ignored or mishandled by the window manager. Many WMs only apply struts when they are set using the **same** X connection that created the window (Qt’s).

---

## Best options for your setup

### 1. **Use Qt’s X11 connection for struts (recommended)**

- Set `_NET_WM_STRUT` and `_NET_WM_STRUT_PARTIAL` using the **Display** that Qt uses for your bar window, not a new one from `XOpenDisplay` in ctypes.
- **PySide6** (used by this app): Exposes `QGuiApplication.nativeInterface()` and `QNativeInterface.QX11Application` with `.display()` (Xlib). The app gets Qt’s X11 Display via `get_qt_x11_display()` in `x11_strut.py` and sets struts on that connection so the WM sees them. This is the most reliable way to get “reserve space” on X11 + GNOME.

### 2. **If you cannot use PySide6**

- If you use PyQt6 instead of PySide6, PyQt6 does not expose the native interface type needed to get Qt’s Display. You can try setting struts before the first `show()` and re-applying after; some WMs may still honor them. For reliable reserve-space behavior, use PySide6 (as this app does).

### 3. **GNOME/Mutter behavior**

- Even with the correct X connection, **GNOME’s Mutter** (on X11 or Wayland) may give priority to its own panels and not always reserve space for third-party docks. So there is no guarantee that “other apps are pushed down” will work 100% on Ubuntu GNOME.
- **Bar top margin** (in Settings) remains useful: set it to the height of the system top bar (e.g. 24–32 px) so your bar is at least **visually** below the system bar and doesn’t sit behind it.

### 4. **If you ever switch to Wayland**

- On **Wayland + GNOME (Mutter)**: There is **no** public API for third-party panels to reserve space. The bar would be an overlay only; “push other apps down” would not be possible.
- On **Wayland + wlroots** (e.g. Sway, Hyprland): You could use the **layer-shell** protocol (`zwlr_layer_surface_v1`) with an **exclusive zone** to reserve space. That would require either a small GTK4 + gtk4-layer-shell helper, or using python-wayland for the layer surface (and another way to draw the bar). Not needed for your **current** X11 setup.

---

## Summary

- **Your device**: X11, Ubuntu GNOME, Mutter, 2 monitors (1920×1080 primary + 900×1600).
- **This app** uses **PySide6** and sets struts via Qt’s X11 Display (`get_qt_x11_display()` in `x11_strut.py`) so the WM sees them on the same connection. Use **Bar top margin** in Settings if the bar still overlaps the system bar.
