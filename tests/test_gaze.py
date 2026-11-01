"""
Tests for Guardian Shield GazeAnalyzer.
"""

import unittest
import numpy as np
from core.events import GazeDirection
from core.gaze import GazeAnalyzer


class TestGazeAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = GazeAnalyzer(sensitivity=0.55)

    def test_centered_iris_screen_gaze(self):
        # Create an eye image with iris centered
        eye = np.full((30, 50, 3), 240, dtype=np.uint8)  # White sclera
        # Center pupil (dark circle at cx=25, cy=15)
        eye[11:19, 21:29] = (20, 20, 20)

        iris_norm = self.analyzer.estimate_iris_center(eye)
        self.assertIsNotNone(iris_norm)
        ix, iy = iris_norm
        # Check normalized coords near center 0.5
        self.assertAlmostEqual(ix, 0.5, delta=0.15)
        self.assertAlmostEqual(iy, 0.5, delta=0.15)

    def test_gaze_direction_classification(self):
        eye = np.full((30, 50, 3), 240, dtype=np.uint8)
        eye[11:19, 21:29] = (20, 20, 20)

        face = np.full((120, 120, 3), 180, dtype=np.uint8)
        direction, conf = self.analyzer.analyze_gaze(
            face_roi=face,
            eye_rois=[eye],
            face_box=(100, 100, 120, 120),
            frame_shape=(480, 640)
        )
        self.assertEqual(direction, GazeDirection.AT_SCREEN)
        self.assertGreater(conf, 0.5)

    def test_diverted_gaze_looking_away(self):
        # Eye with pupil shifted all the way to extreme corner
        eye = np.full((30, 50, 3), 240, dtype=np.uint8)
        eye[12:18, 2:8] = (15, 15, 15)  # Left corner

        face = np.full((120, 120, 3), 180, dtype=np.uint8)
        direction, conf = self.analyzer.analyze_gaze(
            face_roi=face,
            eye_rois=[eye],
            face_box=(100, 100, 120, 120),
            frame_shape=(480, 640)
        )
        self.assertEqual(direction, GazeDirection.LOOKING_AWAY)


if __name__ == "__main__":
    unittest.main()
