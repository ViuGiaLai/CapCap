import os
import subprocess
import tempfile
import unittest
import sys

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from app.layers.timeline import Timeline
from app.services.timeline_video_sequence import (
    append_video,
    move_video,
    normalize_v1_sequence,
    remove_video,
    resolve_timeline_time,
    timeline_video_clips,
)


class TimelineVideoSequenceTests(unittest.TestCase):
    def test_append_reorder_remove_and_time_mapping(self):
        timeline = Timeline()
        first = append_video(timeline, "episode_1.mp4", 10.0)
        second = append_video(timeline, "episode_2.mp4", 20.0)
        clips = timeline_video_clips(timeline)
        self.assertEqual([clip.timeline_start for clip in clips], [0.0, 10.0])
        self.assertEqual(timeline.duration, 30.0)

        self.assertTrue(move_video(timeline, second.id, -1))
        clips = timeline_video_clips(timeline)
        self.assertEqual([os.path.basename(clip.source) for clip in clips], ["episode_2.mp4", "episode_1.mp4"])
        clip, local = resolve_timeline_time(timeline, 21.5)
        self.assertEqual(os.path.basename(clip.source), "episode_1.mp4")
        self.assertAlmostEqual(local, 1.5)

        self.assertTrue(remove_video(timeline, second.id))
        self.assertEqual(timeline.duration, 10.0)
        self.assertEqual(len(timeline_video_clips(timeline)), 1)
        audio_tracks = [track for track in timeline.tracks if track.name.startswith("A1")]
        self.assertEqual(len(audio_tracks[0].layers), 1)
        self.assertEqual(audio_tracks[0].layers[0].metadata["video_layer_id"], first.id)

    def test_normalize_preserves_trim_and_speed(self):
        timeline = Timeline()
        first = append_video(timeline, "one.mp4", 5.0)
        second = append_video(timeline, "two.mp4", 8.0)
        first.source_start = 2.0
        first.speed = 2.0
        first.end = 3.0
        normalize_v1_sequence(timeline)
        clips = timeline_video_clips(timeline)
        self.assertEqual(clips[0].source_start, 2.0)
        self.assertEqual(clips[0].source_duration, 6.0)
        self.assertEqual(clips[1].timeline_start, 3.0)
        self.assertEqual(timeline.duration, 11.0)


class TimelineSequenceExportTests(unittest.TestCase):
    def test_one_pass_export_joins_two_inputs(self):
        from app.runtime_paths import bin_path, subprocess_hidden_kwargs
        from app.services.timeline_sequence_export import export_timeline_sequence

        ffmpeg = str(bin_path("ffmpeg", "ffmpeg.exe"))
        ffprobe = str(bin_path("ffmpeg", "ffprobe.exe"))
        if not os.path.isfile(ffmpeg) or not os.path.isfile(ffprobe):
            self.skipTest("Bundled FFmpeg is unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = []
            for index, color in enumerate(("red", "blue")):
                path = os.path.join(temp_dir, f"source_{index}.mp4")
                command = [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"color=c={color}:s=320x180:d=0.6:r=24",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=0.6",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", path,
                ]
                subprocess.run(command, check=True, capture_output=True, **subprocess_hidden_kwargs())
                sources.append(path)
            clips = [
                {
                    "source": path,
                    "source_start": 0.0,
                    "source_duration": 0.5,
                    "timeline_start": index * 0.5,
                    "timeline_end": (index + 1) * 0.5,
                    "speed": 1.0,
                    "volume": 1.0,
                    "muted": False,
                }
                for index, path in enumerate(sources)
            ]
            output = os.path.join(temp_dir, "timeline.mp4")
            export_timeline_sequence(clips, output, output_fps=24)
            probe = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", output],
                check=True, capture_output=True, text=True, **subprocess_hidden_kwargs(),
            )
            self.assertTrue(os.path.isfile(output))
            self.assertAlmostEqual(float(probe.stdout.strip()), 1.0, delta=0.15)

            from workflows.prepare_workflow import PrepareWorkflow

            timeline_audio = os.path.join(temp_dir, "timeline_audio.wav")
            self.assertTrue(PrepareWorkflow(temp_dir)._extract_timeline_audio(clips, timeline_audio))
            audio_probe = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", timeline_audio],
                check=True, capture_output=True, text=True, **subprocess_hidden_kwargs(),
            )
            self.assertAlmostEqual(float(audio_probe.stdout.strip()), 1.0, delta=0.08)


if __name__ == "__main__":
    unittest.main()
