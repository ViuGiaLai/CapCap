import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "app"), ROOT]

from app.services.auto_recap_engine import AutoRecapEngine
from app.services.auto_recap_benchmark import benchmark_auto_recap_pipeline


class TestAutoRecapBenchmark(unittest.TestCase):
    def test_benchmark_report_generation(self):
        engine = AutoRecapEngine()
        segments = [
            {"start": 0.0, "end": 3.0, "text": "Dramatic opening scene cut!", "source_clip_id": "clip_1"},
            {"start": 3.0, "end": 8.0, "text": "Ordinary conversation scene with regular text", "source_clip_id": "clip_2"},
            {"start": 8.0, "end": 12.0, "text": "Reused scene action shot", "source_clip_id": "clip_1"},
        ]
        decisions, metrics = benchmark_auto_recap_pipeline(engine, segments, has_voiceover=False)

        self.assertGreater(len(decisions), 0)
        report = metrics.generate_ascii_report()
        self.assertIn("VIUStudio Auto Edit Recap Benchmark Report", report)
        self.assertIn("Stage 1", report)
        self.assertIn("Stage 5", report)
        self.assertFalse(metrics.ducked_shots > 0)  # No voiceover -> no ducking applied!


if __name__ == "__main__":
    unittest.main()
