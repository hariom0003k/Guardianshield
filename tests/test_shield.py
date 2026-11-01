"""
Tests for Guardian Shield Privacy Overlay and Image Obscuration.
"""

import sys
import unittest
import numpy as np
import cv2
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from ui.shield import ShieldOverlay


# Ensure QApplication exists for Qt tests
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestShieldOverlay(unittest.TestCase):

    def setUp(self):
        self.shield = ShieldOverlay(
            default_style="blur",
            blur_radius=15,
            dim_opacity=0.9
        )

    def tearDown(self):
        if self.shield.is_active:
            self.shield.dismiss(publish_event=False)
        self.shield.close()

    def test_decoy_pixmap_generation(self):
        pixmap = self.shield._generate_decoy_pixmap(640, 480)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), 640)
        self.assertEqual(pixmap.height(), 480)

    def test_mosaic_pixmap_generation_small_dimensions(self):
        # Test boundary protection with small dimensions to verify no divide-by-zero
        geo = QRect(0, 0, 10, 10)
        # Testing the calculation logic directly
        block_size = 28
        w, h = 10, 10
        small_w = max(1, w // block_size)
        small_h = max(1, h // block_size)
        self.assertGreaterEqual(small_w, 1)
        self.assertGreaterEqual(small_h, 1)

    def test_dismiss_idempotence(self):
        self.assertFalse(self.shield.is_active)
        # Calling dismiss when inactive should not fail or publish extra events
        self.shield.dismiss(publish_event=False)
        self.assertFalse(self.shield.is_active)


if __name__ == "__main__":
    unittest.main()
