import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "ui"), str(ROOT / "app")]
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QPushButton
from ui.widgets.subtitle_editor_dialog import SubtitleEditorDialog


class SubtitleEditorExchangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.segments = [
            {"start": 0.0, "end": 1.0, "source_text": "原文", "text": "Bản cũ"},
        ]
        self.dialog = SubtitleEditorDialog(
            None,
            self.segments,
            lambda _rows: True,
            on_export_xlsx=lambda _segments: True,
            on_import_xlsx=lambda _segments: ["Bản dịch mới"],
            on_copy_ai_prompt=lambda _segments: "Dynamic English prompt",
        )

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        self.app.processEvents()

    def _button(self, text):
        return next(button for button in self.dialog.findChildren(QPushButton) if button.text() == text)

    @patch("ui.widgets.subtitle_editor_dialog.QMessageBox.information")
    def test_import_updates_only_staged_translated_cell(self, _message):
        self._button("Import XLSX…").click()
        self.assertEqual(self.dialog.table.item(0, 3).text(), "原文")
        self.assertEqual(self.dialog.table.item(0, 4).text(), "Bản dịch mới")

    @patch("ui.widgets.subtitle_editor_dialog.QMessageBox.information")
    def test_copy_prompt_uses_callback(self, _message):
        self._button("Copy AI Prompt").click()
        self.assertEqual(QApplication.clipboard().text(), "Dynamic English prompt")


if __name__ == "__main__":
    unittest.main()
