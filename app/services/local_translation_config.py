from __future__ import annotations

import json
import os
from copy import deepcopy

from runtime_paths import join_root, models_path


HYMT_MODELS = {
    "q4_k_m": {
        "id": "q4_k_m",
        "filename": "HY-MT1.5-1.8B-Q4_K_M.gguf",
        "label": "Balanced — Q4_K_M (~1.1 GB)",
        "description": "Recommended for 8 GB RAM; fastest, good quality.",
        "size": 1_133_080_512,
        "sha256": "4383ac0c3c8e476de98ff979c2a3f069f8c4fb385e7860cf2d28da896cc477c7",
    },
    "q6_k": {
        "id": "q6_k",
        "filename": "HY-MT1.5-1.8B-Q6_K.gguf",
        "label": "High quality — Q6_K (~1.5 GB)",
        "description": "Recommended for 12 GB RAM or more; more accurate, slower than Q4.",
        "size": 1_474_785_216,
        "sha256": "c3819200ab9a79cb29b9a05ce8920e2eb01ae7ce520094fc5b57356494f3c641",
    },
    "q8_0": {
        "id": "q8_0",
        "filename": "HY-MT1.5-1.8B-Q8_0.gguf",
        "label": "Maximum — Q8_0 (~1.9 GB)",
        "description": "Recommended for 16 GB RAM or more; highest quality, uses more RAM and is slower.",
        "size": 1_908_528_288,
        "sha256": "6789b06d0902f2f5312c0e1703d56ccbddfcfb6c653d22519b7c720f7db9a98e",
    },
}

MODEL_REPO_URL = "https://huggingface.co/tencent/HY-MT1.5-1.8B-GGUF/resolve/main"
DEFAULT_MODEL_ID = "q4_k_m"


def settings_path() -> str:
    return join_root("config", "local_translation.json")


def default_storage_dir() -> str:
    return models_path("local_translation")


def load_local_translation_config() -> dict:
    defaults = {
        "model_id": DEFAULT_MODEL_ID,
        "storage_dir": default_storage_dir(),
        "custom_model_path": "",
    }
    path = settings_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            defaults.update({key: payload.get(key, value) for key, value in defaults.items()})
    except (OSError, ValueError, TypeError):
        pass
    model_id = str(defaults.get("model_id") or DEFAULT_MODEL_ID).strip().lower()
    if model_id not in HYMT_MODELS and model_id != "custom":
        model_id = DEFAULT_MODEL_ID
    storage_dir = os.path.abspath(
        os.path.expanduser(str(defaults.get("storage_dir") or default_storage_dir()).strip())
    )
    custom_path = str(defaults.get("custom_model_path") or "").strip()
    return {
        "model_id": model_id,
        "storage_dir": storage_dir,
        "custom_model_path": os.path.abspath(os.path.expanduser(custom_path)) if custom_path else "",
    }


def save_local_translation_config(*, model_id: str, storage_dir: str, custom_model_path: str = "") -> dict:
    normalized_id = str(model_id or DEFAULT_MODEL_ID).strip().lower()
    if normalized_id not in HYMT_MODELS and normalized_id != "custom":
        raise ValueError(f"Unsupported local translation model: {normalized_id}")
    normalized_storage = os.path.abspath(os.path.expanduser(str(storage_dir or default_storage_dir()).strip()))
    normalized_custom = str(custom_model_path or "").strip()
    payload = {
        "model_id": normalized_id,
        "storage_dir": normalized_storage,
        "custom_model_path": os.path.abspath(os.path.expanduser(normalized_custom)) if normalized_custom else "",
    }
    path = settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)
    return payload


def selected_model_info() -> dict:
    config = load_local_translation_config()
    if config["model_id"] == "custom":
        custom_path = config["custom_model_path"]
        return {
            "id": "custom",
            "filename": os.path.basename(custom_path) if custom_path else "Custom GGUF",
            "label": "Custom GGUF file",
            "description": "User-selected GGUF model file.",
            "path": custom_path,
            "size": os.path.getsize(custom_path) if custom_path and os.path.isfile(custom_path) else 0,
            "sha256": "",
        }
    info = deepcopy(HYMT_MODELS[config["model_id"]])
    info["path"] = os.path.join(config["storage_dir"], info["filename"])
    return info


def model_info(model_id: str) -> dict:
    info = deepcopy(HYMT_MODELS[str(model_id).strip().lower()])
    config = load_local_translation_config()
    info["path"] = os.path.join(config["storage_dir"], info["filename"])
    info["url"] = f"{MODEL_REPO_URL}/{info['filename']}"
    return info


def is_valid_gguf(path: str) -> bool:
    candidate = str(path or "").strip()
    if not candidate.lower().endswith(".gguf") or not os.path.isfile(candidate):
        return False
    try:
        with open(candidate, "rb") as handle:
            return handle.read(4) == b"GGUF"
    except OSError:
        return False


SKIP_DIR_NAMES = {
    "windows",
    "$recycle.bin",
    "system volume information",
    "program files",
    "program files (x86)",
    "node_modules",
    ".git",
    ".venv",
    "__pycache__",
    "vendor",
    "winre",
    "recovery",
    "msocache",
    "config.msi",
    "$winre_backup",
}


def scan_gguf_models(root_dir: str, *, max_results: int = 2000, progress_cb=None) -> list[tuple[str, int]]:
    root = os.path.abspath(os.path.expanduser(str(root_dir or "").strip()))
    if not os.path.isdir(root):
        return []
    found: list[tuple[str, int]] = []
    for current_dir, dirs, files in os.walk(root):
        # Prune system/junk directories in-place so os.walk does not recurse into them
        dirs[:] = [
            d for d in dirs
            if d.lower() not in SKIP_DIR_NAMES and not d.startswith("$")
        ]
        if progress_cb and progress_cb(current_dir) is False:
            break
        for filename in files:
            if not filename.lower().endswith(".gguf"):
                continue
            path = os.path.join(current_dir, filename)
            if not is_valid_gguf(path):
                continue
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            found.append((path, size))
            if len(found) >= max(1, int(max_results)):
                return sorted(found, key=lambda item: os.path.basename(item[0]).lower())
    return sorted(found, key=lambda item: os.path.basename(item[0]).lower())
