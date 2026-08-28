import os

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication


def relaunch_launcher(window_factory):
    """Show the launcher and open the selected video in a fresh editor window."""
    from views.launcher import LauncherWindow, show_launcher

    video_path = show_launcher(None)
    QApplication.setQuitOnLastWindowClosed(True)
    if not video_path:
        QApplication.quit()
        return

    LauncherWindow.add_recent(None, video_path)
    new_window = window_factory()
    new_window.prepare_initial_editor_layout()
    new_window.show()

    def initialize_window():
        new_window._current_video_path = os.path.abspath(video_path)
        new_window.ensure_media_backend_ready()
        new_window.video_path_edit.setText(video_path)
        new_window.media_player.setSource(QUrl.fromLocalFile(video_path))
        if hasattr(new_window, "refresh_video_dimensions"):
            new_window.refresh_video_dimensions(video_path)
        new_window.current_project_state = new_window.ensure_current_project()
        new_window.load_project_context(new_window.current_project_state)
        if hasattr(new_window, "timeline") and hasattr(new_window.timeline, "set_video_source"):
            try:
                duration = new_window.media_player.duration() / 1000.0
            except Exception:
                duration = 60.0
            new_window.timeline.set_video_source(new_window._current_video_path, duration)
        new_window.schedule_timeline_visual_refresh(waveform=True, thumbnails=True)

    QTimer.singleShot(100, initialize_window)
