import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "ui"), os.path.join(ROOT, "app"), ROOT]

from features.voice_subtitle_preview import VoiceSubtitlePreviewMixin
from features.timeline_editing import TimelineEditingMixin
import preview_processor


class _SubtitleItem:
    def __init__(self):
        self.text = "stale"
        self.visible = True

    def set_text(self, text):
        self.text = text

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False


class _VideoView:
    def __init__(self):
        self.subtitle_item = _SubtitleItem()

    def reposition_subtitle(self):
        pass


class _MediaPlayer:
    def __init__(self, position_ms):
        self._position_ms = position_ms

    def position(self):
        return self._position_ms


class _PreviewHarness(VoiceSubtitlePreviewMixin):
    def __init__(self, position_ms):
        self.video_view = _VideoView()
        self.media_player = _MediaPlayer(position_ms)
        self.live_preview_segments = []
        self._selected_segment_index = 0
        self._preview_video_has_burned_subtitles = False
        self._playback_subtitle_activity_cache = None

    def get_active_segments(self):
        return []

    def _apply_live_subtitle_segment_color(self, segment):
        pass

    def _set_live_subtitle_effects(self, segment, position_ms=None):
        pass


class _SelectionHarness(TimelineEditingMixin, VoiceSubtitlePreviewMixin):
    def __init__(self):
        self.media_player = _MediaPlayer(0)
        # Deliberately stale snapshot from before an import/edit.
        self.live_preview_segments = [
            {"start": 0.0, "end": 20.0, "text": "old cue"},
        ]
        self.current_segments = [
            {"start": 0.0, "end": 2.0, "text": "first"},
            {"start": 4.0, "end": 6.0, "text": "second"},
        ]
        self.current_translated_segments = []
        self.selected = None

    def get_active_segments(self):
        return self.current_segments

    def set_selected_segment_index(self, index, *, sync_ui=True):
        self.selected = index


class SubtitlePreviewTimingTests(unittest.TestCase):
    def test_exact_frame_renderer_preserves_absolute_ass_timestamps(self):
        with tempfile.TemporaryDirectory() as folder:
            video = os.path.join(folder, "video.mp4")
            srt = os.path.join(folder, "subtitle.srt")
            ass = os.path.join(folder, "subtitle.ass")
            output = os.path.join(folder, "frame.png")
            for path in (video, srt, ass):
                with open(path, "wb") as handle:
                    handle.write(b"test")

            with (
                patch.object(preview_processor, "_ffmpeg_path", return_value=video),
                patch("video_processor.get_video_dimensions", return_value=(1024, 576)),
                patch("video_processor.srt_to_ass", return_value=ass),
                patch.object(
                    preview_processor.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0, stderr="", stdout=""),
                ) as run,
            ):
                preview_processor.render_subtitle_frame_preview(
                    video, srt, output, 202.1
                )

            command = run.call_args.args[0]
            self.assertIn("-copyts", command)
            self.assertLess(command.index("-copyts"), command.index("-ss"))
            self.assertLess(command.index("-ss"), command.index("-i"))

    def test_paused_preview_hides_selected_future_subtitle(self):
        harness = _PreviewHarness(0)
        harness._show_subtitle_drag_layer([
            {"start": 9.520, "end": 10.652, "text": "Thật đáng tiếc"},
        ])

        self.assertEqual(harness.video_view.subtitle_item.text, "")
        self.assertFalse(harness.video_view.subtitle_item.visible)

    def test_paused_preview_shows_subtitle_active_at_playhead(self):
        harness = _PreviewHarness(10_000)
        harness._show_subtitle_drag_layer([
            {"start": 9.520, "end": 10.652, "text": "Thật đáng tiếc"},
        ])

        self.assertEqual(harness.video_view.subtitle_item.text, "Thật đáng tiếc")
        self.assertTrue(harness.video_view.subtitle_item.visible)

    def test_explicit_seek_timestamp_updates_inspector_selection(self):
        harness = _SelectionHarness()

        # The backend still reports its old position, but the seek request is
        # already known by the UI.  The Inspector must follow the requested
        # cue immediately instead of waiting for an asynchronous signal.
        harness._sync_selected_segment_to_playback_position(5_000)

        self.assertEqual(harness.selected, 1)

    def test_subtitle_boundary_uses_next_cue_not_previous(self):
        harness = _PreviewHarness(2_000)
        segments = [
            {"start": 0.0, "end": 2.0, "text": "first"},
            {"start": 2.0, "end": 4.0, "text": "second"},
        ]

        self.assertEqual(harness._find_active_segment_indices(2_000, segments), [1])


if __name__ == "__main__":
    unittest.main()
