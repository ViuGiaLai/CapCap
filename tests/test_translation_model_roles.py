import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.translation.orchestrator import TranslationOrchestrator


class TranslationModelRoleTests(unittest.TestCase):
    _ENV_KEYS = [
        "OPENAI_PROVIDER", "AI_POLISHER_PROVIDER",
        "GOOGLE_AI_STUDIO_MODEL", "GOOGLE_AI_STUDIO_POLISH_MODEL",
    ]

    def setUp(self):
        self._old = {key: os.environ.get(key) for key in self._ENV_KEYS}
        os.environ["OPENAI_PROVIDER"] = "google_ai_studio"
        os.environ["AI_POLISHER_PROVIDER"] = "google_ai_studio"
        os.environ.pop("GOOGLE_AI_STUDIO_MODEL", None)
        os.environ.pop("GOOGLE_AI_STUDIO_POLISH_MODEL", None)

    def tearDown(self):
        for key, value in self._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_quality_role_uses_dedicated_model_when_set(self):
        os.environ["GOOGLE_AI_STUDIO_POLISH_MODEL"] = "gemini-2.5-pro-custom"
        orchestrator = TranslationOrchestrator()
        _provider, translate_polisher = orchestrator._resolve_ai_provider(role="translate")
        _provider2, quality_polisher = orchestrator._resolve_ai_provider(role="quality")

        self.assertEqual(translate_polisher.model_name, "gemini-2.5-flash")
        self.assertEqual(quality_polisher.model_name, "gemini-2.5-pro-custom")

    def test_quality_role_defaults_to_pro_for_gemini(self):
        # No dedicated env: the quality role falls back to gemini-2.5-pro
        # while the translate role keeps the fast flash default.
        orchestrator = TranslationOrchestrator()
        _provider, translate_polisher = orchestrator._resolve_ai_provider(role="translate")
        _provider2, quality_polisher = orchestrator._resolve_ai_provider(role="quality")

        self.assertEqual(translate_polisher.model_name, "gemini-2.5-flash")
        self.assertEqual(quality_polisher.model_name, "gemini-2.5-pro")


if __name__ == "__main__":
    unittest.main()
