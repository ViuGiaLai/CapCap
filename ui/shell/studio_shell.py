"""Working CapCap Studio shell used by the current PySide editor.

It intentionally wraps the existing workflow widgets during migration.  The
shell is therefore a real, interactive part of the running application rather
than an isolated component gallery.
"""

from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

from design_system import COLORS as c


class StudioAppBar(QFrame):
    projects_requested = Signal()
    generate_requested = Signal()
    export_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("studioAppBar")
        self.setFixedHeight(56)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(8)

        self.projects_btn = QToolButton(self)
        self.projects_btn.setText("Back")
        self.projects_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.projects_btn.setToolTip("Back to Projects")
        self.projects_btn.setAccessibleName("Back to Projects")
        self.projects_btn.setFixedSize(46, 30)
        self.projects_btn.clicked.connect(self.projects_requested.emit)
        layout.addWidget(self.projects_btn)

        brand = QLabel("CapCap", self)
        brand.setObjectName("studioBrand")
        layout.addWidget(brand)

        divider = QFrame(self)
        divider.setFrameShape(QFrame.VLine)
        divider.setObjectName("studioDivider")
        layout.addWidget(divider)

        self.project_title_label = QLabel("No project loaded", self)
        self.project_title_label.setObjectName("studioProjectTitle")
        self.project_title_label.setMinimumWidth(180)
        self.project_title_label.setMaximumWidth(420)
        self.project_title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.project_title_label)

        self.saved_label = QLabel("Saved", self)
        self.saved_label.setObjectName("studioSaved")
        layout.addWidget(self.saved_label)
        layout.addStretch(1)

        self.undo_btn = self._tool("Undo", "Undo")
        self.redo_btn = self._tool("Redo", "Redo")
        layout.addWidget(self.undo_btn)
        layout.addWidget(self.redo_btn)

        self.generate_btn = QPushButton("Generate", self)
        self.generate_btn.setObjectName("studioPrimaryAction")
        self.generate_btn.clicked.connect(self.generate_requested.emit)
        layout.addWidget(self.generate_btn)

        self.export_btn = QPushButton("Export", self)
        self.export_btn.setObjectName("studioSecondaryAction")
        self.export_btn.clicked.connect(self.export_requested.emit)
        layout.addWidget(self.export_btn)

        self.settings_btn = self._tool("Menu", "Settings")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn)

        window_divider = QFrame(self)
        window_divider.setFrameShape(QFrame.VLine)
        window_divider.setObjectName("studioDivider")
        layout.addWidget(window_divider)

        # The main window is intentionally frameless, so it must provide the
        # complete Windows title-bar controls itself.
        self.minimize_btn = self._window_control("—", "Minimize", "studioWindowMinimize")
        self.maximize_btn = self._window_control("□", "Maximize", "studioWindowMaximize")
        self.close_btn = self._window_control("×", "Close", "studioWindowClose")
        self.minimize_btn.clicked.connect(self._minimize_window)
        self.maximize_btn.clicked.connect(self._toggle_maximize_window)
        self.close_btn.clicked.connect(self._close_window)
        layout.addWidget(self.minimize_btn)
        layout.addWidget(self.maximize_btn)
        layout.addWidget(self.close_btn)

        self.setStyleSheet(f"""
            QFrame#studioAppBar {{ background: {c.panel}; border-bottom: 1px solid {c.border_subtle}; }}
            QLabel#studioBrand {{ color: {c.primary}; font-size: 16px; font-weight: 750; }}
            QLabel#studioProjectTitle {{ color: {c.primary}; font-size: 13px; font-weight: 600; }}
            QLabel#studioSaved {{ color: {c.success}; background: #10261e; border: 1px solid #1f6046; border-radius: 9px; padding: 3px 8px; font-size: 11px; font-weight: 650; }}
            QFrame#studioDivider {{ color: {c.border_default}; max-width: 1px; margin: 13px 2px; }}
            QToolButton {{ background: transparent; color: {c.secondary}; border: none; border-radius: 6px; padding: 0; font-size: 11px; font-weight: 650; }}
            QToolButton:hover {{ background: {c.hover}; color: {c.primary}; }}
            QToolButton#studioWindowMinimize, QToolButton#studioWindowMaximize, QToolButton#studioWindowClose {{
                border-radius: 0; font-size: 16px; font-weight: 400;
            }}
            QToolButton#studioWindowMinimize:hover, QToolButton#studioWindowMaximize:hover {{ background: {c.hover}; }}
            QToolButton#studioWindowClose:hover {{ background: #d83b4a; color: white; }}
            QPushButton#studioPrimaryAction {{ background: {c.accent}; color: {c.canvas}; border: none; border-radius: 8px; font-weight: 750; padding: 8px 16px; }}
            QPushButton#studioPrimaryAction:hover {{ background: {c.accent_hover}; }}
            QPushButton#studioSecondaryAction {{ background: {c.elevated}; color: {c.primary}; border: 1px solid {c.border_default}; border-radius: 8px; font-weight: 650; padding: 8px 14px; }}
            QPushButton#studioSecondaryAction:hover {{ background: {c.hover}; border-color: {c.accent}; }}
        """)

    def _tool(self, text: str, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setFixedSize(46, 30)
        return button

    def _window_control(self, text: str, tooltip: str, object_name: str) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(object_name)
        button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setFixedSize(42, 56)
        return button

    def _minimize_window(self) -> None:
        self.window().showMinimized()

    def _toggle_maximize_window(self) -> None:
        window = self.window()
        if window.isMaximized():
            window.showNormal()
            self.maximize_btn.setText("□")
            self.maximize_btn.setToolTip("Maximize")
        else:
            window.showMaximized()
            self.maximize_btn.setText("❐")
            self.maximize_btn.setToolTip("Restore down")

    def _close_window(self) -> None:
        self.window().close()

    def bind_legacy_actions(self, *, generate: QPushButton, export: QPushButton, undo: QPushButton, redo: QPushButton) -> None:
        """Mirror legacy action state while the old controller API is retained."""
        self.generate_requested.connect(generate.click)
        self.export_requested.connect(export.click)
        self.undo_btn.clicked.connect(undo.click)
        self.redo_btn.clicked.connect(redo.click)
        self._legacy_actions = (generate, export, undo, redo)
        self.sync_legacy_actions()

    def sync_legacy_actions(self) -> None:
        """Copy state after controllers refresh their existing buttons."""
        actions = getattr(self, "_legacy_actions", None)
        if not actions:
            return
        generate, export, undo, redo = actions
        self.generate_btn.setEnabled(generate.isEnabled())
        self.generate_btn.setText(generate.text())
        self.export_btn.setEnabled(export.isEnabled())
        self.export_btn.setText(export.text())
        self.undo_btn.setEnabled(undo.isEnabled())
        self.redo_btn.setEnabled(redo.isEnabled())


class StudioToolRail(QFrame):
    section_requested = Signal(str)

    SECTIONS: tuple[tuple[str, str, str], ...] = (
        ("edit", "", "Edit"),
        ("subtitles", "", "Subtitles"),
        ("voice", "", "Voice"),
        ("style", "", "Style"),
        ("media", "", "Media"),
        ("effects", "", "Effects"),
    )

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("studioToolRail")
        self.setFixedWidth(60)
        self._buttons: dict[str, QToolButton] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 10, 4, 10)
        layout.setSpacing(6)
        for section, glyph, label in self.SECTIONS:
            button = QToolButton(self)
            button.setText(label)
            button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setFixedHeight(38)
            button.clicked.connect(lambda _checked=False, key=section: self.section_requested.emit(key))
            layout.addWidget(button)
            self._buttons[section] = button
        layout.addStretch(1)
        self.setStyleSheet(f"""
            QFrame#studioToolRail {{ background: {c.panel}; border-right: 1px solid {c.border_subtle}; }}
            QToolButton {{ background: transparent; color: {c.muted}; border: 1px solid transparent; border-radius: 7px; padding: 3px 0; font-size: 10px; font-weight: 600; }}
            QToolButton:hover {{ background: {c.hover}; color: {c.primary}; }}
            QToolButton:checked {{ background: {c.selected}; color: {c.accent_hover}; border-left: 2px solid {c.accent}; }}
        """)

    def select(self, section: str) -> None:
        button = self._buttons.get(section)
        if button is not None:
            button.setChecked(True)

    def clear_selection(self) -> None:
        for button in self._buttons.values():
            button.setAutoExclusive(False)
            button.setChecked(False)
            button.setAutoExclusive(True)


class StudioStatusBar(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("studioStatusBar")
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(12)
        self.task_label = QLabel("Ready", self)
        self.task_label.setObjectName("studioStatusTask")
        self.device_label = QLabel("", self)
        self.time_label = QLabel("00:00 / 00:00", self)
        layout.addWidget(self.task_label, 1)
        layout.addWidget(self.device_label)
        layout.addWidget(self.time_label)
        self.setStyleSheet(f"""
            QFrame#studioStatusBar {{ background: {c.panel}; border-top: 1px solid {c.border_subtle}; }}
            QLabel {{ color: {c.muted}; font-size: 11px; }} QLabel#studioStatusTask {{ color: {c.secondary}; }}
        """)

    def set_task(self, text: str) -> None:
        self.task_label.setText(text or "Ready")
