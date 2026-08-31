import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from services.asr_ocr_reconciliation_service import AsrOcrReconciliationService
from sensevoice_processor import (
    _lang_code,
    _pad_and_merge_vad_segments,
    requires_multilingual_whisper,
    supports_language,
)


class AsrOcrReconciliationTests(unittest.TestCase):
    def test_restores_truncated_chinese_cue_at_same_time(self):
        asr = [{"start": 81.464, "end": 82.272, "text": "下"}]
        ocr = [{"start": 81.25, "end": 82.50, "text": "等一下"}]

        repaired, count = AsrOcrReconciliationService.reconcile(asr, ocr)

        self.assertEqual(count, 1)
        self.assertEqual(repaired[0]["text"], "等一下")
        self.assertEqual(repaired[0]["asr_text_original"], "下")
        self.assertEqual(repaired[0]["text_source"], "ocr_reconciled")
        self.assertEqual(repaired[0]["start"], 81.464)
        self.assertEqual(repaired[0]["end"], 82.272)

    def test_keeps_complete_asr_text(self):
        asr = [{"start": 1.0, "end": 2.0, "text": "等一下"}]
        ocr = [{"start": 1.0, "end": 2.0, "text": "等一下"}]

        repaired, count = AsrOcrReconciliationService.reconcile(asr, ocr)

        self.assertEqual(count, 0)
        self.assertEqual(repaired, asr)

    def test_does_not_copy_unrelated_title_or_non_overlapping_text(self):
        asr = [{"start": 10.0, "end": 10.7, "text": "下"}]
        ocr = [
            {"start": 10.0, "end": 10.7, "text": "修仙传奇"},
            {"start": 20.0, "end": 21.0, "text": "等一下"},
        ]

        repaired, count = AsrOcrReconciliationService.reconcile(asr, ocr)

        self.assertEqual(count, 0)
        self.assertEqual(repaired[0]["text"], "下")

    def test_scan_gate_does_not_use_chinese_signs_for_other_languages(self):
        segments = [{"start": 0.0, "end": 1.0, "text": "下"}]
        self.assertTrue(AsrOcrReconciliationService.should_scan(segments, "zh"))
        self.assertTrue(AsrOcrReconciliationService.should_scan(segments, "auto"))
        self.assertFalse(AsrOcrReconciliationService.should_scan(segments, "en"))

    def test_repairs_supported_writing_systems_without_cross_script_replacement(self):
        examples = [
            ("ja", "て", "待って"),
            ("ko", "려", "기다려"),
            ("en", "wait", "Wait a moment"),
            ("vi", "đã", "Đợi đã"),
            ("ru", "жди", "Подожди"),
            ("ar", "قف", "توقف"),
            ("th", "รอ", "รอก่อน"),
        ]
        for language, partial, complete in examples:
            with self.subTest(language=language):
                repaired, count = AsrOcrReconciliationService.reconcile(
                    [{"start": 3.0, "end": 3.7, "text": partial}],
                    [{"start": 2.9, "end": 3.8, "text": complete}],
                    source_language=language,
                )
                self.assertEqual(count, 1)
                self.assertEqual(repaired[0]["text"], complete)

                cross_script, cross_count = AsrOcrReconciliationService.reconcile(
                    [{"start": 3.0, "end": 3.7, "text": partial}],
                    [{"start": 2.9, "end": 3.8, "text": "等一下"}],
                    source_language=language,
                )
                self.assertEqual(cross_count, 0)
                self.assertEqual(cross_script[0]["text"], partial)

    def test_latin_matching_uses_complete_words_not_substrings(self):
        repaired, count = AsrOcrReconciliationService.reconcile(
            [{"start": 1.0, "end": 1.5, "text": "he"}],
            [{"start": 1.0, "end": 1.5, "text": "The hero returns"}],
            source_language="en",
        )
        self.assertEqual(count, 0)
        self.assertEqual(repaired[0]["text"], "he")

    def test_only_suspicious_cue_windows_are_requested_for_ocr(self):
        ranges = AsrOcrReconciliationService.suspicious_time_ranges([
            {"start": 20.0, "end": 20.4, "text": "完整句子"},
            {"start": 10.0, "end": 10.4, "text": "下"},
            {"start": 11.0, "end": 11.2, "text": "走"},
        ])
        self.assertEqual(ranges, [(9.25, 11.95)])


class SenseVoiceBoundaryTests(unittest.TestCase):
    def test_vad_boundaries_are_merged_and_padded(self):
        result = _pad_and_merge_vad_segments(
            [
                {"start": 1.00, "end": 1.30},
                {"start": 1.40, "end": 1.80},
                {"start": 3.00, "end": 3.20},
            ],
            4.0,
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {"start": 0.78, "end": 1.98})
        self.assertEqual(result[1], {"start": 2.78, "end": 3.38})

    def test_vietnamese_is_not_forced_through_chinese_decoder(self):
        self.assertEqual(_lang_code("vi"), "auto")
        self.assertEqual(_lang_code("zh-CN"), "zh")

    def test_only_native_sensevoice_languages_stay_on_sensevoice(self):
        for language in ("auto", "zh", "zh-CN", "yue", "en", "ja", "ko"):
            self.assertTrue(supports_language(language), language)
        for language in ("vi", "th", "id", "es", "fr", "de", "pt", "ru", "ar"):
            self.assertFalse(supports_language(language), language)
        for language in ("zh", "zh-CN", "yue", "en", "ja", "ko"):
            self.assertFalse(requires_multilingual_whisper(language), language)
        for language in ("auto", "vi", "th", "id", "es", "fr", "de", "pt", "ru", "ar"):
            self.assertTrue(requires_multilingual_whisper(language), language)


if __name__ == "__main__":
    unittest.main()
