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

    def test_absorbs_tiny_trailing_fragment_after_longer_cue(self):
        result = SegmentRegroupService.deduplicate_and_clamp_timeline([
            {
                "start": 47.52,
                "end": 48.385,
                "text": "操縱層是你打的",
                "words": [{"start": 47.55, "end": 47.80, "text": "操"}, {"start": 48.2, "end": 48.38, "text": "的"}],
            },
            {
                "start": 48.385,
                "end": 48.485,
                "text": "草重层",
                "words": [{"start": 48.40, "end": 48.47, "text": "层"}],
            },
        ])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "操縱層是你打的")
        self.assertAlmostEqual(result[0]["end"], 48.485)
        self.assertEqual(len(result[0]["words"]), 3)

    def test_absorbs_tiny_trailing_fragment_after_short_cue(self):
        result = SegmentRegroupService.deduplicate_and_clamp_timeline([
            {"start": 347.12, "end": 347.73, "text": "血胜值"},
            {"start": 347.73, "end": 347.94, "text": "先盛職"},
        ])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "血胜值")
        self.assertAlmostEqual(result[0]["end"], 347.94)

    def test_does_not_absorb_genuine_adjacent_short_dialogue(self):
        # ``你没死`` lasts 0.5s - a real reply, not a sub-second echo.
        result = SegmentRegroupService.deduplicate_and_clamp_timeline([
            {"start": 241.295, "end": 242.030, "text": "父亲"},
            {"start": 242.030, "end": 242.530, "text": "你没死"},
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual([item["text"] for item in result], ["父亲", "你没死"])

        # Two full-length fight callouts must stay separate.
        result = SegmentRegroupService.deduplicate_and_clamp_timeline([
            {"start": 83.761, "end": 84.984, "text": "猛虎啸山"},
            {"start": 84.984, "end": 85.940, "text": "给我死"},
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual([item["text"] for item in result], ["猛虎啸山", "给我死"])

    def test_does_not_absorb_short_reply_when_window_is_wide(self):
        # A 0.25s reply after a 1.2s line leaves a 1.45s combined window.
        result = SegmentRegroupService.deduplicate_and_clamp_timeline([
            {"start": 10.0, "end": 11.2, "text": "我可是他的父亲"},
            {"start": 11.2, "end": 11.45, "text": "滚"},
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual([item["text"] for item in result], ["我可是他的父亲", "滚"])


    def test_clamps_large_timeline_overlap_cleanly(self):
        result = SegmentRegroupService.deduplicate_and_clamp_timeline([
            {"start": 10.0, "end": 14.0, "text": "第一句话"},
            {"start": 13.0, "end": 16.0, "text": "第二句话"},
        ])
        self.assertEqual(len(result), 2)
        self.assertLessEqual(result[0]["end"], result[1]["start"])

    def test_orders_imported_cues_before_deduplication(self):
        result = SegmentRegroupService.deduplicate_and_clamp_timeline([
            {"start": 2.0, "end": 3.0, "text": "第二句"},
            {"start": 0.0, "end": 1.0, "text": "第一句"},
            {"start": "bad", "end": 4.0, "text": "忽略"},
        ])
        self.assertEqual([item["text"] for item in result], ["第一句", "第二句"])
        self.assertEqual(result[0]["start"], 0.0)


if __name__ == "__main__":
    unittest.main()
