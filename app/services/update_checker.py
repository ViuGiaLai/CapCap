from __future__ import annotations

import json
import urllib.request
from PySide6.QtCore import QThread, Signal
try:
    from app.version import APP_VERSION
except ImportError:
    from version import APP_VERSION


class UpdateCheckerThread(QThread):
    """Background thread to check GitHub Releases for VIUStudio updates."""

    update_available = Signal(dict)
    no_update_available = Signal(str)
    check_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_url = "https://api.github.com/repos/ViuGiaLai/VIUStudio/releases/latest"

    def run(self):
        try:
            req = urllib.request.Request(
                self.api_url,
                headers={"User-Agent": f"VIUStudio-App/{APP_VERSION}"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status != 200:
                    self.check_failed.emit(f"HTTP Error {response.status}")
                    return
                data = json.loads(response.read().decode("utf-8"))

            tag_name = data.get("tag_name", "").lstrip("v").strip()
            if not tag_name:
                self.check_failed.emit("Invalid release tag")
                return

            if self._is_newer_version(tag_name, APP_VERSION):
                self.update_available.emit({
                    "version": tag_name,
                    "release_notes": data.get("body", "No release notes provided."),
                    "html_url": data.get("html_url", ""),
                    "assets": data.get("assets", []),
                })
            else:
                self.no_update_available.emit(APP_VERSION)

        except Exception as exc:
            self.check_failed.emit(str(exc))

    def _is_newer_version(self, latest: str, current: str) -> bool:
        """Parses semver strings like 1.2.0 and compares."""
        def parse_ver(v_str):
            return [int(x) for x in v_str.split(".") if x.isdigit()]

        try:
            return parse_ver(latest) > parse_ver(current)
        except Exception:
            return False
