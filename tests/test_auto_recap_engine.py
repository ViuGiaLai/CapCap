import unittest
from app.services.auto_recap_engine import AutoRecapConfig, AutoRecapEngine, FootageReuseManager


class TestAutoRecapEngine(unittest.TestCase):
    def setUp(self):
        self.config = AutoRecapConfig(
            enabled=True,
            editing_style="Balanced",
            max_zoom_percent=110.0,
            allow_smart_zoom=True,
            allow_pan_reframe=True,
            allow_horizontal_flip=True,
            allow_speed_change=True,
            allow_freeze_frame=True,
            ducking_preset="Balanced",
            cooldown_shots=2,
            safety_blacklist_text=True,
            strict_flip_safety=True,
        )
        self.engine = AutoRecapEngine(self.config)

    def test_calculate_importance_score(self):
        score_high = self.engine.calculate_importance_score("Bí mật quan trọng cuối cùng!", 4.0, True)
        score_low = self.engine.calculate_importance_score("", 2.0, False)
        self.assertGreater(score_high, 70.0)
        self.assertLess(score_low, 35.0)

    def test_evaluate_shot_zoom_and_preserve_empty_content(self):
        decision_keep = self.engine.evaluate_shot(0, 0.0, 4.0, "Sự thật bất ngờ quan trọng!", True)
        self.assertEqual(decision_keep.action_type, "KEEP")
        self.assertGreater(decision_keep.zoom_scale, 1.0)

        decision_empty = self.engine.evaluate_shot(1, 0.0, 5.0, "", is_scene_cut=False)
        self.assertEqual(decision_empty.action_type, "KEEP")
        self.assertEqual(decision_empty.duration, 5.0)

    def test_safety_blacklist_text(self):
        self.assertFalse(self.engine.check_safety_blacklist("Top 10 Bí Mật 2026"))
        self.assertFalse(self.engine.check_safety_blacklist("HOT NEWS"))
        self.assertFalse(self.engine.check_safety_blacklist("Normal Text", has_logo=True))
        self.assertFalse(self.engine.check_safety_blacklist(""))
        self.assertTrue(self.engine.check_safety_blacklist("Đây là một câu thoại bình thường"))

    def test_footage_reuse_manager(self):
        mgr = FootageReuseManager()
        use1 = mgr.get_reuse_strategy("clip_A", is_safe_for_flip=True)
        use2 = mgr.get_reuse_strategy("clip_A", is_safe_for_flip=True)
        use3 = mgr.get_reuse_strategy("clip_A", is_safe_for_flip=True)
        self.assertFalse(use1["flip"])
        self.assertEqual(use2["crop"], "speaker")
        self.assertTrue(use3["flip"])

    def test_generate_edl(self):
        segments = [
            {"start": 0.0, "end": 4.0, "text": "Đoạn văn quan trọng đầu tiên!"},
            {"start": 4.0, "end": 8.0, "text": "", "is_scene_cut": False},
            {"start": 8.0, "end": 12.0, "text": "Bí mật thành công rực rỡ?"},
        ]
        edl = self.engine.generate_edl(segments)
        self.assertEqual(len(edl), 3)
        self.assertEqual(edl[0].shot_index, 0)
        self.assertEqual(edl[1].shot_index, 1)
        self.assertEqual(edl[2].shot_index, 2)

    def test_scene_shots_preserve_full_timeline_and_receive_subtitle_context(self):
        scenes = [
            {"start": 0.0, "end": 2.0},
            {"start": 2.0, "end": 5.0},
        ]
        segments = [
            {"start": 1.0, "end": 3.0, "text": "Điểm nhấn quan trọng!"},
        ]
        enriched = self.engine.apply_subtitles_to_scenes(scenes, segments)
        edl = self.engine.generate_edl(segments, enriched)
        self.assertEqual(edl[0].start_time, 0.0)
        self.assertEqual(edl[-1].end_time, 5.0)
        self.assertAlmostEqual(sum(d.duration for d in edl), 5.0)
        self.assertTrue(all(d.action_type == "KEEP" for d in edl))
        self.assertTrue(all("Điểm nhấn" in item["text"] for item in enriched))

    def test_distinct_segments_are_not_treated_as_reused_footage(self):
        segments = [
            {"start": i * 2.0, "end": (i + 1) * 2.0, "text": "Cảnh có lời thoại bình thường"}
            for i in range(6)
        ]
        edl = self.engine.generate_edl(segments)
        self.assertEqual([d.source_clip_id for d in edl], [f"clip_{i}" for i in range(6)])
        self.assertFalse(any(d.horizontal_flip for d in edl))

    def test_output_duration_accounts_for_speed_and_freeze(self):
        decision = self.engine.evaluate_shot(0, 0.0, 4.0, "Bí mật quan trọng cuối cùng!", True)
        expected = decision.duration / decision.speed + decision.freeze_duration
        self.assertAlmostEqual(decision.output_duration, expected)

    def test_video_only_filtergraph_does_not_reference_audio(self):
        edl = self.engine.generate_edl([
            {"start": 0.0, "end": 2.0, "text": "Một cảnh hợp lệ"},
        ])
        graph, maps = self.engine.build_ffmpeg_filtergraph(edl, has_audio=False)
        self.assertNotIn("[0:a]", graph)
        self.assertNotIn("[afinal]", maps)

    def test_motion_schedule_generates_requested_effect_families(self):
        scenes = [
            {
                "start": index * 5.0,
                "end": (index + 1) * 5.0,
                "text": "Một cảnh có nội dung bình thường",
                "source_clip_id": f"scene_{index}",
            }
            for index in range(8)
        ]
        edl = self.engine.generate_edl([], scenes)
        self.assertEqual(edl[0].zoom_direction, "in")
        self.assertEqual(edl[1].zoom_direction, "out")
        self.assertIn(edl[2].pan_direction, {"left_right", "right_left"})
        self.assertIn(edl[3].pan_direction, {"top_bottom", "bottom_top"})
        self.assertNotEqual(edl[4].crop_mode, "none")
        self.assertIn(edl[4].position_shift, {"left", "right"})
        self.assertNotEqual(edl[6].crop_mode, "none")
        self.assertIn(edl[6].position_shift, {"up", "down"})

        graph, _maps = self.engine.build_ffmpeg_filtergraph(edl)
        self.assertIn("zoompan=", graph)
        self.assertIn("pzoom+", graph)
        self.assertIn("pzoom-", graph)
        self.assertIn("crop=", graph)

    def test_reused_safe_footage_can_flip_horizontally(self):
        decisions = [
            self.engine.evaluate_shot(
                index,
                index * 2.0,
                (index + 1) * 2.0,
                "Cảnh thoại bình thường",
                source_clip_id="same_clip",
            )
            for index in range(3)
        ]
        self.assertFalse(decisions[0].horizontal_flip)
        self.assertFalse(decisions[1].horizontal_flip)
        self.assertTrue(decisions[2].horizontal_flip)

    def test_freeze_padding_precedes_speed_retime(self):
        decision = self.engine.evaluate_shot(
            0,
            0.0,
            7.0,
            "Bí mật quan trọng cuối cùng!",
        )
        self.assertEqual(decision.speed, 0.9)
        self.assertEqual(decision.freeze_duration, 0.4)

        graph, _maps = self.engine.build_ffmpeg_filtergraph([decision])

        self.assertIn("tpad=stop_mode=clone:stop=11,setpts=PTS/0.90", graph)
        self.assertIn("apad=pad_dur=0.3600,atempo=0.90", graph)


if __name__ == "__main__":
    unittest.main()
