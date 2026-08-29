"""Single source of truth for CapCap Studio visual tokens."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorTokens:
    canvas: str = "#0B0D12"
    panel: str = "#11141B"
    elevated: str = "#171B24"
    hover: str = "#1C2230"
    selected: str = "#202A44"
    input: str = "#0F1218"
    primary: str = "#F4F7FB"
    secondary: str = "#B4BDCA"
    muted: str = "#7E8999"
    disabled: str = "#535D6C"
    border_subtle: str = "#242A36"
    border_default: str = "#303847"
    border_focus: str = "#7C8CFF"
    accent: str = "#7C8CFF"
    accent_hover: str = "#94A2FF"
    accent_pressed: str = "#6575E8"
    success: str = "#45D39C"
    warning: str = "#F5B94C"
    danger: str = "#F06A77"
    info: str = "#57B8FF"
    video: str = "#4D8DFF"
    audio: str = "#36B983"
    subtitle: str = "#9B7BFF"
    voice: str = "#F29B5E"
    blur: str = "#53C5D9"
    image: str = "#E777B9"
    mask: str = "#E7B34D"
    text_layer: str = "#B979F2"


COLORS = ColorTokens()

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 20, "2xl": 24, "3xl": 32}
RADIUS = {"control": 6, "button": 8, "panel": 10, "pill": 999}
