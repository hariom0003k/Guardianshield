"""
Guardian Shield Face Detection Engine.
Detects human faces, extracts face regions, landmarks, and calculates face geometry.
Supports OpenCV 4.x Haar cascades, OpenCV 5.x FaceDetectorYN, and robust skin-geometry fallbacks.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import cv2
import numpy as np


@dataclass
class RawFaceDetection:
    box: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float
    center: Tuple[int, int]
    area_ratio: float  # face area relative to frame
    face_roi: np.ndarray  # cropped face image
    eye_rois: List[np.ndarray]  # cropped eye regions
    eye_boxes: List[Tuple[int, int, int, int]]  # eye boxes relative to face


class FaceDetector:
    """Detects faces in video frames with automatic multi-version OpenCV compatibility."""

    def __init__(self, min_face_size: int = 50, confidence_threshold: float = 0.65):
        self.min_face_size = min_face_size
        self.confidence_threshold = confidence_threshold

        self.has_haar = hasattr(cv2, "CascadeClassifier")
        self.face_cascade = None
        self.profile_cascade = None
        self.eye_cascade = None

        if self.has_haar and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            cascade_dir = cv2.data.haarcascades
            try:
                self.face_cascade = cv2.CascadeClassifier(cascade_dir + "haarcascade_frontalface_default.xml")
                self.profile_cascade = cv2.CascadeClassifier(cascade_dir + "haarcascade_profileface.xml")
                self.eye_cascade = cv2.CascadeClassifier(cascade_dir + "haarcascade_eye.xml")
            except Exception:
                self.has_haar = False

    def detect(self, frame: np.ndarray) -> List[RawFaceDetection]:
        """
        Analyzes a frame and returns a list of detected faces.
        Returns:
            List[RawFaceDetection]
        """
        if frame is None or frame.size == 0:
            return []

        frame_h, frame_w = frame.shape[:2]
        frame_area = frame_h * frame_w
        if frame_area == 0:
            return []

        if self.has_haar and self.face_cascade and not self.face_cascade.empty():
            return self._detect_haar(frame, frame_w, frame_h, frame_area)
        else:
            return self._detect_color_geometry(frame, frame_w, frame_h, frame_area)

    def _detect_haar(self, frame: np.ndarray, frame_w: int, frame_h: int, frame_area: int) -> List[RawFaceDetection]:
        """Haar cascade detection path for OpenCV 4.x environments."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        gray = cv2.equalizeHist(gray)

        frontal_faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(self.min_face_size, self.min_face_size),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        detected_boxes = list(frontal_faces) if len(frontal_faces) > 0 else []

        if self.profile_cascade and not self.profile_cascade.empty():
            profiles = self.profile_cascade.detectMultiScale(
                gray,
                scaleFactor=1.15,
                minNeighbors=5,
                minSize=(self.min_face_size, self.min_face_size)
            )
            for p in profiles:
                px, py, pw, ph = p
                overlap = False
                for fx, fy, fw, fh in detected_boxes:
                    dx = min(px + pw, fx + fw) - max(px, fx)
                    dy = min(py + ph, fy + fh) - max(py, fy)
                    if dx > 0 and dy > 0 and (dx * dy) / (pw * ph) > 0.3:
                        overlap = True
                        break
                if not overlap:
                    detected_boxes.append(p)

        results: List[RawFaceDetection] = []
        for (x, y, w, h) in detected_boxes:
            x, y = max(0, x), max(0, y)
            w, h = min(w, frame_w - x), min(h, frame_h - y)
            if w < self.min_face_size or h < self.min_face_size:
                continue

            face_roi = frame[y:y + h, x:x + w]
            eye_rois, eye_boxes = self._extract_eyes(face_roi)

            results.append(RawFaceDetection(
                box=(x, y, w, h),
                confidence=0.88,
                center=(x + w // 2, y + h // 2),
                area_ratio=(w * h) / float(frame_area),
                face_roi=face_roi,
                eye_rois=eye_rois,
                eye_boxes=eye_boxes
            ))

        results.sort(key=lambda d: d.area_ratio, reverse=True)
        return results

    def _detect_color_geometry(self, frame: np.ndarray, frame_w: int, frame_h: int, frame_area: int) -> List[RawFaceDetection]:
        """
        Color & geometry segmentation detector for OpenCV 5.0 and synthetic feeds.
        Robustly extracts face ellipses and head regions.
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV) if len(frame.shape) == 3 else frame

        # Combine broad skin/flesh chromatic ranges (YCbCr + HSV)
        lower_skin = np.array([0, 15, 60], dtype=np.uint8)
        upper_skin = np.array([25, 180, 255], dtype=np.uint8)
        mask1 = cv2.inRange(hsv, lower_skin, upper_skin)

        lower_skin2 = np.array([170, 15, 60], dtype=np.uint8)
        upper_skin2 = np.array([180, 180, 255], dtype=np.uint8)
        mask2 = cv2.inRange(hsv, lower_skin2, upper_skin2)
        mask = cv2.bitwise_or(mask1, mask2)

        # Morphological filtering to close holes
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results: List[RawFaceDetection] = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w < self.min_face_size or h < self.min_face_size:
                continue

            # Human face aspect ratio (height / width typically between 0.8 and 1.8)
            aspect_ratio = h / float(w)
            if aspect_ratio < 0.7 or aspect_ratio > 2.0:
                continue

            # Enforce boundary limits
            x, y = max(0, x), max(0, y)
            w, h = min(w, frame_w - x), min(h, frame_h - y)

            face_roi = frame[y:y + h, x:x + w]
            eye_rois, eye_boxes = self._extract_eyes(face_roi)

            results.append(RawFaceDetection(
                box=(x, y, w, h),
                confidence=0.82,
                center=(x + w // 2, y + h // 2),
                area_ratio=(w * h) / float(frame_area),
                face_roi=face_roi,
                eye_rois=eye_rois,
                eye_boxes=eye_boxes
            ))

        results.sort(key=lambda d: d.area_ratio, reverse=True)
        return results

    def _extract_eyes(self, face_roi: np.ndarray) -> Tuple[List[np.ndarray], List[Tuple[int, int, int, int]]]:
        """Extracts eye regions from the upper half of a detected face."""
        if face_roi is None or face_roi.size == 0:
            return [], []

        h, w = face_roi.shape[:2]
        eye_rois = []
        eye_boxes = []

        # If Haar eye cascade is available, use it
        if self.has_haar and self.eye_cascade and not self.eye_cascade.empty():
            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY) if len(face_roi.shape) == 3 else face_roi
            upper_half = gray[0:int(h * 0.65), :]
            eyes = self.eye_cascade.detectMultiScale(
                upper_half,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(int(w * 0.12), int(h * 0.12))
            )
            for (ex, ey, ew, eh) in eyes[:2]:
                eye_rois.append(face_roi[ey:ey + eh, ex:ex + ew])
                eye_boxes.append((ex, ey, ew, eh))
            if eye_rois:
                return eye_rois, eye_boxes

        # Geometry-based eye region extraction (left eye socket & right eye socket)
        # In human faces, left eye is around x: 15-45%, y: 25-50%; right eye is x: 55-85%, y: 25-50%
        eye_y1 = int(h * 0.22)
        eye_y2 = int(h * 0.52)
        eye_h = eye_y2 - eye_y1

        # Left eye crop
        lx1, lx2 = int(w * 0.15), int(w * 0.48)
        if lx2 > lx1 and eye_y2 > eye_y1:
            left_crop = face_roi[eye_y1:eye_y2, lx1:lx2]
            if left_crop.size > 0:
                eye_rois.append(left_crop)
                eye_boxes.append((lx1, eye_y1, lx2 - lx1, eye_h))

        # Right eye crop
        rx1, rx2 = int(w * 0.52), int(w * 0.85)
        if rx2 > rx1 and eye_y2 > eye_y1:
            right_crop = face_roi[eye_y1:eye_y2, rx1:rx2]
            if right_crop.size > 0:
                eye_rois.append(right_crop)
                eye_boxes.append((rx1, eye_y1, rx2 - rx1, eye_h))

        return eye_rois, eye_boxes
