import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "app"), ROOT]

from core.models import AudioChunk
from services import AsrMergeService


def _chunk(chunk_id, start, end, *, overlap_left=0.0, overlap_right=0.0):
    return AudioChunk(
        chunk_id=chunk_id,
        audio_path=f"{chunk_id}.wav",
        start_seconds=start,
        end_seconds=end,
        overlap_left_seconds=overlap_left,
        overlap_right_seconds=overlap_right,
        speech_start_seconds=start,
        speech_end_seconds=end,
    )


class AsrMergeServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = AsrMergeService()

    def test_removes_corrupted_partial_repeat_at_chunk_boundary(self):
        first = _chunk("chunk-1", 0.0, 12.5, overlap_right=0.5)
        second = _chunk("chunk-2", 11.5, 24.5, overlap_left=0.5)
        results = [
            {
                "chunk": first,
                "segments": [
                    {"start": 10.42, "end": 12.48, "text": "招來了一個年輕的決事要"},
                ],
            },
            {
                "chunk": second,
                "segments": [
                    {"start": 0.0, "end": 1.36, "text": "年轻的绝世腰腻"},
                    {"start": 2.2, "end": 4.72, "text": "还把陶宗成内老东西给打了"},
                ],
            },
        ]

        merged = self.service.merge_chunk_results(results)

        self.assertEqual(
            [segment["text"] for segment in merged],
            ["招來了一個年輕的決事要", "还把陶宗成内老东西给打了"],
        )
        self.assertEqual(merged[1]["start"], 13.7)

    def test_keeps_unrelated_overlapping_speech_at_chunk_boundary(self):
        first = _chunk("chunk-1", 0.0, 12.5, overlap_right=0.5)
        second = _chunk("chunk-2", 11.5, 24.5, overlap_left=0.5)
        results = [
            {"chunk": first, "segments": [{"start": 10.4, "end": 12.4, "text": "Stop him now"}]},
            {"chunk": second, "segments": [{"start": 0.0, "end": 1.3, "text": "What are you doing"}]},
        ]

        merged = self.service.merge_chunk_results(results)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[1]["text"], "What are you doing")

    def test_keeps_repeated_dialogue_inside_same_chunk(self):
        chunk = _chunk("chunk-1", 0.0, 12.5)
        results = [{
            "chunk": chunk,
            "segments": [
                {"start": 3.0, "end": 4.0, "text": "Confirmed"},
                {"start": 3.8, "end": 4.8, "text": "Confirmed"},
            ],
        }]

        merged = self.service.merge_chunk_results(results)

        self.assertEqual(len(merged), 2)

    def test_keeps_similar_cue_that_does_not_start_at_chunk_edge(self):
        first = _chunk("chunk-1", 0.0, 12.5, overlap_right=0.5)
        second = _chunk("chunk-2", 11.5, 24.5, overlap_left=0.5)
        results = [
            {"chunk": first, "segments": [{"start": 10.3, "end": 12.3, "text": "Young prodigy"}]},
            {"chunk": second, "segments": [{"start": 0.8, "end": 2.0, "text": "Young prodigy"}]},
        ]

        merged = self.service.merge_chunk_results(results)

        self.assertEqual(len(merged), 2)


if __name__ == "__main__":
    unittest.main()
