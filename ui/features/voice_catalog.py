"""Voice catalog, engine, and translation-provider UI feature."""

import json
import os
import re

from PySide6.QtCore import QThread, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from runtime_paths import app_path, models_path


class GgufScanWorker(QThread):
    progress_updated = Signal(str)
    scan_finished = Signal(list)

    def __init__(self, drives: list[str], parent=None):
        super().__init__(parent)
        self.drives = drives
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        import os
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from services.local_translation_config import scan_gguf_models

        all_found: list[tuple[str, int]] = []
        lock = threading.Lock()

        def _scan_drive(drive: str) -> list[tuple[str, int]]:
            def _cb(_dir: str) -> bool:
                return not self._is_cancelled
            return scan_gguf_models(drive, progress_cb=_cb)

        executor = ThreadPoolExecutor(max_workers=min(len(self.drives), 8))
        futures = {executor.submit(_scan_drive, drv): drv for drv in self.drives}

        completed = 0
        for future in as_completed(futures):
            if self._is_cancelled:
                break
            drv = futures[future]
            try:
                res = future.result()
                with lock:
                    all_found.extend(res)
            except Exception:
                pass
            completed += 1
            self.progress_updated.emit(
                f"Scanning drive {drv} ({completed}/{len(self.drives)} drives complete) — Found {len(all_found)} model(s)"
            )

        executor.shutdown(wait=False)
        if not self._is_cancelled:
            found = sorted(set(all_found), key=lambda x: os.path.basename(x[0]).lower())
            self.scan_finished.emit(found)
        else:
            self.scan_finished.emit([])


def _default_asr_engine() -> str:
    return "sensevoice"


