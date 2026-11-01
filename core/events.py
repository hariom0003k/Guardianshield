"""
Guardian Shield Event Bus & Event Definitions.
Implements a thread-safe publish-subscribe architecture for event routing.
"""

from dataclasses import dataclass, field
from enum import Enum
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Type


class ThreatLevel(Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GazeDirection(Enum):
    AT_SCREEN = "AT_SCREEN"
    LOOKING_AWAY = "LOOKING_AWAY"
    INDETERMINATE = "INDETERMINATE"


class FaceIdentity(Enum):
    PRIMARY_USER = "PRIMARY_USER"
    TRUSTED_USER = "TRUSTED_USER"
    UNAUTHORIZED_PEEPER = "UNAUTHORIZED_PEEPER"
    UNKNOWN = "UNKNOWN"


@dataclass
class BaseEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)


@dataclass
class FaceMetadata:
    box: tuple  # (x, y, w, h)
    identity: FaceIdentity
    confidence: float
    gaze: GazeDirection
    gaze_confidence: float
    proximity_ratio: float  # Face area / frame area
    profile_id: str = ""


@dataclass
class FrameAnalyzedEvent(BaseEvent):
    faces: List[FaceMetadata] = field(default_factory=list)
    has_primary_user: bool = False
    unauthorized_count: int = 0
    peeper_gazing_count: int = 0


@dataclass
class ThreatDetectedEvent(BaseEvent):
    level: ThreatLevel = ThreatLevel.NONE
    threat_score: float = 0.0
    peeper_count: int = 0
    max_gaze_confidence: float = 0.0
    max_proximity: float = 0.0
    dwell_time_seconds: float = 0.0
    faces: List[FaceMetadata] = field(default_factory=list)


@dataclass
class ThreatClearedEvent(BaseEvent):
    reason: str = "Peeper left or looked away"
    safe_duration_sec: float = 0.0


@dataclass
class ToastAlertTriggeredEvent(BaseEvent):
    threat_score: float = 0.0
    peeper_count: int = 1
    urgency: str = "normal"  # "normal", "high", "critical"
    auto_shield_pending: bool = False


@dataclass
class ShieldRequestedEvent(BaseEvent):
    source: str = "manual"  # "toast_button", "hotkey", "auto_shield", "tray"
    preferred_style: str = "blur"


@dataclass
class ShieldActivatedEvent(BaseEvent):
    style: str = "blur"
    scope: str = "fullscreen"


@dataclass
class ShieldDismissedEvent(BaseEvent):
    method: str = "hotkey"  # "hotkey", "button", "threat_cleared", "tray"


@dataclass
class NotificationDismissedEvent(BaseEvent):
    reason: str = "user_dismissed"  # "user_dismissed", "timeout", "shield_deployed"


@dataclass
class TrustedFaceEnrolledEvent(BaseEvent):
    label: str = "Coworker"
    profile_id: str = ""


@dataclass
class AlarmTriggeredEvent(BaseEvent):
    seconds_lingered: float = 0.0
    action_taken: str = "screen_border_flash"


class EventBus:
    """Thread-safe, decoupled Event Bus."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventBus, cls).__new__(cls)
                cls._instance._subscribers = {}
                cls._instance._subscribers_lock = threading.RLock()
            return cls._instance

    def subscribe(self, event_type: Type[BaseEvent], handler: Callable[[Any], None]) -> None:
        """Subscribes a callable handler to a specific event type."""
        with self._subscribers_lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[BaseEvent], handler: Callable[[Any], None]) -> None:
        """Unsubscribes a handler."""
        with self._subscribers_lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    def publish(self, event: BaseEvent) -> None:
        """Publishes an event synchronously to all registered listeners."""
        with self._subscribers_lock:
            handlers = list(self._subscribers.get(type(event), []))
            # Also notify any base BaseEvent subscribers
            if type(event) is not BaseEvent:
                handlers.extend(self._subscribers.get(BaseEvent, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"[EventBus] Error in handler {handler.__name__ if hasattr(handler, '__name__') else handler}: {e}")

    def clear(self) -> None:
        """Clears all subscribers."""
        with self._subscribers_lock:
            self._subscribers.clear()


# Global default instance
event_bus = EventBus()
