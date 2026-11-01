"""
Guardian Shield Camera Capture & Synthetic Stream Generator.
Manages user-facing camera feeds with thread-safe acquisition, multi-backend fallback,
hardware sensor warmup, real-time metrics, and synthetic scenario generation.
"""

from dataclasses import dataclass
import threading
import time
from typing import List, Optional, Tuple
import cv2
import numpy as np

# Suppress noisy OpenCV backend warnings
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except Exception:
    pass


@dataclass
class CameraDeviceInfo:
    index: int
    name: str
    backend: str
    is_active: bool


class CameraManager:
    """
    Captures frames from hardware webcam with throttling to minimize CPU overhead.
    Includes auto-detection, multi-backend fallback, sensor warmup, and synthetic simulation.
    """

    def __init__(
        self,
        device_id: int = 0,
        width: int = 640,
        height: int = 480,
        fps_limit: int = 8,
        enable_simulation: bool = False
    ):
        self.device_id = device_id
        self.width = width
        self.height = height
        self.fps_limit = max(1, fps_limit)
        self.frame_interval = 1.0 / self.fps_limit
        self.enable_simulation = enable_simulation

        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._sim_scenario: str = "primary_alone"  # "primary_alone", "peeper_gazing", "peeper_looking_away"
        self._sim_tick: int = 0

        # Live Hardware Metrics
        self.latest_mean_brightness: float = 0.0
        self.is_dark_warning: bool = False
        self.active_backend_name: str = "None"
        self.actual_fps: float = 0.0
        self._fps_counter = 0
        self._fps_last_time = time.time()

    def get_device_info(self) -> CameraDeviceInfo:
        """Returns details about currently active camera source."""
        name = "Integrated Camera" if self.device_id == 0 else f"Camera {self.device_id}"
        if self.enable_simulation:
            name = "Synthetic Simulation Generator"
        return CameraDeviceInfo(
            index=self.device_id,
            name=name,
            backend=self.active_backend_name if not self.enable_simulation else "SIMULATION",
            is_active=self._running
        )

    @staticmethod
    def scan_available_cameras(max_test: int = 3) -> List[CameraDeviceInfo]:
        """Detects all functioning physical cameras on the system."""
        detected = []
        backends = [
            ("DSHOW", getattr(cv2, "CAP_DSHOW", None)),
            ("MSMF", getattr(cv2, "CAP_MSMF", None)),
            ("DEFAULT", getattr(cv2, "CAP_ANY", 0)),
        ]

        for i in range(max_test):
            found_for_index = False
            for b_name, b_const in backends:
                if b_const is None:
                    continue
                try:
                    cap = cv2.VideoCapture(i, b_const)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            name = "Integrated Camera" if i == 0 else f"USB / External Camera {i}"
                            detected.append(CameraDeviceInfo(
                                index=i,
                                name=name,
                                backend=b_name,
                                is_active=True
                            ))
                            found_for_index = True
                            cap.release()
                            break
                    cap.release()
                except Exception:
                    pass
            # If camera 0 wasn't opened (e.g. busy or lens closed), still list it
            if not found_for_index and i == 0:
                detected.append(CameraDeviceInfo(
                    index=0,
                    name="Integrated Camera (Busy or Default)",
                    backend="DSHOW",
                    is_active=False
                ))
            # Stop probing further if higher indices fail on first backend
            if not found_for_index and i > 0:
                break

        return detected

    def _open_camera_capture(self, dev_id: int) -> Optional[cv2.VideoCapture]:
        """Tries multiple backends (DirectShow, MSMF, Default) with auto-warmup."""
        backends = [
            ("CAP_DSHOW", getattr(cv2, "CAP_DSHOW", None)),
            ("CAP_MSMF", getattr(cv2, "CAP_MSMF", None)),
            ("CAP_ANY", getattr(cv2, "CAP_ANY", 0)),
        ]

        for name, backend in backends:
            if backend is None:
                continue
            try:
                cap = cv2.VideoCapture(dev_id, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

                    # Sensor Warmup: discard first 3-5 frames while AGC/AEC calibrate
                    for _ in range(4):
                        cap.read()

                    self.active_backend_name = name
                    print(f"[CameraManager] Successfully opened camera {dev_id} using {name}")
                    return cap
                cap.release()
            except Exception as e:
                print(f"[CameraManager] Backend {name} error: {e}")

        return None

    def start(self) -> bool:
        """Starts the background capture loop."""
        if self._running:
            return True

        if not self.enable_simulation:
            self._cap = self._open_camera_capture(self.device_id)
            if self._cap is None:
                print(f"[CameraManager] Hardware camera {self.device_id} not opened. Falling back to simulation mode.")
                self.enable_simulation = True

        self._running = True
        self._thread = threading.Thread(target=self._capture_worker, daemon=True, name="GuardianCameraWorker")
        self._thread.start()
        return True

    def switch_camera(self, device_id: int) -> bool:
        """Switches active camera device on the fly."""
        with self._lock:
            if self._cap:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None

            self.device_id = device_id
            self.enable_simulation = False
            self._cap = self._open_camera_capture(device_id)
            if self._cap is None:
                self.enable_simulation = True
                return False
            return True

    def set_simulation_mode(self, enable: bool) -> None:
        """Toggles between real hardware camera and synthetic simulation."""
        with self._lock:
            self.enable_simulation = enable
            if not enable and self._cap is None:
                self._cap = self._open_camera_capture(self.device_id)
                if self._cap is None:
                    self.enable_simulation = True

    def stop(self) -> None:
        """Stops the capture worker and releases hardware resources."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def read_frame(self) -> Optional[np.ndarray]:
        """Returns a copy of the latest captured frame."""
        with self._lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()
            return None

    def set_simulation_scenario(self, scenario: str) -> None:
        """Sets scenario for simulation mode: 'primary_alone', 'peeper_gazing', 'peeper_looking_away'."""
        self._sim_scenario = scenario

    def _capture_worker(self) -> None:
        """Background frame grabbing loop with frame rate throttling and live metric tracking."""
        last_frame_time = 0.0

        while self._running:
            now = time.time()
            elapsed = now - last_frame_time

            if elapsed < self.frame_interval:
                time.sleep(max(0.005, self.frame_interval - elapsed))
                continue

            last_frame_time = time.time()

            # Measure actual FPS
            self._fps_counter += 1
            if now - self._fps_last_time >= 1.0:
                self.actual_fps = round(self._fps_counter / (now - self._fps_last_time), 1)
                self._fps_counter = 0
                self._fps_last_time = now

            if self.enable_simulation or self._cap is None:
                frame = self._generate_synthetic_frame()
                mean_b = float(np.mean(frame))
                dark = False
            else:
                ret, raw_frame = self._cap.read()
                if ret and raw_frame is not None:
                    frame = cv2.resize(raw_frame, (self.width, self.height))
                    mean_b = float(np.mean(frame))
                    dark = bool(mean_b < 4.0)
                else:
                    # Attempt soft auto-reconnect if hardware dropped
                    frame = self._generate_synthetic_frame()
                    mean_b = 0.0
                    dark = True

            with self._lock:
                self._latest_frame = frame
                self.latest_mean_brightness = mean_b
                self.is_dark_warning = dark

    def _generate_synthetic_frame(self) -> np.ndarray:
        """
        Synthesizes a realistic test frame depicting an office environment,
        the authenticated primary user, and optional simulated shoulder-surfers.
        """
        self._sim_tick += 1
        frame = np.full((self.height, self.width, 3), (35, 38, 45), dtype=np.uint8)

        # Draw simulated office background elements
        cv2.rectangle(frame, (0, 0), (self.width, int(self.height * 0.42)), (50, 55, 65), -1)
        cv2.line(frame, (0, int(self.height * 0.42)), (self.width, int(self.height * 0.42)), (70, 75, 88), 2)

        # 1. Primary User (Center of screen, facing forward)
        owner_center_x = self.width // 2
        owner_center_y = int(self.height * 0.58)
        owner_r = 75

        # Shoulders & torso
        cv2.ellipse(frame, (owner_center_x, int(self.height * 0.95)), (140, 100), 0, 0, 180, (45, 75, 125), -1)
        # Head
        cv2.circle(frame, (owner_center_x, owner_center_y), owner_r, (175, 195, 215), -1)
        cv2.circle(frame, (owner_center_x, owner_center_y), owner_r, (140, 160, 180), 2)

        # Primary user eyes (looking forward at monitor)
        cv2.ellipse(frame, (owner_center_x - 24, owner_center_y - 10), (12, 7), 0, 0, 360, (245, 245, 245), -1)
        cv2.ellipse(frame, (owner_center_x + 24, owner_center_y - 10), (12, 7), 0, 0, 360, (245, 245, 245), -1)
        # Centered pupils
        cv2.circle(frame, (owner_center_x - 24, owner_center_y - 10), 4, (30, 20, 20), -1)
        cv2.circle(frame, (owner_center_x + 24, owner_center_y - 10), 4, (30, 20, 20), -1)

        # 2. Simulated Shoulder-Surfer / Peeper (Behind owner's right shoulder)
        if self._sim_scenario in ("peeper_gazing", "peeper_looking_away"):
            peeper_x = int(self.width * 0.82)
            peeper_y = int(self.height * 0.38)
            peeper_r = 48

            # Peeper shoulders
            cv2.ellipse(frame, (peeper_x, int(self.height * 0.65)), (75, 60), 0, 0, 180, (70, 50, 60), -1)
            # Peeper head
            cv2.circle(frame, (peeper_x, peeper_y), peeper_r, (160, 175, 200), -1)
            cv2.circle(frame, (peeper_x, peeper_y), peeper_r, (120, 130, 150), 2)

            if self._sim_scenario == "peeper_gazing":
                # Eyes gazing toward screen/owner's monitor
                cv2.ellipse(frame, (peeper_x - 16, peeper_y - 6), (9, 5), 0, 0, 360, (240, 240, 240), -1)
                cv2.ellipse(frame, (peeper_x + 16, peeper_y - 6), (9, 5), 0, 0, 360, (240, 240, 240), -1)
                # Iris looking forward/down toward display
                cv2.circle(frame, (peeper_x - 17, peeper_y - 6), 3, (25, 20, 20), -1)
                cv2.circle(frame, (peeper_x + 15, peeper_y - 6), 3, (25, 20, 20), -1)
            else:
                # Peeper looking away (turned sideways)
                cv2.ellipse(frame, (peeper_x - 16, peeper_y - 6), (8, 5), 0, 0, 360, (220, 220, 220), -1)
                cv2.circle(frame, (peeper_x - 21, peeper_y - 6), 3, (25, 20, 20), -1)

        return frame
