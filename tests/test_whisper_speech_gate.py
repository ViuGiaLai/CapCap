import tempfile
import unittest
import wave
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from services.chunking_service import ChunkingService
from whisper_processor import transcribe_audio_with_model


def _write_silent_wav(path: str, duration: float = 0.5) -> None:
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * int(16000 * duration))


class WhisperSpeechGateTests(unittest.TestCase):
    def test_confirmed_silence_never_invokes_whisper(self):
        fd, audio_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            _write_silent_wav(audio_path)
            model = SimpleNamespace(transcribe=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model called")))
            with patch("whisper_processor._detect_direct_speech_regions", return_value=[]):
                self.assertEqual(transcribe_audio_with_model(model, audio_path), [])
        finally:
            os.unlink(audio_path)

    def test_speech_segments_include_gate_metadata(self):
        segment = SimpleNamespace(
            start=0.1,
            end=1.2,
            text=" hello ",
            words=[],
            no_speech_prob=0.02,
        )
        model = SimpleNamespace(transcribe=lambda *args, **kwargs: ([segment], None))
        fd, audio_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            _write_silent_wav(audio_path, 2.0)
            with patch("whisper_processor._detect_direct_speech_regions", return_value=[{"start": 0.0, "end": 2.0}]):
                result = transcribe_audio_with_model(model, audio_path, use_batched=False)
        finally:
            os.unlink(audio_path)
        self.assertEqual(result[0]["text"], "hello")
        self.assertTrue(result[0]["speech_detected"])
        self.assertEqual(result[0]["speech_gate"], "silero_vad+whisper")
        self.assertAlmostEqual(result[0]["no_speech_prob"], 0.02)

    def test_chunking_keeps_all_silent_audio_empty(self):
        service = ChunkingService(tempfile.gettempdir())
        with patch.object(service, "probe_wav_duration", return_value=2.0), patch.object(
            service, "detect_speech_regions", return_value=[]
        ):
            self.assertEqual(service.build_chunks("ignored.wav", tempfile.mkdtemp()), [])

    def test_chunking_handles_silence_until_eof(self):
        service = ChunkingService(tempfile.gettempdir())
        completed = SimpleNamespace(stderr="silence_start: 0.00\n", returncode=0)
        fd, audio_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            with patch.object(service, "probe_wav_duration", return_value=2.0), patch.object(
                service, "ffmpeg_path", audio_path
            ), patch("services.chunking_service.subprocess.run", return_value=completed):
                self.assertEqual(service.detect_speech_regions(audio_path), [])
        finally:
            os.unlink(audio_path)


if __name__ == "__main__":
    unittest.main()
