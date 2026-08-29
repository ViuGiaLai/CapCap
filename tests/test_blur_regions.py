import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from app.layers.base import LayerType
from app.layers.blur import BlurLayer
from app.layers.sync_bridge import sync_blur_regions_to_layers
from app.layers.timeline import Timeline, Track
from app.video_processor import _build_blur_filter_chain
from ui.utils.media_backend import MpvMediaPlayerBackend


class BlurRegionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    def test_sync_keeps_layer_identity_timing_and_style_while_dragging(self):
        timeline = Timeline(duration=42.0)
        track = Track(name="B1", type=LayerType.BLUR, height=60)
        layer = BlurLayer(
            id="keep-this-id",
            name="Subtitle cover",
            start=4.0,
            end=12.0,
            position_x=0.2,
            position_y=0.7,
            width=0.4,
            height=0.12,
            blur_strength=17.0,
            pixelate=True,
            pixelate_size=18,
        )
        track.layers.append(layer)
        timeline.tracks.append(track)

        sync_blur_regions_to_layers(timeline, [{
            "x": 0.32, "y": 0.74, "width": 0.45, "height": 0.16,
        }])

        self.assertIs(track.layers[0], layer)
        self.assertEqual(layer.id, "keep-this-id")
        self.assertEqual((layer.start, layer.end), (4.0, 12.0))
        self.assertEqual(layer.blur_strength, 17.0)
        self.assertTrue(layer.pixelate)
        self.assertEqual(layer.pixelate_size, 18)
        self.assertEqual((layer.position_x, layer.position_y), (0.32, 0.74))

    def test_export_filter_contains_the_requested_blur_region(self):
        graph = _build_blur_filter_chain(
            [{"x": 0.25, "y": 0.70, "width": 0.50, "height": 0.15, "blur_strength": 20}],
            1920,
            1080,
        )
        self.assertIn("crop=w=960:h=162:x=480:y=756", graph)
        self.assertIn("boxblur=20", graph)

    def test_small_subtitle_region_clamps_radius_to_a_valid_value(self):
        graph = _build_blur_filter_chain(
            [{"x": 0.25, "y": 0.70, "width": 0.50, "height": 0.15}],
            320,
            180,
        )
        self.assertIn("crop=w=160:h=27:x=80:y=126", graph)
        self.assertIn("boxblur=13:3:6:3", graph)

    def test_live_preview_clamps_a_user_selected_radius_for_short_regions(self):
        backend = SimpleNamespace(
            _blur_region=[{
                "x": 0.25, "y": 0.70, "width": 0.50, "height": 0.15,
                "blur_strength": 20,
            }],
            video_view=SimpleNamespace(video_source_width=320, video_source_height=180),
        )
        graph = MpvMediaPlayerBackend._build_blur_body(backend)
        self.assertIn("boxblur=13:3:6:3", graph)

    def test_qt_fallback_renders_and_keeps_an_editable_blur_region(self):
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication
        from ui.widgets.video_view import VideoView

        app = QApplication.instance() or QApplication([])
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
        app.processEvents()

        self.assertTrue(view.has_blur_region())
        self.assertEqual(view.get_blur_region_normalized()["y"], 0.78)
        self.assertEqual(len(view._blur_preview_items), 1)


if __name__ == "__main__":
    unittest.main()
