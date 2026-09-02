"""Shared Qt renderer for editor Text layers.

The editor and export paths deliberately use this module rather than ASS so
font metrics, padding, background bounds, and the centre anchor come from one
implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import os

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter

from app.layers.text import TEXT_LAYER_PADDING_X, TEXT_LAYER_PADDING_Y


_HEADLESS_QT_APPLICATION = None


def _ensure_qt_font_application() -> None:
    """Provide a font database when export runs in the headless API worker."""
    global _HEADLESS_QT_APPLICATION
    if QGuiApplication.instance() is not None:
        return
    # The desktop editor already owns QApplication. The remote export worker
    # has no GUI application, but QFontMetrics still requires QGuiApplication.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _HEADLESS_QT_APPLICATION = QGuiApplication([])


@dataclass(frozen=True)
class RenderedTextLayer:
    image: QImage
    rect: QRectF
    font: QFont
    metrics: QFontMetrics
    lines: tuple[str, ...]


@dataclass(frozen=True)
class TextLayerLayout:
    rect: QRectF
    font: QFont
    metrics: QFontMetrics
    lines: tuple[str, ...]
    padding_x: int
    padding_y: int


def _color(value: object, fallback: str) -> QColor:
    color = QColor(str(value or fallback))
    return color if color.isValid() else QColor(fallback)


def layout_text_layer(item: dict, canvas_width: int, canvas_height: int) -> TextLayerLayout:
    """Calculate one layer's shared Qt geometry in target-canvas pixels.

    ``font_size`` and ``padding_scale`` are already in the target canvas's
    pixels. The editor supplies preview-scaled values; export supplies source
    video pixels. That keeps this renderer independent of the caller's canvas
    resolution while preserving identical geometry after scaling.
    """
    _ensure_qt_font_application()
    font = QFont(str(item.get("font_name", "Arial") or "Arial"))
    font.setPixelSize(max(1, int(round(float(item.get("font_size", 60) or 60)))))
    font.setBold(bool(item.get("font_bold", False)))
    font.setItalic(bool(item.get("font_italic", False)))
    font.setUnderline(bool(item.get("font_underline", False)))
    metrics = QFontMetrics(font)
    lines = tuple(str(item.get("text", " ") or " ").splitlines() or [" "])
    padding_scale = max(0.01, float(item.get("padding_scale", 1.0) or 1.0))
    padding_x = max(0, int(round(TEXT_LAYER_PADDING_X * padding_scale)))
    padding_y = max(0, int(round(TEXT_LAYER_PADDING_Y * padding_scale)))
    width = max(metrics.horizontalAdvance(line) for line in lines) + padding_x * 2
    height = metrics.height() * len(lines) + padding_y * 2
    raw_x = item.get("x", 0.5)
    raw_y = item.get("y", 0.5)
    center_x = float(0.5 if raw_x is None else raw_x) * max(1, int(canvas_width))
    center_y = float(0.5 if raw_y is None else raw_y) * max(1, int(canvas_height))
    # FFmpeg's overlay filter ultimately places images on integer pixel
    # coordinates. Quantize the shared top-left anchor here as well, so the
    # direct QPainter preview and exported cropped PNG use the same origin
    # instead of differing by a half-pixel at centred positions.
    rect = QRectF(
        int(round(center_x - width / 2.0)),
        int(round(center_y - height / 2.0)),
        width,
        height,
    )

    return TextLayerLayout(rect=rect, font=font, metrics=metrics, lines=lines,
                           padding_x=padding_x, padding_y=padding_y)


def paint_text_layer(painter: QPainter, item: dict, layout: TextLayerLayout, *, origin: QPointF | None = None) -> None:
    """Paint the shared layout directly into an existing Qt painter."""
    origin = origin or QPointF(0.0, 0.0)
    rect = layout.rect.translated(origin)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    base_opacity = max(0.0, min(1.0, float(item.get("opacity", 1.0) if item.get("opacity", None) is not None else 1.0)))
    previous_opacity = painter.opacity()
    painter.setOpacity(base_opacity)
    background = _color(item.get("background_color", ""), "#000000")
    if str(item.get("background_color", "") or "").strip():
        opacity = max(0.0, min(1.0, float(item.get("background_opacity", 0.5) or 0.0)))
        background.setAlpha(int(round(opacity * 255)))
        painter.fillRect(rect, background)
    painter.setFont(layout.font)
    painter.setPen(_color(item.get("font_color", "#FFFFFF"), "#FFFFFF"))
    baseline = rect.top() + layout.padding_y + layout.metrics.ascent()
    for line in layout.lines:
        painter.drawText(QPointF(rect.left() + layout.padding_x, baseline), line)
        baseline += layout.metrics.height()
    painter.setOpacity(previous_opacity)


def render_text_layer(item: dict, canvas_width: int, canvas_height: int) -> RenderedTextLayer:
    """Render one layer into a cropped transparent image at its canvas rect."""
    layout = layout_text_layer(item, canvas_width, canvas_height)
    image = QImage(max(1, int(math.ceil(layout.rect.width()))), max(1, int(math.ceil(layout.rect.height()))), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    # Render at local origin while retaining the exact shared text layout.
    local_layout = TextLayerLayout(
        rect=QRectF(0.0, 0.0, layout.rect.width(), layout.rect.height()),
        font=layout.font,
        metrics=layout.metrics,
        lines=layout.lines,
        padding_x=layout.padding_x,
        padding_y=layout.padding_y,
    )
    paint_text_layer(painter, item, local_layout)
    painter.end()
    return RenderedTextLayer(image=image, rect=layout.rect, font=layout.font,
                             metrics=layout.metrics, lines=layout.lines)
