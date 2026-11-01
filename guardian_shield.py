"""
Guardian Shield Core Orchestrator.
Coordinates the camera feed, computer vision detection pipeline, threat evaluation,
toast alert system, and privacy shield overlay.
"""

import sys
import threading
import time
from typing import Optional
from PySide6.QtWidgets import QApplication

try:
    from .config.config_manager import AppConfig, ConfigManager
    from .core.camera import CameraManager
    from .core.detector import FaceDetector
    from .core.events import (
        FaceIdentity,
        FaceMetadata,
        GazeDirection,
        ShieldActivatedEvent,
        ShieldDismissedEvent,
        ShieldRequestedEvent,
        ThreatLevel,
        event_bus,
    )
    from .core.gaze import GazeAnalyzer
    from .core.hotkeys import HotkeyManager
    from .core.logger import AuditLogger
    from .core.recognizer import FaceRecognizer
    from .core.security import SecurityManager
    from .core.threat import ThreatClassifier
    from .ui.app_window import AppWindow
    from .ui.dashboard import DashboardDialog
    from .ui.notification import ToastNotification
    from .ui.shield import ShieldOverlay
    from .ui.tray import GuardianTray
except ImportError:
    from config.config_manager import AppConfig, ConfigManager
    from core.camera import CameraManager
    from core.detector import FaceDetector
    from core.events import (
        FaceIdentity,
        FaceMetadata,
        GazeDirection,
        ShieldActivatedEvent,
        ShieldDismissedEvent,
        ShieldRequestedEvent,
        ThreatLevel,
        event_bus,
    )
    from core.gaze import GazeAnalyzer
    from core.hotkeys import HotkeyManager
    from core.logger import AuditLogger
    from core.recognizer import FaceRecognizer
    from core.security import SecurityManager
    from core.threat import ThreatClassifier
    from ui.app_window import AppWindow
    from ui.dashboard import DashboardDialog
    from ui.notification import ToastNotification
    from ui.shield import ShieldOverlay
    from ui.tray import GuardianTray


