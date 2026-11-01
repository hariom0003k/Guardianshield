"""
Guardian Shield Security Utilities & Windows Platform Integration.
Provides active window geometry, sensitive title detection, and Windows workstation locking.
"""

import ctypes
from ctypes import wintypes
import sys
from typing import Optional, Tuple


class SecurityManager:
    """Provides security operations like session locking and active window inspection."""

    @staticmethod
    def lock_workstation() -> bool:
        """
        Locks the current Windows session (equivalent to Win+L).
        Useful for extreme threat scenarios where unauthorized viewers persist.
        """
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                return bool(user32.LockWorkStation())
            except Exception as e:
                print(f"[SecurityManager] LockWorkStation failed: {e}")
                return False
        else:
            print("[SecurityManager] Session lock is only supported on Windows.")
            return False

    @staticmethod
    def get_foreground_window_bounds() -> Optional[Tuple[int, int, int, int]]:
        """
        Returns (x, y, width, height) of the currently focused foreground window.
        Used for zone-based shielding (Feature F).
        """
        if sys.platform != "win32":
            return None

        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None

            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                x = rect.left
                y = rect.top
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                return (x, y, w, h)
        except Exception as e:
            print(f"[SecurityManager] Error retrieving window bounds: {e}")

        return None

    @staticmethod
    def get_foreground_window_title() -> str:
        """Returns the window title of the currently focused window."""
        if sys.platform != "win32":
            return ""

        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return ""

            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value
        except Exception:
            return ""

    @staticmethod
    def is_foreground_window_sensitive() -> bool:
        """Heuristic check whether active window contains sensitive identifiers."""
        title = SecurityManager.get_foreground_window_title().lower()
        sensitive_keywords = [
            "password", "keepass", "1password", "bitwarden", "authenticator",
            "bank", "financial", "crypto", "terminal", "powershell", "cmd.exe",
            "private", "incognito", "confidential"
        ]
        return any(keyword in title for keyword in sensitive_keywords)
