"""
Guardian Shield Face Recognition & Whitelist Engine.
Differentiates the primary authenticated user and trusted colleagues from unauthorized peepers.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from .events import FaceIdentity


@dataclass
class FaceProfile:
    profile_id: str
    label: str
    identity: FaceIdentity
    embedding: List[float]
    enrolled_at: float = field(default_factory=time.time)


class FaceRecognizer:
    """
    Computes facial feature signatures, enrolls the primary owner,
    maintains a registry of trusted profiles, and classifies faces.
    """

    def __init__(
        self,
        tolerance: float = 0.20,
        profiles_file: str = "trusted_profiles.json"
    ):
        self.tolerance = tolerance
        self.profiles_file = Path(profiles_file)
        self.profiles: Dict[str, FaceProfile] = {}
        self.primary_profile_id: Optional[str] = None
        self._load_profiles()

    def _compute_embedding(self, face_roi: np.ndarray) -> np.ndarray:
        """
        Extracts a normalized, rotation/illumination-invariant feature vector.
        Combines spatial grid HSV color distributions, gradient magnitude, and texture histograms.
        """
        if face_roi is None or face_roi.size == 0:
            return np.zeros(256, dtype=np.float32)

        # Standardize face patch dimensions
        target_size = (96, 96)
        resized = cv2.resize(face_roi, target_size, interpolation=cv2.INTER_AREA)

        # 1. Grayscale & HSV representations
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)

        # 2. Multi-region spatial histograms (3x3 grid)
        features = []
        cell_h, cell_w = 32, 32

        for row in range(3):
            for col in range(3):
                y1, y2 = row * cell_h, (row + 1) * cell_h
                x1, x2 = col * cell_w, (col + 1) * cell_w

                cell_gray = gray[y1:y2, x1:x2]
                cell_hsv = hsv[y1:y2, x1:x2]

                # Grayscale intensity histogram (16 bins)
                hist_gray = cv2.calcHist([cell_gray], [0], None, [16], [0, 256])
                cv2.normalize(hist_gray, hist_gray)
                features.extend(hist_gray.flatten())

                # Hue histogram (8 bins)
                hist_hue = cv2.calcHist([cell_hsv], [0], None, [8], [0, 180])
                cv2.normalize(hist_hue, hist_hue)
                features.extend(hist_hue.flatten())

        # 3. Sobel edge gradients for contour structure
        sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(sobel_x, sobel_y)
        mag_hist = cv2.calcHist([mag.astype(np.uint8)], [0], None, [40], [0, 256])
        cv2.normalize(mag_hist, mag_hist)
        features.extend(mag_hist.flatten())

        # 4. Global color and intensity moments
        mean_val, std_val = cv2.meanStdDev(resized)
        features.extend((mean_val.flatten() / 255.0).tolist())
        features.extend((std_val.flatten() / 255.0).tolist())

        emb = np.array(features, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 1e-6:
            emb /= norm
        return emb

    def _calculate_distance(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Calculates cosine distance between two feature vectors [0.0 = identical, 2.0 = opposite]."""
        dot = np.dot(emb1, emb2)
        return float(1.0 - np.clip(dot, -1.0, 1.0))

    def enroll_primary_user(self, face_roi: np.ndarray, label: str = "Primary User") -> str:
        """Enrolls the primary device owner."""
        emb = self._compute_embedding(face_roi)
        profile_id = f"owner_{int(time.time())}"
        profile = FaceProfile(
            profile_id=profile_id,
            label=label,
            identity=FaceIdentity.PRIMARY_USER,
            embedding=emb.tolist()
        )
        self.profiles[profile_id] = profile
        self.primary_profile_id = profile_id
        self._save_profiles()
        return profile_id

    def enroll_trusted_face(self, face_roi: np.ndarray, label: str = "Trusted Colleague") -> str:
        """Enrolls a trusted colleague/friend who should not trigger shoulder-surfing alerts."""
        emb = self._compute_embedding(face_roi)
        profile_id = f"trusted_{int(time.time())}"
        profile = FaceProfile(
            profile_id=profile_id,
            label=label,
            identity=FaceIdentity.TRUSTED_USER,
            embedding=emb.tolist()
        )
        self.profiles[profile_id] = profile
        self._save_profiles()
        return profile_id

    def classify_face(self, face_roi: np.ndarray) -> Tuple[FaceIdentity, float, Optional[str]]:
        """
        Classifies a detected face against enrolled profiles.
        Returns:
            (FaceIdentity, match_confidence, profile_id)
        """
        if not self.profiles:
            # If no user enrolled yet, treat the first detected face as Primary User dynamically
            profile_id = self.enroll_primary_user(face_roi, "Auto-Enrolled Primary User")
            return FaceIdentity.PRIMARY_USER, 1.0, profile_id

        emb = self._compute_embedding(face_roi)
        best_match_id: Optional[str] = None
        min_distance = 999.0

        for pid, profile in self.profiles.items():
            ref_emb = np.array(profile.embedding, dtype=np.float32)
            dist = self._calculate_distance(emb, ref_emb)
            if dist < min_distance:
                min_distance = dist
                best_match_id = pid

        # Check if best match is within tolerance threshold
        if best_match_id and min_distance <= self.tolerance:
            match_confidence = max(0.0, 1.0 - (min_distance / self.tolerance))
            matched_profile = self.profiles[best_match_id]
            return matched_profile.identity, match_confidence, best_match_id

        # Face did not match any enrolled owner or trusted profile -> UNAUTHORIZED_PEEPER
        peeper_confidence = min(1.0, min_distance)
        return FaceIdentity.UNAUTHORIZED_PEEPER, peeper_confidence, None

    def classify_scene(
        self,
        detections: List[Any]
    ) -> List[Tuple[FaceIdentity, float, Optional[str]]]:
        """
        Classifies all faces in a scene enforcing strict single-owner semantics:
        1. At most ONE face in any scene can be the PRIMARY_USER.
        2. Any SECOND or additional face is NEVER taken as primary user.
        3. A secondary face is ONLY trusted if explicitly enrolled in trusted whitelist with strict match.
        4. ALL other secondary faces are marked UNAUTHORIZED_PEEPER!
        """
        if not detections:
            return []

        # If only 1 face detected, standard classification
        if len(detections) == 1:
            return [self.classify_face(detections[0].face_roi)]

        # Multiple faces detected in frame (2 or more people):
        # 1. Identify which face is the primary user
        best_owner_idx = 0
        best_owner_dist = 999.0

        owner_profile = self.profiles.get(self.primary_profile_id) if self.primary_profile_id else None
        if not owner_profile:
            for p in self.profiles.values():
                if p.identity == FaceIdentity.PRIMARY_USER:
                    owner_profile = p
                    break

        if owner_profile:
            ref_emb = np.array(owner_profile.embedding, dtype=np.float32)
            for idx, d in enumerate(detections):
                emb = self._compute_embedding(d.face_roi)
                dist = self._calculate_distance(emb, ref_emb)
                if dist < best_owner_dist:
                    best_owner_dist = dist
                    best_owner_idx = idx
        else:
            # If no owner enrolled yet, the largest face is the primary owner
            best_owner_idx = max(range(len(detections)), key=lambda i: getattr(detections[i], "area_ratio", 0.0))

        results = []
        for idx, d in enumerate(detections):
            if idx == best_owner_idx:
                # Primary user face slot
                if owner_profile and best_owner_dist <= self.tolerance:
                    conf = max(0.0, 1.0 - (best_owner_dist / self.tolerance))
                    results.append((FaceIdentity.PRIMARY_USER, conf, owner_profile.profile_id))
                elif not owner_profile:
                    pid = self.enroll_primary_user(d.face_roi, "Auto-Enrolled Primary User")
                    results.append((FaceIdentity.PRIMARY_USER, 1.0, pid))
                else:
                    results.append((FaceIdentity.PRIMARY_USER, 0.85, owner_profile.profile_id if owner_profile else ""))
            else:
                # SECONDARY FACE (Second person added!)
                # Rule: NEVER treat secondary face as primary user.
                # Rule: Do NOT take everyone as trusted. Only check explicit TRUSTED_USER with strict tolerance.
                emb = self._compute_embedding(d.face_roi)
                matched_trusted = False
                trusted_pid = None
                trusted_conf = 0.0

                for pid, profile in self.profiles.items():
                    if profile.identity == FaceIdentity.TRUSTED_USER:
                        ref_emb = np.array(profile.embedding, dtype=np.float32)
                        dist = self._calculate_distance(emb, ref_emb)
                        if dist <= (self.tolerance * 0.75):  # Strict 0.15 threshold
                            matched_trusted = True
                            trusted_pid = pid
                            trusted_conf = max(0.0, 1.0 - (dist / self.tolerance))
                            break

                if matched_trusted:
                    results.append((FaceIdentity.TRUSTED_USER, trusted_conf, trusted_pid))
                else:
                    # SECOND PERSON IS AN UNAUTHORIZED PEEPER!
                    results.append((FaceIdentity.UNAUTHORIZED_PEEPER, 0.95, None))

        return results

    def _save_profiles(self) -> None:
        """Saves enrolled profiles to JSON."""
        data = {
            "primary_profile_id": self.primary_profile_id,
            "profiles": [
                {
                    "profile_id": p.profile_id,
                    "label": p.label,
                    "identity": p.identity.value,
                    "embedding": p.embedding,
                    "enrolled_at": p.enrolled_at
                }
                for p in self.profiles.values()
            ]
        }
        try:
            with open(self.profiles_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[FaceRecognizer] Error saving profiles: {e}")

    def _load_profiles(self) -> None:
        """Loads enrolled profiles from disk."""
        if not self.profiles_file.exists():
            return
        try:
            with open(self.profiles_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.primary_profile_id = data.get("primary_profile_id")
            for item in data.get("profiles", []):
                profile = FaceProfile(
                    profile_id=item["profile_id"],
                    label=item["label"],
                    identity=FaceIdentity(item["identity"]),
                    embedding=item["embedding"],
                    enrolled_at=item.get("enrolled_at", time.time())
                )
                self.profiles[profile.profile_id] = profile
        except Exception as e:
            print(f"[FaceRecognizer] Error reading profiles: {e}")
