import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.core.state import ProjectState
from app.services.project_service import ProjectService


class ProjectArtifactRecoveryTests(unittest.TestCase):
    def test_invalid_numbers_preserve_previous_file_and_clean_temporary_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "timeline.json"
            original = {"duration": 5.0}
            ProjectService._atomic_write_json(str(target), original)
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.assertRaises(ValueError):
                    ProjectService._atomic_write_json(str(target), {"duration": value})
                self.assertEqual(json.loads(target.read_text(encoding="utf-8")), original)
                self.assertEqual(list(Path(temp_dir).glob("*.tmp")), [])

    def test_failed_replace_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "project.json"
            ProjectService._atomic_write_json(str(target), {"version": 1})
            with patch("app.services.project_service.os.replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    ProjectService._atomic_write_json(str(target), {"version": 2})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"version": 1})
            self.assertEqual(list(Path(temp_dir).glob("*.tmp")), [])

    def test_missing_or_corrupt_artifact_returns_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ProjectService(temp_dir)
            state = ProjectState(
                project_id="demo",
                project_root=str(Path(temp_dir) / "projects" / "demo"),
                input_video="",
            )
            service._ensure_project_dirs(state.project_root)
            missing = "missing.json"
            state.set_artifact("broken", str(Path(state.project_root) / missing))
            self.assertEqual(service.load_json_artifact(state, "broken", default={"ok": False}), {"ok": False})

            broken_path = Path(state.project_root) / "analysis" / "broken.json"
            broken_path.write_text("{not valid json", encoding="utf-8")
            state.set_artifact("broken", str(broken_path))
            self.assertEqual(service.load_json_artifact(state, "broken", default=[]), [])

    def test_valid_artifact_still_loads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ProjectService(temp_dir)
            state = ProjectState(
                project_id="demo",
                project_root=str(Path(temp_dir) / "projects" / "demo"),
                input_video="",
            )
            service._ensure_project_dirs(state.project_root)
            artifact_path = Path(state.project_root) / "analysis" / "ok.json"
            artifact_path.write_text(json.dumps({"value": 42}), encoding="utf-8")
            state.set_artifact("ok", str(artifact_path))
            self.assertEqual(service.load_json_artifact(state, "ok"), {"value": 42})


if __name__ == "__main__":
    unittest.main()
