import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from app.audio_mixer import voice_track_storage_plan
from app.audio_waveform import build_waveform_envelope
from app.translation.orchestrator import TranslationOrchestrator


class LongMediaStabilityTests(unittest.TestCase):
    def test_one_to_five_hour_voice_tracks_use_disk_backed_storage(self):
        for hours in (1, 2, 3, 5):
            plan = voice_track_storage_plan(hours * 3600)
            self.assertEqual(plan["backend"], "disk_chunks")
            self.assertLessEqual(plan["peak_chunk_bytes"], 6_000_000)

    def test_waveform_length_is_bounded_for_five_hour_wav(self):
        sample_rate = 100
        frames = 5 * 3600 * sample_rate
        data_size = frames * 2
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + data_size, b"WAVE",
            b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
            b"data", data_size,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "five_hours.wav")
            with open(path, "wb") as handle:
                handle.write(header)
                handle.write(struct.pack("<h", 12000))
                handle.truncate(44 + data_size)
            waveform, duration = build_waveform_envelope(path)
        self.assertAlmostEqual(duration, 5 * 3600, places=2)
        self.assertLessEqual(len(waveform), 1200)

    def test_five_hour_translation_plan_remains_batched(self):
        cues = [f"Cue {index}" for index in range(5 * 1800)]
        batches, full_context = TranslationOrchestrator._build_ai_batches(
            source_texts=cues, translated_texts=None, requested_max_segments=80,
        )
        self.assertFalse(full_context)
        self.assertEqual(sum(len(batch[0]) for batch in batches), len(cues))
        self.assertTrue(all(len(batch[0]) <= 80 for batch in batches))


if __name__ == "__main__":
    unittest.main()
