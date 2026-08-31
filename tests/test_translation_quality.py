import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.translation.orchestrator import TranslationOrchestrator
from app.translation.prompt_builder import build_translation_messages
from app.translation.quality_guard import apply_translation_quality_guard


class _CapturingPolisher:
    def __init__(self):
        self.styles = []

    def polish_batch(self, *, source_texts, style_instruction, **_kwargs):
        self.styles.append(style_instruction)
        return [f"dịch {index + 1}" for index in range(len(source_texts))], [], "fake"


class _RepairPolisher:
    def __init__(self):
        self.style = ""

    def polish_batch(self, *, style_instruction, **_kwargs):
        self.style = style_instruction
        return ["Hắn có 100 linh thạch"], [], "fake"


class _FallbackTranslator:
    def translate_batch(self, texts, **_kwargs):
        return ["Đừng tưởng rằng chúng ta sợ ngươi."] * len(texts)


class TranslationQualityTests(unittest.TestCase):
    def test_ai_source_contains_timing_metadata_but_keeps_one_line(self):
        value = TranslationOrchestrator._build_timed_ai_source(
            {"start": 2.5, "end": 4.75, "text": "原来他\n一直在骗我"},
            3,
        )
        self.assertIn('id="4"', value)
        self.assertIn('duration="2.250"', value)
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
        self.assertIn("Upcoming source context", polisher.styles[0])
        self.assertIn("preceding cues", polisher.styles[1])
        self.assertIn("câu một => dịch 1", polisher.styles[1])

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

    def test_translation_prompt_contains_fidelity_context_ocr_and_glossary_rules(self):
        system, _user = build_translation_messages(
            source_texts=['<CUE duration="2.0">师兄来了</CUE>'],
            translated_texts=None,
            src_lang="zh-Hans",
            target_lang="vi",
            style_instruction="recap",
        )
        self.assertIn("Meaning is the first quality gate", system)
        self.assertIn("2–5 neighbouring cues", system)
        self.assertIn("OCR/ASR safety", system)
        self.assertIn("师兄=sư huynh", system)
        self.assertIn("duration", system)

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
        self.assertIn("他来了", polisher.style)
        self.assertIn("然后离开", polisher.style)
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


if __name__ == "__main__":
    unittest.main()
