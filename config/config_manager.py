"""
Guardian Shield Configuration Manager.
Loads, validates, and provides typed access to system configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class SystemConfig:
    app_name: str = "Guardian Shield"
    version: str = "2.0.0"
    log_level: str = "INFO"
    database_path: str = "guardian_audit.db"


@dataclass
class CameraConfig:
    device_id: int = 0
    frame_width: int = 640
    frame_height: int = 480
    fps_limit: int = 8
    enable_simulation: bool = False


@dataclass
class DetectionConfig:
    min_face_size_px: int = 50
    face_detection_confidence: float = 0.65
    primary_user_tolerance: float = 0.18
    debounce_seconds: float = 0.4


@dataclass
class GazeConfig:
    gaze_sensitivity: float = 0.60
    head_pose_weight: float = 0.35
    iris_weight: float = 0.65


@dataclass
class ThreatWeights:
    gaze: float = 0.40
    proximity: float = 0.30
    dwell_time: float = 0.20
    peeper_count: float = 0.10


@dataclass
class ThreatThresholds:
    toast_alert: float = 0.45
    auto_shield: float = 0.82


@dataclass
class ThreatConfig:
    weights: ThreatWeights = field(default_factory=ThreatWeights)
    thresholds: ThreatThresholds = field(default_factory=ThreatThresholds)


@dataclass
class NotificationConfig:
    position: str = "center"
    duration_seconds: int = 15
    sound_alert: bool = True
    show_confidence_badge: bool = True


@dataclass
class ShieldConfig:
    default_style: str = "blur"
    blur_radius: int = 35
    dim_opacity: float = 0.92
    decoy_type: str = "spreadsheet"
    decoy_image_path: str = ""
    scope: str = "fullscreen"
    instant_unlock_hotkey: str = "<ctrl>+<shift>+u"
    deploy_hotkey: str = "<ctrl>+<shift>+d"
    pause_hotkey: str = "<ctrl>+<shift>+p"


@dataclass
class FeaturesConfig:
    auto_shield_enabled: bool = False
    stealth_mode: bool = False
    break_away_alarm: bool = True
    break_away_timeout_sec: int = 15
    session_lock_on_critical: bool = False
    proximity_sensitivity: bool = True


@dataclass
class TrustedFacesConfig:
    storage_file: str = "trusted_profiles.json"
    auto_trust_threshold: float = 0.45


@dataclass
class AppConfig:
    system: SystemConfig = field(default_factory=SystemConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    gaze: GazeConfig = field(default_factory=GazeConfig)
    threat: ThreatConfig = field(default_factory=ThreatConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    shield: ShieldConfig = field(default_factory=ShieldConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    trusted_faces: TrustedFacesConfig = field(default_factory=TrustedFacesConfig)


class ConfigManager:
    """Manages loading, updating, and saving configuration."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path(__file__).resolve().parent / "settings.yaml"

        self.config = self._load()

    def _load(self) -> AppConfig:
        if not self.config_path.exists():
            return AppConfig()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return self._dict_to_config(data)
        except Exception as e:
            print(f"[GuardianShield] Warning loading config: {e}. Using defaults.")
            return AppConfig()

    def _dict_to_config(self, d: Dict[str, Any]) -> AppConfig:
        sys_d = d.get("system", {})
        cam_d = d.get("camera", {})
        det_d = d.get("detection", {})
        gaze_d = d.get("gaze", {})
        threat_d = d.get("threat", {})
        weights_d = threat_d.get("weights", {})
        thresh_d = threat_d.get("thresholds", {})
        notif_d = d.get("notification", {})
        shield_d = d.get("shield", {})
        feat_d = d.get("features", {})
        trust_d = d.get("trusted_faces", {})

        return AppConfig(
            system=SystemConfig(**sys_d) if sys_d else SystemConfig(),
            camera=CameraConfig(**cam_d) if cam_d else CameraConfig(),
            detection=DetectionConfig(**det_d) if det_d else DetectionConfig(),
            gaze=GazeConfig(**gaze_d) if gaze_d else GazeConfig(),
            threat=ThreatConfig(
                weights=ThreatWeights(**weights_d) if weights_d else ThreatWeights(),
                thresholds=ThreatThresholds(**thresh_d) if thresh_d else ThreatThresholds(),
            ),
            notification=NotificationConfig(**notif_d) if notif_d else NotificationConfig(),
            shield=ShieldConfig(**shield_d) if shield_d else ShieldConfig(),
            features=FeaturesConfig(**feat_d) if feat_d else FeaturesConfig(),
            trusted_faces=TrustedFacesConfig(**trust_d) if trust_d else TrustedFacesConfig(),
        )

    def save(self) -> None:
        """Serializes current configuration back to disk."""
        # Convert dataclasses to dict
        def to_dict(obj):
            if hasattr(obj, "__dataclass_fields__"):
                return {k: to_dict(getattr(obj, k)) for k in obj.__dataclass_fields__}
            return obj

        data = to_dict(self.config)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
