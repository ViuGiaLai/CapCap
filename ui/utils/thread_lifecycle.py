"""Helpers for safely releasing :class:`QThread` worker objects.

Several workers expose a result signal named ``finished`` for historical
reasons.  That signal is emitted from inside ``run()`` and therefore fires
before Qt emits the native ``QThread.finished`` signal.  Dropping the last
reference or calling ``deleteLater`` from the result slot can consequently
destroy a still-running thread and abort the application.
"""

from PySide6.QtCore import QTimer


def release_thread_when_stopped(thread, on_released=None, poll_ms=25):
    """Release *thread* only after its native thread has stopped.

    The closure intentionally retains the worker while polling.  This makes
    it safe for a result callback to clear the owner's reference immediately;
    the C++ object is deleted only once ``isRunning()`` is false.
    """

    if thread is None:
        return

    released = False

    def poll():
        nonlocal released
        if released:
            return
        try:
            running = bool(thread.isRunning())
        except RuntimeError:
            running = False
        if running:
            QTimer.singleShot(max(1, int(poll_ms)), poll)
            return

        released = True
        if callable(on_released):
            try:
                on_released()
            except Exception:
                pass
        try:
            thread.deleteLater()
        except RuntimeError:
            pass

    QTimer.singleShot(0, poll)
