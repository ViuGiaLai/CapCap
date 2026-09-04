from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget


class StudioInspector(QFrame):
    """Contextual editor for the layer selected in the timeline.

    The established layer cards already own the real bindings used by the
    preview, timeline and persistence code. Host those cards here instead
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

        self.title = QLabel("Track Inspector")
        self.title.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")
        self.summary = QLabel("")
        self.summary.setStyleSheet("font-size: 12px; color: #94a3b8;")

        self.delete_btn = QPushButton("Delete selection")
        self.delete_btn.setObjectName("secondaryActionBtn")
        self.delete_btn.clicked.connect(self._delete_selected)

        layout.addWidget(self.title)
        layout.addWidget(self.summary)

        self.editor_stack = QStackedWidget(self)
        self.editor_stack.setObjectName("studioInspectorEditors")
        self._adopt_existing_editors()
        layout.addWidget(self.editor_stack, 1)

        layout.addWidget(self.delete_btn)
        self.hide()
        self.setStyleSheet("""
            QFrame#studioInspector {
                background-color: #121824;
                border-left: 1px solid #1e293b;
            }
        """)

    def _adopt_existing_editors(self):
        """Adopt cards from gui.inspector_stack so StudioInspector hosts real editor controls."""
        if hasattr(self.gui, "inspector_stack") and self.gui.inspector_stack is not None:
            old_stack = self.gui.inspector_stack
            while old_stack.count() > 0:
                widget = old_stack.widget(0)
                old_stack.removeWidget(widget)
                self.editor_stack.addWidget(widget)
            self.gui.inspector_stack = self.editor_stack

    def _delete_selected(self):
        if hasattr(self.gui, "timeline_delete_selected_layer"):
            self.gui.timeline_delete_selected_layer()
        elif hasattr(self.gui, "on_timeline_delete_clicked"):
            self.gui.on_timeline_delete_clicked()
