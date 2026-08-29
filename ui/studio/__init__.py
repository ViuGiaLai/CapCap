"""Visible Studio panels for the editor workspace.

Legacy controls remain instantiated as an internal controller adapter while
these widgets own the user-facing editor experience.
"""

from .panels import StudioInspector, StudioTaskPanel

__all__ = ["StudioInspector", "StudioTaskPanel"]
