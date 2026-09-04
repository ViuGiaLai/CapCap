import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.translation.errors import TranslationValidationError
from app.translation.orchestrator import TranslationOrchestrator


class _TruncatingPolisher:
    """Fake polisher that reproduces the real failure: a numbered reply that
    is malformed whenever the requested batch exceeds a cue limit."""

    def __init__(self, hard_limit: int = 6):
        self.hard_limit = hard_limit
        self.attempt_sizes: list[int] = []

    def polish_batch(
        self,
        *,
        source_texts,
        translated_texts=None,
        style_instruction="",
        max_tokens=4096,
        **_kwargs,
    ):
        self.attempt_sizes.append(len(source_texts))
        if len(source_texts) > self.hard_limit:
            raise TranslationValidationError(
                f"Malformed or incomplete numbered output: "
                f"expected IDs 1..{len(source_texts)}, got [1, 2, 3]..."
            )
        # Mirrors each source so the merged result order can be asserted.
        return list(source_texts), [], "fake"


class TranslationBatchRecoveryTests(unittest.TestCase):
    def _run(self, polisher, texts):
        orchestrator = TranslationOrchestrator()
        return orchestrator._run_ai_batches(
            polisher=polisher,
            provider_type="google_ai_studio",
            source_texts=texts,
            translated_texts=None,
            src_lang="zh-Hans",
            target_lang="vi",
            style_instruction="",
            polish_batch_size=24,
        )

    def test_truncated_batch_is_split_into_smaller_retries(self):
        texts = [f"câu {index}" for index in range(1, 15)]
        polisher = _TruncatingPolisher(hard_limit=6)
        translated, providers, warnings = self._run(polisher, texts)

        self.assertEqual(translated, texts)  # merge kept the global order
        self.assertEqual(providers, ["fake"])
        self.assertEqual(warnings, [])
        # The original oversized attempt happened, then retries used <= 6 cues.
        # The original oversized attempt happened, then retries succeeded on
        # batches of 6 cues or fewer.
        self.assertGreater(max(polisher.attempt_sizes), 6)
        self.assertLessEqual(max(polisher.attempt_sizes), 14)
        self.assertLessEqual(min(polisher.attempt_sizes), 6)
        self.assertGreater(len(polisher.attempt_sizes), 1)

    def test_deep_split_recovers_multiple_truncations(self):
        # 27 cues: 27 -> 13+14 -> ... forces several nested half-splits with
        # a strict limit of 2 cues per request.
        texts = [f"câu {index}" for index in range(1, 28)]
        polisher = _TruncatingPolisher(hard_limit=2)
        translated, _providers, _warnings = self._run(polisher, texts)
        self.assertEqual(translated, texts)

    def test_single_cue_failure_still_surfaces(self):
        polisher = _TruncatingPolisher(hard_limit=0)
        with self.assertRaises(TranslationValidationError):
            self._run(polisher, ["câu 1"])


    def test_split_batches_receive_continuity_context(self):
        class _CapturingSplitPolisher(_TruncatingPolisher):
            def __init__(self, hard_limit: int = 4):
                super().__init__(hard_limit=hard_limit)
                self.contexts_seen = []

            def polish_batch(self, *, source_texts, context_before=None, context_after=None, **kwargs):
                self.contexts_seen.append((list(source_texts), list(context_before or []), list(context_after or [])))
                return super().polish_batch(source_texts=source_texts, **kwargs)

        texts = [f"câu {i}" for i in range(1, 9)]
        polisher = _CapturingSplitPolisher(hard_limit=4)
        translated, _providers, _warnings = self._run(polisher, texts)
        self.assertEqual(translated, texts)
        second_half_calls = [c for c in polisher.contexts_seen if len(c[0]) == 4 and c[0][0] == "câu 5"]
        self.assertTrue(second_half_calls)
        self.assertTrue(any("câu 4" in item for item in second_half_calls[0][1]))


if __name__ == "__main__":
    unittest.main()
