"""Qt stylesheet generated from CapCap Studio design tokens."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

from .tokens import COLORS as c


def load_application_fonts() -> None:
    """Register bundled fonts before any Studio widget resolves its family."""
    font_root = Path(__file__).resolve().parents[2] / "assets" / "fonts"
    for filename in ("Inter-Variable.ttf", "Roboto-Variable.ttf", "Poppins-Regular.ttf", "Poppins-Bold.ttf"):
        path = font_root / filename
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))


def build_application_stylesheet() -> str:
    """Return the final global layer of the Studio Dark theme.

    This is intentionally appended after legacy QSS during the migration so
    generic controls become consistent without breaking object-specific
    behavior that the existing editor still relies on.
    """
    return f"""
        QMainWindow, QWidget#centralWidget {{ background: {c.canvas}; color: {c.primary}; }}
        QWidget {{ font-family: Inter, Roboto, Arial, sans-serif; font-size: 12px; }}

        QFrame#studioSurface, QFrame#statusCard, QFrame#heroCard,
        QFrame#sideInfoCard, QFrame#segmentInspectorCard {{
            background: {c.panel}; border: 1px solid {c.border_subtle}; border-radius: 10px;
        }}
        QFrame#studioFlatPanel {{ background: {c.panel}; border: none; border-right: 1px solid {c.border_subtle}; }}

        QLabel {{ color: {c.secondary}; background: transparent; }}
        QLabel#heroTitle, QLabel#statusHeadline {{ color: {c.primary}; }}
        QLabel#sectionTitle {{ color: {c.accent}; font-size: 11px; font-weight: 700; }}
        QLabel#helperLabel, QLabel#previewContextLabel {{ color: {c.muted}; }}

        QPushButton, QToolButton {{
            background: {c.elevated}; color: {c.secondary}; border: 1px solid {c.border_default};
            border-radius: 8px; padding: 7px 12px; font-weight: 600;
        }}
        QPushButton:hover, QToolButton:hover {{ background: {c.hover}; color: {c.primary}; border-color: {c.accent}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {c.selected}; border-color: {c.accent_pressed}; }}
        QPushButton:disabled, QToolButton:disabled {{ background: {c.input}; color: {c.disabled}; border-color: {c.border_subtle}; }}
        QPushButton#mainActionBtn, QToolButton#mainActionBtn {{
            background: {c.accent}; color: {c.canvas}; border: 1px solid {c.accent}; font-weight: 700;
        }}
        QPushButton#mainActionBtn:hover, QToolButton#mainActionBtn:hover {{ background: {c.accent_hover}; border-color: {c.accent_hover}; }}
        QPushButton#secondaryActionBtn {{ background: {c.elevated}; color: {c.primary}; border-color: {c.border_default}; }}

        /* Studio editor transport: controls are compact, grouped, and never
           look like a generic settings form. */
        QPushButton#studioPreviewTransportButton {{
            min-width: 34px; max-width: 34px; min-height: 32px; max-height: 32px;
            padding: 0; background: {c.elevated}; color: {c.primary};
            border: 1px solid {c.border_default}; border-radius: 8px;
        }}
        QPushButton#studioPreviewTransportButton:hover {{ background: {c.selected}; border-color: {c.accent}; }}
        QPushButton#studioPreviewEffectButton {{
            min-height: 32px; padding: 0 12px; background: transparent;
            color: {c.secondary}; border: 1px solid {c.border_default}; border-radius: 8px;
        }}
        QPushButton#studioPreviewEffectButton:hover {{ background: {c.hover}; color: {c.primary}; border-color: {c.accent}; }}
        QPushButton#studioTimelineButton {{
            min-height: 26px; max-height: 26px; padding: 0 10px;
            background: transparent; color: {c.secondary}; border: 1px solid {c.border_default}; border-radius: 7px;
        }}
        QPushButton#studioTimelineButton:hover {{ background: {c.hover}; color: {c.primary}; border-color: {c.accent}; }}
        QPushButton#studioTimelineAddButton {{
            min-height: 26px; max-height: 26px; padding: 0 11px;
            background: {c.selected}; color: {c.accent_hover}; border: 1px solid #38496d; border-radius: 7px;
        }}
        QPushButton#studioTimelineAddButton:hover {{ background: #28375a; color: {c.primary}; border-color: {c.accent}; }}

        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background: {c.input}; color: {c.primary}; border: 1px solid {c.border_default};
            border-radius: 6px; padding: 7px 9px; selection-background-color: {c.selected};
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 2px solid {c.border_focus}; padding: 6px 8px;
        }}
        QComboBox QAbstractItemView {{ background: {c.elevated}; color: {c.primary}; border: 1px solid {c.border_default}; }}

        QScrollArea {{ background: transparent; border: none; }}
        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {c.border_default}; min-height: 28px; border-radius: 4px; }}
        QScrollBar::handle:vertical:hover {{ background: {c.muted}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; }}
        QScrollBar::handle:horizontal {{ background: {c.border_default}; min-width: 28px; border-radius: 4px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

        QSlider::groove:horizontal {{ height: 4px; background: {c.border_default}; border-radius: 2px; }}
        QSlider::sub-page:horizontal {{ background: {c.accent}; border-radius: 2px; }}
        QSlider::handle:horizontal {{ background: {c.primary}; border: 2px solid {c.accent}; width: 12px; height: 12px; margin: -5px 0; border-radius: 7px; }}
        QSlider::handle:horizontal:hover {{ border-color: {c.accent_hover}; }}

        QProgressBar {{ background: {c.input}; color: {c.primary}; border: 1px solid {c.border_subtle}; border-radius: 5px; text-align: center; }}
        QProgressBar::chunk {{ background: {c.accent}; border-radius: 4px; }}
        QToolTip {{ background: {c.elevated}; color: {c.primary}; border: 1px solid {c.border_default}; border-radius: 6px; padding: 6px 8px; }}
    """
