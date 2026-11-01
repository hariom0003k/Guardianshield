"""
Guardian Shield Threat Classifier.
Evaluates peeper gaze, proximity, dwell time, and face count to assess shoulder-surfing threats.
"""

from dataclasses import dataclass
import time
from typing import List, Optional
import numpy as np

from .events import (
    FaceIdentity,
    FaceMetadata,
    GazeDirection,
    ThreatClearedEvent,
    ThreatDetectedEvent,
    ThreatLevel,
    ToastAlertTriggeredEvent,
    event_bus,
)


@dataclass
class ThreatEvaluationResult:
    threat_level: ThreatLevel
    threat_score: float
    peeper_count: int
    max_gaze_confidence: float
    max_proximity: float
    dwell_time_seconds: float
    should_alert: bool
    should_auto_shield: bool


class ThreatClassifier:
    """
    Assesses threat levels by aggregating gaze confidence, face proximity (area ratio),
    and persistence duration over time. Prevents momentary glances from triggering false alarms.
    """

    def __init__(
        self,
        gaze_weight: float = 0.40,
        proximity_weight: float = 0.30,
        dwell_weight: float = 0.20,
        peeper_count_weight: float = 0.10,
        toast_threshold: float = 0.45,
        auto_shield_threshold: float = 0.82,
        debounce_seconds: float = 0.4,
        auto_shield_enabled: bool = False,
    ):
        self.gaze_weight = gaze_weight
        self.proximity_weight = proximity_weight
        self.dwell_weight = dwell_weight
        self.peeper_count_weight = peeper_count_weight

        self.toast_threshold = toast_threshold
        self.auto_shield_threshold = auto_shield_threshold
        self.debounce_seconds = debounce_seconds
        self.auto_shield_enabled = auto_shield_enabled

        self.first_detected_time: Optional[float] = None
        self.last_detected_time: Optional[float] = None
        self.current_threat_level: ThreatLevel = ThreatLevel.NONE
        self.alert_already_shown: bool = False

    def evaluate(self, faces: List[FaceMetadata]) -> ThreatEvaluationResult:
        """
        Evaluates a frame's detected faces.
        Returns ThreatEvaluationResult and dispatches events via EventBus.
        """
        now = time.time()

        # Filter for unauthorized faces (peepers)
        peepers = [
            f for f in faces
            if f.identity == FaceIdentity.UNAUTHORIZED_PEEPER
        ]

        if not peepers:
            if self.first_detected_time is not None:
                safe_duration = now - (self.last_detected_time or now)
                if safe_duration > 0.8:
                    self._handle_threat_cleared(safe_duration)

            return ThreatEvaluationResult(
                threat_level=ThreatLevel.NONE,
                threat_score=0.0,
                peeper_count=0,
                max_gaze_confidence=0.0,
                max_proximity=0.0,
                dwell_time_seconds=0.0,
                should_alert=False,
                should_auto_shield=False
            )

        # Active peepers facing screen or workstation area
        gazing_peepers = [
            p for p in peepers
            if p.gaze == GazeDirection.AT_SCREEN
        ]
        indeterminate_peepers = [
            p for p in peepers
            if p.gaze == GazeDirection.INDETERMINATE
        ]

        # If all peepers are explicitly looking away (passerby scenario)
        if not gazing_peepers and not indeterminate_peepers:
            if self.first_detected_time is not None:
                safe_duration = now - (self.last_detected_time or now)
                if safe_duration > 0.8:
                    self._handle_threat_cleared(safe_duration)

            return ThreatEvaluationResult(
                threat_level=ThreatLevel.NONE,
                threat_score=0.0,
                peeper_count=0,
                max_gaze_confidence=0.0,
                max_proximity=0.0,
                dwell_time_seconds=0.0,
                should_alert=False,
                should_auto_shield=False
            )

        active_peepers = gazing_peepers if gazing_peepers else indeterminate_peepers

        # Unauthorized peeper is actively present
        if self.first_detected_time is None:
            self.first_detected_time = now
        self.last_detected_time = now

        dwell_time = now - self.first_detected_time

        # 1. Gaze factor [0.0 - 1.0]
        if gazing_peepers:
            max_gaze = max(p.gaze_confidence for p in gazing_peepers)
        else:
            max_gaze = max(0.65, max(p.gaze_confidence for p in indeterminate_peepers))

        # 2. Proximity factor [0.0 - 1.0]: normalized against a close face (15% of frame area)
        max_prox = max(p.proximity_ratio for p in active_peepers)
        proximity_factor = min(1.0, max_prox / 0.15)

        # 3. Dwell factor [0.0 - 1.0]: saturates at 2.5 seconds
        dwell_factor = min(1.0, dwell_time / 2.5)

        # 4. Count factor [0.0 - 1.0]: extra penalty if multiple peepers
        count_factor = min(1.0, (len(active_peepers) - 1) * 0.5 + 0.5)

        # Composite weighted threat score
        raw_score = (
            self.gaze_weight * max_gaze +
            self.proximity_weight * proximity_factor +
            self.dwell_weight * dwell_factor +
            self.peeper_count_weight * count_factor
        )
        threat_score = round(float(np.clip(raw_score, 0.0, 1.0)), 3)

        # Map to threat level
        if threat_score < 0.25:
            threat_level = ThreatLevel.LOW
        elif threat_score < 0.55:
            threat_level = ThreatLevel.MEDIUM
        elif threat_score < 0.80:
            threat_level = ThreatLevel.HIGH
        else:
            threat_level = ThreatLevel.CRITICAL

        self.current_threat_level = threat_level

        # Check debounce timing before triggering alert
        is_debounced = dwell_time >= self.debounce_seconds
        should_alert = is_debounced and (threat_score >= self.toast_threshold) and not self.alert_already_shown
        should_auto_shield = (
            self.auto_shield_enabled and
            is_debounced and
            (threat_score >= self.auto_shield_threshold)
        )

        # Dispatch threat detected event
        threat_event = ThreatDetectedEvent(
            level=threat_level,
            threat_score=threat_score,
            peeper_count=len(gazing_peepers),
            max_gaze_confidence=max_gaze,
            max_proximity=max_prox,
            dwell_time_seconds=dwell_time,
            faces=faces
        )
        event_bus.publish(threat_event)

        if should_alert:
            self.alert_already_shown = True
            urgency = "critical" if threat_level == ThreatLevel.CRITICAL else ("high" if threat_level == ThreatLevel.HIGH else "normal")
            event_bus.publish(ToastAlertTriggeredEvent(
                threat_score=threat_score,
                peeper_count=len(gazing_peepers),
                urgency=urgency,
                auto_shield_pending=should_auto_shield
            ))

        return ThreatEvaluationResult(
            threat_level=threat_level,
            threat_score=threat_score,
            peeper_count=len(gazing_peepers),
            max_gaze_confidence=max_gaze,
            max_proximity=max_prox,
            dwell_time_seconds=dwell_time,
            should_alert=should_alert,
            should_auto_shield=should_auto_shield
        )

    def _handle_threat_cleared(self, safe_duration: float) -> None:
        """Resets tracking state and emits ThreatClearedEvent."""
        self.first_detected_time = None
        self.last_detected_time = None
        self.current_threat_level = ThreatLevel.NONE
        self.alert_already_shown = False
        event_bus.publish(ThreatClearedEvent(
            reason="Unauthorized viewer left field of view or averted gaze",
            safe_duration_sec=safe_duration
        ))

    def reset(self) -> None:
        """Manually resets the classifier state."""
        self.first_detected_time = None
        self.last_detected_time = None
        self.current_threat_level = ThreatLevel.NONE
        self.alert_already_shown = False
