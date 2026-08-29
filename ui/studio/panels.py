from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget,
)

from design_system import COLORS as c


def _section(title: str, hint: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("studioSection")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 13, 14, 13)
    layout.setSpacing(8)
    heading = QLabel(title, frame)
    heading.setObjectName("studioSectionTitle")
    layout.addWidget(heading)
    if hint:
        description = QLabel(hint, frame)
        description.setObjectName("studioSectionHint")
        description.setWordWrap(True)
        layout.addWidget(description)
    return frame, layout


class StudioTaskPanel(QFrame):
    """Compact, task-oriented replacement for the old workflow sidebar."""

    SECTION_TITLES = {
        "edit": ("Edit", "Make precise changes at the current playhead."),
        "subtitles": ("Subtitles", "Create, translate and refine captions."),
        "voice": ("Voice", "Generate a natural Vietnamese voice track."),
        "style": ("Style", "Apply a readable recap subtitle style."),
        "media": ("Media", "Bring footage into this recap project."),
        "effects": ("Effects", "Add a layer to the selected time range."),
    }

    def __init__(self, gui, parent: QWidget | None = None):
        super().__init__(parent)
        self.gui = gui
        self.setObjectName("studioTaskPanel")
        self.setFixedWidth(312)
        self._active_section: str | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame(self)
        header.setObjectName("studioTaskHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 8, 10)
        self.title = QLabel("Media", header)
        self.title.setObjectName("studioTaskTitle")
        header_layout.addWidget(self.title, 1)
        close = QPushButton("Close", header)
        close.setObjectName("studioPanelClose")
        close.setToolTip("Close task panel")
        close.clicked.connect(self.hide_panel)
        header_layout.addWidget(close)
        outer.addWidget(header)

        self.stack = QStackedWidget(self)
        self._pages: dict[str, QWidget] = {}
        for section in self.SECTION_TITLES:
            page = self._page_for(section)
            self._pages[section] = page
            self.stack.addWidget(page)
        outer.addWidget(self.stack, 1)
        self.hide()
        self.setStyleSheet(f"""
            QFrame#studioTaskPanel {{ background: {c.panel}; border-right: 1px solid {c.border_subtle}; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background: {c.panel}; }}
            QFrame#studioTaskHeader {{ border-bottom: 1px solid {c.border_subtle}; }}
            QLabel#studioTaskTitle {{ color: {c.primary}; font-size: 14px; font-weight: 700; }}
            QFrame#studioSection {{ background: transparent; border-bottom: 1px solid {c.border_subtle}; }}
            QLabel#studioSectionTitle {{ color: {c.primary}; font-size: 12px; font-weight: 700; }}
            QLabel#studioSectionHint {{ color: {c.muted}; font-size: 11px; }}
            QPushButton {{ background: {c.elevated}; color: {c.secondary}; border: 1px solid {c.border_default}; border-radius: 7px; padding: 8px 10px; text-align: left; font-weight: 600; }}
            QPushButton:hover {{ background: {c.hover}; color: {c.primary}; border-color: {c.accent}; }}
            QPushButton#studioTaskPrimary {{ background: {c.accent}; color: {c.canvas}; border: none; text-align: center; font-weight: 750; }}
            QPushButton#studioTaskPrimary:hover {{ background: {c.accent_hover}; }}
            QPushButton#studioPanelClose {{ border: none; background: transparent; color: {c.muted}; padding: 5px; }}
            QPushButton#studioPanelClose:hover {{ color: {c.primary}; background: {c.hover}; }}
            QComboBox {{ background: {c.input}; color: {c.primary}; border: 1px solid {c.border_default}; border-radius: 6px; padding: 7px; }}
        """)

    def _scroll_page(self) -> tuple[QWidget, QVBoxLayout]:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 18)
        layout.setSpacing(10)
        layout.addStretch(1)
        scroll.setWidget(body)
        return scroll, layout

    def _button(self, layout: QVBoxLayout, text: str, target: str | None = None, primary: bool = False) -> QPushButton:
        button = QPushButton(text)
        if primary:
            button.setObjectName("studioTaskPrimary")
        if target:
            button.clicked.connect(lambda: self._click_legacy(target))
        layout.insertWidget(max(0, layout.count() - 1), button)
        return button

    def _page_for(self, section: str) -> QWidget:
        page, root = self._scroll_page()
        title, subtitle = self.SECTION_TITLES[section]
        intro, intro_layout = _section(title, subtitle)
        root.insertWidget(0, intro)
        if section == "media":
            actions, lay = _section("Project media", "Choose the main recap video. The preview and timeline update automatically.")
            self._button(lay, "Choose video", "browse_video", primary=True)
            root.insertWidget(1, actions)
        elif section == "subtitles":
            actions, lay = _section("Caption workflow")
            self._button(lay, "Transcribe video", "transcribe_btn", primary=True)
            self._button(lay, "Translate subtitles", "translate_btn")
            self._button(lay, "Import source SRT", "import_original_srt_btn")
            self._button(lay, "Import translated SRT", "import_translation_btn")
            self._button(lay, "Open subtitle editor", "subtitle_editor_btn")
            root.insertWidget(1, actions)
        elif section == "voice":
            actions, lay = _section("Voiceover", "Use translated subtitles to build the narration and mix it with the source.")
            self._button(lay, "Generate voice / mix", "voiceover_btn", primary=True)
            root.insertWidget(1, actions)
        elif section == "style":
            actions, lay = _section("Caption style", "Fine-tune the visual language without leaving the editor.")
            self._add_combo(lay, "Font", "subtitle_font_combo")
            self._add_combo(lay, "Animation", "subtitle_animation_combo")
            self._button(lay, "Open subtitle editor", "subtitle_editor_btn")
            root.insertWidget(1, actions)
        elif section == "edit":
            actions, lay = _section("Timeline edit", "Select a clip or subtitle in the timeline, then use a focused edit command.")
            self._button(lay, "Split selected clip", "timeline_split_btn")
            self._button(lay, "Delete selected clip", "timeline_delete_btn")
            root.insertWidget(1, actions)
        else:
            actions, lay = _section("Add to timeline", "New items are placed at the playhead and remain editable in the Inspector.")
            for label, layer_type in (("Text", "text"), ("Logo", "logo"), ("Blur", "blur"), ("Mask", "mask")):
                button = self._button(lay, f"Add {label}")
                button.clicked.connect(lambda _checked=False, kind=layer_type: self.gui.on_add_timeline_layer(kind))
            root.insertWidget(1, actions)
        return page

    def _add_combo(self, layout: QVBoxLayout, label: str, legacy_name: str) -> None:
        legacy = getattr(self.gui, legacy_name, None)
        if legacy is None:
            return
        caption = QLabel(label)
        caption.setObjectName("studioSectionHint")
        combo = QComboBox()
        combo.addItems([legacy.itemText(i) for i in range(legacy.count())])
        combo.setCurrentIndex(legacy.currentIndex())
        combo.currentIndexChanged.connect(legacy.setCurrentIndex)
        legacy.currentIndexChanged.connect(combo.setCurrentIndex)
        layout.insertWidget(max(0, layout.count() - 1), caption)
        layout.insertWidget(max(0, layout.count() - 1), combo)

    def _click_legacy(self, name: str) -> None:
        target = getattr(self.gui, name, None)
        if name == "browse_video":
            self.gui.browse_video()
        elif target is not None and target.isEnabled():
            target.click()

    def show_section(self, section: str) -> bool:
        if section not in self._pages:
            return False
        if self.isVisible() and self._active_section == section:
            self.hide_panel()
            return False
        self.title.setText(self.SECTION_TITLES[section][0])
        self.stack.setCurrentWidget(self._pages[section])
        self._active_section = section
        self.show()
        return True

    def hide_panel(self) -> None:
        self.hide()
        self._active_section = None
        rail = getattr(self.gui, "studio_tool_rail", None)
        if rail:
            rail.clear_selection()


