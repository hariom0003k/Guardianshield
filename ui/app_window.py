"""
Guardian Shield — Desktop Application Control Center.
Modern Qt6 desktop application window for live monitoring, video preview,
threat visualization, trusted face management, and system settings.
"""

import csv
from datetime import datetime
import os
from pathlib import Path
import sys
import time
from typing import List, Optional

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, QTimer, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QSplitter,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from ..core.camera import CameraDeviceInfo, CameraManager
    from ..core.events import (
        FaceIdentity,
        FaceMetadata,
        GazeDirection,
        ShieldActivatedEvent,
        ShieldDismissedEvent,
        ShieldRequestedEvent,
        ThreatClearedEvent,
        ThreatDetectedEvent,
        ThreatLevel,
        ToastAlertTriggeredEvent,
        TrustedFaceEnrolledEvent,
        event_bus,
    )
    from ..core.security import SecurityManager
except ImportError:
    from core.camera import CameraDeviceInfo, CameraManager
    from core.events import (
        FaceIdentity,
        FaceMetadata,
        GazeDirection,
        ShieldActivatedEvent,
        ShieldDismissedEvent,
        ShieldRequestedEvent,
        ThreatClearedEvent,
        ThreatDetectedEvent,
        ThreatLevel,
        ToastAlertTriggeredEvent,
        TrustedFaceEnrolledEvent,
        event_bus,
    )
    from core.security import SecurityManager


