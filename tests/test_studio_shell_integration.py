import os
import sys
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "ui"), os.path.join(ROOT, "app"), ROOT]
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from app.layers.base import LayerType
from app.layers.blur import BlurLayer
from app.layers.timeline import Timeline, Track
from main_window import VideoTranslatorGUI


class TestStudioShellIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = VideoTranslatorGUI()

    def test_selected_blur_uses_the_real_editable_inspector(self):
        timeline = Timeline(duration=10.0)
        track = Track(name="B1", type=LayerType.BLUR, height=60)
        layer = BlurLayer(name="Blur 1", start=1.0, end=6.0)
        track.layers.append(layer)
        timeline.tracks.append(track)
        self.window.timeline._timeline = timeline
        self.window.timeline._duration = timeline.duration
        self.window.timeline._selected_layer_id = layer.id

        self.window.on_timeline_layer_selected(layer.id)
        QTest.qWait(1)

        self.assertEqual(self.window.inspector_stack.currentIndex(), 2)
        if hasattr(self.window, "blur_inspector_radius_slider"):
            self.window.blur_inspector_radius_slider.setValue(9)
            self.window.blur_inspector_start_spin.setValue(2.0)
            self.assertEqual(layer.blur_strength, 9)
            self.assertEqual(layer.start, 2.0)

    def test_blur_controls_update_selected_region_without_replacing_others(self):
        timeline = Timeline(duration=10.0)
        track = Track(name="B1", type=LayerType.BLUR, height=60)
        first = BlurLayer(name="Blur 1", start=0.0, end=10.0,
                          position_x=0.1, position_y=0.1, width=0.3, height=0.2)
        second = BlurLayer(name="Blur 2", start=0.0, end=10.0,
                           position_x=0.5, position_y=0.6, width=0.4, height=0.2)
        track.layers.extend([first, second])
        timeline.tracks.append(track)
        self.window.timeline._timeline = timeline
        self.window.timeline._duration = timeline.duration
        self.window.timeline._selected_layer_id = second.id
        self.window.video_view.set_blur_regions_normalized([
            {"x": first.position_x, "y": first.position_y,
             "width": first.width, "height": first.height},
            {"x": second.position_x, "y": second.position_y,
             "width": second.width, "height": second.height},
        ])

        self.window.on_timeline_layer_selected(second.id)
        self.window.blur_inspector_radius_slider.setValue(55)
        self.window.blur_inspector_opacity_slider.setValue(40)
        self.window.blur_inspector_pixelate_cb.setChecked(True)
        self.window.blur_inspector_pixel_size_slider.setValue(24)
        QTest.qWait(1)

        self.assertEqual(first.blur_strength, 36.0)
        self.assertEqual(second.blur_strength, 55)
        self.assertAlmostEqual(second.blur_opacity, 0.4)
        self.assertTrue(second.pixelate)
        self.assertEqual(second.pixelate_size, 24)
        regions = self.window.video_view.get_blur_region_normalized()
        self.assertIsInstance(regions, list)
        self.assertEqual(len(regions), 2)

    def test_track_label_click_selects_layer_and_opens_inspector(self):
        timeline = Timeline(duration=10.0)
        track = Track(name="B1", type=LayerType.BLUR, height=60)
        layer = BlurLayer(name="Blur 1", start=0.0, end=10.0)
        track.layers.append(layer)
        timeline.tracks.append(track)
        self.window.timeline._timeline = timeline
        self.window.timeline._duration = timeline.duration

        self.window.on_track_label_selected("B1")
        QTest.qWait(1)

        self.assertEqual(self.window.timeline._selected_layer_id, layer.id)
        self.assertEqual(self.window.inspector_stack.currentIndex(), 2)

    def test_layer_menu_is_available_for_any_loaded_video(self):
        with tempfile.TemporaryDirectory() as folder:
            video_path = Path(folder) / "source.mp4"
            video_path.touch()
            self.window.video_path_edit.setText(str(video_path))
            self.window.current_segments = []
            self.window.current_translated_segments = []

            self.window.refresh_ui_state()

            self.assertTrue(self.window.add_layer_btn.isEnabled())
            self.assertTrue(self.window.timeline_layers_btn.isEnabled())

    def test_timeline_zoom_icons_execute_real_actions(self):
        self.assertFalse(self.window.timeline_zoom_out_btn.icon().isNull())
        self.assertFalse(self.window.timeline_zoom_in_btn.icon().isNull())
        self.assertFalse(self.window.timeline_zoom_reset_btn.icon().isNull())
        before = self.window.timeline.zoom_percent()

        self.window.timeline_zoom_in_btn.click()
        QTest.qWait(1)

        self.assertGreater(self.window.timeline.zoom_percent(), before)
        self.window.timeline_zoom_reset_btn.click()
        self.assertEqual(self.window.timeline.zoom_percent(), 100)

    def test_locked_track_layer_remains_clickable_for_inspection(self):
        timeline = Timeline(duration=10.0)
        track = Track(name="B1", type=LayerType.BLUR, height=60, locked=True)
        layer = BlurLayer(name="Blur 1", start=0.0, end=10.0)
        track.layers.append(layer)
        timeline.tracks.append(track)
        widget = self.window.timeline
        widget._timeline = timeline
        widget._duration = timeline.duration
        widget._track_heights[track.id] = 60
        widget.resize(900, 220)
        widget.show()
        widget._redraw()
        spy = QSignalSpy(widget.layerSelected)
        x = widget.CONTENT_LEFT_PAD + round(5 * widget.pixels_per_second)
        y = widget.RULER_HEIGHT + 30

        QTest.mouseClick(widget.viewport(), Qt.LeftButton, pos=QPoint(x, y))

        self.assertEqual(widget._selected_layer_id, layer.id)
        self.assertEqual(spy.count(), 1)


if __name__ == "__main__":
    unittest.main()
