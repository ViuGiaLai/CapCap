import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "ui"), os.path.join(ROOT, "app"), ROOT]

from PySide6.QtWidgets import QApplication

from main_window import VideoTranslatorGUI


class StudioShellNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = VideoTranslatorGUI()

    def tearDown(self):
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()

    def test_navigation_rail_proxies_existing_workflow_stack(self):
        source = patch.object(self.window, "resolve_canonical_video_path", return_value=__file__)
        source.start()
        self.addCleanup(source.stop)
        self.window.update_workflow_availability()
        self.assertEqual(
            set(self.window.navigation_buttons),
            {"source", "audio", "captions", "voice", "style", "advanced"},
        )
        for key, index in (("source", 0), ("audio", 1), ("captions", 2),
                           ("voice", 3), ("style", 4), ("advanced", 5)):
            self.window.navigation_buttons[key].click()
            self.app.processEvents()
            self.assertEqual(self.window.left_panel_stack.currentIndex(), index)
            self.assertTrue(self.window.navigation_buttons[key].isChecked())
            legacy_key = {"source": "media", "captions": "language"}.get(key, key)
            self.assertTrue(self.window.workflow_tab_buttons[legacy_key].isChecked())

    def test_empty_project_locks_the_same_pages_on_both_navigation_controls(self):
        with patch.object(self.window, "resolve_canonical_video_path", return_value=""):
            self.window.update_workflow_availability()
            for key in ("audio", "captions", "voice", "style"):
                self.assertFalse(self.window.navigation_buttons[key].isEnabled())
                self.window.navigation_buttons[key].click()
                self.assertEqual(self.window.left_panel_stack.currentIndex(), 0)
            self.window.navigation_buttons["advanced"].click()
            self.window.update_workflow_availability()
            self.assertEqual(self.window.left_panel_stack.currentIndex(), 5)

    def test_voice_controls_follow_output_mode_independently_of_timing_mode(self):
        with patch.object(self.window, "resolve_canonical_video_path", return_value=__file__), \
             patch.object(self.window, "using_existing_audio_source", return_value=False), \
             patch.object(self.window, "_translation_phase_complete", return_value=True):
            self.window.translated_text.setPlainText("Translated dialogue")
            for output_index in range(self.window.output_mode_combo.count()):
                self.window.output_mode_combo.setCurrentIndex(output_index)
                wants_voice = self.window.get_output_mode_key() in ("voice", "both")
                for timing_index in range(self.window.voice_timing_sync_combo.count()):
                    self.window.voice_timing_sync_combo.setCurrentIndex(timing_index)
                    self.window.refresh_ui_state()
                    self.assertEqual(self.window.voice_engine_combo.isEnabled(), wants_voice)
                self.assertEqual(self.window.use_generated_audio_radio.isHidden(), not wants_voice)

    def test_legacy_duplicate_tab_bar_is_hidden_but_controls_remain_available(self):
        self.assertFalse(self.window.workflow_tab_bar.isVisible())
        self.assertEqual(len(self.window.workflow_tab_buttons), 6)

    def test_output_controls_keep_a_usable_height_in_compact_workbench(self):
        # The controls live in nested vertical layouts.  Without an explicit
        # minimum height Qt can legally squeeze the lower rows to 10px while
        # the scroll area is resolving its content size, making their labels
        # appear blank or clipped.
        for name in (
            "output_quality_combo",
            "output_fps_combo",
            "output_ratio_combo",
            "output_scale_mode_combo",
        ):
            control = getattr(self.window, name)
            self.assertGreaterEqual(control.minimumHeight(), 32)
            self.assertGreaterEqual(control.height(), 32)
        self.assertFalse(self.window.reset_framing_btn.isVisible())


if __name__ == "__main__":
    unittest.main()
