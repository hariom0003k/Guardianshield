"""
Tests for Guardian Shield ThreatClassifier.
"""

import time
import unittest
from core.events import FaceIdentity, FaceMetadata, GazeDirection, ThreatLevel
from core.threat import ThreatClassifier


class TestThreatClassifier(unittest.TestCase):

    def setUp(self):
        self.classifier = ThreatClassifier(
            gaze_weight=0.40,
            proximity_weight=0.30,
            dwell_weight=0.20,
            peeper_count_weight=0.10,
            toast_threshold=0.45,
            auto_shield_threshold=0.80,
            debounce_seconds=0.2,  # Short debounce for quick tests
            auto_shield_enabled=False
        )

    def test_primary_user_alone_is_safe(self):
        faces = [
            FaceMetadata(
                box=(200, 150, 120, 120),
                identity=FaceIdentity.PRIMARY_USER,
                confidence=0.95,
                gaze=GazeDirection.AT_SCREEN,
                gaze_confidence=0.90,
                proximity_ratio=0.15
            )
        ]
        res = self.classifier.evaluate(faces)
        self.assertEqual(res.threat_level, ThreatLevel.NONE)
        self.assertEqual(res.threat_score, 0.0)
        self.assertFalse(res.should_alert)

    def test_peeper_looking_away_is_safe(self):
        faces = [
            FaceMetadata(
                box=(200, 150, 120, 120),
                identity=FaceIdentity.PRIMARY_USER,
                confidence=0.95,
                gaze=GazeDirection.AT_SCREEN,
                gaze_confidence=0.90,
                proximity_ratio=0.15
            ),
            FaceMetadata(
                box=(400, 100, 80, 80),
                identity=FaceIdentity.UNAUTHORIZED_PEEPER,
                confidence=0.90,
                gaze=GazeDirection.LOOKING_AWAY,
                gaze_confidence=0.20,
                proximity_ratio=0.04
            )
        ]
        res = self.classifier.evaluate(faces)
        self.assertEqual(res.threat_level, ThreatLevel.NONE)
        self.assertFalse(res.should_alert)

    def test_peeper_gazing_triggers_alert_after_debounce(self):
        faces = [
            FaceMetadata(
                box=(200, 150, 120, 120),
                identity=FaceIdentity.PRIMARY_USER,
                confidence=0.95,
                gaze=GazeDirection.AT_SCREEN,
                gaze_confidence=0.90,
                proximity_ratio=0.15
            ),
            FaceMetadata(
                box=(400, 100, 100, 100),
                identity=FaceIdentity.UNAUTHORIZED_PEEPER,
                confidence=0.92,
                gaze=GazeDirection.AT_SCREEN,
                gaze_confidence=0.90,
                proximity_ratio=0.09
            )
        ]

        # First evaluation: dwell time < debounce_seconds -> no alert yet
        res1 = self.classifier.evaluate(faces)
        self.assertFalse(res1.should_alert)

        # Wait for debounce duration
        time.sleep(0.25)

        # Second evaluation: debounced -> alert triggered
        res2 = self.classifier.evaluate(faces)
        self.assertTrue(res2.should_alert)
        self.assertIn(res2.threat_level, (ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL))

    def test_auto_shield_mode(self):
        self.classifier.auto_shield_enabled = True
        critical_faces = [
            FaceMetadata(
                box=(300, 100, 150, 150),
                identity=FaceIdentity.UNAUTHORIZED_PEEPER,
                confidence=0.98,
                gaze=GazeDirection.AT_SCREEN,
                gaze_confidence=0.99,
                proximity_ratio=0.18
            )
        ]
        self.classifier.first_detected_time = time.time() - 3.0  # Simulate sustained dwell
        res = self.classifier.evaluate(critical_faces)
        self.assertTrue(res.should_auto_shield)


if __name__ == "__main__":
    unittest.main()
