import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.translation.errors import TranslationProviderError
from app.translation.providers.gemini_polisher import OpenAICompatiblePolisherProvider
from app.translation.providers.google_web_translator import GoogleWebTranslatorProvider


class _RateLimitError(Exception):
    status_code = 429


class _GenericApiError(Exception):
    pass


class _FakeClient:
    def __init__(self, error):
        self.error = error
        self.calls = 0

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **_kwargs):
        self.calls += 1
        raise self.error


class TranslationProviderErrorTests(unittest.TestCase):
    _ENV_KEYS = ("UNIT_API_KEY", "UNIT_MODEL", "UNIT_BASE_URL")

    def setUp(self):
        self._old = {key: os.environ.get(key) for key in self._ENV_KEYS}
        os.environ["UNIT_API_KEY"] = "test-key"
        os.environ["UNIT_MODEL"] = "test-model"
        os.environ["UNIT_BASE_URL"] = "http://127.0.0.1:1/v1"

    def tearDown(self):
        for key, value in self._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _provider(self):
        return OpenAICompatiblePolisherProvider(
            provider_id="custom",
            display_name="Test AI",
            env_prefix="UNIT",
            default_base_url="http://127.0.0.1:1/v1",
            default_model="test-model",
        )

    def test_quota_error_fails_fast_with_clear_message(self):
        provider = self._provider()
        fake = _FakeClient(_RateLimitError("quota exceeded"))
        provider._client = fake

        with self.assertRaises(TranslationProviderError) as raised:
            provider.polish_batch(
                source_texts=["câu 1"],
                src_lang="zh-Hans",
                target_lang="vi",
                style_instruction="",
                max_retries=2,
            )
        message = str(raised.exception).lower()
        self.assertIn("quota", message)
        self.assertEqual(fake.calls, 1)  # no pointless retries on quota errors

    def test_generic_error_still_retries_then_reports(self):
        provider = self._provider()
        fake = _FakeClient(_GenericApiError("connection reset"))
        provider._client = fake

        with self.assertRaises(TranslationProviderError) as raised:
            provider.polish_batch(
                source_texts=["câu 1"],
                src_lang="zh-Hans",
                target_lang="vi",
                style_instruction="",
                max_retries=2,
            )
        self.assertIn("connection reset", str(raised.exception))
        self.assertGreater(fake.calls, 1)

    def test_google_fallback_does_not_return_source_on_total_failure(self):
        provider = GoogleWebTranslatorProvider()
        with patch.object(provider, "ENDPOINTS", []), patch(
            "app.translation.providers.google_web_translator.requests.get",
            side_effect=RuntimeError("offline"),
        ):
            with self.assertRaises(TranslationProviderError):
                provider._translate_single_text_with_fallbacks(
                    text="你好",
                    src_lang="zh-Hans",
                    target_lang="vi",
                    timeout=1,
                    max_retries=1,
                )


if __name__ == "__main__":
    unittest.main()
