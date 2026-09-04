import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from ocr_processor import (
    _OCR_MODEL_CATALOG,
    _resolve_ocr_profile,
)


def _make_models_dir(*file_names: str) -> str:
    directory = tempfile.mkdtemp(prefix="ocr_models_")
    for name in file_names:
        Path(directory, name).write_bytes(b"")
    return directory


class OcrModelSelectionTests(unittest.TestCase):
    def setUp(self):
        self._previous = os.environ.get("VIUSTUDIO_OCR_QUALITY")
        if self._previous is None:
            os.environ.pop("VIUSTUDIO_OCR_QUALITY", None)

    def tearDown(self):
        if self._previous is None:
            os.environ.pop("VIUSTUDIO_OCR_QUALITY", None)
        else:
            os.environ["VIUSTUDIO_OCR_QUALITY"] = self._previous

    def _set_quality(self, quality):
        if quality is None:
            os.environ.pop("VIUSTUDIO_OCR_QUALITY", None)
        else:
            os.environ["VIUSTUDIO_OCR_QUALITY"] = quality

    def test_default_balanced_selects_v6_small(self):
        models_dir = _make_models_dir(
            *_OCR_MODEL_CATALOG["balanced"][:2],
            "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        )
        requested, key, det, rec, version, model_type, label = _resolve_ocr_profile(models_dir)
        self.assertEqual(requested, "balanced")
        self.assertEqual(key, "balanced")
        self.assertEqual(det, "PP-OCRv6_det_small.onnx")
        self.assertEqual(version, "PP-OCRv6")
        self.assertEqual(model_type, "small")

    def test_best_selects_v6_medium_when_bundled(self):
        models_dir = _make_models_dir(
            *_OCR_MODEL_CATALOG["best"][:2],
            *_OCR_MODEL_CATALOG["balanced"][:2],
        )
        self._set_quality("best")
        requested, key, det, rec, version, model_type, label = _resolve_ocr_profile(models_dir)
        self.assertEqual(requested, "best")
        self.assertEqual(key, "best")
        self.assertIn("medium", det)

    def test_best_falls_back_to_small_when_medium_absent(self):
        models_dir = _make_models_dir(
            *_OCR_MODEL_CATALOG["balanced"][:2],
        )
        self._set_quality("best")
        requested, key, det, rec, version, model_type, label = _resolve_ocr_profile(models_dir)
        self.assertEqual(requested, "best")
        self.assertEqual(key, "balanced")
        self.assertEqual(det, "PP-OCRv6_det_small.onnx")
        self.assertEqual(label, "PP-OCRv6 small")

    def test_fast_falls_back_across_chain(self):
        models_dir = _make_models_dir(
            *_OCR_MODEL_CATALOG["v4"][:2],
        )
        self._set_quality("fast")
        requested, key, det, _rec, version, model_type, _label = _resolve_ocr_profile(models_dir)
        self.assertEqual(requested, "fast")
        self.assertEqual(key, "v4")
        self.assertEqual(version, "PP-OCRv4")

    def test_no_supported_files_returns_none(self):
        models_dir = _make_models_dir("unrelated.txt")
        self._set_quality("best")
        requested, key, det, rec, version, model_type, label = _resolve_ocr_profile(models_dir)
        self.assertEqual(requested, "best")
        self.assertIsNone(key)
        self.assertIsNone(det)
        self.assertEqual(label, "")

    def test_unknown_quality_falls_back_to_balanced(self):
        models_dir = _make_models_dir(
            *_OCR_MODEL_CATALOG["balanced"][:2],
        )
        self._set_quality("ultra")
        requested, key, _det, _rec, _version, _model_type, label = _resolve_ocr_profile(models_dir)
        self.assertEqual(requested, "balanced")
        self.assertEqual(key, "balanced")
        self.assertEqual(label, "PP-OCRv6 small")


if __name__ == "__main__":
    unittest.main()
