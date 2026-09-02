import json
import os
import sys
import tempfile
import unittest

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from app.layers.base import LayerType
from app.layers.text import TextLayer
from app.layers.timeline import Timeline, Track
from app.workflows.export_workflow import ExportWorkflow
from core.state.project_state import ProjectState


class ExportOverlayTests(unittest.TestCase):
    def test_detects_visible_timeline_text_layers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state = ProjectState(project_id="p1", project_root=temp_dir, input_video="video.mp4")
            timeline = Timeline()
            track = Track(name="T1 Text", type=LayerType.TEXT)
            layer = TextLayer(text="Hello", start=0.0, end=5.0)
            layer.transform.x = 0.5
            layer.transform.y = 0.5
            track.layers.append(layer)
            timeline.tracks.append(track)

            timeline_path = os.path.join(temp_dir, "timeline", "timeline.json")
            os.makedirs(os.path.dirname(timeline_path), exist_ok=True)
            with open(timeline_path, "w", encoding="utf-8") as handle:
                json.dump(timeline.to_dict(), handle)
            state.artifacts["timeline"] = timeline_path

            workflow = ExportWorkflow(temp_dir)
            self.assertTrue(workflow._has_visible_overlay_layers(state))

    def test_text_layer_opacity_is_carried_into_overlay_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state = ProjectState(project_id="p1", project_root=temp_dir, input_video="video.mp4")
            timeline = Timeline()
            track = Track(name="T1 Text", type=LayerType.TEXT)
            layer = TextLayer(text="Hello", start=0.0, end=5.0)
            layer.transform.x = 0.5
            layer.transform.y = 0.5
            layer.opacity = 0.35
            layer.background_opacity = 0.25
            track.layers.append(layer)
            timeline.tracks.append(track)

            timeline_path = os.path.join(temp_dir, "timeline", "timeline.json")
            os.makedirs(os.path.dirname(timeline_path), exist_ok=True)
            with open(timeline_path, "w", encoding="utf-8") as handle:
                json.dump(timeline.to_dict(), handle)
            state.artifacts["timeline"] = timeline_path

            workflow = ExportWorkflow(temp_dir)
            _, _, text_layers, _ = workflow._extract_overlay_layers(state)
            self.assertEqual(len(text_layers), 1)
            self.assertAlmostEqual(text_layers[0]["opacity"], 0.35, places=6)
            self.assertAlmostEqual(text_layers[0]["background_opacity"], 0.25, places=6)

    def test_builds_ass_for_visual_text_layers_without_srt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = ExportWorkflow(temp_dir)
            layers = [{
                "text": "Hello",
                "font_name": "Arial",
                "font_size": 48,
                "font_color": "#FFFFFF",
                "background_color": "",
                "background_opacity": 0.5,
                "opacity": 0.8,
                "font_bold": True,
                "font_italic": False,
                "font_underline": False,
                "x": 0.5,
                "y": 0.5,
                "start": 0.0,
                "end": 2.0,
            }]

            ass_path = workflow._build_text_layer_ass(
                os.path.join(temp_dir, "visual_only.ass"),
                layers,
                temp_dir=temp_dir,
                width=1920,
                height=1080,
            )
            self.assertTrue(os.path.exists(ass_path))
            with open(ass_path, "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("Dialogue:", content)
            self.assertIn("Hello", content)


if __name__ == "__main__":
    unittest.main()