class AppWindow(QMainWindow):
    """Main Desktop Application Window for Guardian Shield."""

    sig_threat_event = Signal(object)
    sig_shield_event = Signal(object)

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.config = engine.config

        self.setWindowTitle("Guardian Shield v2.0 — Shoulder-Surfing Privacy Defense")
        self.resize(1120, 720)
        self.setMinimumSize(920, 600)

        # Connect signals
        self.sig_threat_event.connect(self._on_threat_event_qt)
        self.sig_shield_event.connect(self._on_shield_event_qt)

        event_bus.subscribe(ThreatDetectedEvent, lambda evt: self.sig_threat_event.emit(evt))
        event_bus.subscribe(ThreatClearedEvent, lambda evt: self.sig_threat_event.emit(evt))
        event_bus.subscribe(ShieldActivatedEvent, lambda evt: self.sig_shield_event.emit(evt))
        event_bus.subscribe(ShieldDismissedEvent, lambda evt: self.sig_shield_event.emit(evt))

        self._current_threat_level = "SAFE"
        self._current_peepers = 0
        self._current_score = 0.0
        self._camera_list_cache: List[CameraDeviceInfo] = []

        self._init_theme()
        self._init_ui()
        self._init_video_timer()
        self._populate_camera_list(initial=True)

    def _init_theme(self) -> None:
        """Applies a sleek dark glassmorphic cybersecurity theme."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0A0E17;
            }
            QWidget {
                color: #F1F5F9;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame.card {
                background-color: #111827;
                border: 1px solid #1F2937;
                border-radius: 10px;
                padding: 16px;
            }
            QFrame.card-glow {
                background-color: #111827;
                border: 1px solid #00E5FF;
                border-radius: 10px;
                padding: 16px;
            }
            QPushButton {
                background-color: #1F2937;
                color: #F8FAFC;
                border: 1px solid #374151;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #374151;
                border-color: #00E5FF;
            }
            QPushButton:pressed {
                background-color: #111827;
            }
            QPushButton.primary-btn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00B0FF, stop:1 #00E5FF);
                color: #0A0E17;
                font-weight: bold;
                border: none;
            }
            QPushButton.primary-btn:hover {
                background: #80D8FF;
            }
            QPushButton.danger-btn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #DC2626, stop:1 #EF4444);
                color: #FFFFFF;
                font-weight: bold;
                border: none;
            }
            QPushButton.danger-btn:hover {
                background: #F87171;
            }
            QPushButton.success-btn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10B981);
                color: #FFFFFF;
                font-weight: bold;
                border: none;
            }
            QPushButton.success-btn:hover {
                background: #34D399;
            }
            QPushButton.nav-btn {
                background: transparent;
                border: none;
                border-radius: 8px;
                text-align: left;
                padding: 12px 18px;
                font-size: 13px;
                color: #94A3B8;
                font-weight: 500;
            }
            QPushButton.nav-btn:hover {
                background-color: #1F2937;
                color: #F8FAFC;
            }
            QPushButton.nav-btn-active {
                background-color: #1F2937;
                border-left: 3px solid #00E5FF;
                color: #00E5FF;
                font-weight: bold;
                text-align: left;
                padding: 12px 18px;
                font-size: 13px;
            }
            QTableWidget {
                background-color: #111827;
                gridline-color: #1F2937;
                border: 1px solid #1F2937;
                border-radius: 8px;
                color: #F8FAFC;
                selection-background-color: #0284C7;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #0A0E17;
                color: #94A3B8;
                padding: 8px 10px;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #1F2937;
                text-transform: uppercase;
            }
            QRadioButton, QCheckBox {
                spacing: 8px;
                color: #E2E8F0;
                font-size: 12px;
            }
            QRadioButton::indicator, QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QLineEdit, QComboBox {
                background-color: #0A0E17;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 7px 12px;
                color: #F8FAFC;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #00E5FF;
            }
            QScrollBar:vertical {
                border: none;
                background: #0A0E17;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #374151;
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00E5FF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QProgressBar {
                background-color: #1F2937;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00B0FF, stop:1 #00E5FF);
                border-radius: 3px;
            }
        """)

    def _init_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -------------------------------------------------------------
        # Left Navigation Sidebar
        # -------------------------------------------------------------
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background-color: #0D1322; border-right: 1px solid #1F2937;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 20, 14, 20)
        sidebar_layout.setSpacing(6)

        # App Brand Header
        brand_layout = QHBoxLayout()
        brand_icon = QLabel("🛡️")
        brand_icon.setStyleSheet("font-size: 28px;")
        brand_layout.addWidget(brand_icon)

        title_layout = QVBoxLayout()
        brand_title = QLabel("GUARDIAN")
        brand_title.setStyleSheet("font-weight: 900; font-size: 16px; color: #00E5FF; letter-spacing: 1.5px;")
        brand_sub = QLabel("Shield Protection v2.0")
        brand_sub.setStyleSheet("font-size: 10px; color: #64748B; text-transform: uppercase; letter-spacing: 1px;")
        title_layout.addWidget(brand_title)
        title_layout.addWidget(brand_sub)
        brand_layout.addLayout(title_layout)
        sidebar_layout.addLayout(brand_layout)

        sidebar_layout.addSpacing(22)

        # Navigation Buttons
        self.nav_btns = []
        nav_items = [
            ("📊 Dashboard", 0),
            ("📷 Live Camera Feed", 1),
            ("⚙️ Shield Settings", 2),
            ("👥 Trusted Faces", 3),
            ("📋 Audit History", 4),
        ]
        for label, idx in nav_items:
            btn = QPushButton(label)
            btn.setProperty("class", "nav-btn" if idx != 0 else "nav-btn-active")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=idx: self._switch_tab(i))
            sidebar_layout.addWidget(btn)
            self.nav_btns.append(btn)

        sidebar_layout.addStretch()

        # Engine Status Box in Sidebar
        self.status_box = QFrame()
        self.status_box.setStyleSheet("""
            background-color: #111827;
            border: 1px solid #10B981;
            border-radius: 8px;
            padding: 10px;
        """)
        sb_layout = QVBoxLayout(self.status_box)
        sb_layout.setSpacing(4)
        sb_layout.setContentsMargins(8, 8, 8, 8)

        self.lbl_guard_status = QLabel("● ACTIVE MONITORING")
        self.lbl_guard_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
        sb_layout.addWidget(self.lbl_guard_status)

        self.lbl_guard_fps = QLabel(f"Target: {self.config.camera.fps_limit} FPS")
        self.lbl_guard_fps.setStyleSheet("color: #94A3B8; font-size: 10px;")
        sb_layout.addWidget(self.lbl_guard_fps)

        self.lbl_guard_source = QLabel("Source: Webcam")
        self.lbl_guard_source.setStyleSheet("color: #64748B; font-size: 10px;")
        sb_layout.addWidget(self.lbl_guard_source)

        sidebar_layout.addWidget(self.status_box)

        # Turn Off App Button (Stops all background processes)
        self.btn_quit_app = QPushButton("🛑 Turn Off App (Exit)")
        self.btn_quit_app.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #B91C1C, stop:1 #DC2626);
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                padding: 10px 14px;
                border-radius: 6px;
                border: 1px solid #EF4444;
            }
            QPushButton:hover {
                background: #EF4444;
            }
            QPushButton:pressed {
                background: #991B1B;
            }
        """)
        self.btn_quit_app.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quit_app.setToolTip("Completely stops Guardian Shield, turns off camera, and terminates all background processes")
        self.btn_quit_app.clicked.connect(self._turn_off_app_completely)
        sidebar_layout.addWidget(self.btn_quit_app)

        root_layout.addWidget(sidebar)

        # -------------------------------------------------------------
        # Right Main Stacked Pages
        # -------------------------------------------------------------
        self.stacked = QStackedWidget()
        self.stacked.setStyleSheet("background-color: #0A0E17; padding: 6px;")

        self.stacked.addWidget(self._create_dashboard_page())
        self.stacked.addWidget(self._create_camera_page())
        self.stacked.addWidget(self._create_settings_page())
        self.stacked.addWidget(self._create_trusted_page())
        self.stacked.addWidget(self._create_audit_page())

        root_layout.addWidget(self.stacked, 1)

    def _switch_tab(self, index: int) -> None:
        """Switches active page in stacked widget."""
        self.stacked.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_btns):
            btn.setProperty("class", "nav-btn-active" if i == index else "nav-btn")
            btn.setStyleSheet("")
        if index == 4:
            self.refresh_audit_table()
        elif index == 3:
            self.refresh_trusted_table()

    # =================================================================
    # PAGE 1: Security Dashboard
    # =================================================================
    def _create_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        # Header Title Row
        hdr = QHBoxLayout()
        t_lbl = QLabel("Security Protection Dashboard")
        t_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #F8FAFC;")
        hdr.addWidget(t_lbl)
        hdr.addStretch()

        self.btn_pause = QPushButton("⏸️ Pause Protection")
        self.btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause.clicked.connect(self._toggle_pause_btn)
        hdr.addWidget(self.btn_pause)

        self.btn_turn_off_dash = QPushButton("🛑 Turn Off App")
        self.btn_turn_off_dash.setProperty("class", "danger-btn")
        self.btn_turn_off_dash.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_turn_off_dash.setToolTip("Stops Guardian Shield and completely shuts down the app")
        self.btn_turn_off_dash.clicked.connect(self._turn_off_app_completely)
        hdr.addWidget(self.btn_turn_off_dash)

        layout.addLayout(hdr)

        # Main Protection Status Hero Card
        hero_card = QFrame()
        hero_card.setProperty("class", "card-glow")
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(18, 14, 18, 14)

        hero_left = QVBoxLayout()
        self.hero_status_title = QLabel("🛡️ Screen Viewport is Protected")
        self.hero_status_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #00E5FF;")
        hero_left.addWidget(self.hero_status_title)

        self.hero_desc = QLabel("Real-time camera feed is analyzing your surroundings for shoulder-surfers gazing at your monitor.")
        self.hero_desc.setStyleSheet("color: #94A3B8; font-size: 12px;")
        hero_left.addWidget(self.hero_desc)
        hero_layout.addLayout(hero_left, 3)

        hero_right = QHBoxLayout()
        hero_right.setSpacing(8)

        btn_deploy_now = QPushButton("🛡️ Deploy Shield")
        btn_deploy_now.setProperty("class", "danger-btn")
        btn_deploy_now.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_deploy_now.setToolTip("Immediately obscures your screen with privacy shield")
        btn_deploy_now.clicked.connect(lambda: event_bus.publish(ShieldRequestedEvent(source="app_window")))
        hero_right.addWidget(btn_deploy_now)

        btn_test_popup = QPushButton("⚡ Test Alert Popup")
        btn_test_popup.setProperty("class", "primary-btn")
        btn_test_popup.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test_popup.setToolTip("Triggers a demo shoulder-surfing detection alert popup")
        btn_test_popup.clicked.connect(self._trigger_demo_popup)
        hero_right.addWidget(btn_test_popup)

        hero_layout.addLayout(hero_right, 2)
        layout.addWidget(hero_card)

        # KPI Metrics Cards Row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        self.card_kpi_threat = self._make_kpi_card("Current Threat Level", "SAFE", "#10B981")
        self.card_kpi_peepers = self._make_kpi_card("Onlookers Detected", "0", "#38BDF8")
        self.card_kpi_alerts = self._make_kpi_card("Total Alerts Triggered", "0", "#EF4444")
        self.card_kpi_shields = self._make_kpi_card("Shield Deployments", "0", "#A855F7")

        kpi_row.addWidget(self.card_kpi_threat)
        kpi_row.addWidget(self.card_kpi_peepers)
        kpi_row.addWidget(self.card_kpi_alerts)
        kpi_row.addWidget(self.card_kpi_shields)
        layout.addLayout(kpi_row)

        # Lower Operations Grid: Mini Camera Preview + Quick Activity Log
        ops_row = QHBoxLayout()
        ops_row.setSpacing(12)

        # Card A: Live Camera Monitor Viewport (Dashboard Mini View)
        cam_card = QFrame()
        cam_card.setProperty("class", "card")
        cam_layout = QVBoxLayout(cam_card)
        cam_layout.setContentsMargins(14, 12, 14, 12)
        cam_layout.setSpacing(8)

        cam_hdr = QHBoxLayout()
        lbl_cam_t = QLabel("📷 Live Vision Monitor")
        lbl_cam_t.setStyleSheet("font-size: 13px; font-weight: bold; color: #CBD5E1;")
        cam_hdr.addWidget(lbl_cam_t)
        cam_hdr.addStretch()

        self.btn_mini_sim = QPushButton("🎮 Simulation Mode")
        self.btn_mini_sim.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        self.btn_mini_sim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mini_sim.clicked.connect(self._toggle_simulation_mode)
        cam_hdr.addWidget(self.btn_mini_sim)

        btn_cam_tab = QPushButton("Full Studio →")
        btn_cam_tab.setStyleSheet("background: transparent; border: none; color: #00E5FF; font-size: 11px; font-weight: bold;")
        btn_cam_tab.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cam_tab.clicked.connect(lambda: self._switch_tab(1))
        cam_hdr.addWidget(btn_cam_tab)
        cam_layout.addLayout(cam_hdr)

        # Video Viewport Widget
        self.lbl_mini_video = QLabel("Initializing Camera...")
        self.lbl_mini_video.setFixedSize(380, 215)
        self.lbl_mini_video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mini_video.setStyleSheet("""
            background-color: #060910;
            border: 1px solid #1F2937;
            border-radius: 6px;
            color: #64748B;
            font-size: 12px;
        """)
        cam_layout.addWidget(self.lbl_mini_video, alignment=Qt.AlignmentFlag.AlignCenter)

        # Camera Status & Brightness Bar
        meter_row = QHBoxLayout()
        meter_row.setSpacing(8)
        self.lbl_mini_status = QLabel("● Source: Scanning...")
        self.lbl_mini_status.setStyleSheet("color: #10B981; font-size: 11px; font-weight: bold;")
        meter_row.addWidget(self.lbl_mini_status)
        meter_row.addStretch()

        meter_row.addWidget(QLabel("Brightness:"))
        self.mini_brightness_bar = QProgressBar()
        self.mini_brightness_bar.setFixedSize(80, 8)
        self.mini_brightness_bar.setRange(0, 255)
        self.mini_brightness_bar.setValue(0)
        meter_row.addWidget(self.mini_brightness_bar)
        cam_layout.addLayout(meter_row)

        ops_row.addWidget(cam_card, 4)

        # Card B: Quick Activity Log Feed
        log_card = QFrame()
        log_card.setProperty("class", "card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(14, 12, 14, 12)
        log_layout.setSpacing(8)

        log_hdr = QHBoxLayout()
        lbl_recent = QLabel("📋 Recent Security Events")
        lbl_recent.setStyleSheet("font-size: 13px; font-weight: bold; color: #CBD5E1;")
        log_hdr.addWidget(lbl_recent)
        log_hdr.addStretch()

        btn_view_all = QPushButton("View Full History →")
        btn_view_all.setStyleSheet("background: transparent; border: none; color: #00E5FF; font-size: 11px; font-weight: bold;")
        btn_view_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_view_all.clicked.connect(lambda: self._switch_tab(4))
        log_hdr.addWidget(btn_view_all)
        log_layout.addLayout(log_hdr)

        self.quick_log_table = QTableWidget()
        self.quick_log_table.setColumnCount(4)
        self.quick_log_table.setHorizontalHeaderLabels(["Time", "Event", "Threat", "Action"])
        self.quick_log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.quick_log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.quick_log_table.setFixedHeight(235)
        log_layout.addWidget(self.quick_log_table)

        ops_row.addWidget(log_card, 5)
        layout.addLayout(ops_row)

        return page

    def _make_kpi_card(self, title: str, initial_val: str, color: str) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; text-transform: uppercase; font-weight: 600;")
        layout.addWidget(t_lbl)

        v_lbl = QLabel(initial_val)
        v_lbl.setObjectName("kpi_value")
        v_lbl.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {color};")
        layout.addWidget(v_lbl)
        return card

    # =================================================================
    # PAGE 2: Live Camera & Vision Studio
    # =================================================================
    def _create_camera_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        hdr = QHBoxLayout()
        t_lbl = QLabel("Live Vision & Gaze Tracking Studio")
        t_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #F8FAFC;")
        hdr.addWidget(t_lbl)
        hdr.addStretch()

        self.cb_show_boxes = QCheckBox("Show Vision Bounding Boxes & Gaze Vectors")
        self.cb_show_boxes.setChecked(True)
        hdr.addWidget(self.cb_show_boxes)
        layout.addLayout(hdr)

        # Hardware Camera Toolbar
        cam_bar = QHBoxLayout()
        cam_bar.setSpacing(8)

        cam_bar.addWidget(QLabel("<b>Camera Device:</b>"))
        self.combo_cam_dev = QComboBox()
        self.combo_cam_dev.setMinimumWidth(260)
        self.combo_cam_dev.currentIndexChanged.connect(self._on_cam_device_changed)
        cam_bar.addWidget(self.combo_cam_dev)

        btn_refresh_cams = QPushButton("🔄 Scan Cameras")
        btn_refresh_cams.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh_cams.clicked.connect(lambda: self._populate_camera_list(initial=False))
        cam_bar.addWidget(btn_refresh_cams)

        self.btn_toggle_sim = QPushButton("🎮 Switch to Simulation Stream")
        self.btn_toggle_sim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_sim.clicked.connect(self._toggle_simulation_mode)
        cam_bar.addWidget(self.btn_toggle_sim)

        btn_retry_cam = QPushButton("🔄 Re-initialize")
        btn_retry_cam.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_retry_cam.clicked.connect(self._retry_camera_connect)
        cam_bar.addWidget(btn_retry_cam)

        cam_bar.addStretch()
        layout.addLayout(cam_bar)

        # Dark Frame Warning Banner
        self.banner_dark = QFrame()
        self.banner_dark.setStyleSheet("""
            background-color: rgba(220, 38, 38, 0.2);
            border: 1px solid #EF4444;
            border-radius: 8px;
            padding: 8px 14px;
        """)
        banner_layout = QHBoxLayout(self.banner_dark)
        banner_layout.setContentsMargins(8, 6, 8, 6)
        self.lbl_dark_text = QLabel(
            "⚠️ CAMERA INPUT DARK: The camera is connected, but the image is completely black. "
            "Please check your laptop's physical webcam privacy slider (cover on top bezel) or press the camera Fn key. "
            "You can also click 'Switch to Simulation Stream' above to test immediately."
        )
        self.lbl_dark_text.setStyleSheet("color: #FCA5A5; font-size: 11px; font-weight: bold;")
        self.lbl_dark_text.setWordWrap(True)
        banner_layout.addWidget(self.lbl_dark_text)
        layout.addWidget(self.banner_dark)
        self.banner_dark.hide()

        # Center Video Player Frame
        video_frame = QFrame()
        video_frame.setProperty("class", "card")
        v_layout = QVBoxLayout(video_frame)
        v_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_video = QLabel("Connecting to Camera Feed...")
        self.lbl_video.setFixedSize(640, 400)
        self.lbl_video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_video.setStyleSheet("""
            background-color: #060910;
            border: 2px dashed #1F2937;
            border-radius: 8px;
            color: #64748B;
            font-size: 13px;
        """)
        v_layout.addWidget(self.lbl_video)
        layout.addWidget(video_frame)

        # Diagnostics & Face Enrollment Toolbar
        controls = QHBoxLayout()
        controls.setSpacing(10)

        btn_enroll_owner = QPushButton("👤 Enroll My Face as Primary Owner")
        btn_enroll_owner.setToolTip("Sets current detected face as the primary authenticated device owner")
        btn_enroll_owner.clicked.connect(self._enroll_current_as_owner)
        controls.addWidget(btn_enroll_owner)

        btn_add_trusted = QPushButton("➕ Whitelist Face as Trusted Colleague")
        btn_add_trusted.setToolTip("Whitelists unauthorized face in view so it will not trigger alerts")
        btn_add_trusted.clicked.connect(self._whitelist_current_face)
        controls.addWidget(btn_add_trusted)

        controls.addStretch()

        self.lbl_live_status = QLabel("Initializing...")
        self.lbl_live_status.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 11px;")
        controls.addWidget(self.lbl_live_status)

        layout.addLayout(controls)
        return page

    def _populate_camera_list(self, initial: bool = False) -> None:
        """Scans and populates camera combo dropdown without blocking UI."""
        self.combo_cam_dev.blockSignals(True)
        self.combo_cam_dev.clear()

        devices = CameraManager.scan_available_cameras(max_test=2)
        self._camera_list_cache = devices

        curr_id = self.engine.camera.device_id
        selected_index = 0

        for i, dev in enumerate(devices):
            status = " (Active)" if dev.index == curr_id else ""
            item_text = f"Camera {dev.index}: {dev.name}{status}"
            self.combo_cam_dev.addItem(item_text, dev.index)
            if dev.index == curr_id:
                selected_index = i

        self.combo_cam_dev.setCurrentIndex(selected_index)
        self.combo_cam_dev.blockSignals(False)

        if not initial:
            QMessageBox.information(self, "Camera Scan", f"Detected {len(devices)} physical camera device(s).")

    # =================================================================
    # PAGE 3: Settings & Customization
    # =================================================================
    def _create_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        t_lbl = QLabel("Guardian Shield Configuration & Tuning")
        t_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #F8FAFC;")
        layout.addWidget(t_lbl)

        card = QFrame()
        card.setProperty("class", "card")
        c_layout = QGridLayout(card)
        c_layout.setContentsMargins(18, 18, 18, 18)
        c_layout.setVerticalSpacing(16)
        c_layout.setHorizontalSpacing(16)

        # Row 0: Shield Style
        c_layout.addWidget(QLabel("<b>Privacy Shield Style:</b>"), 0, 0)
        self.combo_style = QComboBox()
        self.combo_style.addItems(["Gaussian Blur (blur)", "Privacy Dim (dim)", "Mosaic Pixelate (mosaic)", "Decoy Spreadsheet (decoy)"])
        curr_style = self.config.shield.default_style
        for idx, item in enumerate(["blur", "dim", "mosaic", "decoy"]):
            if item in curr_style:
                self.combo_style.setCurrentIndex(idx)
        c_layout.addWidget(self.combo_style, 0, 1)

        # Row 1: Notification Position
        c_layout.addWidget(QLabel("<b>Alert Pop-Up Position:</b>"), 1, 0)
        self.combo_pos = QComboBox()
        self.combo_pos.addItems(["Center of Screen (center)", "Bottom-Right Corner (bottom-right)", "Top-Right Corner (top-right)", "Bottom-Left Corner (bottom-left)"])
        pos_val = self.config.notification.position.lower()
        if "bottom-right" in pos_val:
            self.combo_pos.setCurrentIndex(1)
        elif "top-right" in pos_val:
            self.combo_pos.setCurrentIndex(2)
        elif "bottom-left" in pos_val:
            self.combo_pos.setCurrentIndex(3)
        else:
            self.combo_pos.setCurrentIndex(0)
        c_layout.addWidget(self.combo_pos, 1, 1)

        # Row 2: Alert Duration
        c_layout.addWidget(QLabel("<b>Alert Auto-Dismiss Timer:</b>"), 2, 0)
        dur_box = QHBoxLayout()
        self.slider_dur = QSlider(Qt.Orientation.Horizontal)
        self.slider_dur.setRange(5, 30)
        self.slider_dur.setValue(self.config.notification.duration_seconds)
        self.lbl_dur_val = QLabel(f"{self.config.notification.duration_seconds}s")
        self.slider_dur.valueChanged.connect(lambda v: self.lbl_dur_val.setText(f"{v}s"))
        dur_box.addWidget(self.slider_dur)
        dur_box.addWidget(self.lbl_dur_val)
        c_layout.addLayout(dur_box, 2, 1)

        # Row 3: Autonomous Defense
        c_layout.addWidget(QLabel("<b>Autonomous Defense Modes:</b>"), 3, 0)
        auto_box = QVBoxLayout()
        self.chk_auto_shield = QCheckBox("Auto-Shield Mode: Instantly deploy privacy shield on High/Critical threat without waiting for prompt")
        self.chk_auto_shield.setChecked(self.config.features.auto_shield_enabled)
        auto_box.addWidget(self.chk_auto_shield)

        self.chk_session_lock = QCheckBox("Session Lock: Automatically lock Windows workstation (Win+L) if critical peeper persists > 6s")
        self.chk_session_lock.setChecked(self.config.features.session_lock_on_critical)
        auto_box.addWidget(self.chk_session_lock)
        c_layout.addLayout(auto_box, 3, 1)

        # Row 4: Global Hotkeys Display
        c_layout.addWidget(QLabel("<b>Keyboard Shortcuts:</b>"), 4, 0)
        hk_lbl = QLabel("• Deploy Shield: <b>Ctrl+Shift+D</b>   • Instant Unlock: <b>Ctrl+Shift+U</b>   • Pause: <b>Ctrl+Shift+P</b>")
        hk_lbl.setStyleSheet("color: #94A3B8;")
        c_layout.addWidget(hk_lbl, 4, 1)

        layout.addWidget(card)

        # Save Button Row
        btn_save = QPushButton("💾 Save Configuration Changes")
        btn_save.setProperty("class", "primary-btn")
        btn_save.setFixedWidth(240)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)

        layout.addStretch()
        return page

    def _save_settings(self) -> None:
        """Saves settings to config file and live engine."""
        style_idx = self.combo_style.currentIndex()
        styles = ["blur", "dim", "mosaic", "decoy"]
        chosen_style = styles[style_idx]
        self.engine.set_shield_style(chosen_style)

        pos_idx = self.combo_pos.currentIndex()
        positions = ["center", "bottom-right", "top-right", "bottom-left"]
        chosen_pos = positions[pos_idx]
        self.config.notification.position = chosen_pos
        if self.engine.toast:
            self.engine.toast.position = chosen_pos

        dur = self.slider_dur.value()
        self.config.notification.duration_seconds = dur
        if self.engine.toast:
            self.engine.toast.duration_seconds = dur

        self.config.features.auto_shield_enabled = self.chk_auto_shield.isChecked()
        self.engine.threat_classifier.auto_shield_enabled = self.chk_auto_shield.isChecked()

        self.config.features.session_lock_on_critical = self.chk_session_lock.isChecked()

        self.engine.config_mgr.save()
        QMessageBox.information(self, "Settings Saved", "Guardian Shield configuration successfully updated!")

    # =================================================================
    # PAGE 4: Trusted Faces Management
    # =================================================================
    def _create_trusted_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        hdr = QHBoxLayout()
        t_lbl = QLabel("Trusted Faces & Colleague Whitelist")
        t_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #F8FAFC;")
        hdr.addWidget(t_lbl)
        hdr.addStretch()

        btn_add = QPushButton("➕ Enroll Face from Camera")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._whitelist_current_face)
        hdr.addWidget(btn_add)

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self.refresh_trusted_table)
        hdr.addWidget(btn_refresh)
        layout.addLayout(hdr)

        info_lbl = QLabel("Individuals enrolled here are recognized by Guardian Shield and will never trigger shoulder-surfing alerts.")
        info_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(info_lbl)

        self.trusted_table = QTableWidget()
        self.trusted_table.setColumnCount(4)
        self.trusted_table.setHorizontalHeaderLabels(["Profile ID", "Label / Name", "Identity Role", "Enrolled Date"])
        self.trusted_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.trusted_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.trusted_table)

        return page

    def refresh_trusted_table(self) -> None:
        """Populates trusted faces table from recognizer."""
        profiles = self.engine.recognizer.profiles
        self.trusted_table.setRowCount(len(profiles))
        for row, p in enumerate(profiles.values()):
            self.trusted_table.setItem(row, 0, QTableWidgetItem(p.profile_id))
            self.trusted_table.setItem(row, 1, QTableWidgetItem(p.label))
            self.trusted_table.setItem(row, 2, QTableWidgetItem(p.identity.value))
            t_str = datetime.fromtimestamp(p.enrolled_at).strftime("%Y-%m-%d %H:%M")
            self.trusted_table.setItem(row, 3, QTableWidgetItem(t_str))

    # =================================================================
    # PAGE 5: Security Audit History
    # =================================================================
    def _create_audit_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        hdr = QHBoxLayout()
        t_lbl = QLabel("Security Audit Trail & Threat History")
        t_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #F8FAFC;")
        hdr.addWidget(t_lbl)
        hdr.addStretch()

        btn_export = QPushButton("📥 Export CSV")
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.clicked.connect(self._export_audit_csv)
        hdr.addWidget(btn_export)

        btn_clear = QPushButton("🗑️ Clear Logs")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self._clear_audit_logs)
        hdr.addWidget(btn_clear)

        btn_refresh = QPushButton("🔄 Refresh Log")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self.refresh_audit_table)
        hdr.addWidget(btn_refresh)
        layout.addLayout(hdr)

        # Filter bar
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Filter:"))
        self.txt_audit_filter = QLineEdit()
        self.txt_audit_filter.setPlaceholderText("Search by event, threat, or details...")
        self.txt_audit_filter.textChanged.connect(self._filter_audit_table)
        filter_bar.addWidget(self.txt_audit_filter)
        layout.addLayout(filter_bar)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(6)
        self.audit_table.setHorizontalHeaderLabels(["Timestamp", "Event Type", "Threat Level", "Score", "Peepers", "Action / Details"])
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.audit_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.audit_table)

        return page

    def refresh_audit_table(self) -> None:
        """Fetches SQLite records and populates audit tables."""
        events = self.engine.logger.get_recent_events(limit=120)
        self.audit_table.setRowCount(len(events))

        for row, evt in enumerate(events):
            t_str = datetime.fromtimestamp(evt["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            self.audit_table.setItem(row, 0, QTableWidgetItem(t_str))
            self.audit_table.setItem(row, 1, QTableWidgetItem(evt.get("event_type", "")))
            self.audit_table.setItem(row, 2, QTableWidgetItem(evt.get("threat_level", "NONE")))

            score = evt.get("threat_score", 0.0)
            score_item = QTableWidgetItem(f"{int(score * 100)}%" if score else "-")
            self.audit_table.setItem(row, 3, score_item)

            p_count = evt.get("peeper_count", 0)
            self.audit_table.setItem(row, 4, QTableWidgetItem(str(p_count) if p_count else "-"))

            details = evt.get("action_taken") or evt.get("details") or "-"
            self.audit_table.setItem(row, 5, QTableWidgetItem(details))

        # Also update quick log table on dashboard page
        quick_events = events[:15]
        self.quick_log_table.setRowCount(len(quick_events))
        for row, evt in enumerate(quick_events):
            t_str = datetime.fromtimestamp(evt["timestamp"]).strftime("%H:%M:%S")
            self.quick_log_table.setItem(row, 0, QTableWidgetItem(t_str))
            self.quick_log_table.setItem(row, 1, QTableWidgetItem(evt.get("event_type", "")))
            self.quick_log_table.setItem(row, 2, QTableWidgetItem(evt.get("threat_level", "NONE")))
            self.quick_log_table.setItem(row, 3, QTableWidgetItem(evt.get("action_taken") or evt.get("details") or "-"))

    def _filter_audit_table(self, query: str) -> None:
        """Filters audit rows based on search text."""
        query = query.lower().strip()
        for row in range(self.audit_table.rowCount()):
            match = False
            for col in range(self.audit_table.columnCount()):
                item = self.audit_table.item(row, col)
                if item and query in item.text().lower():
                    match = True
                    break
            self.audit_table.setRowHidden(row, not match)

    def _export_audit_csv(self) -> None:
        """Exports audit logs to CSV file."""
        path, _ = QFileDialog.getSaveFileName(self, "Export Audit Log to CSV", "guardian_audit_export.csv", "CSV Files (*.csv)")
        if not path:
            return
        events = self.engine.logger.get_recent_events(limit=500)
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Event Type", "Threat Level", "Threat Score", "Peepers", "Action", "Details"])
                for e in events:
                    t_str = datetime.fromtimestamp(e["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                    writer.writerow([
                        t_str,
                        e.get("event_type", ""),
                        e.get("threat_level", ""),
                        e.get("threat_score", 0.0),
                        e.get("peeper_count", 0),
                        e.get("action_taken", ""),
                        e.get("details", "")
                    ])
            QMessageBox.information(self, "Export Successful", f"Audit logs saved to:\n{path}")
        except Exception as err:
            QMessageBox.warning(self, "Export Failed", f"Could not write CSV: {err}")

    def _clear_audit_logs(self) -> None:
        """Clears audit logs after user confirmation."""
        confirm = QMessageBox.question(
            self,
            "Confirm Clear Logs",
            "Are you sure you want to purge all audit records from SQLite?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.engine.logger.clear_all_events()
            self.refresh_audit_table()
            QMessageBox.information(self, "Logs Cleared", "Audit log database has been reset.")

    # =================================================================
    # Live Video Loop & Annotations
    # =================================================================
    def _init_video_timer(self) -> None:
        self.video_timer = QTimer(self)
        self.video_timer.setInterval(90)  # ~11 FPS smooth preview
        self.video_timer.timeout.connect(self._update_video_preview)
        self.video_timer.start()

    def _update_video_preview(self) -> None:
        """Fetches latest camera frame, paints overlays, and updates viewports."""
        curr_page = self.stacked.currentIndex()
        if curr_page not in (0, 1):
            return

        frame, faces = self.engine.get_latest_preview_data()
        if frame is None or frame.size == 0:
            frame = self.engine.camera.read_frame()

        if frame is None or frame.size == 0:
            return

        display_frame = frame.copy()
        mean_b = float(np.mean(frame))
        is_sim = self.engine.camera.enable_simulation

        # Check for dark frame
        if mean_b < 4.0 and not is_sim:
            if hasattr(self, "banner_dark"):
                self.banner_dark.show()
            h, w = display_frame.shape[:2]
            cv2.rectangle(display_frame, (20, 120), (w - 20, 310), (15, 23, 42), -1)
            cv2.rectangle(display_frame, (20, 120), (w - 20, 310), (0, 80, 255), 2)
            cv2.putText(display_frame, "! CAMERA IMAGE IS PITCH BLACK", (40, 160),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 165, 255), 2)
            cv2.putText(display_frame, "- Check if physical webcam privacy shutter is CLOSED", (40, 205),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 240), 1)
            cv2.putText(display_frame, "- Check camera Fn key / Lenovo Vantage privacy toggle", (40, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 240), 1)
            cv2.putText(display_frame, "- Or click 'Switch to Simulation Stream' to test features", (40, 275),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 229, 255), 1)
        else:
            if hasattr(self, "banner_dark"):
                self.banner_dark.hide()

        # If bounding boxes are enabled, annotate faces
        if hasattr(self, "cb_show_boxes") and self.cb_show_boxes.isChecked() and faces:
            for d in faces:
                x, y, w, h = d.box
                if d.identity == FaceIdentity.PRIMARY_USER:
                    color = (0, 230, 118)  # Green
                    label = f"Owner ({int(d.confidence * 100)}%)"
                elif d.identity == FaceIdentity.TRUSTED_USER:
                    color = (0, 229, 255)  # Cyan
                    label = "Trusted Colleague"
                else:  # PEEPER
                    if d.gaze == GazeDirection.AT_SCREEN:
                        color = (0, 23, 255)  # Red
                        label = f"PEEPER! Gaze: {int(d.gaze_confidence * 100)}%"
                    else:
                        color = (0, 165, 255)  # Orange
                        label = "Unauthorized (Looking Away)"

                cv2.rectangle(display_frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(
                    display_frame, label, (x, max(20, y - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2
                )

        # Convert OpenCV BGR -> QPixmap for Qt with memory safety copy
        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()

        # Update Tab 0: Dashboard Mini Video Viewport
        if curr_page == 0 and hasattr(self, "lbl_mini_video"):
            pixmap = QPixmap.fromImage(qimg).scaled(
                self.lbl_mini_video.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_mini_video.setPixmap(pixmap)
            self.mini_brightness_bar.setValue(min(255, int(mean_b)))
            if is_sim:
                self.lbl_mini_status.setText("● Simulation Stream Active")
                self.lbl_mini_status.setStyleSheet("color: #00E5FF; font-size: 11px; font-weight: bold;")
                self.btn_mini_sim.setText("📷 Real Webcam")
            elif mean_b < 4.0:
                self.lbl_mini_status.setText("⚠️ Shutter Closed (Dark)")
                self.lbl_mini_status.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold;")
                self.btn_mini_sim.setText("🎮 Simulation Mode")
            else:
                self.lbl_mini_status.setText(f"● Hardware Camera (B:{int(mean_b)})")
                self.lbl_mini_status.setStyleSheet("color: #10B981; font-size: 11px; font-weight: bold;")
                self.btn_mini_sim.setText("🎮 Simulation Mode")

        # Update Tab 1: Full Camera Page Viewport
        elif curr_page == 1 and hasattr(self, "lbl_video"):
            pixmap = QPixmap.fromImage(qimg).scaled(
                self.lbl_video.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_video.setPixmap(pixmap)
            if is_sim:
                self.lbl_live_status.setText("● SIMULATION STREAM ACTIVE")
                self.lbl_live_status.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 11px;")
                self.btn_toggle_sim.setText("📷 Switch to Real Hardware Camera")
            else:
                if mean_b < 4.0:
                    self.lbl_live_status.setText("⚠️ HARDWARE CAMERA (BLACK IMAGE)")
                    self.lbl_live_status.setStyleSheet("color: #FF5252; font-weight: bold; font-size: 11px;")
                else:
                    self.lbl_live_status.setText(f"● WEBCAM ONLINE (Brightness: {int(mean_b)})")
                    self.lbl_live_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
                self.btn_toggle_sim.setText("🎮 Switch to Simulation Stream")

    def _on_cam_device_changed(self, idx: int) -> None:
        """Switches camera device index."""
        if idx < 0 or idx >= len(self._camera_list_cache):
            return
        dev_info = self._camera_list_cache[idx]
        print(f"[AppWindow] Switching camera to index {dev_info.index}...")
        success = self.engine.camera.switch_camera(dev_info.index)
        if not success:
            QMessageBox.warning(self, "Camera Switch", f"Could not open Camera {dev_info.index}. Reverting to available source.")

    def _toggle_simulation_mode(self) -> None:
        """Toggles between real hardware camera and synthetic simulation."""
        curr_sim = self.engine.camera.enable_simulation
        new_sim = not curr_sim
        self.engine.camera.set_simulation_mode(new_sim)
        source_name = "Simulation" if new_sim else "Webcam"
        self.lbl_guard_source.setText(f"Source: {source_name}")
        print(f"[AppWindow] Input toggled to: {source_name}")

    def _retry_camera_connect(self) -> None:
        """Re-initializes hardware camera."""
        idx = self.combo_cam_dev.currentIndex()
        if idx >= 0 and idx < len(self._camera_list_cache):
            dev_idx = self._camera_list_cache[idx].index
        else:
            dev_idx = 0
        self.engine.camera.switch_camera(dev_idx)
        QMessageBox.information(self, "Camera Re-initialized", f"Re-connected to Camera {dev_idx}!")

    def _enroll_current_as_owner(self) -> None:
        """Captures face in current frame and enrolls as Primary User."""
        frame = self.engine.camera.read_frame()
        if frame is None:
            QMessageBox.warning(self, "Enrollment Error", "No camera frame available.")
            return

        detections = self.engine.detector.detect(frame)
        if not detections:
            QMessageBox.warning(self, "Enrollment Error", "No face detected in camera view. Please look directly at the webcam.")
            return

        primary_face = detections[0].face_roi
        pid = self.engine.recognizer.enroll_primary_user(primary_face, "Primary Authenticated Owner")
        self.refresh_trusted_table()
        QMessageBox.information(self, "Enrollment Success", f"Face successfully enrolled as Primary Device Owner!\nProfile ID: {pid}")

    def _whitelist_current_face(self) -> None:
        """Captures unauthorized face and whitelists as Colleague."""
        frame = self.engine.camera.read_frame()
        if frame is None:
            return

        detections = self.engine.detector.detect(frame)
        if not detections:
            QMessageBox.warning(self, "Whitelist Error", "No face detected in view.")
            return

        face_roi = detections[-1].face_roi
        label, ok = QInputDialog.getText(self, "Whitelist Face", "Enter colleague name or description:", text="Trusted Colleague")
        if not ok or not label:
            label = "Trusted Colleague"

        pid = self.engine.recognizer.enroll_trusted_face(face_roi, label)
        self.refresh_trusted_table()
        QMessageBox.information(self, "Whitelisted", f"Face whitelisted into Trusted Profiles!\nLabel: {label}\nProfile ID: {pid}")

    def _trigger_demo_popup(self) -> None:
        """Simulates an unauthorized onlooker alert popup."""
        event_bus.publish(ToastAlertTriggeredEvent(
            threat_score=0.89,
            peeper_count=1,
            urgency="high"
        ))

    def _toggle_pause_btn(self) -> None:
        """Toggles monitoring state."""
        self.engine.toggle_pause()
        is_paused = self.engine._pause_event.is_set()
        if is_paused:
            self.btn_pause.setText("▶️ Resume Protection")
            self.lbl_guard_status.setText("⏸ MONITORING PAUSED")
            self.lbl_guard_status.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 11px;")
            self.hero_status_title.setText("⏸️ Protection is Currently Paused")
            self.hero_status_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #F59E0B;")
        else:
            self.btn_pause.setText("⏸️ Pause Protection")
            self.lbl_guard_status.setText("● ACTIVE MONITORING")
            self.lbl_guard_status.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
            self.hero_status_title.setText("🛡️ Screen Viewport is Protected")
            self.hero_status_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #00E5FF;")

    def _on_threat_event_qt(self, evt) -> None:
        """Updates dashboard counters when threat events occur."""
        if isinstance(evt, ThreatDetectedEvent):
            self.card_kpi_threat.findChild(QLabel, "kpi_value").setText(evt.level.value)
            color_map = {
                "NONE": "#10B981",
                "LOW": "#00E5FF",
                "MEDIUM": "#F59E0B",
                "HIGH": "#EF4444",
                "CRITICAL": "#DC2626",
            }
            c = color_map.get(evt.level.value, "#00E5FF")
            self.card_kpi_threat.findChild(QLabel, "kpi_value").setStyleSheet(f"font-size: 22px; font-weight: bold; color: {c};")
            self.card_kpi_peepers.findChild(QLabel, "kpi_value").setText(str(evt.peeper_count))
        elif isinstance(evt, ThreatClearedEvent):
            self.card_kpi_threat.findChild(QLabel, "kpi_value").setText("SAFE")
            self.card_kpi_threat.findChild(QLabel, "kpi_value").setStyleSheet("font-size: 22px; font-weight: bold; color: #10B981;")
            self.card_kpi_peepers.findChild(QLabel, "kpi_value").setText("0")

    def _on_shield_event_qt(self, evt) -> None:
        """Updates shield count on dashboard."""
        stats = self.engine.logger.get_summary_stats()
        self.card_kpi_alerts.findChild(QLabel, "kpi_value").setText(str(stats["total_alerts"]))
        self.card_kpi_shields.findChild(QLabel, "kpi_value").setText(str(stats["total_shields"]))

    def _turn_off_app_completely(self) -> None:
        """Prompts user and completely terminates Guardian Shield and background tasks."""
        confirm = QMessageBox.question(
            self,
            "Turn Off Guardian Shield",
            "Are you sure you want to completely turn off Guardian Shield?\n\n"
            "This will stop camera capture, disable background protection, and completely exit the app.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            print("[AppWindow] User requested complete turn off.")
            self.engine.shutdown()

    def closeEvent(self, event) -> None:
        """Handles window close with clear option to minimize to background or turn off completely."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Close Guardian Shield")
        msg_box.setText("How would you like to close Guardian Shield?")
        msg_box.setInformativeText("• Keep protecting in background (system tray)\n• Turn off completely and exit")
        btn_tray = msg_box.addButton("Run in Background", QMessageBox.ButtonRole.ActionRole)
        btn_exit = msg_box.addButton("Turn Off Completely", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(btn_tray)
        msg_box.exec()

        clicked = msg_box.clickedButton()
        if clicked == btn_exit:
            event.accept()
            self.engine.shutdown()
        elif clicked == btn_tray:
            event.ignore()
            self.hide()
            if self.engine.tray:
                self.engine.tray.showMessage(
                    "Guardian Shield",
                    "Guardian Shield is running in the background.\nDouble-click the tray icon to reopen, or right-click to turn off.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2500
                )
        else:
            event.ignore()
