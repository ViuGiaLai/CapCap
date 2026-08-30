"""Voice catalog, engine, and translation-provider UI feature."""

import json
import os
import re

from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from runtime_paths import app_path, models_path


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
        test_btn = getattr(self, "translation_test_btn", None)
        status_lbl = getattr(self, "translation_test_status", None)

        show_config = provider not in ("google", "llama_app")
        llama_panel = getattr(self, "llama_app_config_panel", None)
        
        if config_panel:
            config_panel.setVisible(show_config)
        if llama_panel:
            llama_panel.setVisible(provider == "llama_app")
            
        if provider == "llama_app" and llama_panel:
            self._refresh_llama_models_list()
            
        if status_lbl:
            status_lbl.setText("")

        PRESETS = {
            "google_ai_studio": {
                "key_env": "GOOGLE_AI_STUDIO_API_KEY", "model_env": "GOOGLE_AI_STUDIO_MODEL",
                "url_env": "GOOGLE_AI_STUDIO_BASE_URL",
                "default_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "default_model": "gemini-2.5-flash",
                "link": "Lấy API Key miễn phí: <a href='https://aistudio.google.com/apikey'>Google AI Studio</a>",
            },
            "deepseek": {
                "key_env": "DEEPSEEK_API_KEY", "model_env": "DEEPSEEK_MODEL",
                "url_env": "DEEPSEEK_BASE_URL",
                "default_url": "https://api.deepseek.com/v1",
                "default_model": "deepseek-chat",
                "link": "Lấy API Key: <a href='https://platform.deepseek.com/api_keys'>DeepSeek Platform</a>",
            },
            "openai": {
                "key_env": "OPENAI_API_KEY", "model_env": "OPENAI_MODEL",
                "url_env": "OPENAI_BASE_URL",
                "default_url": "https://api.openai.com/v1/",
                "default_model": "gpt-4o-mini",
                "link": "Lấy API Key: <a href='https://platform.openai.com/api-keys'>OpenAI Platform</a>",
            },
            "ollama": {
                "key_env": "", "model_env": "OLLAMA_MODEL",
                "url_env": "OLLAMA_BASE_URL",
                "default_url": "http://localhost:11434/v1",
                "default_model": "qwen2.5:7b",
                "link": "Cài Ollama: <a href='https://ollama.com/download'>ollama.com/download</a>. Model gợi ý: <b>qwen2.5:7b</b> hoặc <b>llama3.1:8b</b>",
            },
            "custom": {
                "key_env": "CUSTOM_AI_API_KEY", "model_env": "CUSTOM_AI_MODEL",
                "url_env": "CUSTOM_AI_BASE_URL",
                "default_url": "https://api.openai.com/v1/",
                "default_model": "gpt-4o-mini",
                "link": "Nhập URL của bất kỳ API tương thích OpenAI nào",
            },
        }
        if provider not in PRESETS:
            return
        p = PRESETS[provider]
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
        if url_edit:
            url_edit.setText(os.getenv(p["url_env"], "") or p["default_url"])
        if link_label:
            link_label.setText(p["link"])

        # Save provider selection to env
        self._save_translation_engine_env(provider, "", "", "")

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
                status_lbl.setText("Google Translate không cần kết nối — sẵn sàng ✓")
            return
        url = (url_edit.text().strip() if url_edit else "") or "https://api.openai.com/v1/"
        key = (key_edit.text().strip() if key_edit else "") or ("ollama" if provider == "ollama" else "")
        model = (model_edit.text().strip() if model_edit else "") or "gpt-4o-mini"
        if status_lbl:
            status_lbl.setText("Đang kiểm tra...")
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
                status_lbl.setText(f"Kết nối thành công: {model} ✓")
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
                "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL"),
                "openai": ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"),
                "ollama": ("", "OLLAMA_MODEL", "OLLAMA_BASE_URL"),
                "custom": ("CUSTOM_AI_API_KEY", "CUSTOM_AI_MODEL", "CUSTOM_AI_BASE_URL"),
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
                status_lbl.setText(f"Thất bại: {exc}")


    def on_selected_voice_changed(self):
        self._update_voice_preview_meta()
        self._preload_active_voice_if_needed()

    def _refresh_llama_models_list(self):
        import os
        from app.services.llama_local_manager import LlamaServerManager
        manager = LlamaServerManager.get_instance()
        combo = getattr(self, "llama_model_combo", None)
        if not combo:
            return
        
        current = combo.currentData()
        combo.clear()
        
        has_models = False
        if os.path.exists(manager.models_dir):
            for file in os.listdir(manager.models_dir):
                if file.lower().endswith(".gguf"):
                    combo.addItem(f"{file} (Ready)", os.path.join(manager.models_dir, file))
                    has_models = True
                    
        # Also add from env if the user previously selected one via Scan
        saved = os.getenv("LLAMA_APP_MODEL")
        if saved and os.path.exists(saved) and saved not in [combo.itemData(i) for i in range(combo.count())]:
            combo.addItem(f"{os.path.basename(saved)} (Selected)", saved)
            has_models = True
            
        if not has_models:
            combo.addItem("No model found. Please download or scan.", "")
        else:
            if current:
                idx = combo.findData(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            elif saved:
                idx = combo.findData(saved)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

        # Connect buttons if not connected
        dl_btn = getattr(self, "llama_download_btn", None)
        if dl_btn:
            dl_btn.setVisible(not has_models)
            
        if not getattr(self, "_llama_buttons_connected", False):
            scan_btn = getattr(self, "llama_scan_btn", None)
            test_btn = getattr(self, "llama_test_btn", None)
            if scan_btn:
                scan_btn.clicked.connect(self._on_llama_scan_clicked)
            if dl_btn:
                dl_btn.clicked.connect(self._on_llama_download_clicked)
            if test_btn:
                test_btn.clicked.connect(self._on_llama_test_clicked)
            
            if combo:
                combo.currentIndexChanged.connect(self._on_llama_model_selected)
                
            self._llama_buttons_connected = True

    def _on_llama_model_selected(self, index: int):
        combo = getattr(self, "llama_model_combo", None)
        if combo and index >= 0:
            data = combo.itemData(index)
            if data:
                os.environ["LLAMA_APP_MODEL"] = data

    def _on_llama_scan_clicked(self):
        from app.services.llama_local_manager import fast_scan_gguf
        import os
        lbl = getattr(self, "llama_status_label", None)
        if lbl:
            lbl.setText("Scanning entire PC. Please wait a few seconds...")
            lbl.repaint()
        
        results = fast_scan_gguf()
        
        if not results:
            if lbl:
                lbl.setText("No .gguf files found on your PC.")
            return
            
        # Create dialog to show results
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, QLabel, QWidget
        from PySide6.QtCore import Qt
        
        parent_widget = self if isinstance(self, QWidget) else None
        dlg = QDialog(parent_widget)
        dlg.setWindowTitle("Select Local Model")
        dlg.resize(600, 400)
        ly = QVBoxLayout(dlg)
        
        ly.addWidget(QLabel(f"Found {len(results)} models:"))
        lst = QListWidget()
        for r in results:
            mb = r['size'] / (1024 * 1024)
            item = QListWidgetItem(f"{r['name']} ({mb:.1f} MB)\n{r['path']}")
            item.setData(Qt.UserRole, r['path'])
            lst.addItem(item)
        ly.addWidget(lst)
        
        btn_layout = QHBoxLayout()
        use_btn = QPushButton("Use Selected Model")
        def on_use():
            if lst.currentItem():
                path = lst.currentItem().data(Qt.UserRole)
                os.environ["LLAMA_APP_MODEL"] = path
                self._refresh_llama_models_list()
                if lbl:
                    lbl.setText(f"Selected: {os.path.basename(path)}")
                dlg.accept()
        use_btn.clicked.connect(on_use)
        btn_layout.addStretch()
        btn_layout.addWidget(use_btn)
        ly.addLayout(btn_layout)
        
        dlg.exec()

    def _on_llama_download_clicked(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        # Open huggingface download link
        QDesktopServices.openUrl(QUrl("https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"))
        lbl = getattr(self, "llama_status_label", None)
        if lbl:
            lbl.setText("Browser opened for download. Once finished, click 'Scan Entire PC' to select it.")

    def _on_llama_test_clicked(self):
        import os
        from app.services.llama_local_manager import LlamaServerManager
        lbl = getattr(self, "llama_test_status", None)
        if lbl:
            lbl.setText("Starting Server & Loading Model. Please wait...")
            lbl.repaint()
            
        model_path = os.environ.get("LLAMA_APP_MODEL")
        if not model_path or not os.path.exists(model_path):
            if lbl:
                lbl.setText("Error: Model file not found!")
            return
            
        try:
            manager = LlamaServerManager.get_instance()
            manager.start_server(model_path)
            
            from openai import OpenAI
            client = OpenAI(api_key="dummy", base_url=manager.get_base_url(), timeout=120.0)
            
            if lbl:
                lbl.setText("Calling translation API...")
                lbl.repaint()
                
            resp = client.chat.completions.create(
                model=os.path.basename(model_path),
                messages=[{"role": "user", "content": "Reply exactly with OK."}],
                max_tokens=8,
            )
            
            if lbl:
                lbl.setText(f"Connection successful! Server responded: {resp.choices[0].message.content} ✓")
        except Exception as exc:
            if lbl:
                lbl.setText(f"Error: {str(exc)[:100]}")
