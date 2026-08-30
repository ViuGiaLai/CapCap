from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.layers.base import BaseLayer, LayerType


@dataclass
class BlurLayer(BaseLayer):
    type: LayerType = field(default=LayerType.BLUR, init=False)
    position_x: float = 0.0
    position_y: float = 0.0
    width: float = 200.0
    height: float = 80.0
    blur_strength: float = 36.0
    blur_opacity: float = 1.0
    pixelate: bool = False
    pixelate_size: int = 12

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "position_x": self.position_x,
            "position_y": self.position_y,
            "width": self.width,
            "height": self.height,
            "blur_strength": self.blur_strength,
            "blur_opacity": self.blur_opacity,
            "pixelate": self.pixelate,
            "pixelate_size": self.pixelate_size,
        })
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlurLayer:
        base = super().from_dict(data)
        return cls(
            id=base.id, name=base.name,
            start=base.start, end=base.end,
            z_index=base.z_index,
            visible=base.visible, locked=base.locked,
            opacity=base.opacity, blend_mode=base.blend_mode,
            metadata=base.metadata,
            position_x=float(data.get("position_x", 0.0)),
            position_y=float(data.get("position_y", 0.0)),
            width=float(data.get("width", 200.0)),
            height=float(data.get("height", 80.0)),
            blur_strength=float(data.get("blur_strength", 36.0)),
            blur_opacity=float(data.get("blur_opacity", 1.0)),
            pixelate=bool(data.get("pixelate", False)),
            pixelate_size=int(data.get("pixelate_size", 12)),
        )
