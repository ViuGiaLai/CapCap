import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.layers.base import LayerType
from app.layers.dub_subtitle import DubSubtitleLayer
from app.layers.sync_bridge import sync_segments_to_dub_subtitle_layers
from app.layers.timeline import Timeline, Track


class SyncBridgeTests(unittest.TestCase):
    def test_sync_removes_stale_subtitle_layers_and_preserves_matching_audio(self):
        keep = DubSubtitleLayer(
            name="old keep",
            start=0.0,
            end=1.0,
            text="Câu một",
            dub_text="Câu một",
            audio_path="voice-1.wav",
        )
        keep.metadata["_seg_index"] = 0
        stale = DubSubtitleLayer(
            name="stale",
            start=9.0,
            end=10.0,
            text="Không còn tồn tại",
        )
        stale.metadata["_seg_index"] = 99
        track = Track(name="TS1", type=LayerType.DUB_SUBTITLE, layers=[keep, stale])
        timeline = Timeline(duration=10.0, tracks=[track])

        layers = sync_segments_to_dub_subtitle_layers(
            timeline,
            [
                {"start": 0.0, "end": 1.0, "text": "Câu một"},
                {"start": 1.0, "end": 2.0, "text": "Câu hai"},
            ],
        )

        self.assertEqual(track.layers, layers)
        self.assertEqual(len(track.layers), 2)
        self.assertNotIn(stale, track.layers)
        self.assertIs(track.layers[0], keep)
        self.assertEqual(track.layers[0].audio_path, "voice-1.wav")
        self.assertEqual(
            [layer.metadata.get("_seg_index") for layer in track.layers],
            [0, 1],
        )


if __name__ == "__main__":
    unittest.main()