class VoiceCatalogMixin:
    def setup_audio_preview_player(self):
        if getattr(self, "_preview_audio_signals_bound", False):
            return
        self._preview_audio_signals_bound = True
        self.audio_preview_player = QMediaPlayer(self)
        self.audio_preview_output = QAudioOutput(self)
        self.audio_preview_player.setAudioOutput(self.audio_preview_output)
        self.voice_preview_library_player = QMediaPlayer(self)
        self.voice_preview_library_output = QAudioOutput(self)
        self.voice_preview_library_player.setAudioOutput(self.voice_preview_library_output)
        self.voice_preview_dialog = None
        self._voice_preview_row_buttons = {}

    def _voice_catalog_data_value(self, entry: dict) -> str:
        provider = str(entry.get("provider", "")).strip().lower()
        provider_voice = str(entry.get("provider_voice", "")).strip()
        entry_id = str(entry.get("id", "")).strip()
        if provider == "piper":
            return entry_id
        if provider == "edge":
            return f"edge:{provider_voice or 'vi-VN-HoaiMyNeural'}"
        return ""

    def _voice_provider_label(self, provider: str) -> str:
        provider_key = str(provider or "").strip().lower()
        if provider_key == "piper":
            return "Local"
        if provider_key == "edge":
            return "Edge"
        return str(provider or "Other").strip().title() or "Other"

    def _current_voice_tier(self) -> str:
        return "free"

    def _selected_voice_gender(self) -> str:
        if not hasattr(self, "voice_gender_combo"):
            return "any"
        return str(self.voice_gender_combo.currentText()).strip().lower()

    def _entry_has_preview_media(self, entry: dict | None) -> bool:
        if not entry:
            return False
        return bool(
            entry.get("preview_video_path")
            or entry.get("preview_video_url")
            or entry.get("preview_audio_path")
            or entry.get("preview_audio_url")
        )

    def set_voice_combo_value(self, combo, value):
        target = str(value or "").strip()
        if not combo or not target:
            return
        for index in range(combo.count()):
            item_value = str(combo.itemData(index) or "").strip()
            item_entry_id = str(combo.itemData(index, self.VOICE_ENTRY_ID_ROLE) or "").strip()
            if item_value == target or item_entry_id == target:
                combo.setCurrentIndex(index)
                return

    def _get_previewable_voice_catalog_entry(self):
        return None

    def _update_voice_preview_meta(self):
        if not hasattr(self, "voice_preview_meta_label"):
            return
        total_entries = len(self.voice_catalog_entries or [])
        if hasattr(self, "preview_voice_btn"):
            self.preview_voice_btn.setVisible(True)
            self.preview_voice_btn.setEnabled(total_entries > 0)
        if total_entries <= 0:
            self.voice_preview_meta_label.setText("No voices are available in the catalog yet.")
            return
        self.voice_preview_meta_label.setText(
            f"Local voices: {total_entries}. Click “Preview voice” to generate a short test clip."
        )

    def _current_voice_engine_key(self) -> str:
        combo = getattr(self, "voice_engine_combo", None)
        if combo is None:
            return "fast"
        return str(combo.currentData() or "fast").strip().lower() or "fast"

    def get_transcription_engine(self) -> str:
        """Return the recognition source for the open project, never a stale global preference."""
        state = getattr(self, "current_project_state", None)
        settings = getattr(state, "settings", {}) if state is not None else {}
        value = str(settings.get("transcription_engine", "") or "").strip().lower()
        return value if value in {"whisper", "sensevoice", "ocr"} else _default_asr_engine()

    def set_project_transcription_engine(self, engine: str) -> None:
        """Apply a project-local source choice and clear incompatible range state."""
        engine = str(engine or "").strip().lower()
        if engine not in {"whisper", "sensevoice", "ocr"}:
            engine = _default_asr_engine()
        previous = self.get_transcription_engine()
        os.environ["TRANSCRIPTION_ENGINE"] = engine
        state = getattr(self, "current_project_state", None)
        if state is not None:
            state.set_setting("transcription_engine", engine)
            self.project_service.save_project(state)
        if engine != previous:
            # A new OCR project needs the crop editor immediately. Existing
            # projects with completed OCR remain unobstructed until the user
            # explicitly reopens the region tool.
            if engine == "ocr" and not self.current_segments and not self.transcript_text.toPlainText().strip():
                self._ocr_overlay_visible = True
            timeline = getattr(self, "timeline", None)
            if timeline is not None:
                timeline.clear_selection_range()
            self._alternate_ocr_range_pending = None
            overlay = getattr(self, "ocr_region_overlay", None)
            if overlay is not None:
                overlay.set_editable(False)
                overlay.hide()
            button = getattr(self, "timeline_alt_transcribe_btn", None)
            if button is not None:
                self._update_alt_transcribe_button_label()
            self.log(f"[Subtitle Source] Changed to {engine}; cleared Selection Range.")
        self.update_speaker_diarization_availability()
        self._update_ocr_overlay()

    def _alternate_transcription_engine(self) -> str:
        return "whisper" if self.get_transcription_engine() == "ocr" else "ocr"

    def _update_alt_transcribe_button_label(self) -> None:
        button = getattr(self, "timeline_alt_transcribe_btn", None)
        if button is None or getattr(self, "_alternate_range_transcription_worker", None) is not None:
            return
        if bool(getattr(self, "_alternate_ocr_range_pending", None)):
            button.setText("Run OCR")
            return
        button.setText("Alt Transcribe")
        button.setToolTip("Transcribe the Selection Range with custom Whisper or OCR settings")

    def _resolve_active_voice_name(self, *, persist_new_clone: bool = False) -> str:
        free_value = str(self.free_voice_combo.currentData() or "").strip() if hasattr(self, "free_voice_combo") else ""
        if free_value and free_value.startswith("edge:"):
            return free_value
        if free_value and free_value in getattr(self, "voice_catalog_map", {}):
            return free_value
        target_language = self.get_target_language_code()
        if target_language == "vi" and "ngochuyen" in getattr(self, "voice_catalog_map", {}):
            return "ngochuyen"
        if target_language == "vi" and "vi_VN-vais1000-medium" in getattr(self, "voice_catalog_map", {}):
            return "vi_VN-vais1000-medium"
        if hasattr(self, "free_voice_combo") and self.free_voice_combo.count() > 0:
            fallback_value = str(self.free_voice_combo.itemData(0) or "").strip()
            if fallback_value:
                return fallback_value
            fallback_entry_id = str(self.free_voice_combo.itemData(0, self.VOICE_ENTRY_ID_ROLE) or "").strip()
            if fallback_entry_id:
                return fallback_entry_id
        return ""

    def on_voice_engine_changed(self):
        self._voiceover_force_refresh = True

    def load_voice_preview_catalog(self):
        self._auto_sync_piper_voices_to_catalog()
        self.voice_catalog_entries_all = self.voice_catalog_service.load_catalog()
        self._apply_piper_voice_meta_overrides()
        if self.voice_preview_dialog is not None:
            self.voice_preview_dialog.close()
            self.voice_preview_dialog = None
        self.refresh_voice_catalog_combos()

    def _load_piper_voice_meta(self) -> dict:
        meta_path = models_path("piper", "voices_meta.json")
        if not os.path.exists(meta_path):
            return {}
        try:
            with open(meta_path, "r", encoding="utf-8-sig") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                return {}
            voices = payload.get("voices", {})
            return voices if isinstance(voices, dict) else {}
        except Exception:
            return {}

    def _normalize_gender_value(self, value: str) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return ""
        if raw in {"m", "male", "nam"}:
            return "male"
        if raw in {"f", "female", "nu", "ná»¯"}:
            return "female"
        if raw in {"any", "unknown", "none"}:
            return ""
        return raw

    def _voice_gender_sort_rank(self, value: str) -> int:
        normalized = self._normalize_gender_value(value)
        if normalized == "female":
            return 0
        if normalized == "male":
            return 1
        return 2

    def _voice_entry_sort_key(self, entry: dict) -> tuple:
        provider = str(entry.get("provider", "")).strip().lower()
        name = str(entry.get("name", entry.get("id", ""))).strip().lower()
        return (
            self._voice_gender_sort_rank(str(entry.get("gender", ""))),
            0 if provider == "edge" else 1,
            name,
        )

    def _apply_piper_voice_meta_overrides(self):
        voices_meta = self._load_piper_voice_meta()
        if not voices_meta:
            return
        for entry in self.voice_catalog_entries_all or []:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("provider", "")).strip().lower() != "piper":
                continue
            voice_id = str(entry.get("id", "")).strip()
            if not voice_id:
                continue
            meta = voices_meta.get(voice_id, {})
            if not isinstance(meta, dict):
                continue
            if "gender" in meta:
                entry["gender"] = self._normalize_gender_value(meta.get("gender", ""))

    def _auto_sync_piper_voices_to_catalog(self):
        model_directories = (
            (models_path("piper"), "models/piper"),
            (models_path("piper-en"), "models/piper-en"),
        )
        if not any(os.path.isdir(path) for path, _relative_path in model_directories):
            return
        catalog_path = app_path("voice_preview_catalog.json")
        os.makedirs(os.path.dirname(catalog_path), exist_ok=True)

        def titleize(voice_id: str) -> str:
            stem = str(voice_id or "").strip()
            if not stem:
                return "Voice"
            if re.match(r"^[a-z]{2}_[A-Z]{2}-", stem):
                return stem
            text = re.sub(r"[_-]+", " ", stem, flags=re.UNICODE).strip()
            text = re.sub(r"\s+", " ", text, flags=re.UNICODE)
            parts = [p for p in text.split(" ") if p]
            out = []
            for part in parts:
                if any(ch.isdigit() for ch in part):
                    out.append(part)
                else:
                    out.append(part[:1].upper() + part[1:].lower())
            return " ".join(out) if out else stem

        def language_from_piper_config(model_path: str) -> str:
            cfg_path = f"{model_path}.json"
            if not os.path.exists(cfg_path):
                return ""
            try:
                with open(cfg_path, "r", encoding="utf-8", errors="ignore") as handle:
                    head = handle.read(16384)
            except Exception:
                return ""
            match = re.search(
                r"\"espeak\"\\s*:\\s*{[^}]*\"voice\"\\s*:\\s*\"([^\"]+)\"",
                head,
                flags=re.IGNORECASE | re.DOTALL,
            )
            voice = (match.group(1).strip() if match else "").lower()
            if not voice:
                return ""
            return re.split(r"[-_]", voice, 1)[0].strip().lower()

        def provider_voice_for_model(model_path: str, relative_dir: str) -> str:
            return f"{relative_dir}/{os.path.basename(model_path)}"

        try:
            if os.path.exists(catalog_path):
                with open(catalog_path, "r", encoding="utf-8-sig") as handle:
                    payload = json.load(handle) or {}
            else:
                payload = {}
        except Exception:
            payload = {}

        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("schema_version", 2)
        payload.setdefault("voices", [])
        voices = list(payload.get("voices", []) or [])

        by_id = {}
        for entry in voices:
            if isinstance(entry, dict) and entry.get("id"):
                by_id[str(entry.get("id")).strip()] = entry

        model_paths = []
        for models_dir, relative_dir in model_directories:
            if not os.path.isdir(models_dir):
                continue
            for root, _dirs, files in os.walk(models_dir):
                for name in files:
                    if name.lower().endswith(".onnx"):
                        full_path = os.path.join(root, name)
                        rel_path = os.path.relpath(full_path, app_path("..")).replace("\\", "/")
                        model_paths.append((full_path, rel_path))
        model_paths.sort(key=lambda item: (item[1], os.path.basename(item[0]).lower()))
        changed = False
        model_ids = set()
        if not model_paths:
            return

        for model_path, rel_pv in model_paths:
            voice_id = os.path.splitext(os.path.basename(model_path))[0]
            model_ids.add(voice_id)
            pv = rel_pv
            lang = language_from_piper_config(model_path) or "vi"

            existing = by_id.get(voice_id)
            if isinstance(existing, dict) and str(existing.get("provider", "")).strip().lower() == "piper":
                if str(existing.get("provider_voice", "")).strip() != pv:
                    existing["provider_voice"] = pv
                    changed = True
                if not str(existing.get("language", "")).strip():
                    existing["language"] = lang
                    changed = True
                for key in ("preview_audio_url", "preview_audio_path", "preview_video_url", "preview_video_path"):
                    if key not in existing:
                        existing[key] = ""
                        changed = True
                if "tier" not in existing:
                    existing["tier"] = "free"
                    changed = True
                if "enabled" not in existing:
                    existing["enabled"] = True
                    changed = True
                if "tags" not in existing:
                    existing["tags"] = ["local", "piper"]
                    changed = True
                continue

            if voice_id == "vi_VN-vais1000-medium":
                name = "Vais1000 Medium (Local)"
            else:
                name = f"{titleize(voice_id)} (Local)"
            voices.append(
                {
                    "id": voice_id,
                    "name": name,
                    "provider": "piper",
                    "provider_voice": pv,
                    "language": lang,
                    "gender": "",
                    "tier": "free",
                    "preview_video_url": "",
                    "preview_video_path": "",
                    "preview_audio_url": "",
                    "preview_audio_path": "",
                    "enabled": True,
                    "tags": ["local", "piper"],
                }
            )
            changed = True

        # Remove Piper entries whose models were deleted.
        new_voices = []
        for entry in voices:
            if not isinstance(entry, dict):
                continue
            provider = str(entry.get("provider", "")).strip().lower()
            if provider == "piper":
                entry_id = str(entry.get("id", "")).strip()
                if not entry_id or entry_id not in model_ids:
                    changed = True
                    continue
            new_voices.append(entry)
        voices = new_voices

        if not changed:
            return

        payload["voices"] = voices
        try:
            with open(catalog_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except Exception as exc:
            try:
                self.log(f"[Voice Catalog] Auto-sync Piper failed: {exc}")
            except Exception:
                pass

    def refresh_voice_catalog_combos(self):
        self.voice_catalog_entries = []
        target_language = self.get_target_language_code()
        for entry in (self.voice_catalog_entries_all or []):
            if not entry or not isinstance(entry, dict):
                continue
            if not entry.get("enabled", True):
                continue
            provider = str(entry.get("provider", "")).strip().lower()
            if provider not in {"piper", "edge"}:
                continue
            entry_language = str(entry.get("language", "")).strip().lower().split("-", 1)[0]
            if entry_language and entry_language != target_language:
                continue
            self.voice_catalog_entries.append(entry)
        self.voice_catalog_entries.sort(key=self._voice_entry_sort_key)
        self.voice_catalog_map = {entry.get("id", ""): entry for entry in self.voice_catalog_entries if entry.get("id")}
        if not hasattr(self, "free_voice_combo"):
            return

        selected_gender = self._selected_voice_gender()
        previous_free = str(self.free_voice_combo.currentData() or "")

        self.free_voice_combo.clear()
        for entry in self.voice_catalog_entries:
            entry_gender = str(entry.get("gender", "")).strip().lower()
            if selected_gender in ("male", "female") and entry_gender not in (selected_gender, "any", ""):
                continue
            self.free_voice_combo.addItem(
                str(entry.get("name", entry.get("id", "Voice"))),
                self._voice_catalog_data_value(entry),
            )
            index = self.free_voice_combo.count() - 1
            self.free_voice_combo.setItemData(index, entry.get("id", ""), self.VOICE_ENTRY_ID_ROLE)

        if self.free_voice_combo.count() > 0:
            self.free_voice_combo.setCurrentIndex(0)
        if previous_free:
            self.set_voice_combo_value(self.free_voice_combo, previous_free)
        elif target_language == "vi" and "ngochuyen" in self.voice_catalog_map:
            self.set_voice_combo_value(self.free_voice_combo, "ngochuyen")
        elif target_language == "vi" and "vi_VN-vais1000-medium" in self.voice_catalog_map:
            self.set_voice_combo_value(self.free_voice_combo, "vi_VN-vais1000-medium")
        if not self._voice_signals_bound:
            self._voice_signals_bound = True
        self.on_voice_tier_changed()
        self._update_voice_preview_meta()
        self.refresh_detected_speakers_section()

    def on_voice_gender_changed(self):
        self.refresh_voice_catalog_combos()

    def on_target_language_changed(self, _index: int = -1):
        """Show and select only local voices that match the output language."""
        self._voiceover_force_refresh = True
        if getattr(self, "voice_catalog_entries_all", None):
            self.refresh_voice_catalog_combos()

    def on_translation_engine_changed(self, _index: int = -1):
        """Update Translation Engine UI fields based on selected provider."""
        import os
        engine_combo = getattr(self, "translation_engine_combo", None)
        if engine_combo is None:
            return
        provider = engine_combo.currentData() or "google"
        config_panel = getattr(self, "translation_config_panel", None)
        key_edit = getattr(self, "translation_api_key_edit", None)
        model_edit = getattr(self, "translation_model_edit", None)
        url_edit = getattr(self, "translation_base_url_edit", None)
        link_label = getattr(self, "translation_link_label", None)
        key_label = getattr(self, "translation_key_label", None)
        model_label = getattr(self, "translation_model_label", None)
        url_label = getattr(self, "translation_base_url_label", None)
        test_btn = getattr(self, "translation_test_btn", None)
        status_lbl = getattr(self, "translation_test_status", None)
        local_panel = getattr(self, "translation_local_panel", None)

        show_config = provider != "google"
        if config_panel:
            config_panel.setVisible(show_config)
        if status_lbl:
            status_lbl.setText("")

        PRESETS = {
            "google_ai_studio": {
                "key_env": "GOOGLE_AI_STUDIO_API_KEY", "model_env": "GOOGLE_AI_STUDIO_MODEL",
                "url_env": "GOOGLE_AI_STUDIO_BASE_URL",
                "default_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "default_model": "gemini-2.5-flash",
                "link": "Get a free API Key at: <a href='https://aistudio.google.com/apikey'>Google AI Studio</a>",
            },
            "local_hymt": {
                "key_env": "", "model_env": "", "url_env": "",
                "default_url": "Managed automatically by CapCap",
                "default_model": "HY-MT 1.8B Q4_K_M",
                "link": "",
            },
        }
        if provider not in PRESETS:
            return
        p = PRESETS[provider]
        is_local = provider == "local_hymt"
        if local_panel:
            local_panel.setVisible(is_local)
        if key_edit:
            key_visible = bool(p["key_env"])
            if key_label:
                key_label.setVisible(key_visible)
            key_edit.setVisible(key_visible)
            if key_visible:
                key_edit.setText(os.getenv(p["key_env"], ""))
            else:
                key_edit.clear()
        if model_edit:
            model_edit.setText(os.getenv(p["model_env"], "") or p["default_model"])
            model_edit.setReadOnly(is_local)
            model_edit.setVisible(not is_local)
        if url_edit:
            url_edit.setText(os.getenv(p["url_env"], "") or p["default_url"])
            url_edit.setReadOnly(is_local)
            url_edit.setVisible(not is_local)
        if model_label:
            model_label.setVisible(not is_local)
        if url_label:
            url_label.setVisible(not is_local)
        if link_label:
            link_label.setText(p["link"])
        if is_local:
            self.refresh_local_translation_controls()

        # Save provider selection to env
        self._save_translation_engine_env(provider, "", "", "")

    def refresh_local_translation_controls(self):
        combo = getattr(self, "translation_local_model_combo", None)
        if combo is None:
            return
        from services.local_translation_config import HYMT_MODELS, load_local_translation_config, selected_model_info

        config = load_local_translation_config()
        combo.blockSignals(True)
        combo.clear()
        for model_id, entry in HYMT_MODELS.items():
            combo.addItem(entry["label"], model_id)
        combo.addItem("Custom GGUF file / other model", "custom")
        index = combo.findData(config["model_id"])
        combo.setCurrentIndex(max(0, index))
        combo.blockSignals(False)

        storage_edit = getattr(self, "translation_local_storage_edit", None)
        if storage_edit:
            storage_edit.setText(config["storage_dir"])
        info = selected_model_info()
        model_path = str(info.get("path") or "")
        ready = bool(model_path and os.path.isfile(model_path))
        size = os.path.getsize(model_path) if ready else int(info.get("size") or 0)
        size_text = f"{size / (1024 ** 3):.2f} GB" if size else "unknown size"
        hint = getattr(self, "translation_local_model_hint", None)
        if hint:
            hint.setText(str(info.get("description") or "Select a GGUF model suitable for translation."))
        path_label = getattr(self, "translation_local_path_label", None)
        if path_label:
            state = "✓ Ready" if ready else "⚠ No model file — scan your machine or download one below"
            path_label.setText(f"{state} | {size_text}\n{model_path or 'No file selected'}")
        # Update manage button label based on whether model file exists
        manage_btn = getattr(self, "translation_local_manage_btn", None)
        if manage_btn:
            if ready:
                manage_btn.setText("✓ Installed — Manage Models")
                manage_btn.setToolTip(
                    f"Model is ready at:\n{model_path}\n\n"
                    "Click to open Manage Resources if you want to download additional models."
                )
            else:
                manage_btn.setText("📥 Download Model")
                manage_btn.setToolTip(
                    "Download the HY-MT model to your storage folder.\n"
                    "Once downloaded, the model will be detected automatically."
                )

    def on_local_translation_model_changed(self, _index: int = -1):
        combo = getattr(self, "translation_local_model_combo", None)
        if combo is None:
            return
        from services.local_translation_config import load_local_translation_config, save_local_translation_config
        from services.local_translation_runtime import stop_local_translation_runtime

        config = load_local_translation_config()
        model_id = str(combo.currentData() or "q4_k_m")
        save_local_translation_config(
            model_id=model_id,
            storage_dir=config["storage_dir"],
            custom_model_path=config["custom_model_path"],
        )
        stop_local_translation_runtime()
        self.refresh_local_translation_controls()

    def choose_local_translation_storage(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from services.local_translation_config import load_local_translation_config, save_local_translation_config

        config = load_local_translation_config()
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Select folder to store Local AI models",
            config["storage_dir"],
        )
        if not selected_dir:
            return
        save_local_translation_config(
            model_id=config["model_id"],
            storage_dir=selected_dir,
            custom_model_path=config["custom_model_path"],
        )
        self.refresh_local_translation_controls()
        QMessageBox.information(
            self,
            "Storage folder changed",
            "New model downloads will be saved to this folder. CapCap will not move or delete existing models.",
        )

    def choose_local_translation_model_file(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from services.local_translation_config import is_valid_gguf, load_local_translation_config, save_local_translation_config
        from services.local_translation_runtime import stop_local_translation_runtime

        config = load_local_translation_config()
        file_path, _filter = QFileDialog.getOpenFileName(
            self,
            "Select GGUF model for translation",
            config["storage_dir"],
            "GGUF models (*.gguf);;All files (*)",
        )
        if not file_path:
            return
        if not is_valid_gguf(file_path):
            QMessageBox.warning(self, "Invalid model", "The selected file is not a valid GGUF model.")
            return
        save_local_translation_config(
            model_id="custom",
            storage_dir=config["storage_dir"],
            custom_model_path=file_path,
        )
        stop_local_translation_runtime()
        self.refresh_local_translation_controls()

    def scan_local_translation_models(self):
        from PySide6.QtWidgets import QProgressDialog, QMessageBox
        from services.local_translation_config import load_local_translation_config
        import string, platform

        config = load_local_translation_config()

        if platform.system() == "Windows":
            available_drives = [
                f"{letter}:\\"
                for letter in string.ascii_uppercase
                if os.path.exists(f"{letter}:\\")
            ]
        else:
            available_drives = ["/"]

        progress = QProgressDialog(
            f"Scanning {len(available_drives)} drive(s)...", "Cancel", 0, 0, self
        )
        progress.setWindowTitle("🔍 Scanning for GGUF models")
        progress.setMinimumWidth(480)
        progress.setMinimumDuration(0)
        progress.show()

        worker = GgufScanWorker(available_drives, self)

        def _on_progress(msg: str):
            progress.setLabelText(msg)

        def _on_canceled():
            worker.cancel()

        def _on_finished(found: list):
            progress.close()
            if not found and not worker._is_cancelled:
                drives_text = ", ".join(available_drives)
                QMessageBox.information(
                    self,
                    "Scan complete — nothing found",
                    f"Scanned {len(available_drives)} drive(s) ({drives_text}).\n"
                    "No GGUF files found on this machine.\n\n"
                    "Click '📥 Download Model' to get the HY-MT model.",
                )
                return
            if found:
                self._show_scanned_models_dialog(found, config)

        worker.progress_updated.connect(_on_progress)
        worker.scan_finished.connect(_on_finished)
        progress.canceled.connect(_on_canceled)

        self._scan_worker = worker
        worker.start()

    def _show_scanned_models_dialog(self, found: list[tuple[str, int]], config: dict):
        from PySide6.QtWidgets import (
            QDialog, QDialogButtonBox, QHeaderView, QLabel,
            QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
        )
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QFont
        from services.local_translation_config import save_local_translation_config
        from services.local_translation_runtime import stop_local_translation_runtime

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Select translation model — {len(found)} file(s) found")
        dlg.resize(820, 420)
        dlg.setModal(True)
        dlg.setStyleSheet("""
            QDialog { background-color: #0c0e14; color: #e2e8f0; }
            QLabel  { color: #cbd5e1; font-size: 12px; }
            QTableWidget {
                background-color: #111520; color: #e2e8f0;
                gridline-color: #1e2433; border: 1px solid #1e2433;
                border-radius: 6px; font-size: 12px;
            }
            QTableWidget::item:selected {
                background-color: #1e3a5f; color: #ffffff;
            }
            QHeaderView::section {
                background-color: #141824; color: #94a3b8;
                border: none; border-bottom: 1px solid #1e2433;
                padding: 6px 8px; font-weight: 600; font-size: 11px;
            }
            QDialogButtonBox QPushButton {
                background-color: #10b981; color: #fff;
                border: none; border-radius: 6px;
                padding: 8px 24px; font-weight: 700; font-size: 12px;
            }
            QDialogButtonBox QPushButton:hover  { background-color: #059669; }
            QDialogButtonBox QPushButton:disabled { background-color: #1e2433; color: #475569; }
            QDialogButtonBox QPushButton[text="Cancel"] {
                background-color: #1c2230; color: #94a3b8; border: 1px solid #2b354a;
            }
            QDialogButtonBox QPushButton[text="Cancel"]:hover { background-color: #262e42; color: #fff; }
        """)

        vbox = QVBoxLayout(dlg)
        vbox.setSpacing(10)
        vbox.setContentsMargins(16, 16, 16, 16)

        hint = QLabel(
            f"Found <b>{len(found)}</b> GGUF file(s) on your machine.<br>"
            "Select a model to use for translation and click <b>Use this model</b>."
        )
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.RichText)
        hint.setStyleSheet("color: #94a3b8; font-size: 12px;")
        vbox.addWidget(hint)

        table = QTableWidget(len(found), 4)
        table.setHorizontalHeaderLabels(["File name", "Size", "Path", "Status"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setStyleSheet("QTableWidget { alternate-background-color: #131825; }")

        for row, (path, size) in enumerate(found):
            name = os.path.basename(path)
            size_gb = size / (1024 ** 3)
            size_text = f"{size_gb:.2f} GB" if size_gb >= 1.0 else f"{size / (1024 ** 2):.0f} MB"

            name_item = QTableWidgetItem(name)
            name_item.setFont(QFont("Segoe UI", 11, QFont.Bold))
            table.setItem(row, 0, name_item)

            size_item = QTableWidgetItem(size_text)
            size_item.setTextAlignment(Qt.AlignCenter)
            if size_gb >= 3.0:
                size_item.setForeground(QColor("#f87171"))
            elif size_gb >= 1.0:
                size_item.setForeground(QColor("#fbbf24"))
            else:
                size_item.setForeground(QColor("#6ee7b7"))
            table.setItem(row, 1, size_item)

            path_item = QTableWidgetItem(path)
            path_item.setForeground(QColor("#64748b"))
            table.setItem(row, 2, path_item)

            status_item = QTableWidgetItem("✓ Valid")
            status_item.setForeground(QColor("#6ee7b7"))
            status_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 3, status_item)

        table.resizeRowsToContents()
        if len(found) > 0:
            table.selectRow(0)
        vbox.addWidget(table)

        tip = QLabel(
            "💡 Tip: Any GGUF file is accepted — not just HY-MT models. "
            "For best translation quality, choose a model trained on Vietnamese/Chinese/English."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #475569; font-size: 11px; padding: 4px 0;")
        vbox.addWidget(tip)

        btn_box = QDialogButtonBox()
        ok_btn = btn_box.addButton("Use this model", QDialogButtonBox.AcceptRole)
        cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        ok_btn.setEnabled(len(found) > 0)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        vbox.addWidget(btn_box)

        if dlg.exec() != QDialog.Accepted:
            return

        selected_rows = table.selectedItems()
        if not selected_rows:
            return
        selected_row = table.currentRow()
        selected_path = found[selected_row][0]

        save_local_translation_config(
            model_id="custom",
            storage_dir=config["storage_dir"],
            custom_model_path=selected_path,
        )
        stop_local_translation_runtime()
        self.refresh_local_translation_controls()
        QMessageBox.information(
            self,
            "Model selected",
            f"Model set to:\n{os.path.basename(selected_path)}\n\n"
            f"Path: {selected_path}\n\n"
            "CapCap will use this model for all future translation jobs.",
        )

    def _save_translation_engine_env(self, provider: str, api_key: str, model: str, base_url: str):
        """Persist the selected provider to .env (provider only, not credentials yet — saved on Save)."""
        import re
        env_path = ".env"
        env_lines = []
        try:
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    env_lines = f.readlines()
        except Exception:
            pass
        updates = {"OPENAI_PROVIDER": provider, "AI_POLISHER_PROVIDER": provider}
        new_lines = []
        handled = set()
        for line in env_lines:
            m = re.match(r"^([^=\s]+)=", line)
            if m and m.group(1) in updates:
                new_lines.append(f"{m.group(1)}={updates[m.group(1)]}\n")
                handled.add(m.group(1))
            else:
                new_lines.append(line)
        for k, v in updates.items():
            if k not in handled:
                new_lines.append(f"{k}={v}\n")
        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            os.environ[list(updates.keys())[0]] = provider
            os.environ[list(updates.keys())[1]] = provider
        except Exception:
            pass

    def on_translation_engine_test_connection(self):
        """Test the AI translation connection from the sidebar."""
        status_lbl = getattr(self, "translation_test_status", None)
        engine_combo = getattr(self, "translation_engine_combo", None)
        key_edit = getattr(self, "translation_api_key_edit", None)
        model_edit = getattr(self, "translation_model_edit", None)
        url_edit = getattr(self, "translation_base_url_edit", None)
        if not engine_combo:
            return
        provider = engine_combo.currentData() or "google"
        if provider == "google":
            if status_lbl:
                status_lbl.setText("Google Translate does not require connection — Ready ✓")
            return
        if provider == "local_hymt":
            if status_lbl:
                status_lbl.setText("Starting Local AI...")
                status_lbl.repaint()
            try:
                from services.local_translation_runtime import get_local_translation_runtime
                get_local_translation_runtime().ensure_ready()
                if status_lbl:
                    status_lbl.setText("Local AI is ready ✓")
            except FileNotFoundError:
                if status_lbl:
                    status_lbl.setText("Local AI model package not installed — open Manage Resources to download.")
            except Exception as exc:
                if status_lbl:
                    status_lbl.setText(f"Failed to start Local AI: {exc}")
            return
        url = (url_edit.text().strip() if url_edit else "") or "https://api.openai.com/v1/"
        key = key_edit.text().strip() if key_edit else ""
        model = (model_edit.text().strip() if model_edit else "") or "gpt-4o-mini"
        if status_lbl:
            status_lbl.setText("Testing connection...")
            status_lbl.repaint()
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key, base_url=url, timeout=15.0)
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with OK."}],
                max_tokens=8,
            )
            if status_lbl:
                status_lbl.setText(f"Connection successful: {model} ✓")
            # Save credentials on success
            import re
            env_path = ".env"
            env_lines = []
            try:
                if os.path.exists(env_path):
                    with open(env_path, "r", encoding="utf-8") as f:
                        env_lines = f.readlines()
            except Exception:
                pass
            PRESETS = {
                "google_ai_studio": ("GOOGLE_AI_STUDIO_API_KEY", "GOOGLE_AI_STUDIO_MODEL", "GOOGLE_AI_STUDIO_BASE_URL"),
            }
            k_env, m_env, u_env = PRESETS.get(provider, ("", "", ""))
            updates = {"OPENAI_PROVIDER": provider, "AI_POLISHER_PROVIDER": provider}
            if k_env and key:
                updates[k_env] = key
            if m_env and model:
                updates[m_env] = model
            if u_env and url:
                updates[u_env] = url
            new_lines = []
            handled = set()
            for line in env_lines:
                m2 = re.match(r"^([^=\s]+)=", line)
                if m2 and m2.group(1) in updates:
                    new_lines.append(f"{m2.group(1)}={updates[m2.group(1)]}\n")
                    handled.add(m2.group(1))
                else:
                    new_lines.append(line)
            for k, v in updates.items():
                if k not in handled:
                    new_lines.append(f"{k}={v}\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            for k, v in updates.items():
                os.environ[k] = v
            self.log(f"[Translation] Provider saved: {provider} ({model})")
        except Exception as exc:
            if status_lbl:
                status_lbl.setText(f"Connection failed: {exc}")


    def on_selected_voice_changed(self):
        self._update_voice_preview_meta()
        self._preload_active_voice_if_needed()