class GuardianShield:
    """Main application controller for Guardian Shield."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_mgr = ConfigManager(config_path)
        self.config: AppConfig = self.config_mgr.config

        # 1. Audit Logger & SQLite store
        self.logger = AuditLogger(db_path=self.config.system.database_path)

        # 2. Computer Vision Pipeline Components
        self.detector = FaceDetector(
            min_face_size=self.config.detection.min_face_size_px,
            confidence_threshold=self.config.detection.face_detection_confidence
        )
        self.recognizer = FaceRecognizer(
            tolerance=self.config.detection.primary_user_tolerance,
            profiles_file=self.config.trusted_faces.storage_file
        )
        self.gaze_analyzer = GazeAnalyzer(
            sensitivity=self.config.gaze.gaze_sensitivity
        )
        self.threat_classifier = ThreatClassifier(
            gaze_weight=self.config.threat.weights.gaze,
            proximity_weight=self.config.threat.weights.proximity,
            dwell_weight=self.config.threat.weights.dwell_time,
            peeper_count_weight=self.config.threat.weights.peeper_count,
            toast_threshold=self.config.threat.thresholds.toast_alert,
            auto_shield_threshold=self.config.threat.thresholds.auto_shield,
            debounce_seconds=self.config.detection.debounce_seconds,
            auto_shield_enabled=self.config.features.auto_shield_enabled,
        )

        # 3. Camera Manager
        self.camera = CameraManager(
            device_id=self.config.camera.device_id,
            width=self.config.camera.frame_width,
            height=self.config.camera.frame_height,
            fps_limit=self.config.camera.fps_limit,
            enable_simulation=self.config.camera.enable_simulation
        )

        # 4. Global Hotkey Manager
        self.hotkeys = HotkeyManager(
            deploy_hotkey=self.config.shield.deploy_hotkey,
            unlock_hotkey=self.config.shield.instant_unlock_hotkey,
            pause_hotkey=self.config.shield.pause_hotkey,
            on_pause_toggle=self.toggle_pause
        )

        # 5. UI Widgets (initialized on Qt Application thread)
        self.toast: Optional[ToastNotification] = None
        self.shield: Optional[ShieldOverlay] = None
        self.tray: Optional[GuardianTray] = None
        self.dashboard_dialog: Optional[DashboardDialog] = None
        self.app_window: Optional[AppWindow] = None

        self._running = False
        self._pause_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._shield_deployed_time: Optional[float] = None
        self._preview_lock = threading.Lock()
        self._latest_preview_frame: Optional[np.ndarray] = None

    def initialize_ui(self, show_window: bool = True) -> None:
        """Instantiates all Qt UI components on the main thread."""
        self.toast = ToastNotification(
            duration_seconds=self.config.notification.duration_seconds,
            position=self.config.notification.position,
            deploy_hotkey_label="Ctrl+Shift+D"
        )
        self.shield = ShieldOverlay(
            default_style=self.config.shield.default_style,
            blur_radius=self.config.shield.blur_radius,
            dim_opacity=self.config.shield.dim_opacity,
            unlock_hotkey_label="Ctrl+Shift+U"
        )
        self.app_window = AppWindow(self)

        self.tray = GuardianTray(
            on_open_dashboard=self.show_app_window,
            on_toggle_pause=self.toggle_pause,
            on_change_style=self.set_shield_style,
            on_exit=self.shutdown
        )
        self.tray.show()

        # Double clicking tray icon opens the main app window
        self.tray.activated.connect(self._on_tray_activated)

        # Show desktop app window on startup
        if show_window:
            self.show_app_window()

        # Listen for shield lifecycle to track linger duration
        event_bus.subscribe(ShieldActivatedEvent, self._on_shield_activated)
        event_bus.subscribe(ShieldDismissedEvent, self._on_shield_dismissed)

    def _on_tray_activated(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.show_app_window()

    def show_app_window(self) -> None:
        """Shows and focuses the main desktop application window."""
        if self.app_window:
            self.app_window.show()
            self.app_window.raise_()
            self.app_window.activateWindow()

    def start(self) -> None:
        """Starts monitoring and camera pipeline."""
        if self._running:
            return

        print("[GuardianShield] Starting Guardian Shield Shoulder-Surfing Monitor...")
        self.camera.start()
        self.hotkeys.start()

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._analysis_loop,
            daemon=True,
            name="GuardianAnalysisWorker"
        )
        self._worker_thread.start()
        print("[GuardianShield] Real-time detection active.")

    def stop(self) -> None:
        """Stops background detection worker and releases resources."""
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        self.camera.stop()
        self.hotkeys.stop()
        print("[GuardianShield] Stopped monitoring.")

    def toggle_pause(self) -> None:
        """Toggles monitoring pause state."""
        if self._pause_event.is_set():
            self._pause_event.clear()
            is_paused = False
        else:
            self._pause_event.set()
            is_paused = True
        state_str = "Paused" if is_paused else "Resumed"
        print(f"[GuardianShield] Monitoring {state_str}")
        if self.tray:
            self.tray.action_pause.setText("▶️ Resume Monitoring" if is_paused else "⏸️ Pause Monitoring")

    def set_shield_style(self, style: str) -> None:
        """Updates preferred shield style."""
        self.config.shield.default_style = style
        if self.shield:
            self.shield.default_style = style
        print(f"[GuardianShield] Shield style changed to: {style}")

    def show_dashboard(self) -> None:
        """Displays security dashboard."""
        if self.dashboard_dialog is None:
            self.dashboard_dialog = DashboardDialog(logger=self.logger)
        self.dashboard_dialog.refresh_data()
        self.dashboard_dialog.show()
        self.dashboard_dialog.raise_()

    def shutdown(self) -> None:
        """Gracefully shuts down the application and completely exits background process."""
        print("[GuardianShield] Shutting down Guardian Shield completely...")
        self.stop()
        if self.shield:
            self.shield.dismiss()
        if self.toast:
            self.toast.hide()
        if self.tray:
            self.tray.hide()
        if self.app_window:
            self.app_window.hide()
        QApplication.quit()
        import os
        os._exit(0)

    def _analysis_loop(self) -> None:
        """Continuous face and gaze analysis worker loop."""
        frame_interval = 1.0 / self.config.camera.fps_limit

        while self._running:
            start_time = time.time()

            if self._pause_event.is_set():
                time.sleep(0.1)
                continue

            frame = self.camera.read_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            # 1. Detect faces in current frame
            raw_detections = self.detector.detect(frame)
            frame_shape = frame.shape[:2]

            # 2. Strict Scene-Aware Classification: Enforces single Primary User;
            # any second person added is categorized as UNAUTHORIZED_PEEPER!
            classifications = self.recognizer.classify_scene(raw_detections)

            evaluated_faces = []
            for d, (identity, conf, pid) in zip(raw_detections, classifications):
                gaze_dir = GazeDirection.INDETERMINATE
                gaze_conf = 0.5

                # 3. Gaze analysis for unauthorized faces
                if identity == FaceIdentity.UNAUTHORIZED_PEEPER:
                    gaze_dir, gaze_conf = self.gaze_analyzer.analyze_gaze(
                        face_roi=d.face_roi,
                        eye_rois=d.eye_rois,
                        face_box=d.box,
                        frame_shape=frame_shape
                    )

                metadata = FaceMetadata(
                    box=d.box,
                    identity=identity,
                    confidence=conf,
                    gaze=gaze_dir,
                    gaze_confidence=gaze_conf,
                    proximity_ratio=d.area_ratio,
                    profile_id=pid or ""
                )
                evaluated_faces.append(metadata)

            # 4. Evaluate threat levels
            eval_result = self.threat_classifier.evaluate(evaluated_faces)

            # Store preview frame for UI
            with self._preview_lock:
                self._latest_preview_frame = frame.copy()
                self._latest_evaluated_faces = evaluated_faces

            # 5. Feature C: Auto-Shield Mode
            if eval_result.should_auto_shield and not (self.shield and self.shield.is_active):
                print("[GuardianShield] Auto-Shield triggered by high threat score!")
                event_bus.publish(ShieldRequestedEvent(
                    source="auto_shield",
                    preferred_style=self.config.shield.default_style
                ))

            # 6. Feature J: Session Lock on critical threat
            if (
                self.config.features.session_lock_on_critical and
                eval_result.threat_level == ThreatLevel.CRITICAL and
                eval_result.dwell_time_seconds >= 6.0
            ):
                print("[GuardianShield] CRITICAL THREAT PERSISTS — Locking Windows workstation.")
                SecurityManager.lock_workstation()

            # Throttled sleep to maintain targeted FPS
            elapsed = time.time() - start_time
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

    def get_latest_preview_data(self):
        """Returns (frame, evaluated_faces) without thread contention."""
        with self._preview_lock:
            if self._latest_preview_frame is not None:
                return self._latest_preview_frame.copy(), getattr(self, "_latest_evaluated_faces", [])
            return None, []

    def _on_shield_activated(self, evt: ShieldActivatedEvent) -> None:
        self._shield_deployed_time = time.time()

    def _on_shield_dismissed(self, evt: ShieldDismissedEvent) -> None:
        self._shield_deployed_time = None
        self.threat_classifier.reset()
