import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app"), str(ROOT / "ui")]

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from features.timeline_selection import TimelineSelectionMixin
from widgets.video_view import VideoView


APP = QApplication.instance() or QApplication([])


class _SelectionHarness(TimelineSelectionMixin):
    def _preview_is_playing(self):
        return False

    def refresh_timed_layer_preview(self):
        return None


class BlurPreviewTests(unittest.TestCase):
    def test_selected_blur_is_not_suppressed_while_editing(self):
        harness = _SelectionHarness()
        harness._deferred_effect_edit_type = ""
        harness._deferred_effect_edit_layer_id = ""
        track = SimpleNamespace(name="B1")
        layer = SimpleNamespace(id="blur-1", type=SimpleNamespace(value="blur"))

        harness._set_deferred_effect_edit_target(track, layer)

        self.assertEqual(harness._deferred_effect_layer_id_for("blur"), "")

    def test_qt_fallback_renders_blur_without_mpv(self):
        view = VideoView()
        view.resize(640, 360)
        view.set_video_dimensions(1280, 720)
        view._last_video_image = QImage(1280, 720, QImage.Format_RGB32)
        view._last_video_image.fill(QColor("red"))
        region = {
            "x": 0.15,
            "y": 0.78,
            "width": 0.70,
            "height": 0.18,
            "blur_strength": 20,
        }

        view.set_blur_regions_normalized([region])
        view.set_blur_effect_regions([region])
        APP.processEvents()

        self.assertTrue(view.has_blur_region())
        self.assertEqual(view.get_blur_region_normalized()["y"], 0.78)
        self.assertEqual(len(view._blur_preview_items), 1)


if __name__ == "__main__":
    unittest.main()
