import os
import sys
import unittest

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
