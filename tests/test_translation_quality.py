import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.translation.orchestrator import TranslationOrchestrator
from app.translation.prompt_builder import build_translation_messages
from app.translation.quality_guard import apply_translation_quality_guard
from app.translation.srt_utils import parse_numbered_line_items


class _CapturingPolisher:
    def __init__(self):
        self.styles = []
        self.context_before = []
        self.context_after = []

    def polish_batch(self, *, source_texts, style_instruction, context_before=None, context_after=None, **_kwargs):
        self.styles.append(style_instruction)
        self.context_before.append(list(context_before or []))
        self.context_after.append(list(context_after or []))
        return [f"dịch {index + 1}" for index in range(len(source_texts))], [], "fake"


class _RepairPolisher:
    def __init__(self):
        self.style = ""
        self.context_before = []
        self.context_after = []

    def polish_batch(self, *, style_instruction, context_before=None, context_after=None, **_kwargs):
        self.style = style_instruction
        self.context_before = list(context_before or [])
        self.context_after = list(context_after or [])
        return ["Hắn có 100 linh thạch"], [], "fake"


class _FallbackTranslator:
    def translate_batch(self, texts, **_kwargs):
        return ["Đừng tưởng rằng chúng ta sợ ngươi."] * len(texts)


class _FailingConfiguredPolisher:
    def is_configured(self):
        return True

    def polish_batch(self, **_kwargs):
        raise RuntimeError("provider quota exhausted")


class _SemanticReviewPolisher:
    model_name = "Qwen3-4B-Q4_K_M.gguf"

    def __init__(self):
        self.calls = []

    def polish_batch(self, *, source_texts, translated_texts=None, style_instruction="", **_kwargs):
        self.calls.append((list(source_texts), translated_texts, style_instruction))
        if translated_texts is None:
            return ["Thưa đạo hữu, tôi vừa chiến đấu với hai vị thiên vương"], [], "llama_app"
        return ["Đạo hữu vừa liên tiếp giao chiến với hai vị Thiên Vương."], [], "llama_app"


