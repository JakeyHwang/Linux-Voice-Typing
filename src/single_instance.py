"""
Single-instance lock: only one app process runs; second launch asks the first to raise its window.
Uses a PID lock file and a Unix socket for raise requests.
"""
from __future__ import annotations

import atexit
import logging
import os
import socket
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_LOCK_DIR: Optional[Path] = None
_LOCK_FILE: Optional[Path] = None
_LISTENER_SOCKET: Optional[socket.socket] = None
_LISTENER_THREAD: Optional[threading.Thread] = None
_RAISE_CALLBACK: Optional[Callable[[], None]] = None


def _get_lock_dir() -> Path:
    """Directory for lock file and socket (XDG_RUNTIME_DIR or fallback to cache)."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        return Path(base) / "linux-voice-typing"
    return Path.home() / ".cache" / "linux-voice-typing"


def _socket_path() -> Path:
    return _get_lock_dir() / "socket"


def _lock_file_path() -> Path:
    return _get_lock_dir() / "instance.lock"


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def try_acquire_lock() -> tuple[bool, Optional[Path]]:
    """
    Try to become the single instance. Returns (True, socket_path) if we got the lock,
    (False, socket_path) if another instance is running. Caller must call release_lock() on exit.
    """
    global _LOCK_DIR, _LOCK_FILE
    lock_dir = _get_lock_dir()
    lock_file = _lock_file_path()
    sock_path = _socket_path()

    lock_dir.mkdir(parents=True, exist_ok=True)
    if lock_file.exists():
        try:
            pid = int(lock_file.read_text().strip())
        except (ValueError, OSError):
            pid = None
        if pid is not None and _is_pid_alive(pid):
            logger.debug("Another instance is running (PID %s); will request raise.", pid)
            return False, sock_path
        # Stale lock
        try:
            lock_file.unlink()
        except OSError:
            pass

    try:
        lock_file.write_text(str(os.getpid()))
    except OSError as e:
        logger.warning("Could not write lock file: %s", e)
        return False, sock_path

    _LOCK_DIR = lock_dir
    _LOCK_FILE = lock_file
    atexit.register(release_lock)
    return True, sock_path


def set_raise_callback(callback: Callable[[], None]) -> None:
    """Register a callable to run when another instance asks to raise (call from main thread after UI exists)."""
    global _RAISE_CALLBACK
    _RAISE_CALLBACK = callback


def _listener_loop(sock: socket.socket) -> None:
    """Accept connections and invoke raise callback (callback should schedule Qt work on main thread)."""
    global _RAISE_CALLBACK
    try:
        sock.listen(1)
        while True:
            try:
                conn, _ = sock.accept()
            except OSError:
                break
            try:
                conn.recv(1)
                if _RAISE_CALLBACK:
                    _RAISE_CALLBACK()
            except OSError:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
    except OSError as e:
        logger.debug("Single-instance listener stopped: %s", e)


def start_raise_listener(socket_path: Path) -> None:
    """Start thread that listens for raise requests. Call after acquiring lock."""
    global _LISTENER_SOCKET, _LISTENER_THREAD
    try:
        if socket_path.exists():
            socket_path.unlink()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(socket_path))
        sock.settimeout(1.0)
        _LISTENER_SOCKET = sock
        _LISTENER_THREAD = threading.Thread(target=_listener_loop, args=(sock,), daemon=True)
        _LISTENER_THREAD.start()
        logger.debug("Single-instance raise listener started at %s", socket_path)
    except OSError as e:
        logger.warning("Could not start raise listener: %s", e)


def request_raise(socket_path: Optional[Path]) -> None:
    """Tell the running instance to raise its window. Call from a second process before exiting."""
    if not socket_path or not socket_path.exists():
        return
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(str(socket_path))
        s.send(b"\x00")
        s.close()
    except OSError as e:
        logger.debug("Could not request raise: %s", e)


def release_lock() -> None:
    """Remove lock file and stop listener. Called at exit."""
    global _LISTENER_SOCKET, _LISTENER_THREAD, _LOCK_FILE
    atexit.unregister(release_lock)
    if _LISTENER_SOCKET:
        try:
            _LISTENER_SOCKET.close()
        except OSError:
            pass
        _LISTENER_SOCKET = None
    if _LISTENER_THREAD:
        _LISTENER_THREAD.join(timeout=2.0)
        _LISTENER_THREAD = None
    sp = _socket_path()
    try:
        if sp.exists():
            sp.unlink()
    except OSError:
        pass
    if _LOCK_FILE and _LOCK_FILE.exists():
        try:
            _LOCK_FILE.unlink()
        except OSError:
            pass
        _LOCK_FILE = None
    logger.debug("Single-instance lock released")
