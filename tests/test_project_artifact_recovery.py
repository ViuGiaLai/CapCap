import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.core.state import ProjectState
from app.services.project_service import ProjectService


class ProjectArtifactRecoveryTests(unittest.TestCase):
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
