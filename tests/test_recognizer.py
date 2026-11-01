"""
Tests for Guardian Shield FaceRecognizer and Whitelist Engine.
"""

import os
import unittest
import numpy as np
from core.events import FaceIdentity
from core.recognizer import FaceRecognizer


class TestFaceRecognizer(unittest.TestCase):

    def setUp(self):
        self.test_profiles_file = "test_profiles.json"
        if os.path.exists(self.test_profiles_file):
            os.remove(self.test_profiles_file)
        self.recognizer = FaceRecognizer(
            tolerance=0.35,
            profiles_file=self.test_profiles_file
        )

    def tearDown(self):
        if os.path.exists(self.test_profiles_file):
            os.remove(self.test_profiles_file)

    def test_auto_enroll_first_face_as_primary(self):
        dummy_face = np.full((100, 100, 3), 128, dtype=np.uint8)
        identity, conf, pid = self.recognizer.classify_face(dummy_face)
        self.assertEqual(identity, FaceIdentity.PRIMARY_USER)
        self.assertIsNotNone(pid)

    def test_match_enrolled_primary_user(self):
        # Create face patch A
        face_a = np.zeros((100, 100, 3), dtype=np.uint8)
        face_a[30:70, 30:70] = (200, 180, 160)
        self.recognizer.enroll_primary_user(face_a, "Owner")

        # Classify the same or slightly shifted face
        identity, conf, pid = self.recognizer.classify_face(face_a)
        self.assertEqual(identity, FaceIdentity.PRIMARY_USER)

    def test_unauthorized_face_classification(self):
        # Enroll user
        user_face = np.full((100, 100, 3), 50, dtype=np.uint8)
        self.recognizer.enroll_primary_user(user_face, "Owner")

        # Very distinct unknown face
        peeper_face = np.full((100, 100, 3), 240, dtype=np.uint8)
        identity, conf, pid = self.recognizer.classify_face(peeper_face)
        self.assertEqual(identity, FaceIdentity.UNAUTHORIZED_PEEPER)

    def test_trusted_face_whitelist(self):
        colleague_face = np.zeros((100, 100, 3), dtype=np.uint8)
        colleague_face[:, :] = (10, 180, 50)
        self.recognizer.enroll_trusted_face(colleague_face, "Colleague Alice")

        identity, conf, pid = self.recognizer.classify_face(colleague_face)
        self.assertEqual(identity, FaceIdentity.TRUSTED_USER)

    def test_second_person_classified_as_peeper(self):
        class MockDet:
            def __init__(self, face_roi, area_ratio):
                self.face_roi = face_roi
                self.area_ratio = area_ratio

        face_owner = np.zeros((100, 100, 3), dtype=np.uint8)
        face_owner[30:70, 30:70] = (200, 180, 160)
        self.recognizer.enroll_primary_user(face_owner, "Owner")

        face_second_person = np.full((100, 100, 3), 190, dtype=np.uint8)

        detections = [
            MockDet(face_owner, 0.15),
            MockDet(face_second_person, 0.08)
        ]

        results = self.recognizer.classify_scene(detections)
        self.assertEqual(len(results), 2)
        # Face 1 is Primary Owner
        self.assertEqual(results[0][0], FaceIdentity.PRIMARY_USER)
        # Face 2 (second person added) MUST be UNAUTHORIZED_PEEPER!
        self.assertEqual(results[1][0], FaceIdentity.UNAUTHORIZED_PEEPER)


if __name__ == "__main__":
    unittest.main()
