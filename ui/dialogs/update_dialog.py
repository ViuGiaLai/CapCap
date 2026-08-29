from __future__ import annotations

import os
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QMessageBox, QProgressBar, QPushButton,
    QTextBrowser, QVBoxLayout, QWidget,
)

from app.services.update_checker import UpdateDownloaderThread


class UpdateDialog(QDialog):
    """Modern dark-themed update notification & installer download dialog for CapCap."""

    def __init__(self, release_info: dict, parent=None):
        super().__init__(parent)
        self.release_info = release_info
        self.downloader_thread = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Software Update Available — CapCap")
        self.resize(560, 440)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #0c0e14;
                color: #e2e8f0;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 13px;
            }
            QTextBrowser {
                background-color: #111520;
                color: #cbd5e1;
                border: 1px solid #1e2433;
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.5;
            }
            QProgressBar {
                background-color: #111520;
                border: 1px solid #1e2433;
                border-radius: 6px;
                text-align: center;
                color: #e2e8f0;
                font-weight: bold;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 5px;
            }
            QPushButton#updateBtn {
                background-color: #10b981;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#updateBtn:hover {
                background-color: #059669;
            }
            QPushButton#updateBtn:disabled {
                background-color: #1e2433;
                color: #64748b;
            }
            QPushButton#laterBtn {
                background-color: #1e2433;
                color: #94a3b8;
                border: 1px solid #2b354a;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton#laterBtn:hover {
                background-color: #262e42;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header Title
        title_label = QLabel("🔔 A new version of CapCap is available!")
        title_font = QFont("Segoe UI", 14, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #6ee7b7;")
        layout.addWidget(title_label)

        # Version Comparison Row
        current_ver = self.release_info.get("current_version", "1.0.0")
        latest_ver = self.release_info.get("latest_version", "1.1.0")
        ver_row = QLabel(
            f"Current version: <b>v{current_ver}</b> &nbsp;➔&nbsp; "
            f"New version: <b style='color:#10b981;'>v{latest_ver}</b>"
        )
        ver_row.setTextFormat(Qt.RichText)
        ver_row.setStyleSheet("color: #cbd5e1; font-size: 13px;")
        layout.addWidget(ver_row)

        # Release Notes Label & Box
        notes_label = QLabel("Release Notes:")
        notes_label.setStyleSheet("color: #94a3b8; font-weight: 600;")
        layout.addWidget(notes_label)

        self.notes_browser = QTextBrowser()
        self.notes_browser.setOpenExternalLinks(True)
        raw_notes = self.release_info.get("release_notes", "").strip()
        formatted_notes = raw_notes.replace("\n", "<br>") if raw_notes else "No detailed release notes provided."
        self.notes_browser.setHtml(f"<div style='font-family: Segoe UI, sans-serif;'>{formatted_notes}</div>")
        layout.addWidget(self.notes_browser, 1)

        # Progress bar area (hidden initially)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.status_label.hide()
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.update_btn = QPushButton("🚀 Download & Update")
        self.update_btn.setObjectName("updateBtn")
        self.update_btn.clicked.connect(self.start_download)

        self.later_btn = QPushButton("Remind Me Later")
        self.later_btn.setObjectName("laterBtn")
        self.later_btn.clicked.connect(self.reject)

        btn_layout.addStretch(1)
        btn_layout.addWidget(self.later_btn)
        btn_layout.addWidget(self.update_btn)

        layout.addLayout(btn_layout)

    def start_download(self):
        download_url = self.release_info.get("setup_url", "")
        filename = self.release_info.get("setup_filename", "CapCap-Setup.exe")

        if not download_url:
            # Fallback to browser if no direct download link
            import webbrowser
            webbrowser.open(self.release_info.get("html_url", "https://github.com/ViuGiaLai/CapCap/releases"))
            self.accept()
            return

        self.update_btn.setEnabled(False)
        self.later_btn.setText("Cancel Download")
        self.status_label.setText("Connecting to server...")
        self.status_label.show()
        self.progress_bar.show()

        self.downloader_thread = UpdateDownloaderThread(download_url, filename, self)
        self.downloader_thread.progress_signal.connect(self.on_download_progress)
        self.downloader_thread.download_finished.connect(self.on_download_finished)
        self.downloader_thread.download_failed.connect(self.on_download_failed)
        self.downloader_thread.start()

    def on_download_progress(self, percent: int, downloaded: int, total: int):
        self.progress_bar.setValue(percent)
        mb_dl = downloaded / (1024 * 1024)
        mb_tot = total / (1024 * 1024) if total > 0 else 0
        if mb_tot > 0:
            self.status_label.setText(f"Downloading installer: {mb_dl:.1f} MB / {mb_tot:.1f} MB ({percent}%)")
        else:
            self.status_label.setText(f"Downloading installer: {mb_dl:.1f} MB ({percent}%)")

    def on_download_finished(self, file_path: str):
        self.status_label.setText("Download complete! Preparing to run installer...")
        self.progress_bar.setValue(100)

        res = QMessageBox.question(
            self,
            "Install Update Now",
            f"The update installer has been downloaded:\n{file_path}\n\n"
            "CapCap will now close to run the installer. Continue?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if res == QMessageBox.Yes:
            try:
                # Launch installer executable
                subprocess.Popen([file_path], shell=True)
                QApplication.quit()
            except Exception as exc:
                QMessageBox.critical(self, "Error Launching Installer", f"Could not start installer:\n{exc}")
                self.accept()
        else:
            self.accept()

    def on_download_failed(self, error_msg: str):
        self.status_label.setText(f"Download failed: {error_msg}")
        self.update_btn.setEnabled(True)
        self.later_btn.setText("Close")
        QMessageBox.warning(
            self,
            "Download Error",
            f"Failed to download update installer:\n{error_msg}\n\n"
            "You can download the update manually from GitHub Releases.",
        )
