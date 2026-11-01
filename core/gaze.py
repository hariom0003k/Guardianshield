"""
Guardian Shield Gaze Direction Analyzer.
Estimates iris position and facial orientation to determine if eyes are gazing towards the screen.
"""

from typing import List, Optional, Tuple
import cv2
import numpy as np

from .events import GazeDirection


class GazeAnalyzer:
    """
    Analyzes eye regions and facial orientation to detect screen-directed gaze.
    Uses iris centroid tracking relative to the sclera and face bounding geometry.
    """

    def __init__(self, sensitivity: float = 0.60):
        self.sensitivity = sensitivity

    def estimate_iris_center(self, eye_roi: np.ndarray) -> Optional[Tuple[float, float]]:
        """
        Locates the dark center of the pupil/iris within an eye crop.
        Returns normalized coordinates (norm_x, norm_y) in range [0.0, 1.0].
        """
        if eye_roi is None or eye_roi.size == 0:
            return None

        h, w = eye_roi.shape[:2]
        if h < 5 or w < 5:
            return None

        if len(eye_roi.shape) == 3:
            gray = cv2.cvtColor(eye_roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = eye_roi

        # Iris is typically the darkest circular element in the eye region
        gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(gray_blur)

        # Threshold to isolate dark iris pixels
        thresh_val = min_val + (max_val - min_val) * 0.25
        _, binary = cv2.threshold(gray_blur, thresh_val, 255, cv2.THRESH_BINARY_INV)

        # Find contours of dark regions
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            # Fall back to minimum brightness coordinate
            return (min_loc[0] / float(w), min_loc[1] / float(h))

        # Find largest contour in reasonable central area
        largest_contour = max(contours, key=cv2.contourArea)
        M = cv2.moments(largest_contour)
        if M["m00"] > 0:
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]
            return (cx / float(w), cy / float(h))

        return (min_loc[0] / float(w), min_loc[1] / float(h))

    def analyze_gaze(
        self,
        face_roi: np.ndarray,
        eye_rois: List[np.ndarray],
        face_box: Tuple[int, int, int, int],
        frame_shape: Tuple[int, int]
    ) -> Tuple[GazeDirection, float]:
        """
        Calculates gaze direction and confidence.
        Returns:
            (GazeDirection, confidence: float 0.0 to 1.0)
        """
        if not eye_rois:
            # Estimate head orientation from face symmetry if eyes cannot be individually resolved
            return self._analyze_head_orientation(face_roi, face_box, frame_shape)

        iris_scores = []
        for eye in eye_rois:
            iris_norm = self.estimate_iris_center(eye)
            if iris_norm is not None:
                ix, iy = iris_norm
                # When looking directly at the monitor, iris is centered: ix in [0.35, 0.65], iy in [0.35, 0.70]
                dist_from_center_x = abs(ix - 0.50)
                dist_from_center_y = abs(iy - 0.50)

                # Score decreases as iris moves toward outer edges of eye
                center_score = max(0.0, 1.0 - (dist_from_center_x * 2.5 + dist_from_center_y * 1.5))
                iris_scores.append(center_score)

        if not iris_scores:
            return self._analyze_head_orientation(face_roi, face_box, frame_shape)

        mean_iris_score = float(np.mean(iris_scores))

        # Check screen gaze threshold
        if mean_iris_score >= self.sensitivity:
            confidence = min(1.0, mean_iris_score)
            return GazeDirection.AT_SCREEN, confidence
        else:
            confidence = min(1.0, 1.0 - mean_iris_score)
            return GazeDirection.LOOKING_AWAY, confidence

    def _analyze_head_orientation(
        self,
        face_roi: np.ndarray,
        face_box: Tuple[int, int, int, int],
        frame_shape: Tuple[int, int]
    ) -> Tuple[GazeDirection, float]:
        """Heuristic check for head pose using horizontal brightness balance."""
        if face_roi is None or face_roi.size == 0:
            return GazeDirection.INDETERMINATE, 0.5

        h, w = face_roi.shape[:2]
        if w < 20 or h < 20:
            return GazeDirection.INDETERMINATE, 0.5

        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY) if len(face_roi.shape) == 3 else face_roi
        left_half = gray[:, :w // 2]
        right_half = gray[:, w // 2:]

        # Asymmetric lighting or feature distribution indicates head turned away
        mean_left = np.mean(left_half)
        mean_right = np.mean(right_half)
        asymmetry = abs(mean_left - mean_right) / (max(mean_left, mean_right) + 1e-5)

        if asymmetry < 0.25:
            # Face is facing approximately forward toward camera/screen
            return GazeDirection.AT_SCREEN, 0.65
        else:
            return GazeDirection.LOOKING_AWAY, 0.70
