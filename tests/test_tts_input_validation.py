from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "app"), str(ROOT)]

from tts_processor import _speed_to_float


def test_tts_speed_normalizes_non_finite_values():
    assert _speed_to_float("nan") == 1.0
    assert _speed_to_float(float("inf")) == 1.0


def test_tts_speed_keeps_valid_positive_values():
    assert _speed_to_float("1.25x") == 1.25
