from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.services.auto_recap_engine import AutoRecapConfig


class AutoRecapSettingsDialog(QDialog):
    """Consumer-focused Settings Dialog for CapCap Auto Edit Recap."""

    config_changed = Signal(object)

    def __init__(self, config: AutoRecapConfig = None, parent=None):
        super().__init__(parent)
        self.config = config or AutoRecapConfig()
        self.setWindowTitle("Auto Edit Recap Settings")
        self.setMinimumWidth(500)
        self.resize(520, 620)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e2430;
                color: #e2e8f0;
                font-family: 'Segoe UI', sans-serif;
            }
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: bold;
                color: #94a3b8;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #cbd5e1;
            }
            QCheckBox, QRadioButton {
                color: #e2e8f0;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #475569;
                background-color: #0f172a;
            }
            QRadioButton::indicator {
                border-radius: 9px;
            }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton#secondaryBtn {
                background-color: #334155;
                color: #cbd5e1;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #475569;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 20, 22, 20)

        # Header Title
        title_label = QLabel("✨ Auto Edit Recap")
        title_font = QFont("Segoe UI", 15, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #6ee7b7;")
        layout.addWidget(title_label)

        sub_label = QLabel("Keep the complete video while adding shot-aware motion framing and emphasis effects.")
        sub_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        sub_label.setWordWrap(True)
        layout.addWidget(sub_label)

        # Section 1: 🎬 Editing Style (Zoom Intensity)
        style_group = QGroupBox("🎬 Editing Style (Zoom Intensity)")
        style_layout = QHBoxLayout(style_group)
        style_layout.setSpacing(15)

        self.style_group_btn = QButtonGroup(self)
        self.radio_subtle = QRadioButton("Subtle (105%)")
        self.radio_subtle.setToolTip("Light subtle zoom for formal/talking head videos")
        self.radio_balanced = QRadioButton("Balanced (110%)")
        self.radio_balanced.setToolTip("Natural balanced zoom for most videos (Recommended)")
        self.radio_dynamic = QRadioButton("Dynamic (115%)")
        self.radio_dynamic.setToolTip("High climax zoom for energetic action/drama videos")

        self.style_group_btn.addButton(self.radio_subtle, 0)
        self.style_group_btn.addButton(self.radio_balanced, 1)
        self.style_group_btn.addButton(self.radio_dynamic, 2)

        if self.config.max_zoom_percent <= 105.0:
            self.radio_subtle.setChecked(True)
        elif self.config.max_zoom_percent >= 115.0:
            self.radio_dynamic.setChecked(True)
        else:
            self.radio_balanced.setChecked(True)

        style_layout.addWidget(self.radio_subtle)
        style_layout.addWidget(self.radio_balanced)
        style_layout.addWidget(self.radio_dynamic)
        layout.addWidget(style_group)

        # Section 2: 🎞️ Footage & Motion
        motion_group = QGroupBox("🎞️ Footage & Motion Controls")
        motion_layout = QVBoxLayout(motion_group)
        motion_layout.setSpacing(8)

        self.zoom_check = QCheckBox("Smart Zoom (Normal / Important / Climax)")
        self.zoom_check.setChecked(getattr(self.config, "allow_smart_zoom", True))
        motion_layout.addWidget(self.zoom_check)

        self.pan_check = QCheckBox("Pan & Reframe (Natural Directional Motion)")
        self.pan_check.setChecked(getattr(self.config, "allow_pan_reframe", True))
        motion_layout.addWidget(self.pan_check)

        self.flip_check = QCheckBox("Horizontal Flip for Reused Clips (Skip Text, Logos & Subtitles)")
        self.flip_check.setChecked(self.config.allow_horizontal_flip)
        motion_layout.addWidget(self.flip_check)

        self.cooldown_check = QCheckBox("Avoid Repeated Shots (Anti-Repetition Cooldown)")
        self.cooldown_check.setChecked(self.config.cooldown_shots > 0)
        motion_layout.addWidget(self.cooldown_check)

        layout.addWidget(motion_group)

        # Section 3: ✨ Effects
        effects_group = QGroupBox("✨ Special Effects")
        effects_layout = QVBoxLayout(effects_group)
        effects_layout.setSpacing(8)

        self.speed_check = QCheckBox("Speed Adjustments (0.90x Accent / 1.15x Fast Transition)")
        self.speed_check.setChecked(self.config.allow_speed_change)
        effects_layout.addWidget(self.speed_check)

        self.freeze_check = QCheckBox("Key Moment Freeze (Only when key reveal is detected, 0.4s)")
        self.freeze_check.setChecked(self.config.allow_freeze_frame)
        effects_layout.addWidget(self.freeze_check)

        layout.addWidget(effects_group)

        # Section 4: 🔊 Audio & Voiceover Ducking
        audio_group = QGroupBox("🔊 Voiceover Ducking (Background Audio)")
        audio_layout = QHBoxLayout(audio_group)
        audio_layout.setSpacing(15)

        self.ducking_group_btn = QButtonGroup(self)
        self.radio_duck_light = QRadioButton("Light (-6 dB)")
        self.radio_duck_balanced = QRadioButton("Balanced (-12 dB)")
        self.radio_duck_strong = QRadioButton("Strong (-16 dB)")

        self.ducking_group_btn.addButton(self.radio_duck_light, 0)
        self.ducking_group_btn.addButton(self.radio_duck_balanced, 1)
        self.ducking_group_btn.addButton(self.radio_duck_strong, 2)

        if self.config.audio_ducking_db >= -6.0:
            self.radio_duck_light.setChecked(True)
        elif self.config.audio_ducking_db <= -16.0:
            self.radio_duck_strong.setChecked(True)
        else:
            self.radio_duck_balanced.setChecked(True)

        audio_layout.addWidget(self.radio_duck_light)
        audio_layout.addWidget(self.radio_duck_balanced)
        audio_layout.addWidget(self.radio_duck_strong)
        layout.addWidget(audio_group)

        layout.addStretch(1)

        # Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.setObjectName("secondaryBtn")
        self.reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(self.reset_btn)

        btn_row.addStretch(1)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryBtn")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self._save_settings)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

    def _reset_defaults(self):
        self.config = AutoRecapConfig()
        self.radio_balanced.setChecked(True)
        self.zoom_check.setChecked(True)
        self.pan_check.setChecked(True)
        self.flip_check.setChecked(True)
        self.cooldown_check.setChecked(True)
        self.speed_check.setChecked(True)
        self.freeze_check.setChecked(True)
        self.radio_duck_balanced.setChecked(True)

    def _save_settings(self):
        if self.radio_subtle.isChecked():
            self.config.editing_style = "Subtle"
            self.config.max_zoom_percent = 105.0
        elif self.config and self.radio_dynamic.isChecked():
            self.config.editing_style = "Dynamic"
            self.config.max_zoom_percent = 115.0
        else:
            self.config.editing_style = "Balanced"
            self.config.max_zoom_percent = 110.0

        self.config.allow_smart_zoom = self.zoom_check.isChecked()
        self.config.allow_pan_reframe = self.pan_check.isChecked()
        self.config.allow_horizontal_flip = self.flip_check.isChecked()
        self.config.cooldown_shots = 2 if self.cooldown_check.isChecked() else 0
        self.config.allow_speed_change = self.speed_check.isChecked()
        self.config.allow_freeze_frame = self.freeze_check.isChecked()

        if self.radio_duck_light.isChecked():
            self.config.ducking_preset = "Light"
            self.config.audio_ducking_db = -6.0
        elif self.radio_duck_strong.isChecked():
            self.config.ducking_preset = "Strong"
            self.config.audio_ducking_db = -16.0
        else:
            self.config.ducking_preset = "Balanced"
            self.config.audio_ducking_db = -12.0

        self.config_changed.emit(self.config)
        self.accept()
