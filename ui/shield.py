"""
Guardian Shield Screen Privacy Overlay.
Obscures sensitive screen content via Gaussian blur, privacy dimming, mosaic, or decoy screens.
"""

from typing import Optional
import cv2
import numpy as np
from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from ..core.events import (
        ShieldActivatedEvent,
        ShieldDismissedEvent,
        ShieldRequestedEvent,
        event_bus,
    )
    from ..core.security import SecurityManager
except ImportError:
    from core.events import (
        ShieldActivatedEvent,
        ShieldDismissedEvent,
        ShieldRequestedEvent,
        event_bus,
    )
    from core.security import SecurityManager


class ShieldOverlay(QWidget):
    """
    High-performance, always-on-top fullscreen or active-window privacy shield.
    Instantly blurs or obscures screen content upon deployment.
    """

    sig_request_deploy = Signal(object)
    sig_request_dismiss = Signal(object)

    def __init__(
        self,
        default_style: str = "blur",
        blur_radius: int = 35,
        dim_opacity: float = 0.92,
        unlock_hotkey_label: str = "Ctrl+Shift+U"
    ):
        super().__init__()
        self.default_style = default_style
        self.blur_radius = blur_radius
        self.dim_opacity = dim_opacity
        self.unlock_hotkey_label = unlock_hotkey_label
        self.is_active = False
        self._pixmap: Optional[QPixmap] = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._init_ui()

        # Connect Qt signals for thread-safe cross-thread execution
        self.sig_request_deploy.connect(self._handle_deploy)
        self.sig_request_dismiss.connect(self._handle_dismiss)

        event_bus.subscribe(ShieldRequestedEvent, lambda evt: self.sig_request_deploy.emit(evt))
        event_bus.subscribe(ShieldDismissedEvent, lambda evt: self.sig_request_dismiss.emit(evt))

        # Local Escape shortcut as immediate fail-safe
        self.shortcut_esc = QShortcut(QKeySequence("Esc"), self)
        self.shortcut_esc.activated.connect(self.dismiss)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Central Unlock Card
        self.card = QWidget()
        self.card.setFixedSize(360, 160)
        self.card.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 23, 42, 0.94);
                border: 2px solid #00E5FF;
                border-radius: 14px;
            }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel("🛡️ GUARDIAN SHIELD ACTIVE")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("color: #00E5FF; font-size: 15px; font-weight: bold; border: none; background: transparent;")
        card_layout.addWidget(icon_label)

        sub_label = QLabel("Screen content obscured to protect privacy.")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_label.setStyleSheet("color: #94A3B8; font-size: 12px; border: none; background: transparent;")
        card_layout.addWidget(sub_label)

        self.btn_unlock = QPushButton(f"🔓 Instant Unlock ({self.unlock_hotkey_label})")
        self.btn_unlock.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_unlock.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00B0FF, stop:1 #00E5FF);
                color: #0F172A;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 18px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background: #80D8FF;
            }
            QPushButton:pressed {
                background: #0091EA;
            }
        """)
        self.btn_unlock.clicked.connect(self.dismiss)
        card_layout.addWidget(self.btn_unlock)

        layout.addWidget(self.card)

    def _capture_and_blur_screen(self, screen_geo: QRect) -> QPixmap:
        """Grabs screenshot and applies fast Gaussian blur."""
        screen = QApplication.primaryScreen()
        if not screen:
            return QPixmap()

        # Capture primary screen
        screenshot = screen.grabWindow(0, screen_geo.x(), screen_geo.y(), screen_geo.width(), screen_geo.height())
        qimage = screenshot.toImage().convertToFormat(QImage.Format.Format_RGB888)

        # Convert to numpy for fast vectorized blur
        w, h = qimage.width(), qimage.height()
        ptr = qimage.bits()
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 3))

        # Downscale -> Gaussian Blur -> Upscale (ultra-fast < 25ms execution)
        small_w, small_h = max(1, w // 4), max(1, h // 4)
        small = cv2.resize(arr, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
        blurred_small = cv2.GaussianBlur(small, (self.blur_radius | 1, self.blur_radius | 1), 0)
        blurred = cv2.resize(blurred_small, (w, h), interpolation=cv2.INTER_LINEAR)

        # Add dark tint for privacy contrast
        blurred = cv2.addWeighted(blurred, 0.45, np.zeros_like(blurred), 0.55, 0)

        # Back to QPixmap
        h, w, ch = blurred.shape
        bytes_per_line = ch * w
        blurred_qimage = QImage(blurred.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
        return QPixmap.fromImage(blurred_qimage)

    def _generate_decoy_pixmap(self, width: int, height: int) -> QPixmap:
        """Renders a convincing benign spreadsheet decoy screen (Feature D)."""
        decoy_arr = np.full((height, width, 3), (250, 250, 250), dtype=np.uint8)

        # Header bar
        cv2.rectangle(decoy_arr, (0, 0), (width, 40), (22, 101, 52), -1)
        cv2.putText(decoy_arr, "Quarterly Inventory & Logistics Audit Report - Q3", (20, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        # Draw spreadsheet grid
        row_h = 28
        col_w = 160
        for y in range(40, height, row_h):
            cv2.line(decoy_arr, (0, y), (width, y), (220, 225, 230), 1)
        for x in range(0, width, col_w):
            cv2.line(decoy_arr, (x, 40), (x, height), (220, 225, 230), 1)

        # Fill sample harmless cells
        headers = ["Item Code", "Product Description", "Warehouse", "Stock Qty", "Reorder Unit", "Status"]
        for i, h_text in enumerate(headers):
            cv2.rectangle(decoy_arr, (i * col_w, 40), ((i + 1) * col_w, 40 + row_h), (235, 240, 245), -1)
            cv2.putText(decoy_arr, h_text, (i * col_w + 12, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 70, 80), 1)

        h, w, ch = decoy_arr.shape
        bytes_per_line = ch * w
        qimage = QImage(decoy_arr.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
        return QPixmap.fromImage(qimage)

    def _generate_mosaic_pixmap(self, screen_geo: QRect) -> QPixmap:
        """Renders pixelated mosaic overlay."""
        screen = QApplication.primaryScreen()
        if not screen:
            return QPixmap()

        screenshot = screen.grabWindow(0, screen_geo.x(), screen_geo.y(), screen_geo.width(), screen_geo.height())
        qimage = screenshot.toImage().convertToFormat(QImage.Format.Format_RGB888)
        w, h = qimage.width(), qimage.height()
        arr = np.frombuffer(qimage.bits(), dtype=np.uint8).reshape((h, w, 3))

        # Pixelate via heavy nearest-neighbor down/up-sampling
        block_size = 28
        small_w, small_h = max(1, w // block_size), max(1, h // block_size)
        small = cv2.resize(arr, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
        mosaic = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

        h, w, ch = mosaic.shape
        bytes_per_line = ch * w
        qimage = QImage(mosaic.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
        return QPixmap.fromImage(qimage)

    def deploy(self, style: Optional[str] = None, scope: str = "fullscreen") -> None:
        """Activates and shows the privacy shield overlay."""
        if self.is_active:
            return

        active_style = style or self.default_style
        screen = QApplication.primaryScreen()
        if not screen:
            return

        screen_geo = screen.geometry()

        # Check for active-window zone shielding (Feature F)
        if scope == "active_window":
            win_bounds = SecurityManager.get_foreground_window_bounds()
            if win_bounds:
                x, y, w, h = win_bounds
                target_geo = QRect(x, y, w, h)
            else:
                target_geo = screen_geo
        else:
            target_geo = screen_geo

        self.setGeometry(target_geo)

        # Generate obscuring backdrop based on selected style
        if active_style == "blur":
            self._pixmap = self._capture_and_blur_screen(target_geo)
        elif active_style == "decoy":
            self._pixmap = self._generate_decoy_pixmap(target_geo.width(), target_geo.height())
        elif active_style == "mosaic":
            self._pixmap = self._generate_mosaic_pixmap(target_geo)
        else:  # "dim"
            self._pixmap = None

        self.is_active = True
        self.show()
        self.raise_()
        self.activateWindow()

        event_bus.publish(ShieldActivatedEvent(
            style=active_style,
            scope=scope
        ))

    def dismiss(self, publish_event: bool = True) -> None:
        """Deactivates and removes the privacy shield overlay."""
        if not self.is_active:
            return

        self.is_active = False
        self.hide()
        self._pixmap = None

        if publish_event:
            event_bus.publish(ShieldDismissedEvent(
                method="user_unlocked"
            ))

    def _handle_deploy(self, evt: ShieldRequestedEvent) -> None:
        self.deploy(style=evt.preferred_style)

    def _handle_dismiss(self, evt: ShieldDismissedEvent) -> None:
        self.dismiss(publish_event=False)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self._pixmap and not self._pixmap.isNull():
            painter.drawPixmap(0, 0, self._pixmap)
        else:
            # Fallback dimming overlay
            dim_val = int(self.dim_opacity * 255)
            painter.fillRect(self.rect(), QColor(10, 15, 24, dim_val))

    def mouseDoubleClickEvent(self, event) -> None:
        """Double clicking background unlocks shield safely."""
        self.dismiss()
