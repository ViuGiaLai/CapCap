from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


def relaunch_launcher(window_factory):
    """Show the launcher and open the selected video in a fresh editor window."""
    from views.launcher import LauncherWindow, show_launcher

    selection = show_launcher(None)
    QApplication.setQuitOnLastWindowClosed(True)
    if not selection:
        QApplication.quit()
        return

    LauncherWindow.add_recent(None, selection)
    new_window = window_factory()
    new_window.prepare_initial_editor_layout()
    new_window.show()

    def initialize_window():
        from utils.project_launch import initialize_editor_from_selection
        initialize_editor_from_selection(new_window, selection)

    QTimer.singleShot(100, initialize_window)
