import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "ui"), os.path.join(ROOT, "app"), ROOT]
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from app.services import ProjectService
from views.launcher import LauncherWindow


class LauncherProjectRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_duplicate_recent_rows_and_project_discovery_render_one_card(self):
        with tempfile.TemporaryDirectory() as root:
            service = ProjectService(root)
            state = service.create_project()
            state_path = service.project_file(state.project_root)
            recent = [
                {"project_state_path": state_path, "opened_at": 20},
                {"project_state_path": state_path, "opened_at": 0},
            ]
            with open(os.path.join(root, "recent_projects.json"), "w", encoding="utf-8") as handle:
                json.dump(recent, handle)

            with patch("views.launcher.workspace_root", return_value=root):
                launcher = LauncherWindow()
                launcher._load_recent()
                self.assertEqual(launcher.grid.count(), 1)
                card = launcher.grid.itemAt(0).widget()
                self.assertEqual(card.name_label.text(), "VIUSTUDIO10000")
                launcher.deleteLater()
                self.app.processEvents()

    def test_recent_project_outside_workspace_is_rejected(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as external:
            state = ProjectService(external).create_project()
            with patch("views.launcher.workspace_root", return_value=workspace):
                record = LauncherWindow._normalize_recent_record({
                    "project_state_path": os.path.join(state.project_root, "project.json"),
                })
            self.assertIsNone(record)


if __name__ == "__main__":
    unittest.main()
