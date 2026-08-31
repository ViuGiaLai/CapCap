import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.services.segment_regroup_service import SegmentRegroupService


class SegmentRegroupServiceTests(unittest.TestCase):
    def test_long_chinese_cue_without_word_timing_is_split(self):
        service = SegmentRegroupService()
        result = service.regroup(
            [{
                "start": 10.0,
                "end": 22.0,
                "text": "你不要以为我们怕了你如今你气血消耗巨大你以为你还能斗得过我们父子二人不成",
            }],
            max_duration_seconds=5.0,
        )
        self.assertEqual(len(result), 3)
        self.assertEqual("".join(item["text"] for item in result), "你不要以为我们怕了你如今你气血消耗巨大你以为你还能斗得过我们父子二人不成")
        self.assertAlmostEqual(result[0]["start"], 10.0)
        self.assertAlmostEqual(result[-1]["end"], 22.0)
        self.assertTrue(all(item["end"] - item["start"] <= 5.01 for item in result))

    def test_word_timestamps_define_split_boundaries(self):
        service = SegmentRegroupService()
        result = service.regroup(
            [{
                "start": 0.0,
                "end": 6.0,
                "text": "Wait here. I will return.",
                "words": [
                    {"start": 0.0, "end": 1.0, "text": "Wait"},
                    {"start": 1.0, "end": 2.0, "text": "here."},
                    {"start": 3.0, "end": 4.0, "text": "I"},
                    {"start": 4.0, "end": 5.0, "text": "will"},
                    {"start": 5.0, "end": 6.0, "text": "return."},
                ],
            }],
            max_duration_seconds=4.0,
        )
        self.assertEqual([item["text"] for item in result], ["Wait here.", "I will return."])
        self.assertEqual(result[0]["end"], 2.0)
        self.assertEqual(result[1]["start"], 3.0)

    def test_short_cue_is_preserved(self):
        source = {"start": 1.0, "end": 2.0, "text": "等一下", "speaker": "SPEAKER_01"}
        result = SegmentRegroupService().regroup([source], max_duration_seconds=5.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "等一下")
        self.assertEqual(result[0]["speaker"], "SPEAKER_01")


if __name__ == "__main__":
    unittest.main()
