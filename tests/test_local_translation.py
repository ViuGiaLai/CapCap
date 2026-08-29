import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from services.resource_download_service import ResourceDownloadService
from services import local_translation_config as local_config
from translation.orchestrator import TranslationOrchestrator
from translation.providers.local_gguf_translator import LocalGGUFTranslatorProvider


class _FailingProvider:
    model_name = "test"

    @staticmethod
    def is_configured():
        return True

    @staticmethod
    def polish_batch(**_kwargs):
        raise RuntimeError("intentional provider failure")


class LocalTranslationTests(unittest.TestCase):
    def test_resource_is_one_click_and_pinned(self):
        service = ResourceDownloadService(str(ROOT))
        item = next(
            resource for resource in service.list_resources()
            if resource["id"] == service.LOCAL_TRANSLATION_RESOURCE_ID
        )
        self.assertTrue(item["auto_download_supported"])
        self.assertEqual(len(service.LOCAL_TRANSLATION_MODEL_SHA256), 64)
        self.assertEqual(len(service.LOCAL_TRANSLATION_RUNTIME_SHA256), 64)
        self.assertEqual(
            service.LOCAL_TRANSLATION_MODEL_SHA256,
            "4383ac0c3c8e476de98ff979c2a3f069f8c4fb385e7860cf2d28da896cc477c7",
        )

    def test_safe_zip_rejects_path_traversal(self):
        service = ResourceDownloadService(str(ROOT))
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "bad.zip")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../outside.txt", "bad")
            with self.assertRaises(ValueError):
                service._extract_zip_safely(archive_path, os.path.join(temp_dir, "target"))

    def test_verified_download_rejects_wrong_checksum(self):
        service = ResourceDownloadService(str(ROOT))
        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "source.bin")
            target = os.path.join(temp_dir, "target.bin")
            Path(source).write_bytes(b"capcap")
            with self.assertRaises(IOError):
                service._download_verified_file(
                    url=Path(source).as_uri(),
                    target=target,
                    expected_size=6,
                    expected_sha256="0" * 64,
                    label="test",
                )

    def test_selected_ai_failure_does_not_silently_use_google(self):
        orchestrator = TranslationOrchestrator()
        with patch.object(orchestrator, "_resolve_ai_provider", return_value=("local_hymt", _FailingProvider())):
            result = orchestrator.translate_segments(
                segments=[{"start": 0.0, "end": 1.0, "text": "贤侄，你先撤，我断后。"}],
                src_lang="zh",
                target_lang="vi",
                enable_polish=True,
            )
        self.assertFalse(result.success)
        self.assertEqual(result.primary_provider, "local_hymt")
        self.assertIn("intentional provider failure", result.errors[0])

    def test_local_provider_requires_installed_assets(self):
        provider = LocalGGUFTranslatorProvider()
        with patch(
            "translation.providers.local_gguf_translator.local_translation_assets_ready",
            return_value=False,
        ):
            self.assertFalse(provider.is_configured())

    def test_hymt_tagged_output_is_clean_and_ordered(self):
        parsed = LocalGGUFTranslatorProvider._parse_hymt_output(
            "<target><sn>1.</sn>Xin chào.</sn>\n<sn>2.</sn>Tạm biệt.</target>"
        )
        self.assertEqual(parsed, [(1, "Xin chào."), (2, "Tạm biệt.")])

    def test_hymt_prompt_applies_contextual_terminology(self):
        prompt = LocalGGUFTranslatorProvider._build_hymt_prompt(
            ["贤侄，你先撤，我断后。"], "vi"
        )
        self.assertIn("贤侄 翻译成 hiền điệt", prompt)
        self.assertIn("我断后 翻译成 ta sẽ chặn hậu", prompt)

    def test_custom_storage_and_model_selection_are_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "local_translation.json")
            storage_dir = os.path.join(temp_dir, "models elsewhere")
            custom_model = os.path.join(temp_dir, "translation.gguf")
            Path(custom_model).write_bytes(b"GGUF" + b"\0" * 32)
            with patch.object(local_config, "settings_path", return_value=config_path):
                local_config.save_local_translation_config(
                    model_id="custom",
                    storage_dir=storage_dir,
                    custom_model_path=custom_model,
                )
                loaded = local_config.load_local_translation_config()
                selected = local_config.selected_model_info()
            self.assertEqual(loaded["storage_dir"], os.path.abspath(storage_dir))
            self.assertEqual(selected["path"], os.path.abspath(custom_model))

    def test_scan_finds_only_valid_gguf_models(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            valid = os.path.join(temp_dir, "valid.gguf")
            invalid = os.path.join(temp_dir, "invalid.gguf")
            Path(valid).write_bytes(b"GGUF" + b"\0" * 32)
            Path(invalid).write_bytes(b"NOPE" + b"\0" * 32)
            found = local_config.scan_gguf_models(temp_dir)
            self.assertEqual(found, [(valid, os.path.getsize(valid))])

    def test_all_downloadable_quantizations_have_pinned_metadata(self):
        self.assertEqual(set(local_config.HYMT_MODELS), {"q4_k_m", "q6_k", "q8_0"})
        for entry in local_config.HYMT_MODELS.values():
            self.assertGreater(entry["size"], 1_000_000_000)
            self.assertEqual(len(entry["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
