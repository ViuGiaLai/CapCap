from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from app.services.update_checker import UpdateCheckerThread
from app.version import get_app_version_string
from ui.dialogs.update_dialog import UpdateDialog


class UpdateFeatureMixin:
    """Mixin for update checking and notification features in VIUStudio."""

    def check_for_updates(self, verbose: bool = False):
        """Check for updates asynchronously in background."""
        if getattr(self, "_update_checker_running", False):
            if verbose:
                QMessageBox.information(self, "Check in Progress", "VIUStudio is currently checking for updates...")
            return

        self._update_checker_running = True
        self._update_checker_thread = UpdateCheckerThread(self)

        def _on_available(info: dict):
            self._update_checker_running = False
            dlg = UpdateDialog(info, self)
            dlg.exec()

        def _on_no_update(current_ver: str):
            self._update_checker_running = False
            if verbose:
                QMessageBox.information(
                    self,
                    "VIUStudio Up to Date",
                    f"You are using the latest version of VIUStudio ({get_app_version_string()}).\nNo updates available at this time.",
                )

        def _on_failed(err_msg: str):
            self._update_checker_running = False
            if verbose:
                QMessageBox.warning(
                    self,
                    "Update Check Failed",
                    f"Could not connect to GitHub to check for updates:\n{err_msg}\n\nPlease try again later.",
                )

        self._update_checker_thread.update_available.connect(_on_available)
        self._update_checker_thread.no_update_available.connect(_on_no_update)
        self._update_checker_thread.check_failed.connect(_on_failed)
        self._update_checker_thread.start()

    def schedule_startup_update_check(self):
        """Perform a silent background update check 5 seconds after startup (Frozen .exe only)."""
        import sys
        # Do not perform background auto-update checks when running from source code in dev mode
        if not getattr(sys, "frozen", False):
            return
        QTimer.singleShot(5000, lambda: self.check_for_updates(verbose=False))
