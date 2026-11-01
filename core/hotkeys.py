"""
Guardian Shield Global Hotkey Manager.
Listens for system-wide keyboard shortcuts to deploy and unlock the shield.
"""

import threading
from typing import Callable, Dict, Optional
from pynput import keyboard

from .events import ShieldDismissedEvent, ShieldRequestedEvent, event_bus


class HotkeyManager:
    """Manages system-wide global hotkeys using pynput."""

    def __init__(
        self,
        deploy_hotkey: str = "<ctrl>+<shift>+d",
        unlock_hotkey: str = "<ctrl>+<shift>+u",
        pause_hotkey: str = "<ctrl>+<shift>+p",
        on_pause_toggle: Optional[Callable[[], None]] = None
    ):
        self.deploy_hotkey = deploy_hotkey
        self.unlock_hotkey = unlock_hotkey
        self.pause_hotkey = pause_hotkey
        self.on_pause_toggle = on_pause_toggle

        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._running = False

    def start(self) -> bool:
        """Starts the global hotkey listener in a background thread."""
        if self._running:
            return True

        hotkey_bindings = {
            self.deploy_hotkey: self._on_deploy,
            self.unlock_hotkey: self._on_unlock,
            self.pause_hotkey: self._on_pause,
        }

        try:
            self._listener = keyboard.GlobalHotKeys(hotkey_bindings)
            self._listener.start()
            self._running = True
            print(f"[HotkeyManager] Global hotkeys active: Deploy={self.deploy_hotkey}, Unlock={self.unlock_hotkey}")
            return True
        except Exception as e:
            print(f"[HotkeyManager] Warning: could not start global hotkey listener: {e}")
            return False

    def stop(self) -> None:
        """Stops the global hotkey listener."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._running = False

    def _on_deploy(self) -> None:
        """Handler when Deploy hotkey is pressed."""
        print("[HotkeyManager] Deploy hotkey triggered!")
        event_bus.publish(ShieldRequestedEvent(
            source="hotkey",
            preferred_style="blur"
        ))

    def _on_unlock(self) -> None:
        """Handler when Unlock hotkey is pressed."""
        print("[HotkeyManager] Unlock hotkey triggered!")
        event_bus.publish(ShieldDismissedEvent(
            method="hotkey"
        ))

    def _on_pause(self) -> None:
        """Handler when Pause hotkey is pressed."""
        print("[HotkeyManager] Pause hotkey triggered!")
        if self.on_pause_toggle:
            self.on_pause_toggle()
