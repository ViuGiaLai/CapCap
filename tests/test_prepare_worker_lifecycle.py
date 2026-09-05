import os
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "ui"), os.path.join(ROOT, "app"), ROOT]

from PySide6.QtCore import QCoreApplication, QThread

from controllers.pipeline_controller import PipelineController
from worker_adapters.processing_workers import PrepareWorkflowWorker


class _ProbePrepareWorker(PrepareWorkflowWorker):
    def __init__(self):
        QThread.__init__(self)

    def run(self):
        self.result_ready.emit("project.json", "")
        self.msleep(120)


class _GuiHarness:
    def __init__(self):
        self._pipeline_active = True
        self._pipeline_step = "prepare"
        self.prepare_workflow_thread = None

    def refresh_ui_state(self):
        pass


class PrepareWorkerLifecycleTests(unittest.TestCase):
    def test_local_worker_never_inherits_gui_console_handles(self):
        controller = PipelineController(_GuiHarness())
        process = Mock()
        process.poll.return_value = None
        with patch.object(controller, "_stop_local_worker_server"), \
             patch.object(controller, "_find_free_local_port", return_value=32123), \
             patch.object(controller, "_wait_for_local_worker_server"), \
             patch("controllers.pipeline_controller.subprocess_hidden_kwargs", return_value={}), \
             patch("controllers.pipeline_controller.subprocess.Popen", return_value=process) as popen:
            controller._start_local_worker_server("cpu")

        kwargs = popen.call_args.kwargs
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.DEVNULL)

    def test_result_does_not_release_qthread_before_native_finished(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        gui = _GuiHarness()
        controller = PipelineController(gui)
        worker = _ProbePrepareWorker()
        gui.prepare_workflow_thread = worker
        observed_running = []

        def on_result(_path, _error):
            observed_running.append(worker.isRunning())
            controller.pipeline_done()

        worker.result_ready.connect(on_result)
        worker.finished.connect(
            lambda: controller._on_prepare_native_thread_finished(worker, 1)
        )
        worker.start()

        def is_worker_running():
            try:
                return worker.isRunning()
            except RuntimeError:
                return False

        deadline = time.monotonic() + 3.0
        while (is_worker_running() or not observed_running) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        app.processEvents()

        self.assertEqual(observed_running, [True])
        self.assertFalse(is_worker_running())
        self.assertIsNone(gui.prepare_workflow_thread)


if __name__ == "__main__":
    unittest.main()
