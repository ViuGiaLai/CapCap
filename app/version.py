from __future__ import annotations

import json
import os
from runtime_paths import app_path, join_root


def get_app_version() -> str:
    """Return the application version string (e.g., '1.0.0').
    
    Reads from app/version.json (injected during GitHub Actions build).
    Falls back to '1.0.0' for local development.
    """
    candidates = [
        join_root("app", "version.json"),
        app_path("version.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ver = str(data.get("version", "")).strip()
                    if ver:
                        return ver
            except Exception:
                pass
    return "1.0.0"


def get_app_version_string() -> str:
    """Return prefixed version string (e.g. 'v1.0.0')."""
    return f"v{get_app_version()}"
