"""Regression tests for the Studio shell wired into the real main window."""

from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "ui"), os.path.join(ROOT, "app"), ROOT]

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.layers.base import LayerType
from app.layers.blur import BlurLayer
from app.layers.timeline import Timeline, Track
from main_window import VideoTranslatorGUI


APP = QApplication.instance() or QApplication([])


class StudioShellIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.window = VideoTranslatorGUI()
        self.window.resize(1280, 720)
        self.window.show()
        QTest.qWait(5)

    def tearDown(self):
        self.window.close()
        QTest.qWait(1)

    def test_shell_is_visible_and_legacy_actions_are_bound(self):
        self.assertTrue(self.window.studio_app_bar.isVisible())
        self.assertTrue(self.window.studio_tool_rail.isVisible())
        self.assertTrue(self.window.studio_app_bar.minimize_btn.isVisible())
        self.assertTrue(self.window.studio_app_bar.maximize_btn.isVisible())
        self.assertTrue(self.window.studio_app_bar.close_btn.isVisible())
        self.assertFalse(self.window.left_panel_scroll_area.isVisible())
        self.assertTrue(self.window._inspector_collapsed)
        self.assertEqual(
            self.window.studio_app_bar.generate_btn.isEnabled(),
            self.window.run_all_btn.isEnabled(),
        )
        self.assertEqual(
            self.window.studio_app_bar.export_btn.isEnabled(),
            self.window.export_btn.isEnabled(),
        )

    def test_tool_rail_opens_a_studio_task_panel_without_revealing_legacy_ui(self):
        rail = self.window.studio_tool_rail
        rail._buttons["subtitles"].click()
        QTest.qWait(1)
        self.assertTrue(self.window.studio_task_panel.isVisible())
        self.assertEqual(self.window.studio_task_panel.title.text(), "Subtitles")
        self.assertFalse(self.window.left_panel_scroll_area.isVisible())
        rail._buttons["subtitles"].click()
        QTest.qWait(1)
        self.assertFalse(self.window.studio_task_panel.isVisible())

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

        self.assertIs(
            self.window.inspector_stack,
            self.window.studio_inspector.editor_stack,
        )
        self.assertEqual(self.window.inspector_stack.currentIndex(), 2)
        self.assertTrue(self.window.blur_inspector_radius_slider.isVisible())
        self.window.blur_inspector_radius_slider.setValue(9)
        self.window.blur_inspector_start_spin.setValue(2.0)
        self.assertEqual(layer.blur_strength, 9)
        self.assertEqual(layer.start, 2.0)


if __name__ == "__main__":
    unittest.main()
