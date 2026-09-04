from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.translation.srt_utils import parse_srt


def test_parse_srt_skips_malformed_and_non_positive_cues():
    content = (
        "1\n00:00:01,000 --> 00:00:02,000\nvalid\n\n"
        "2\nnot-a-time --> 00:00:03,000\ninvalid\n\n"
        "3\n00:00:04,000 --> 00:00:04,000\nzero\n\n"
        "4\n00:00:05,000 --> 00:00:06,000\nvalid 2\n"
    )
    assert parse_srt(content) == [
        {"start": 1.0, "end": 2.0, "text": "valid"},
        {"start": 5.0, "end": 6.0, "text": "valid 2"},
    ]


def test_parse_srt_rejects_invalid_minute_or_second_fields():
    content = "1\n00:61:00,000 --> 00:62:00,000\ninvalid\n"
    assert parse_srt(content) == []
