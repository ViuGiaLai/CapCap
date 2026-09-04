import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.translation.orchestrator import TranslationOrchestrator


class _GroupingPolisher:
    provider_id = "google_ai_studio"

    def __init__(self, fail_group=False):
        self.fail_group = fail_group
        self.call_sizes = []
        self._seq = 0

    def polish_batch(self, *, source_texts, style_instruction="", **_kwargs):
        self.call_sizes.append(len(source_texts))
        if self.fail_group and len(source_texts) > 1:
            raise RuntimeError("group exploded")
        lines = [f"FIX-{self._seq + index + 1}" for index in range(len(source_texts))]
        self._seq += len(source_texts)
        return lines, [], "fake"

    def is_configured(self):
        return True


class TranslationRepairBatchingTests(unittest.TestCase):
    def _run(self, polisher, n_cues, warnings):
        orchestrator = TranslationOrchestrator()
        segments = [{"start": 0.0, "end": 2.0, "text": f"câu {i}"} for i in range(1, n_cues + 1)]
        ai_sources = [orchestrator._build_timed_ai_source(seg, i) for i, seg in enumerate(segments)]
        drafts = [f"dịch {i}" for i in range(1, n_cues + 1)]
        return orchestrator._repair_ai_quality_issues(
            polisher=polisher,
            source_segments=segments,
            ai_source_texts=ai_sources,
            translated_texts=drafts,
            quality_warnings=warnings,
            src_lang="zh-Hans",
            target_lang="vi",
            style_instruction="recap",
        )

    def test_flagged_cues_are_repaired_in_grouped_requests(self):
        # 18 flagged cues: 8 + 8 + 2 = 3 grouped requests instead of 18.
        warnings = [f"Cue {i}: bản dịch trống." for i in range(1, 19)]
        polisher = _GroupingPolisher()
        repaired, _final_warnings = self._run(polisher, 18, warnings)

        self.assertEqual(polisher.call_sizes, [8, 8, 2])
        self.assertEqual(repaired, [f"FIX-{i + 1}" for i in range(18)])

    def test_failed_group_falls_back_to_cue_by_cue(self):
        warnings = [f"Cue {i}: bản dịch trống." for i in range(1, 6)]
        polisher = _GroupingPolisher(fail_group=True)
        repaired, _final_warnings = self._run(polisher, 5, warnings)

        # One failed grouped attempt (5 cues) then 5 single-cue repairs.
        self.assertEqual(polisher.call_sizes[0], 5)
        self.assertEqual(polisher.call_sizes[1:], [1] * 5)
        self.assertEqual(repaired, [f"FIX-{i + 1}" for i in range(5)])

    def test_local_providers_keep_single_cue_repairs(self):
        warnings = [f"Cue {i}: bản dịch trống." for i in range(1, 11)]
        polisher = _GroupingPolisher()
        polisher.provider_id = "ollama"
        _repaired, _final_warnings = self._run(polisher, 10, warnings)
        self.assertEqual(polisher.call_sizes, [1] * 10)


if __name__ == "__main__":
    unittest.main()
