import os
import unittest
import importlib.util

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

TRACK_LABELS_PATH = os.path.join(ROOT, "ui", "views", "editor", "track_labels.py")
SPEC = importlib.util.spec_from_file_location("test_track_labels_module", TRACK_LABELS_PATH)
TRACK_LABELS_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRACK_LABELS_MODULE)
TrackLabelBar = TRACK_LABELS_MODULE.TrackLabelBar


class TrackLabelControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_bar(self, name: str) -> TrackLabelBar:
        bar = TrackLabelBar()
        bar.set_tracks([name], [80], [False], [False])
        bar.resize(bar.TRACK_HEADER_W, bar.RULER_HEIGHT + 80)
        bar.show()
        self.app.processEvents()
        self.addCleanup(bar.deleteLater)
        return bar

    def click(self, bar: TrackLabelBar, x: int):
        QTest.mouseClick(
            bar,
            Qt.LeftButton,
            Qt.NoModifier,
            QPoint(x, bar.RULER_HEIGHT + 30),
        )
        self.app.processEvents()

    def test_subtitle_eye_only_toggles_subtitle_visibility(self):
        bar = self.make_bar("TS1")
        subtitle_spy = QSignalSpy(bar.subtitleToggled)
        mute_spy = QSignalSpy(bar.muteToggled)

        self.click(bar, bar.TRACK_HEADER_W - 36)

        self.assertEqual(subtitle_spy.count(), 1)
        self.assertEqual(list(subtitle_spy.at(0)), ["TS1", False])
        self.assertEqual(mute_spy.count(), 0)

    def test_subtitle_label_selection_never_toggles_voice(self):
        bar = self.make_bar("TS1")
        selected_spy = QSignalSpy(bar.trackSelected)
        mute_spy = QSignalSpy(bar.muteToggled)

        # This was the old TS1 speaker cell. It is now ordinary selection.
        self.click(bar, bar.TRACK_HEADER_W - 60)

        self.assertEqual(selected_spy.count(), 1)
        self.assertEqual(list(selected_spy.at(0)), ["TS1"])
        self.assertEqual(mute_spy.count(), 0)

    def test_audio_speaker_still_toggles_only_audio_track(self):
        bar = self.make_bar("A1 Audio")
        mute_spy = QSignalSpy(bar.muteToggled)
        subtitle_spy = QSignalSpy(bar.subtitleToggled)

        self.click(bar, bar.TRACK_HEADER_W - 36)

        self.assertEqual(mute_spy.count(), 1)
        self.assertEqual(list(mute_spy.at(0)), ["A1 Audio", True])
        self.assertEqual(subtitle_spy.count(), 0)


if __name__ == "__main__":
    unittest.main()
