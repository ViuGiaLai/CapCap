import os
import subprocess
import tempfile
import unittest
from app.services.auto_recap_engine import AutoRecapConfig, AutoRecapEngine


class TestAutoRecapIntegration(unittest.TestCase):
    def test_ffmpeg_1pass_render_synthetic_video(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_video = os.path.join(tmpdir, "input_test.mp4")
            output_video = os.path.join(tmpdir, "output_recap.mp4")

            cmd_gen = [
                "ffmpeg", "-y", "-hide_banner",
                "-f", "lavfi", "-i", "testsrc=duration=4:size=640x360:rate=24",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                "-c:v", "libx264", "-c:a", "aac",
                input_video
            ]
            res_gen = subprocess.run(cmd_gen, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res_gen.returncode != 0:
                self.skipTest("FFmpeg is not available in environment.")

            engine = AutoRecapEngine(AutoRecapConfig())
            segments = [
                {"start": 0.0, "end": 2.0, "text": "Cảnh quay quan trọng thứ nhất!"},
                {"start": 2.0, "end": 4.0, "text": "Bí mật bứt phá thành công!"},
            ]
            edl = engine.generate_edl(segments)
            self.assertGreater(len(edl), 0)

            success = engine.render_recap_video_1pass(input_video, output_video, edl)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(output_video))
            self.assertGreater(os.path.getsize(output_video), 0)

    def test_ffmpeg_1pass_render_video_without_audio(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_video = os.path.join(tmpdir, "silent_input.mp4")
            output_video = os.path.join(tmpdir, "silent_recap.mp4")
            generated = subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=duration=3:size=640x360:rate=24",
                "-c:v", "libx264", "-an", input_video,
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if generated.returncode != 0:
                self.skipTest("FFmpeg is not available in environment.")

            engine = AutoRecapEngine(AutoRecapConfig())
            edl = engine.generate_edl([
                {"start": 0.0, "end": 3.0, "text": "Cảnh video không có âm thanh"},
            ])
            self.assertTrue(engine.render_recap_video_1pass(input_video, output_video, edl))
            self.assertGreater(os.path.getsize(output_video), 0)


if __name__ == "__main__":
    unittest.main()
