import os
import sys
import unittest
from unittest.mock import patch

import numpy as np


APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

import sensevoice_processor


class _Result:
    def __init__(self, text=""):
        self.text = text


class _Stream:
    def __init__(self):
        self.result = _Result()

    def accept_waveform(self, sample_rate, audio):
        self.sample_rate = sample_rate
        self.audio = audio


class _Recognizer:
    def __init__(self):
        self.batch_sizes = []

    def create_stream(self):
        return _Stream()

    def decode_streams(self, streams):
        self.batch_sizes.append(len(streams))
        for index, stream in enumerate(streams):
            stream.result.text = f"line-{index}"


class SenseVoiceBatchTests(unittest.TestCase):
    def test_presegmented_chunks_are_decoded_in_batches_without_vad(self):
        recognizer = _Recognizer()
        mono_second = np.zeros(16000, dtype=np.int16)
        progress = []
        with (
            patch.object(sensevoice_processor, "load_model"),
            patch.object(sensevoice_processor, "_recognizer", recognizer),
            patch.object(sensevoice_processor.wavfile, "read", return_value=(16000, mono_second)),
            patch.object(
                sensevoice_processor,
                "get_speech_segments",
                create=True,
                side_effect=AssertionError("VAD must not run for pre-segmented chunks"),
            ),
        ):
            results = sensevoice_processor.transcribe_presegmented_audio_batch(
                ["a.wav", "b.wav", "c.wav"],
                "model",
                language="zh",
                batch_size=2,
                progress_callback=lambda done, total: progress.append((done, total)),
            )

        self.assertEqual(recognizer.batch_sizes, [2, 1])
        self.assertEqual(progress, [(2, 3), (3, 3)])
        self.assertEqual(len(results), 3)
        self.assertEqual([item[0]["end"] for item in results], [1.0, 1.0, 1.0])
        self.assertTrue(all(item[0]["text"].startswith("line-") for item in results))

    def test_thread_count_leaves_cpu_capacity_for_ui(self):
        with patch.object(sensevoice_processor.os, "cpu_count", return_value=12):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("VIUSTUDIO_ASR_THREADS", None)
                self.assertEqual(sensevoice_processor._sensevoice_thread_count(), 8)


if __name__ == "__main__":
    unittest.main()