class StudioInspector(QFrame):
    """Contextual editor for the layer selected in the timeline.

    The established layer cards already own the real bindings used by the
    preview, timeline and persistence code.  Host those cards here instead
    of replacing them with a read-only name/time summary.
    """

    def __init__(self, gui, parent: QWidget | None = None):
        super().__init__(parent)
        self.gui = gui
        self.setObjectName("studioInspector")
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        self.title = QLabel("Inspector", self)
        self.title.setObjectName("studioInspectorTitle")
        self.summary = QLabel("Select a clip, subtitle or effect to edit it.", self)
        self.summary.setObjectName("studioInspectorSummary")
        self.summary.setWordWrap(True)
        self.delete_btn = QPushButton("Delete selection", self)
        self.delete_btn.clicked.connect(self._delete_selected)
        layout.addWidget(self.title)
        layout.addWidget(self.summary)
        self.editor_stack = QStackedWidget(self)
        self.editor_stack.setObjectName("studioInspectorEditors")
        self._adopt_existing_editors()
        layout.addWidget(self.editor_stack, 1)
        layout.addWidget(self.delete_btn)
        self.hide()
        self.setStyleSheet(f"""
            QFrame#studioInspector {{ background: {c.panel}; border-left: 1px solid {c.border_subtle}; }}
            QLabel#studioInspectorTitle {{ color: {c.primary}; font-size: 14px; font-weight: 750; }}
            QLabel#studioInspectorSummary {{ color: {c.secondary}; font-size: 12px; line-height: 1.35; }}
            QPushButton {{ background: {c.elevated}; color: {c.secondary}; border: 1px solid {c.border_default}; border-radius: 7px; padding: 8px; font-weight: 650; }}
            QPushButton:hover {{ border-color: {c.danger}; color: {c.primary}; }}
        """)

    def _adopt_existing_editors(self) -> None:
        """Move the wired legacy editor pages into the visible Studio panel."""
        source_stack = getattr(self.gui, "inspector_stack", None)
        if source_stack is None:
            self.editor_stack.hide()
            return
        while source_stack.count():
            page = source_stack.widget(0)
            source_stack.removeWidget(page)
            card = page.widget() if isinstance(page, QScrollArea) else page
            if card is not None:
                card.setMinimumWidth(0)
                card.setMaximumWidth(16777215)
            if isinstance(page, QScrollArea):
                page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                page.setFrameShape(QFrame.NoFrame)
            self.editor_stack.addWidget(page)
        # All existing inspector routing now controls the visible Studio
        # stack. This preserves the current per-layer signal wiring.
        self.gui.inspector_stack = self.editor_stack

    def inspect_layer(self, track, layer) -> None:
        if layer is None:
            self.hide()
            return
        raw_type = getattr(getattr(layer, "type", ""), "value", getattr(layer, "type", "clip"))
        layer_type = str(raw_type).replace("_", " ").title()
        name = str(getattr(layer, "name", "") or getattr(track, "name", "") or "Timeline item")
        start = float(getattr(layer, "start", 0.0) or 0.0)
        end = float(getattr(layer, "end", start) or start)
        text = str(getattr(layer, "text", "") or "")
        self.title.setText(layer_type)
        parts = [name, f"{start:0.2f}s – {end:0.2f}s"]
        if text:
            parts.append(text[:180] + ("…" if len(text) > 180 else ""))
        self.summary.setText("\n\n".join(parts))
        # Every supported timeline type has a richer editor page containing
        # its own description and controls; avoid repeating the same summary.
        self.summary.setVisible(self.editor_stack.count() == 0)
        self.editor_stack.setVisible(self.editor_stack.count() > 0)
        self.delete_btn.setEnabled(not bool(getattr(track, "locked", False)) and not bool(getattr(layer, "locked", False)))
        self.show()

    def inspect_segment(self, index: int) -> None:
        segments = list(getattr(self.gui, "live_preview_segments", []) or getattr(self.gui, "current_segments", []) or [])
        if not (0 <= index < len(segments)):
            return
        segment = segments[index]
        self.title.setText("Subtitle")
        self.summary.setText(f"Subtitle {index + 1}\n\n{getattr(segment, 'start', 0):0.2f}s – {getattr(segment, 'end', 0):0.2f}s\n\n{getattr(segment, 'text', '')}")
        self.summary.hide()
        self.editor_stack.show()
        self.delete_btn.setEnabled(True)
        self.show()

    def _delete_selected(self) -> None:
        button = getattr(self.gui, "timeline_delete_btn", None)
        if button is not None and button.isEnabled():
            button.click()
