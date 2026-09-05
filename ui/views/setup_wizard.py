"""First-run setup dialog for installing only the resources a user selects."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QRadioButton,
    QVBoxLayout,
)

from services import ResourceDownloadService
from ui.worker_adapters.processing_workers import ResourceDownloadWorker
from utils.thread_lifecycle import release_thread_when_stopped


class SetupWizard(QDialog):
    """Small guided installer; advanced/manual resources stay in Resource Manager."""

    PROFILES = {
        "basic": {
            "title": "Basic CPU",
            "description": "SenseVoice speech recognition + Google Translate. Recommended for most users.",
            "resources": ("sensevoice:model", "sensevoice:vad"),
        },
        "local": {
            "title": "Local AI",
            "description": "Basic CPU plus selectable offline Piper voices in Vietnamese and English. Llama.cpp/GGUF can be imported afterwards.",
            "resources": ("sensevoice:model", "sensevoice:vad"),
        },
        "gpu": {
            "title": "GPU acceleration",
            "description": "Basic CPU resources plus the CUDA runtime pack for a supported NVIDIA driver.",
            "resources": ("sensevoice:model", "sensevoice:vad", "cuda:whisper"),
        },
    }

    def __init__(self, workspace_root: str, parent=None):
        super().__init__(parent)
        self.workspace_root = workspace_root
        self.service = ResourceDownloadService(workspace_root)
        self._profile_key = "basic"
        self._pending: list[str] = []
        self._worker = None
        self.setWindowTitle("VIUStudio Setup")
        self.setModal(True)
        self.resize(560, 470)
        self.setStyleSheet("""
            QDialog { background: #0d1420; color: #e6edf5; }
            QLabel { color: #cbd5e1; }
            QLabel#title { color: #f8fafc; font-size: 22px; font-weight: 800; }
            QLabel#hint { color: #91a4bb; font-size: 12px; }
            QFrame#profile { background: #111d2c; border: 1px solid #263d58; border-radius: 10px; }
            QRadioButton { color: #e7f0fb; font-size: 13px; font-weight: 700; spacing: 8px; }
            QCheckBox { color: #dbeafe; font-size: 13px; spacing: 8px; }
            QPushButton { background: #17263a; color: #dbeafe; border: 1px solid #315476; border-radius: 7px; padding: 8px 16px; font-weight: 700; }
            QPushButton:hover { background: #203652; border-color: #4b9be8; }
            QPushButton#primary { background: #22b992; color: #07130f; border-color: #22b992; }
            QPushButton#primary:hover { background: #35d1a9; }
            QProgressBar { height: 12px; border: 1px solid #2b435d; border-radius: 6px; background: #0b1320; text-align: center; color: #d8f8ee; }
            QProgressBar::chunk { background: #22b992; border-radius: 5px; }
        """)
        self._build_ui()
        self._refresh_status()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(12)
        title = QLabel("VIUStudio Setup", self)
        title.setObjectName("title")
        root.addWidget(title)
        hint = QLabel("Choose how you plan to use VIUStudio. Only the required resources will be installed.", self)
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._group = QButtonGroup(self)
        self._profile_buttons = {}
        for key, profile in self.PROFILES.items():
            card = QFrame(self)
            card.setObjectName("profile")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 10, 14, 10)
            radio = QRadioButton(profile["title"], card)
            radio.setChecked(key == self._profile_key)
            radio.toggled.connect(lambda checked, selected=key: checked and self._select_profile(selected))
            self._group.addButton(radio)
            self._profile_buttons[key] = radio
            layout.addWidget(radio)
            description = QLabel(profile["description"], card)
            description.setObjectName("hint")
            description.setWordWrap(True)
            layout.addWidget(description)
            root.addWidget(card)

        # Voice packs are optional setup resources.  Keep this choice local to
        # the wizard; the existing voice catalog/TTS selection logic remains
        # unchanged and continues to select the active language at runtime.
        self.voice_options = QFrame(self)
        self.voice_options.setObjectName("profile")
        voice_layout = QVBoxLayout(self.voice_options)
        voice_layout.setContentsMargins(14, 10, 14, 10)
        self.voice_title = QLabel("Offline Piper voice packs (optional)", self.voice_options)
        self.voice_title.setStyleSheet("color: #e7f0fb; font-size: 13px; font-weight: 700;")
        voice_layout.addWidget(self.voice_title)
        voice_hint = QLabel("Choose one or both languages for offline voiceover.", self.voice_options)
        voice_hint.setObjectName("hint")
        voice_hint.setWordWrap(True)
        voice_layout.addWidget(voice_hint)
        voice_layout.addWidget(QLabel("Preferred TTS engine", self.voice_options))
        self.tts_engine_combo = QComboBox(self.voice_options)
        self.tts_engine_combo.addItem("Select an engine…", "")
        self.tts_engine_combo.addItem("Piper (Fast · Offline)", "piper")
        self.tts_engine_combo.addItem("ZeroTTS (Natural · Not installed)", "zerotts")
        self.tts_engine_combo.addItem("KorvaTTS (Natural / Local · Not installed)", "korvatts")
        self.tts_engine_combo.addItem("Kokoro-82M (Natural · Not installed)", "kokoro")
        self.tts_engine_combo.setToolTip(
            "Choose one engine. Models marked Not installed require their runtime before use."
        )
        self.tts_engine_combo.currentIndexChanged.connect(lambda _index: self._refresh_status())
        voice_layout.addWidget(self.tts_engine_combo)
        voice_checks = QHBoxLayout()
        self.voice_vi_check = QCheckBox("Vietnamese", self.voice_options)
        self.voice_en_check = QCheckBox("English", self.voice_options)
        self.voice_vi_check.setChecked(True)
        self.voice_en_check.setChecked(True)
        voice_checks.addWidget(self.voice_vi_check)
        voice_checks.addWidget(self.voice_en_check)
        voice_checks.addStretch(1)
        voice_layout.addLayout(voice_checks)
        self.voice_vi_check.toggled.connect(lambda _checked: self._refresh_status())
        self.voice_en_check.toggled.connect(lambda _checked: self._refresh_status())
        root.addWidget(self.voice_options)
        self.voice_options.setVisible(False)

        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        root.addWidget(self.progress)
        self.detail_label = QLabel("", self)
        self.detail_label.setObjectName("hint")
        self.detail_label.setWordWrap(True)
        root.addWidget(self.detail_label)
        root.addStretch(1)

        buttons = QHBoxLayout()
        self.advanced_btn = QPushButton("Advanced Resources", self)
        self.advanced_btn.clicked.connect(self._open_advanced)
        buttons.addWidget(self.advanced_btn)
        buttons.addStretch(1)
        self.install_btn = QPushButton("Install Selected", self)
        self.install_btn.setObjectName("primary")
        self.install_btn.clicked.connect(self._install_selected)
        buttons.addWidget(self.install_btn)
        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

    def _select_profile(self, key: str):
        self._profile_key = key
        self.voice_options.setVisible(key == "local")
        self._refresh_status()

    def _selected_resources(self) -> list[str]:
        """Return setup resources selected in the wizard.

        Piper packs are deliberately added here instead of changing the
        runtime voice catalog, so existing project and TTS behaviour is kept.
        """
        resources = list(self.PROFILES[self._profile_key]["resources"])
        if self._profile_key == "local" and self.selected_engine() == "piper":
            if self.voice_vi_check.isChecked():
                resources.append("voice:pack")
            if self.voice_en_check.isChecked():
                resources.append("voice:pack-en")
        return resources

    def _refresh_status(self):
        self._update_voice_pack_visibility()
        profile = self.PROFILES[self._profile_key]
        missing = [rid for rid in self._selected_resources() if not self.service.is_resource_installed(rid)]
        self._pending = missing
        selected_engine = str(self.tts_engine_combo.currentData() or "").strip().lower()
        unsupported_engine = selected_engine in {"zerotts", "korvatts", "kokoro"}
        if self._profile_key == "local" and unsupported_engine:
            self.status_label.setText(
                "Selected TTS engine is not integrated in this build; choose Piper or install its runtime manually."
            )
            self.status_label.setStyleSheet("color: #fca5a5; font-weight: 700;")
            self.install_btn.setText("Unavailable")
            self.install_btn.setEnabled(False)
            return
        if missing:
            self.status_label.setText(f"{len(missing)} resource(s) need installation for {profile['title']}.")
            self.status_label.setStyleSheet("color: #f6c453; font-weight: 700;")
            self.install_btn.setText("Install Selected")
            self.install_btn.setEnabled(self._worker is None)
        else:
            self.status_label.setText("✓ Selected setup is ready.")
            self.status_label.setStyleSheet("color: #6ee7b7; font-weight: 700;")
            self.install_btn.setText("Done")
            self.install_btn.setEnabled(self._worker is None)

    def _update_voice_pack_visibility(self):
        """Show Piper language packs only when Piper is selected."""
        visible = self._profile_key == "local" and self.selected_engine() == "piper"
        self.voice_title.setVisible(visible)
        self.voice_vi_check.setVisible(visible)
        self.voice_en_check.setVisible(visible)

    def _install_selected(self):
        if not self._pending:
            self.accept()
            return
        self._pending = list(self._pending)
        self.install_btn.setEnabled(False)
        self.progress.show()
        self._install_next()

    def _install_next(self):
        if not self._pending:
            self._worker = None
            self.progress.setValue(100)
            self.detail_label.setText("Installation complete. You can start a project now.")
            self._refresh_status()
            return
        resource_id = self._pending.pop(0)
        if self.service.is_resource_installed(resource_id):
            self._install_next()
            return
        worker = ResourceDownloadWorker(self.workspace_root, resource_id)
        worker.setParent(self)
        self._worker = worker
        self.detail_label.setText(f"Installing {resource_id}…")
        worker.progress.connect(lambda percent, message: self._on_progress(percent, message))
        worker.finished.connect(lambda done_id, error, current=worker: self._on_finished(done_id, error, current))
        worker.start()

    def _on_progress(self, percent: int, message: str):
        if percent >= 0:
            self.progress.setValue(percent)
        self.detail_label.setText(str(message))

    def _on_finished(self, resource_id: str, error: str, worker):
        if error:
            self.detail_label.setText("Install failed: " + str(error).splitlines()[0])
            self._pending.insert(0, resource_id)
            release_thread_when_stopped(
                worker,
                on_released=lambda: self._finish_failed_install(),
            )
            return
        release_thread_when_stopped(worker, on_released=self._install_next)

    def _finish_failed_install(self):
        self._worker = None
        self.install_btn.setEnabled(True)

    def _open_advanced(self):
        from views.resource_manager import open_resource_manager
        open_resource_manager(self.workspace_root, parent=self)
        self._refresh_status()

    def selected_engine(self) -> str:
        """Return the user's setup choice for synchronizing the editor."""
        return str(self.tts_engine_combo.currentData() or "").strip().lower()


def open_setup_wizard(workspace_root: str, parent=None) -> str:
    wizard = SetupWizard(workspace_root, parent=parent)
    result = wizard.exec()
    return wizard.selected_engine() if result == QDialog.DialogCode.Accepted else ""
