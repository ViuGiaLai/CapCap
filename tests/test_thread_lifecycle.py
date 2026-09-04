import os
import sys
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "ui"), os.path.join(ROOT, "app"), ROOT]

from PySide6.QtCore import QCoreApplication, QThread, Signal

from utils.thread_lifecycle import release_thread_when_stopped


class _ResultWorker(QThread):
    result = Signal()

    def run(self):
        self.result.emit()
        self.msleep(80)


class ThreadLifecycleTests(unittest.TestCase):
    def test_result_signal_does_not_destroy_running_worker(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        worker = _ResultWorker()
        released = []
        worker.result.connect(
            lambda: release_thread_when_stopped(
                worker, lambda: released.append(not worker.isRunning())
            )
        )
        worker.start()

        deadline = time.monotonic() + 3.0
        while (worker.isRunning() or not released) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        app.processEvents()

        self.assertEqual(released, [True])


if __name__ == "__main__":
    unittest.main()
