import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "ui"), os.path.join(ROOT, "app"), ROOT]

from features.voice_subtitle_preview import VoiceSubtitlePreviewMixin


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


class SubtitlePreviewTimingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
