"""
Guardian Shield System Tray Integration.
Provides a background notification area icon with rapid deployment controls and status indicators.
"""

from typing import Callable, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

try:
    from ..core.events import ShieldDismissedEvent, ShieldRequestedEvent, event_bus
except ImportError:
    from core.events import ShieldDismissedEvent, ShieldRequestedEvent, event_bus


class GuardianTray(QSystemTrayIcon):
    """System tray icon and quick-access context menu."""

    def __init__(
        self,
        on_open_dashboard: Optional[Callable[[], None]] = None,
        on_toggle_pause: Optional[Callable[[], None]] = None,
        on_change_style: Optional[Callable[[str], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.on_open_dashboard = on_open_dashboard
        self.on_toggle_pause = on_toggle_pause
        self.on_change_style = on_change_style
        self.on_exit = on_exit

        self.setIcon(self._create_shield_icon())
        self.setToolTip("Guardian Shield — Shoulder-Surfing Protection Active")

        self._init_menu()

    def _create_shield_icon(self, active: bool = True) -> QIcon:
        """Generates a dynamic 32x32 shield icon."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw shield shape
        color = QColor(0, 229, 255) if active else QColor(148, 163, 184)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)

        # Polygon coordinates for shield
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        points = [
            QPointF(16, 2),
            QPointF(29, 6),
            QPointF(29, 18),
            QPointF(16, 30),
            QPointF(3, 18),
            QPointF(3, 6),
        ]
        painter.drawPolygon(QPolygonF(points))

        # Inner emblem
        painter.setBrush(QColor(15, 23, 42))
        inner_points = [
            QPointF(16, 6),
            QPointF(25, 9),
            QPointF(25, 17),
            QPointF(16, 26),
            QPointF(7, 17),
            QPointF(7, 9),
        ]
        painter.drawPolygon(QPolygonF(inner_points))
        painter.end()

        return QIcon(pixmap)

    def _init_menu(self) -> None:
        menu = QMenu()

        action_deploy = QAction("🛡️ Deploy Shield Now (Ctrl+Shift+D)", menu)
        action_deploy.triggered.connect(lambda: event_bus.publish(ShieldRequestedEvent(source="tray")))
        menu.addAction(action_deploy)

        action_unlock = QAction("🔓 Unlock Shield (Ctrl+Shift+U)", menu)
        action_unlock.triggered.connect(lambda: event_bus.publish(ShieldDismissedEvent(method="tray")))
        menu.addAction(action_unlock)

        menu.addSeparator()

        self.action_pause = QAction("⏸️ Pause Monitoring", menu)
        if self.on_toggle_pause:
            self.action_pause.triggered.connect(self.on_toggle_pause)
        menu.addAction(self.action_pause)

        # Submenu for Shield Style
        style_menu = menu.addMenu("🎨 Privacy Shield Style")
        style_mapping = [
            ("Blur Screen", "blur"),
            ("Privacy Dim", "dim"),
            ("Mosaic Pixelate", "mosaic"),
            ("Decoy Spreadsheet", "decoy")
        ]
        for label, code in style_mapping:
            act = QAction(label, style_menu)
            if self.on_change_style:
                act.triggered.connect(lambda checked=False, s=code: self.on_change_style(s))
            style_menu.addAction(act)

        menu.addSeparator()

        if self.on_open_dashboard:
            action_dash = QAction("🖥️ Open Guardian Shield App...", menu)
            action_dash.triggered.connect(self.on_open_dashboard)
            menu.addAction(action_dash)

        menu.addSeparator()

        action_exit = QAction("🚪 Exit Guardian Shield", menu)
        if self.on_exit:
            action_exit.triggered.connect(self.on_exit)
        menu.addAction(action_exit)

        self.setContextMenu(menu)
