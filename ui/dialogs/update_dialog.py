from __future__ import annotations

import webbrowser
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

try:
    from app.version import get_app_version_string
except ImportError:
    from version import get_app_version_string


class UpdateDialog(QDialog):
    """Dialog displayed when a new version of CapCap is available."""

    def __init__(self, release_info: dict, parent=None):
        super().__init__(parent)
        self.release_info = release_info
        self.setWindowTitle("Update Available - CapCap")
        self.setMinimumWidth(480)
        self.resize(500, 380)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel(f"🎉 CapCap v{release_info.get('version')} is Available!")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #6ee7b7;")
        layout.addWidget(title)

        curr_ver = QLabel(f"Current version: {get_app_version_string()}")
        curr_ver.setStyleSheet("color: #94a3b8;")
        layout.addWidget(curr_ver)

        notes_label = QLabel("Release Notes:")
        notes_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(notes_label)

        self.notes_edit = QTextEdit()
        self.notes_edit.setReadOnly(True)
        self.notes_edit.setPlainText(release_info.get("release_notes", "No details available."))
        layout.addWidget(self.notes_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.close_btn = QPushButton("Remind Me Later")
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.close_btn)

        self.download_btn = QPushButton("Download Update")
        self.download_btn.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold;")
        self.download_btn.clicked.connect(self._open_download)
        btn_row.addWidget(self.download_btn)

        layout.addLayout(btn_row)

    def _open_download(self):
        url = self.release_info.get("html_url", "https://github.com/ViuGiaLai/CapCap/releases")
        webbrowser.open(url)
        self.accept()
