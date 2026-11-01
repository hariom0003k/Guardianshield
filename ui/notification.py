"""
Guardian Shield — Peeper Screen Overlay & Notification System.
Provides a prominent screen-edge warning glow and high-visibility HUD alert
when unauthorized shoulder-surfers are detected gazing at the monitor.
"""

import ctypes
import subprocess
import sys
import threading
from typing import Optional
from PySide6.QtCore import QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from ..core.events import (
        NotificationDismissedEvent,
        ShieldRequestedEvent,
        ToastAlertTriggeredEvent,
        TrustedFaceEnrolledEvent,
        event_bus,
    )
except ImportError:
    from core.events import (
        NotificationDismissedEvent,
        ShieldRequestedEvent,
        ToastAlertTriggeredEvent,
        TrustedFaceEnrolledEvent,
        event_bus,
    )


class ScreenEdgeGlow(QWidget):
    """
    Transparent fullscreen overlay that paints a glowing warning border
    around the 4 edges of the screen when an unauthorized onlooker is looking.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.WindowTransparentForInput  # Click-through!
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.glow_color = QColor(255, 23, 68, 220)  # Bright neon red
        self.border_width = 8
        self._pulse_alpha = 220
        self._pulse_direction = -15

        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(60)
        self.pulse_timer.timeout.connect(self._on_pulse)

    def trigger(self, urgency: str = "high") -> None:
        """Positions overlay fullscreen and starts pulsing glow."""
        screen = QApplication.primaryScreen()
        if not screen:
            return

        self.setGeometry(screen.geometry())
        if urgency == "critical":
            self.glow_color = QColor(213, 0, 0, 240)
            self.border_width = 10
        elif urgency == "high":
            self.glow_color = QColor(255, 82, 82, 210)
            self.border_width = 8
        else:
            self.glow_color = QColor(255, 171, 0, 190)
            self.border_width = 6

        self.pulse_timer.start()
        self.show()
        self.raise_()

    def dismiss(self) -> None:
        """Hides screen glow."""
        self.pulse_timer.stop()
        self.hide()

    def _on_pulse(self) -> None:
        self._pulse_alpha += self._pulse_direction
        if self._pulse_alpha <= 110:
            self._pulse_alpha = 110
            self._pulse_direction = 15
        elif self._pulse_alpha >= 235:
            self._pulse_alpha = 235
            self._pulse_direction = -15
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        bw = self.border_width

        color = QColor(self.glow_color)
        color.setAlpha(self._pulse_alpha)
        pen = QPen(color)
        pen.setWidth(bw)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw outer glowing border along screen edges
        painter.drawRect(bw // 2, bw // 2, w - bw, h - bw)

        # Subtle gradient vignettes in four corners
        corner_size = 120
        painter.fillRect(0, 0, corner_size, bw * 2, color)
        painter.fillRect(0, 0, bw * 2, corner_size, color)
        painter.fillRect(w - corner_size, 0, corner_size, bw * 2, color)
        painter.fillRect(w - bw * 2, 0, bw * 2, corner_size, color)
        painter.fillRect(0, h - bw * 2, corner_size, bw * 2, color)
        painter.fillRect(0, h - corner_size, bw * 2, corner_size, color)
        painter.fillRect(w - corner_size, h - bw * 2, corner_size, bw * 2, color)
        painter.fillRect(w - bw * 2, h - corner_size, bw * 2, corner_size, color)


class ToastNotification(QWidget):
    """
    High-visibility Peeper Screen Overlay Popup.
    Appears prominently in the center of the display with clear warning
    and instant [Deploy Shield] & [Dismiss] actions.
    """

    sig_show_alert = Signal(object)

    def __init__(
        self,
        duration_seconds: int = 15,
        position: str = "center",
        deploy_hotkey_label: str = "Ctrl+Shift+D"
    ):
        super().__init__()
        self.duration_seconds = duration_seconds
        self.position = position
        self.deploy_hotkey_label = deploy_hotkey_label
        self.remaining_time = duration_seconds

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Screen Edge Ambient Glow Overlay
        self.edge_glow = ScreenEdgeGlow()

        self._init_ui()
        self._init_timers()

        self.sig_show_alert.connect(self._handle_show_alert)
        event_bus.subscribe(ToastAlertTriggeredEvent, self._on_event_received)

    def _init_ui(self) -> None:
        self.setFixedSize(480, 200)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 18)
        main_layout.setSpacing(12)

        # Top Row: Warning Icon + Title + Severity Tag
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        self.icon_label = QLabel("⚠️")
        self.icon_label.setStyleSheet("font-size: 26px; background: transparent;")
        header_layout.addWidget(self.icon_label)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        self.title_label = QLabel("PEEPER DETECTED!")
        self.title_label.setStyleSheet("font-size: 17px; font-weight: 900; color: #FFFFFF; letter-spacing: 0.5px;")
        title_vbox.addWidget(self.title_label)

        self.subtitle_label = QLabel("Shoulder-surfing observed gazing towards your display")
        self.subtitle_label.setStyleSheet("font-size: 11px; color: #94A3B8;")
        title_vbox.addWidget(self.subtitle_label)

        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        self.badge_label = QLabel("HIGH THREAT")
        self.badge_label.setStyleSheet("""
            background-color: #FF1744;
            color: #FFFFFF;
            font-size: 11px;
            font-weight: bold;
            padding: 4px 10px;
            border-radius: 6px;
        """)
        header_layout.addWidget(self.badge_label)
        main_layout.addLayout(header_layout)

        # Message Body
        self.message_label = QLabel("An unauthorized onlooker is actively looking at your screen.\nDeploy Guardian Shield to obscure and protect sensitive viewport contents?")
        self.message_label.setStyleSheet("font-size: 12px; color: #E2E8F0; line-height: 1.4;")
        self.message_label.setWordWrap(True)
        main_layout.addWidget(self.message_label)

        # Auto-dismiss countdown bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.12);
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00B0FF, stop:1 #00E5FF);
                border-radius: 2px;
            }
        """)
        self.progress_bar.setRange(0, self.duration_seconds * 10)
        self.progress_bar.setValue(self.duration_seconds * 10)
        main_layout.addWidget(self.progress_bar)

        # Action Buttons Row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self.btn_deploy = QPushButton(f"🛡️ DEPLOY SHIELD ({self.deploy_hotkey_label})")
        self.btn_deploy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_deploy.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00C853, stop:1 #00E676);
                color: #060D17;
                font-weight: 900;
                font-size: 12px;
                padding: 9px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background: #69F0AE;
            }
            QPushButton:pressed {
                background: #00B248;
            }
        """)
        self.btn_deploy.clicked.connect(self._on_deploy_clicked)
        actions_layout.addWidget(self.btn_deploy, 3)

        self.btn_dismiss = QPushButton("✕ Dismiss")
        self.btn_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dismiss.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.12);
                color: #F1F5F9;
                font-size: 12px;
                padding: 9px 14px;
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.25);
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.22);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.08);
            }
        """)
        self.btn_dismiss.clicked.connect(self._on_dismiss_clicked)
        actions_layout.addWidget(self.btn_dismiss, 1)

        self.btn_trust = QPushButton("➕ Trust Face")
        self.btn_trust.setToolTip("Whitelist this face as a trusted coworker")
        self.btn_trust.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trust.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.15);
                color: #00E5FF;
                font-size: 12px;
                padding: 9px 12px;
                border-radius: 6px;
                border: 1px solid rgba(0, 229, 255, 0.4);
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.28);
            }
        """)
        self.btn_trust.clicked.connect(self._on_trust_clicked)
        actions_layout.addWidget(self.btn_trust, 1)

        main_layout.addLayout(actions_layout)

    def _init_timers(self) -> None:
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(100)
        self.countdown_timer.timeout.connect(self._on_timer_tick)

    def paintEvent(self, event) -> None:
        """Paints a modern glassmorphic card with neon glow border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)

        # Background gradient
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(15, 23, 42, 250))
        gradient.setColorAt(1, QColor(10, 15, 28, 254))
        painter.fillPath(path, gradient)

        # Glowing Neon border (Red for high/critical, Amber for medium)
        border_color = QColor(255, 23, 68, 230) if "HIGH" in self.badge_label.text() or "CRITICAL" in self.badge_label.text() else QColor(255, 171, 0, 210)
        pen = QPen(border_color)
        pen.setWidth(2)
        painter.strokePath(path, pen)

    def _position_window(self) -> None:
        """Positions toast in the chosen screen location (center, corners)."""
        screen = QApplication.primaryScreen()
        if not screen:
            return

        geo = screen.availableGeometry()
        margin = 24
        pos = (self.position or "center").lower()

        if pos == "center":
            x = geo.left() + (geo.width() - self.width()) // 2
            y = geo.top() + (geo.height() - self.height()) // 2
        elif pos == "bottom-right":
            x = geo.right() - self.width() - margin
            y = geo.bottom() - self.height() - margin
        elif pos == "top-right":
            x = geo.right() - self.width() - margin
            y = geo.top() + margin
        elif pos == "bottom-left":
            x = geo.left() + margin
            y = geo.bottom() - self.height() - margin
        elif pos == "top-left":
            x = geo.left() + margin
            y = geo.top() + margin
        else:
            x = geo.left() + (geo.width() - self.width()) // 2
            y = geo.top() + (geo.height() - self.height()) // 2

        self.move(x, y)

    def _on_event_received(self, evt: ToastAlertTriggeredEvent) -> None:
        self.sig_show_alert.emit(evt)

    def _handle_show_alert(self, evt: ToastAlertTriggeredEvent) -> None:
        """Receives alert event on Qt GUI thread, shows edge glow and overlay card."""
        pct = int(evt.threat_score * 100)
        urgency = evt.urgency.lower()

        if urgency == "critical":
            self.badge_label.setText("CRITICAL THREAT")
            self.badge_label.setStyleSheet("background-color: #D50000; color: #FFF; font-weight: bold; border-radius: 4px; padding: 4px 10px;")
        elif urgency == "high":
            self.badge_label.setText("HIGH THREAT")
            self.badge_label.setStyleSheet("background-color: #FF1744; color: #FFF; font-weight: bold; border-radius: 4px; padding: 4px 10px;")
        else:
            self.badge_label.setText("MEDIUM THREAT")
            self.badge_label.setStyleSheet("background-color: #FFAB00; color: #1E293B; font-weight: bold; border-radius: 4px; padding: 4px 10px;")

        plural = "s" if evt.peeper_count > 1 else ""
        self.message_label.setText(
            f"Detected {evt.peeper_count} unauthorized viewer{plural} gazing directly at screen.\n"
            f"Threat Score: {pct}% • Deploy Shield to protect sensitive fields?"
        )

        # 1. Trigger Screen Edge Glowing Alert
        self.edge_glow.trigger(urgency)

        # 2. Position and display central HUD card
        self._position_window()
        self.remaining_time = self.duration_seconds
        self.progress_bar.setValue(self.duration_seconds * 10)
        self.countdown_timer.start()

        self.show()
        self.raise_()
        self.activateWindow()
        self.update()

        # 3. Audible alert: Windows chime + speech announcement ("Peeper detected")
        try:
            if sys.platform == "win32":
                ctypes.windll.user32.MessageBeep(0x40)  # Windows Warning chime
                self._speak_alert("Peeper detected")
        except Exception:
            pass

    def _speak_alert(self, text: str = "Peeper detected") -> None:
        """Announces alert through Windows Speech Synthesizer in background thread."""
        def _worker():
            try:
                ps_cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text}')"
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                    timeout=3
                )
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _on_timer_tick(self) -> None:
        val = self.progress_bar.value() - 1
        self.progress_bar.setValue(val)
        if val <= 0:
            self._on_timeout()

    def _on_timeout(self) -> None:
        self.countdown_timer.stop()
        self.edge_glow.dismiss()
        self.hide()
        event_bus.publish(NotificationDismissedEvent(reason="timeout"))

    def _on_deploy_clicked(self) -> None:
        self.countdown_timer.stop()
        self.edge_glow.dismiss()
        self.hide()
        event_bus.publish(ShieldRequestedEvent(
            source="overlay_popup_button",
            preferred_style="blur"
        ))

    def _on_dismiss_clicked(self) -> None:
        self.countdown_timer.stop()
        self.edge_glow.dismiss()
        self.hide()
        event_bus.publish(NotificationDismissedEvent(reason="user_dismissed"))

    def _on_trust_clicked(self) -> None:
        self.countdown_timer.stop()
        self.edge_glow.dismiss()
        self.hide()
        event_bus.publish(TrustedFaceEnrolledEvent(
            label="Whitelisted Colleague"
        ))
