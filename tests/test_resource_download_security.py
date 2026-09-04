from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "app"), str(ROOT)]

from services.resource_download_service import ResourceDownloadService


def _archive(*entries: tuple[str, bytes]) -> zipfile.ZipFile:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    payload.seek(0)
    return zipfile.ZipFile(payload, "r")


def test_safe_extract_zip_rejects_parent_traversal(tmp_path):
    destination = tmp_path / "models"
    outside = tmp_path / "outside.txt"
    with _archive(("../outside.txt", b"must not be written")) as archive:
        with pytest.raises(ValueError, match="traversal"):
            ResourceDownloadService._safe_extract_zip(archive, str(destination))
    assert not outside.exists()


def test_safe_extract_zip_rejects_absolute_paths(tmp_path):
    with _archive(("C:/outside.txt", b"must not be written")) as archive:
        with pytest.raises(ValueError, match="absolute path"):
            ResourceDownloadService._safe_extract_zip(archive, str(tmp_path / "models"))


def test_safe_extract_zip_writes_only_valid_members(tmp_path):
    destination = tmp_path / "models"
    with _archive(("nested/model.bin", b"model"), ("nested/config.json", b"{}")) as archive:
        ResourceDownloadService._safe_extract_zip(archive, str(destination))
    assert (destination / "nested" / "model.bin").read_bytes() == b"model"
    assert (destination / "nested" / "config.json").read_text(encoding="utf-8") == "{}"
