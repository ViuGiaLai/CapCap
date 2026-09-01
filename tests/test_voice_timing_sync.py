import os
import math
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.audio_mixer import build_voice_track_from_srt_segments, cap_wav_to_duration, fit_wav_to_duration, ffprobe_wav_duration
from app.workflows.voice_workflow import VoiceWorkflow


def _make_silent_wav(path: str, duration: float, sample_rate: int = 16000) -> None:
    with wave.open(path, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x00\x00" * int(duration * sample_rate))


def _make_tone_wav(path: str, duration: float, sample_rate: int = 16000) -> None:
    frames = bytearray()
    for index in range(int(duration * sample_rate)):
        sample = int(8000 * math.sin(2.0 * math.pi * 440.0 * index / sample_rate))
        frames.extend(struct.pack("<h", sample))
    with wave.open(path, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(bytes(frames))


class VoiceTimingSyncTests(unittest.TestCase):
    def test_hard_duration_cap_uses_a_short_fade_and_hits_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "long.wav")
            capped = os.path.join(folder, "capped.wav")
            _make_tone_wav(source, 2.0)

            result = cap_wav_to_duration(
                input_wav_path=source,
                output_wav_path=capped,
                target_duration_seconds=1.0,
            )

            self.assertEqual(result, capped)
            self.assertAlmostEqual(ffprobe_wav_duration(capped), 1.0, delta=0.05)

    def test_voice_workflow_caps_audio_before_the_next_cue(self):
        with tempfile.TemporaryDirectory() as folder:
            first = os.path.join(folder, "first.wav")
            second = os.path.join(folder, "second.wav")
            _make_tone_wav(first, 2.0)
            _make_tone_wav(second, 0.5)
            segments = [
                {"start": 0.0, "end": 0.8, "text": "First"},
                {"start": 1.0, "end": 1.5, "text": "Second"},
            ]
            workflow = VoiceWorkflow(str(ROOT))

            wavs = workflow._enforce_non_overlapping_voice_windows(
                segments=segments,
                wavs=[first, second],
                tmp_dir=folder,
            )

            self.assertLessEqual(ffprobe_wav_duration(wavs[0]), 0.97)
            self.assertIn("no_overlap_fade", segments[0]["action_taken"])

    def test_mixer_never_sums_a_long_voice_over_the_next_cue(self):
        with tempfile.TemporaryDirectory() as folder:
            first = os.path.join(folder, "first.wav")
            second = os.path.join(folder, "second.wav")
            output = os.path.join(folder, "voice.wav")
            _make_tone_wav(first, 2.0)
            _make_silent_wav(second, 0.5)
            segments = [
                {"start": 0.0, "end": 0.8},
                {"start": 1.0, "end": 1.5},
            ]

            build_voice_track_from_srt_segments(
                segments=segments,
                tts_wav_paths=[first, second],
                output_wav_path=output,
            )

            with wave.open(output, "rb") as rendered:
                rendered.setpos(int(1.1 * rendered.getframerate()))
                samples = rendered.readframes(int(0.2 * rendered.getframerate()))
            self.assertTrue(samples)
            self.assertEqual(max(abs(value) for value in struct.unpack(f"<{len(samples) // 2}h", samples)), 0)

    def test_smart_fit_really_slows_short_speech_to_subtitle_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "short.wav")
            fitted = os.path.join(folder, "fitted.wav")
            _make_silent_wav(source, 1.6)

            result = fit_wav_to_duration(
                input_wav_path=source,
                output_wav_path=fitted,
                target_duration_seconds=2.0,
                mode="smart",
            )

            self.assertEqual(result, fitted)
            self.assertAlmostEqual(ffprobe_wav_duration(fitted), 2.0, delta=0.12)

    def test_smart_fit_speeds_long_speech_without_cutting_words(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "long.wav")
            fitted = os.path.join(folder, "fitted.wav")
            _make_silent_wav(source, 2.0)

            result = fit_wav_to_duration(
                input_wav_path=source,
                output_wav_path=fitted,
                target_duration_seconds=1.6,
                mode="smart",
            )

            self.assertEqual(result, fitted)
            self.assertAlmostEqual(ffprobe_wav_duration(fitted), 1.6, delta=0.12)

    def test_very_short_speech_keeps_source_subtitle_window(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "very_short.wav")
            _make_silent_wav(source, 0.6)
            segments = [{"start": 1.0, "end": 3.0, "text": "A long subtitle"}]
            workflow = VoiceWorkflow(str(ROOT))

            workflow._extend_segment_ends_to_audio(
                segments=segments,
                wavs=[source],
                sync_mode="Smart",
            )

            self.assertAlmostEqual(segments[0]["_audio_end"], 1.6, delta=0.02)
            self.assertAlmostEqual(segments[0]["end"], 3.0, delta=0.03)
            self.assertNotIn("_original_end", segments[0])
            self.assertNotIn("subtitle_sync", segments[0].get("action_taken", ""))

    def test_unavoidably_long_speech_extends_visual_subtitle_to_audio_end(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "very_long.wav")
            _make_silent_wav(source, 3.0)
            segments = [{"start": 1.0, "end": 3.0, "text": "Long speech"}]
            workflow = VoiceWorkflow(str(ROOT))

            workflow._extend_segment_ends_to_audio(
                segments=segments,
                wavs=[source],
                sync_mode="Smart",
            )

            self.assertAlmostEqual(segments[0]["end"], 4.0, delta=0.02)
            self.assertEqual(segments[0]["_original_end"], 3.0)
            self.assertIn("subtitle_sync", segments[0]["action_taken"])

    def test_long_speech_never_extends_visual_subtitle_over_next_cue(self):
        with tempfile.TemporaryDirectory() as folder:
            first = os.path.join(folder, "first_long.wav")
            second = os.path.join(folder, "second.wav")
            _make_silent_wav(first, 3.0)
            _make_silent_wav(second, 1.0)
            segments = [
                {"start": 1.0, "end": 2.0, "text": "First"},
                {"start": 2.2, "end": 3.2, "text": "Second"},
            ]
            workflow = VoiceWorkflow(str(ROOT))

            workflow._extend_segment_ends_to_audio(
                segments=segments,
                wavs=[first, second],
                sync_mode="Smart",
            )

            self.assertAlmostEqual(segments[0]["_audio_end"], 4.0, delta=0.02)
            self.assertAlmostEqual(segments[0]["end"], 2.16, delta=0.02)
            self.assertLess(segments[0]["end"], segments[1]["start"])

    def test_requested_voice_speed_is_applied_before_final_smart_sync(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "speech.wav")
            _make_tone_wav(source, 2.0)
            segments = [{"start": 0.0, "end": 2.0, "text": "Test speech"}]
            workflow = VoiceWorkflow(str(ROOT))

            wavs = workflow._apply_safe_timing_polish(
                segments=segments,
                wavs=[source],
                tmp_dir=folder,
                voice_speed=1.2,
                sync_mode="Smart",
            )
            _, wavs = workflow._apply_deficit_timing_polish(
                segments=segments,
                wavs=wavs,
                tmp_dir=folder,
                sync_mode="Smart",
            )

            self.assertAlmostEqual(ffprobe_wav_duration(wavs[0]), 2.0, delta=0.15)


if __name__ == "__main__":
    unittest.main()
