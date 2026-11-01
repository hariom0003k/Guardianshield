"""
Guardian Shield Persistent Audit Logger.
Stores security audit logs and threat event history in SQLite with privacy-preserving principles.
"""

from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from .events import (
    BaseEvent,
    NotificationDismissedEvent,
    ShieldActivatedEvent,
    ShieldDismissedEvent,
    ThreatClearedEvent,
    ThreatDetectedEvent,
    ToastAlertTriggeredEvent,
    TrustedFaceEnrolledEvent,
    event_bus,
)


class AuditLogger:
    """Manages persistent SQLite logging of shoulder-surfing threat events."""

    def __init__(self, db_path: str = "guardian_audit.db"):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_database()
        self._subscribe_to_events()

    def _init_database(self) -> None:
        """Initializes SQLite tables."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audit_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT UNIQUE,
                        timestamp REAL,
                        event_type TEXT,
                        threat_level TEXT,
                        threat_score REAL,
                        peeper_count INTEGER,
                        gaze_confidence REAL,
                        proximity REAL,
                        dwell_time REAL,
                        action_taken TEXT,
                        details TEXT
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type)
                """)
                conn.commit()

    def _subscribe_to_events(self) -> None:
        """Attaches handlers to event bus."""
        event_bus.subscribe(ThreatDetectedEvent, self._on_threat_detected)
        event_bus.subscribe(ToastAlertTriggeredEvent, self._on_toast_triggered)
        event_bus.subscribe(ShieldActivatedEvent, self._on_shield_activated)
        event_bus.subscribe(ShieldDismissedEvent, self._on_shield_dismissed)
        event_bus.subscribe(NotificationDismissedEvent, self._on_notif_dismissed)
        event_bus.subscribe(ThreatClearedEvent, self._on_threat_cleared)
        event_bus.subscribe(TrustedFaceEnrolledEvent, self._on_face_enrolled)

    def log_event(
        self,
        event_id: str,
        timestamp: float,
        event_type: str,
        threat_level: str = "NONE",
        threat_score: float = 0.0,
        peeper_count: int = 0,
        gaze_confidence: float = 0.0,
        proximity: float = 0.0,
        dwell_time: float = 0.0,
        action_taken: str = "",
        details: str = ""
    ) -> None:
        """Inserts an audit record into SQLite."""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR IGNORE INTO audit_events (
                            event_id, timestamp, event_type, threat_level,
                            threat_score, peeper_count, gaze_confidence,
                            proximity, dwell_time, action_taken, details
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_id, timestamp, event_type, threat_level,
                        threat_score, peeper_count, gaze_confidence,
                        proximity, dwell_time, action_taken, details
                    ))
                    conn.commit()
            except Exception as e:
                print(f"[AuditLogger] Error writing event: {e}")

    def _on_threat_detected(self, evt: ThreatDetectedEvent) -> None:
        self.log_event(
            event_id=evt.event_id,
            timestamp=evt.timestamp,
            event_type="THREAT_DETECTED",
            threat_level=evt.level.value,
            threat_score=evt.threat_score,
            peeper_count=evt.peeper_count,
            gaze_confidence=evt.max_gaze_confidence,
            proximity=evt.max_proximity,
            dwell_time=evt.dwell_time_seconds,
            details=f"Peeper count: {evt.peeper_count}"
        )

    def _on_toast_triggered(self, evt: ToastAlertTriggeredEvent) -> None:
        self.log_event(
            event_id=evt.event_id,
            timestamp=evt.timestamp,
            event_type="TOAST_ALERT_TRIGGERED",
            threat_score=evt.threat_score,
            peeper_count=evt.peeper_count,
            action_taken="TOAST_DISPLAYED",
            details=f"Urgency: {evt.urgency}"
        )

    def _on_shield_activated(self, evt: ShieldActivatedEvent) -> None:
        self.log_event(
            event_id=evt.event_id,
            timestamp=evt.timestamp,
            event_type="SHIELD_ACTIVATED",
            action_taken=f"STYLE_{evt.style.upper()}",
            details=f"Scope: {evt.scope}"
        )

    def _on_shield_dismissed(self, evt: ShieldDismissedEvent) -> None:
        self.log_event(
            event_id=evt.event_id,
            timestamp=evt.timestamp,
            event_type="SHIELD_DISMISSED",
            action_taken=f"METHOD_{evt.method.upper()}"
        )

    def _on_notif_dismissed(self, evt: NotificationDismissedEvent) -> None:
        self.log_event(
            event_id=evt.event_id,
            timestamp=evt.timestamp,
            event_type="NOTIFICATION_DISMISSED",
            action_taken=f"REASON_{evt.reason.upper()}"
        )

    def _on_threat_cleared(self, evt: ThreatClearedEvent) -> None:
        self.log_event(
            event_id=evt.event_id,
            timestamp=evt.timestamp,
            event_type="THREAT_CLEARED",
            details=evt.reason
        )

    def _on_face_enrolled(self, evt: TrustedFaceEnrolledEvent) -> None:
        self.log_event(
            event_id=evt.event_id,
            timestamp=evt.timestamp,
            event_type="TRUSTED_FACE_ENROLLED",
            action_taken="FACE_WHITELISTED",
            details=f"Label: {evt.label}"
        )

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent audit events for UI dashboard display."""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?
                    """, (limit,))
                    rows = cursor.fetchall()
                    return [dict(r) for r in rows]
            except Exception as e:
                print(f"[AuditLogger] Error querying events: {e}")
                return []

    def get_summary_stats(self) -> Dict[str, Any]:
        """Calculates aggregate threat statistics."""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM audit_events WHERE event_type = 'TOAST_ALERT_TRIGGERED'")
                    total_alerts = cursor.fetchone()[0]

                    cursor.execute("SELECT COUNT(*) FROM audit_events WHERE event_type = 'SHIELD_ACTIVATED'")
                    total_shields = cursor.fetchone()[0]

                    cursor.execute("SELECT MAX(threat_score) FROM audit_events")
                    max_score = cursor.fetchone()[0] or 0.0

                    return {
                        "total_alerts": total_alerts,
                        "total_shields": total_shields,
                        "peak_threat_score": round(max_score, 2)
                    }
            except Exception:
                return {"total_alerts": 0, "total_shields": 0, "peak_threat_score": 0.0}

    def clear_all_events(self) -> bool:
        """Purges all audit log records from SQLite."""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM audit_events")
                    conn.commit()
                    return True
            except Exception as e:
                print(f"[AuditLogger] Error clearing events: {e}")
                return False