class TranslationQualityTests(unittest.TestCase):
    def test_selected_ai_provider_failure_never_silently_uses_google_web(self):
        orchestrator = TranslationOrchestrator()
        orchestrator.google_web = _FallbackTranslator()
        with patch.object(
            orchestrator,
            "_resolve_ai_provider",
            return_value=("google_ai_studio", _FailingConfiguredPolisher()),
        ):
            with self.assertRaises(Exception) as raised:
                orchestrator.translate_segments(
                    segments=[{"start": 0.0, "end": 2.0, "text": "你是谁"}],
                    src_lang="zh-Hans",
                    target_lang="vi",
                    enable_polish=True,
                )

        self.assertIn("provider quota exhausted", str(raised.exception))
    def test_ai_source_contains_timing_metadata_but_keeps_one_line(self):
        value = TranslationOrchestrator._build_timed_ai_source(
            {"start": 2.5, "end": 4.75, "text": "原来他\n一直在骗我", "speaker": "SPEAKER_01"},
            3,
        )
        self.assertIn('id="4"', value)
        self.assertIn('duration="2.250"', value)
        self.assertIn('speaker="SPEAKER_01"', value)
        self.assertNotIn("\n", value)
        self.assertIn("原来他 一直在骗我", value)

    def test_vietnamese_guard_normalizes_only_terms_supported_by_source(self):
        texts, warnings = apply_translation_quality_guard(
            source_segments=[
                {"start": 0.0, "end": 3.0, "text": "神域出现了魔族"},
                {"start": 3.0, "end": 6.0, "text": "他去了神界"},
            ],
            translated_texts=[
                "Thần giới xuất hiện tộc ma",
                "Hắn đã tới thần giới",
            ],
            target_lang="vi",
        )
        self.assertEqual(texts[0], "Thần Vực xuất hiện Ma tộc")
        self.assertEqual(texts[1], "Hắn đã tới thần giới")
        self.assertEqual(warnings, [])

    def test_guard_reports_untranslated_cjk_missing_numbers_and_readability(self):
        _texts, warnings = apply_translation_quality_guard(
            source_segments=[{"start": 0.0, "end": 1.0, "text": "他有100颗灵石"}],
            translated_texts=["Hắn có rất rất nhiều 灵石 quý giá ở trong túi"],
            target_lang="vi",
        )
        joined = " ".join(warnings)
        self.assertIn("chữ viết nguồn", joined)
        self.assertIn("100", joined)
        self.assertIn("ký tự/giây", joined)

    def test_ordered_batches_receive_previous_and_upcoming_context(self):
        polisher = _CapturingPolisher()
        result, providers, warnings = TranslationOrchestrator._run_ai_batch_requests(
            polisher=polisher,
            batches=[(["câu một"], None, 1024), (["câu hai"], None, 1024)],
            src_lang="zh-Hans",
            target_lang="vi",
            style_instruction="recap",
            max_workers=1,
        )
        self.assertEqual(result, ["dịch 1", "dịch 1"])
        self.assertEqual(providers, ["fake"])
        self.assertEqual(warnings, [])
        self.assertIn("câu hai", " ".join(polisher.context_after[0]))
        self.assertIn("câu một => dịch 1", " ".join(polisher.context_before[1]))
        self.assertNotIn("Upcoming source context", polisher.styles[0])
        self.assertEqual(polisher.styles[0], "recap")

    def test_script_and_readability_checks_follow_target_language(self):
        segments = [{"start": 0.0, "end": 2.0, "text": "原文"}]
        _english, english_warnings = apply_translation_quality_guard(
            source_segments=segments,
            translated_texts=["English with 原文 left behind"],
            target_lang="en",
        )
        _japanese, japanese_warnings = apply_translation_quality_guard(
            source_segments=segments,
            translated_texts=["日本語の字幕"],
            target_lang="ja",
        )
        english_joined = " ".join(english_warnings)
        japanese_joined = " ".join(japanese_warnings)
        self.assertIn("chữ viết nguồn", english_joined)
        self.assertNotIn("chữ viết nguồn", japanese_joined)

    def test_vietnamese_glossary_is_not_forced_into_other_targets(self):
        texts, _warnings = apply_translation_quality_guard(
            source_segments=[{"start": 0.0, "end": 3.0, "text": "神域"}],
            translated_texts=["Divine Realm"],
            target_lang="en",
        )
        self.assertEqual(texts, ["Divine Realm"])

    def test_vietnamese_guard_reports_leaked_english_clause_but_allows_names(self):
        segments = [{"start": 0.0, "end": 5.0, "text": "你不要以为我们怕了你"}]
        _texts, warnings = apply_translation_quality_guard(
            source_segments=segments,
            translated_texts=["Don't think that we are afraid of you. Bây giờ hãy lui đi."],
            target_lang="vi",
        )
        self.assertIn("cụm tiếng Anh", " ".join(warnings))

        _texts, name_warnings = apply_translation_quality_guard(
            source_segments=segments,
            translated_texts=["Peter đã đưa thanh kiếm cho Mary."],
            target_lang="vi",
        )
        self.assertNotIn("cụm tiếng Anh", " ".join(name_warnings))

    def test_guard_detects_contextual_role_idiom_and_action_changes(self):
        _texts, warnings = apply_translation_quality_guard(
            source_segments=[
                {"start": 0.0, "end": 3.0, "text": "道友刚才连战两位天王"},
                {"start": 3.0, "end": 7.0, "text": "我段炼佩服得五体投地"},
            ],
            translated_texts=[
                "Thưa đạo bạn, tôi vừa chiến thắng hai vị thiên vương.",
                "Ta Đoạn Luyện ngưỡng mộ đến mức ngã xuống đất.",
            ],
            target_lang="vi",
        )
        joined = " ".join(warnings)
        self.assertIn("fighting successively, not winning", joined)
        self.assertIn("addressee was changed", joined)
        self.assertNotIn("literal fall", joined)
        self.assertNotIn("emphasis of 五体投地 was omitted", joined)
        self.assertEqual(_texts[0], "Thưa đạo hữu, tôi vừa chiến thắng hai vị Thiên Vương.")
        self.assertEqual(_texts[1], "Ta Đoạn Luyện khâm phục sát đất")

    def test_translation_prompt_contains_fidelity_context_ocr_and_glossary_rules(self):
        system, _user = build_translation_messages(
            source_texts=['<CUE duration="2.0">师兄来了</CUE>'],
            translated_texts=None,
            src_lang="zh-Hans",
            target_lang="vi",
            style_instruction="recap",
        )
        self.assertIn("Meaning is the first quality gate", system)
        self.assertIn("OCR/ASR safety", system)
        self.assertIn("师兄=sư huynh", system)
        self.assertIn("duration", system)
        self.assertIn("`speaker` names the person producing that cue", system)
        self.assertNotIn('id="', _user)

    def test_translation_user_payload_keeps_scene_context_out_of_style(self):
        _system, user = build_translation_messages(
            source_texts=['<CUE id="2" duration="2.0" speaker="SPEAKER_01">他来了</CUE>'],
            translated_texts=None,
            src_lang="zh-Hans",
            target_lang="vi",
            style_instruction="recap",
            context_before=['<CUE duration="1.0">师兄小心</CUE>'],
            context_after=['<CUE duration="1.0">然后离开</CUE>'],
        )
        self.assertIn("<CONTEXT_BEFORE>", user)
        self.assertIn("<CONTEXT_AFTER>", user)
        self.assertIn("<PREV>师兄小心</PREV>", user)
        self.assertIn("<NEXT>然后离开</NEXT>", user)
        self.assertIn('speaker="SPEAKER_01"', user)
        self.assertNotIn('id="2"', user)
        self.assertIn("<TRANSLATE>", user)

    def test_guard_localizes_wuti_toudi_without_literal_or_mixed_language(self):
        texts, warnings = apply_translation_quality_guard(
            source_segments=[{
                "start": 0.0,
                "end": 4.0,
                "text": "这等神通手段我段炼佩服得五体投地",
            }],
            translated_texts=[
                "Loại thần thông này, tôi Đoạn Luyện ngưỡng mộ đến mức cinco thể"
            ],
            target_lang="vi",
        )
        self.assertEqual(
            texts,
            ["Loại thần thông này, Đoạn Luyện ta khâm phục sát đất"],
        )
        self.assertNotIn("semantic mismatch", " ".join(warnings))

    def test_guard_keeps_lianzhan_as_successive_fighting_not_victory(self):
        texts, warnings = apply_translation_quality_guard(
            source_segments=[{
                "start": 0.0,
                "end": 3.0,
                "text": "道友刚才连战两位天王",
            }],
            translated_texts=[
                "Đạo hữu vừa rồi đã chiến đấu với hai Thiên Vương liên tiếp"
            ],
            target_lang="vi",
        )
        self.assertEqual(texts, ["Đạo hữu vừa đấu liền hai vị Thiên Vương"])
        self.assertNotIn("semantic mismatch", " ".join(warnings))

    def test_objectively_broken_cue_is_retried_with_local_context(self):
        orchestrator = TranslationOrchestrator()
        polisher = _RepairPolisher()
        segments = [
            {"start": 0.0, "end": 2.0, "text": "他来了"},
            {"start": 2.0, "end": 4.0, "text": "他有100颗灵石"},
            {"start": 4.0, "end": 6.0, "text": "然后离开"},
        ]
        ai_sources = [orchestrator._build_timed_ai_source(seg, i) for i, seg in enumerate(segments)]

        repaired, warnings = orchestrator._repair_ai_quality_issues(
            polisher=polisher,
            source_segments=segments,
            ai_source_texts=ai_sources,
            translated_texts=["Hắn đến", "Hắn có 灵石", "Sau đó rời đi"],
            quality_warnings=[
                "Cue 2: còn ký tự thuộc chữ viết nguồn chưa dịch.",
                "Cue 2: bản dịch có thể thiếu số 100.",
            ],
            src_lang="zh-Hans",
            target_lang="vi",
            style_instruction="recap",
        )

        self.assertEqual(repaired[1], "Hắn có 100 linh thạch")
        self.assertEqual(warnings, [])
        self.assertIn("他来了", " ".join(polisher.context_before))
        self.assertIn("然后离开", " ".join(polisher.context_after))
        self.assertNotIn("Nearby source context", polisher.style)
        self.assertIn("never output nearby cues", polisher.style)

    def test_unresolved_wrong_language_cue_uses_final_fallback(self):
        orchestrator = TranslationOrchestrator()
        orchestrator.google_web = _FallbackTranslator()
        repaired, warnings = orchestrator._fallback_unresolved_quality_issues(
            source_segments=[{"start": 0.0, "end": 3.0, "text": "你不要以为我们怕了你"}],
            translated_texts=["Don't think that we are afraid of you."],
            quality_warnings=["Cue 1: còn cụm tiếng Anh trong bản dịch tiếng Việt."],
            src_lang="zh-Hans",
            target_lang="vi",
        )
        self.assertEqual(repaired, ["Đừng tưởng rằng chúng ta sợ ngươi."])
        self.assertEqual(warnings, [])

    def test_local_chat_translation_receives_source_versus_draft_semantic_review(self):
        orchestrator = TranslationOrchestrator()
        polisher = _SemanticReviewPolisher()
        segments = [{"start": 162.115, "end": 165.126, "text": "道友刚才连战两位天王"}]
        ai_sources = [orchestrator._build_timed_ai_source(segments[0], 0)]

        reviewed, warnings = orchestrator._review_local_translation_with_context(
            polisher=polisher,
            provider_type="llama_app",
            source_segments=segments,
            ai_source_texts=ai_sources,
            translated_texts=["Thưa đạo hữu, tôi vừa chiến đấu với hai vị thiên vương"],
            src_lang="zh-Hans",
            target_lang="vi",
            style_instruction="Standard / Natural",
        )

        self.assertEqual(reviewed, ["Đạo hữu vừa liên tiếp giao chiến với hai vị Thiên Vương."])
        self.assertEqual(warnings, [])
        self.assertIsNotNone(polisher.calls[0][1])
        self.assertIn("speaker versus addressee", polisher.calls[0][2])
        self.assertIn("五体投地", polisher.calls[0][2])

    def test_single_line_split_does_not_repeat_unsplit_model_text(self):
        orchestrator = TranslationOrchestrator()
        full_text = "Đánh người của ta mà còn dám chủ động nhận nhiệm vụ do ta dẫn đội?"
        split = orchestrator._split_segments_for_single_line(
            [{
                "id": 17,
                "start": 54.520,
                "end": 57.785,
                "text": full_text,
                "final_text": full_text,
                "raw_translation": full_text,
                "tts_text": full_text,
            }],
            words_per_segment=5,
        )

        self.assertGreater(len(split), 1)
        self.assertEqual(" ".join(item["text"] for item in split), full_text)
        self.assertTrue(all(item["final_text"] == item["text"] for item in split))
        self.assertTrue(all(item["raw_translation"] == item["text"] for item in split))
        # Voice remains one complete grouped utterance; only the visible cue is split.
        self.assertTrue(all(item["tts_text"] == full_text for item in split))
        self.assertFalse(any(item["text"] == full_text for item in split))


    def test_cloud_provider_uses_scene_sized_ordered_batches(self):
        class _SizePolisher:
            def __init__(self):
                self.sizes = []
                self.context_before = []

            def polish_batch(self, *, source_texts, context_before=None, **_kwargs):
                self.sizes.append(len(source_texts))
                self.context_before.append(list(context_before or []))
                return [f"dịch {index + 1}" for index in range(len(source_texts))], [], "fake"

        polisher = _SizePolisher()
        sources = [f"câu {index}" for index in range(30)]
        result, _providers, _warnings = TranslationOrchestrator()._run_ai_batches(
            polisher=polisher,
            provider_type="google_ai_studio",
            source_texts=sources,
            translated_texts=None,
            src_lang="zh-Hans",
            target_lang="vi",
            style_instruction="",
            polish_batch_size=80,
        )
        self.assertEqual(len(result), 30)
        self.assertGreater(len(polisher.sizes), 1)
        self.assertTrue(all(size <= 24 for size in polisher.sizes))
        self.assertTrue(any(polisher.context_before))

    def test_local_provider_ordered_batches_are_small_by_default(self):
        sources = [f"câu {index}" for index in range(30)]
        batches, full_context = TranslationOrchestrator._build_ai_batches(
            source_texts=sources,
            translated_texts=None,
            requested_max_segments=12,
            force_ordered=True,
            max_chars_limit=6000,
            response_token_limit=1800,
        )
        self.assertFalse(full_context)
        self.assertGreater(len(batches), 1)
        self.assertTrue(all(len(source) <= 12 for source, _draft, _tokens in batches))
        self.assertEqual(sum(len(source) for source, _draft, _tokens in batches), 30)

    def test_local_batch_failure_retries_once_with_half_size_batches(self):
        class _ShrinkPolisher:
            def __init__(self):
                self.sizes = []

            def polish_batch(self, *, source_texts, translated_texts=None, style_instruction="", **_kwargs):
                self.sizes.append(len(source_texts))
                if len(self.sizes) == 1:
                    raise RuntimeError("request timed out")
                answers = []
                for index, _source in enumerate(source_texts, 1):
                    answers.append(f"bản dịch {index}")
                return answers, [], "llama_app"

        polisher = _ShrinkPolisher()
        orchestrator = TranslationOrchestrator()
        sources = [f"câu {index}" for index in range(24)]
        result, _providers, _warnings = orchestrator._run_ai_batches(
            polisher=polisher,
            provider_type="llama_app",
            source_texts=sources,
            translated_texts=None,
            src_lang="zh-Hans",
            target_lang="vi",
            style_instruction="",
            polish_batch_size=80,
        )
        self.assertEqual(len(result), 24)
        # First pass raised, then the whole request set was retried at <= 6 cues.
        self.assertGreaterEqual(len(polisher.sizes), 2)
        self.assertTrue(all(size <= 6 for size in polisher.sizes[1:]))

    def test_cloud_batch_failure_is_not_swallowed(self):
        class _CloudFailPolisher:
            def polish_batch(self, **_kwargs):
                raise RuntimeError("provider quota exhausted")

        with self.assertRaisesRegex(Exception, "quota exhausted"):
            TranslationOrchestrator()._run_ai_batches(
                polisher=_CloudFailPolisher(),
                provider_type="google_ai_studio",
                source_texts=["câu một"],
                translated_texts=None,
                src_lang="zh-Hans",
                target_lang="vi",
                style_instruction="",
                polish_batch_size=80,
            )

    def test_parse_numbered_line_items_strips_translation_prefixes(self):
        raw = """
        1. Dịch: Sư huynh, cẩn thận!
        2. Bản dịch: Đừng lo cho ta.
        3. Translation: Mau đi đi.
        """
        items = parse_numbered_line_items(raw)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0], (1, "Sư huynh, cẩn thận!"))
        self.assertEqual(items[1], (2, "Đừng lo cho ta."))
        self.assertEqual(items[2], (3, "Mau đi đi."))

    def test_prompt_builder_preserves_speaker_turn_in_context(self):
        _system, user = build_translation_messages(
            source_texts=['<CUE id="2" duration="2.0" speaker="Speaker 2">Ta là sư huynh của ngươi.</CUE>'],
            translated_texts=None,
            src_lang="zh-Hans",
            target_lang="vi",
            context_before=['<CUE duration="1.0" speaker="Speaker 1">Ngươi là ai?</CUE>'],
            context_after=['<CUE duration="1.0" speaker="Speaker 1">Thật vậy sao?</CUE>'],
        )
    def test_quality_guard_supports_original_text_and_canonical_cues(self):
        source_segments = [
            {"id": 1, "start": 0.0, "end": 1.0, "original_text": "不错"},
            {"id": 2, "start": 1.0, "end": 2.0, "original_text": "在下韩念川"},
            {"id": 3, "start": 2.0, "end": 3.0, "original_text": "参见韩大人"},
        ]
        translated = ["Không tệ", "Ở dưới Hàn Niệm Xuyên", "Gặp Hàn đại nhân"]
        guarded, _ = apply_translation_quality_guard(
            source_segments=source_segments,
            translated_texts=translated,
            target_lang="vi",
        )
        self.assertEqual(guarded[0], "Đúng vậy")
        self.assertIn("tại hạ", guarded[1].lower())
        self.assertIn("bái kiến", guarded[2].lower())

    def test_orchestrator_source_text_extractors(self):
        orchestrator = TranslationOrchestrator()
        seg1 = {"original_text": "曹兄", "start": 1.0, "end": 2.0}
        seg2 = {"source_text": "韩兄", "start": 2.0, "end": 3.0}
        seg3 = {"text": "贺兄", "start": 3.0, "end": 4.0}
        self.assertEqual(orchestrator._segment_source_text(seg1), "曹兄")
        self.assertEqual(orchestrator._segment_source_text(seg2), "韩兄")
        self.assertEqual(orchestrator._segment_source_text(seg3), "贺兄")

        timed = orchestrator._build_timed_ai_source(seg1, 0)
        self.assertIn("曹兄", timed)
        self.assertIn('start="1.000"', timed)

    def test_validate_texts_and_clone_with_texts_behavior(self):
        from app.translation.srt_utils import clone_with_texts, validate_texts
        self.assertTrue(validate_texts(["Xin chào", ""], 2))
        self.assertFalse(validate_texts(["", ""], 2))
        self.assertFalse(validate_texts(["Xin chào"], 2))

        cloned = clone_with_texts([{"start": 1.0, "end": 2.0, "original_text": "曹兄"}], ["Tào huynh"], "test_prov")
        self.assertEqual(cloned[0]["source_text"], "曹兄")
        self.assertEqual(cloned[0]["text"], "Tào huynh")


if __name__ == "__main__":
    unittest.main()
