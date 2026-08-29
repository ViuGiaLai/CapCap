from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from PySide6.QtCore import QThread, Signal

from app.version import get_app_version


GITHUB_REPO = "ViuGiaLai/CapCap"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse_semver(version_str: str) -> tuple[int, ...]:
    """Parse version string like 'v1.2.3' or '1.2.3-beta' into a comparable tuple of integers."""
    clean = re.sub(r"^[vV]", "", str(version_str or "").strip())
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", clean)
    if not match:
        return (0, 0, 0)
    parts = match.groups()
    return tuple(int(p) if p is not None else 0 for p in parts)


def is_version_newer(latest_ver: str, current_ver: str) -> bool:
    """Return True if latest_ver is strictly newer than current_ver."""
    return parse_semver(latest_ver) > parse_semver(current_ver)


class UpdateCheckerThread(QThread):
    """Background worker thread to check for latest release on GitHub."""

    update_available = Signal(dict)       # Emits release info dict
    no_update_available = Signal(str)     # Emits current version
    check_failed = Signal(str)            # Emits error message

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        current_version = get_app_version()
        req = urllib.request.Request(
            LATEST_RELEASE_API,
            headers={
                "User-Agent": "CapCap-App-UpdateChecker",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status != 200:
                    self.check_failed.emit(f"GitHub API returned HTTP {resp.status}")
                    return
                data = json.loads(resp.read().decode("utf-8", errors="replace"))

            tag_name = str(data.get("tag_name", "")).strip()
            latest_version = re.sub(r"^[vV]", "", tag_name)
            release_notes = str(data.get("body", "")).strip()
            published_at = str(data.get("published_at", "")).strip()
            html_url = str(data.get("html_url", "")).strip()

            # Find setup executable or portable zip asset
            setup_asset_url = ""
            portable_asset_url = ""
            setup_filename = ""

            for asset in data.get("assets", []):
                name = str(asset.get("name", "")).lower()
                download_url = str(asset.get("browser_download_url", ""))
                if name.endswith(".exe") and "setup" in name:
                    setup_asset_url = download_url
                    setup_filename = asset.get("name", "CapCap-Setup.exe")
                elif name.endswith(".zip") and ("portable" in name or "windows" in name):
                    portable_asset_url = download_url

            if is_version_newer(latest_version, current_version):
                info = {
                    "current_version": current_version,
                    "latest_version": latest_version,
                    "tag_name": tag_name,
                    "release_notes": release_notes,
                    "published_at": published_at,
                    "html_url": html_url,
                    "setup_url": setup_asset_url or portable_asset_url or html_url,
                    "setup_filename": setup_filename or f"CapCap-{latest_version}-Setup.exe",
                }
                self.update_available.emit(info)
            else:
                self.no_update_available.emit(current_version)

        except urllib.error.URLError as exc:
            self.check_failed.emit(f"Network connection failed: {exc.reason}")
        except Exception as exc:
            self.check_failed.emit(f"Update check error: {exc}")


class UpdateDownloaderThread(QThread):
    """Background worker thread to download the installer file."""

    progress_signal = Signal(int, int, int)   # (percent, downloaded_bytes, total_bytes)
    download_finished = Signal(str)          # Emits local file path
    download_failed = Signal(str)            # Emits error message

    def __init__(self, download_url: str, target_filename: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.target_filename = target_filename
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        temp_dir = tempfile.gettempdir()
        target_path = os.path.join(temp_dir, self.target_filename or "CapCap-Setup.exe")
        req = urllib.request.Request(
            self.download_url,
            headers={"User-Agent": "CapCap-App-UpdateDownloader"},
        )

        try:
            with urllib.request.urlopen(req, timeout=30.0) as response:
                total_bytes = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 64 * 1024

                with open(target_path, "wb") as f:
                    while not self._is_cancelled:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        percent = int((downloaded / total_bytes * 100)) if total_bytes > 0 else 0
                        self.progress_signal.emit(percent, downloaded, total_bytes)

            if self._is_cancelled:
                if os.path.exists(target_path):
                    try:
                        os.remove(target_path)
                    except OSError:
                        pass
                return

            self.download_finished.emit(target_path)

        except Exception as exc:
            self.download_failed.emit(str(exc))
