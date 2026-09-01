from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from core.models import Segment, coerce_segments
from core.state import ProjectState


class ProjectService:
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.projects_root = os.path.join(workspace_root, "projects")

    def ensure_project(
        self,
        video_path: str,
        *,
        mode: str = "subtitle",
        translator_ai: bool = True,
        translator_style: str = "",
        input_language: str = "auto",
        target_language: str = "vi",
    ) -> ProjectState:
        os.makedirs(self.projects_root, exist_ok=True)
        project_id = self._build_project_id(video_path)
        project_root = os.path.join(self.projects_root, project_id)
        self._ensure_project_dirs(project_root)

        state_path = self.project_file(project_root)
        current_identity = self._input_video_identity(video_path)
        if os.path.exists(state_path):
            state = self.load_project(state_path)
            if not state.display_name:
                state.display_name = os.path.basename(video_path) or state.project_id
            previous_identity = dict(state.settings.get("input_video_identity") or {})
            state.input_video = os.path.abspath(video_path)
            if previous_identity and previous_identity != current_identity:
                state.set_setting("input_video_content_changed", {
                    "previous": previous_identity,
                    "current": current_identity,
                })
            state.set_setting("input_video_identity", current_identity)
            self.save_project(state)
            return state

        existing_state = self._find_existing_project_by_identity(current_identity)
        if existing_state is not None:
            previous_identity = dict(existing_state.settings.get("input_video_identity") or {})
            existing_state.input_video = os.path.abspath(video_path)
            if previous_identity and previous_identity != current_identity:
                existing_state.set_setting("input_video_content_changed", {
                    "previous": previous_identity,
                    "current": current_identity,
                })
            existing_state.set_setting("input_video_identity", current_identity)
            self.save_project(existing_state)
            return existing_state

        state = ProjectState(
            project_id=project_id,
            project_root=project_root,
            input_video=os.path.abspath(video_path),
            display_name=os.path.basename(video_path) or project_id,
            input_language=input_language,
            target_language=target_language,
            mode=mode,
            translator_ai=translator_ai,
            translator_style=translator_style,
        )
        state.set_setting("input_video_identity", current_identity)
        self.save_project(state)
        return state

    def create_project(self) -> ProjectState:
        """Create a video-independent project with the next VIUSTUDIO name."""
        os.makedirs(self.projects_root, exist_ok=True)
        next_number = self._next_viustudio_number()
        while True:
            display_name = f"VIUSTUDIO{next_number}"
            # A deterministic folder is also an atomic number reservation:
            # if two app instances create at once, only one mkdir succeeds
            # and the other advances to the next number.
            project_id = display_name.lower()
            project_root = os.path.join(self.projects_root, project_id)
            try:
                os.mkdir(project_root)
                break
            except FileExistsError:
                next_number += 1
        self._ensure_project_dirs(project_root)
        state = ProjectState(
            project_id=project_id,
            project_root=project_root,
            input_video="",
            display_name=display_name,
        )
        self.save_project(state)
        return state

    def rename_project(self, state: ProjectState, display_name: str) -> ProjectState:
        name = " ".join(str(display_name or "").strip().split())
        if not name:
            raise ValueError("Project name cannot be empty.")
        if len(name) > 120:
            raise ValueError("Project name must be 120 characters or fewer.")
        if any(char in name for char in '<>:"/\\|?*'):
            raise ValueError("Project name contains invalid characters.")
        state.display_name = name
        self.save_project(state)
        return state

    def _next_viustudio_number(self) -> int:
        highest = 9999
        try:
            entries = list(os.scandir(self.projects_root))
        except OSError:
            entries = []
        pattern = re.compile(r"^VIUSTUDIO(\d+)$", re.IGNORECASE)
        for entry in entries:
            if not entry.is_dir():
                continue
            candidates = [entry.name.split("_", 1)[0]]
            try:
                state = self.load_project(self.project_file(entry.path))
                candidates.append(state.display_name)
            except (OSError, ValueError, TypeError, KeyError):
                pass
            for candidate in candidates:
                match = pattern.match(str(candidate or "").strip())
                if match:
                    highest = max(highest, int(match.group(1)))
        return highest + 1

    def _find_existing_project_by_identity(self, identity: dict[str, Any]) -> ProjectState | None:
        if not identity.get("path"):
            return None
        try:
            entries = list(os.scandir(self.projects_root))
        except OSError:
            return None
        for entry in entries:
            if not entry.is_dir():
                continue
            state_path = os.path.join(entry.path, "project.json")
            if not os.path.isfile(state_path):
                continue
            try:
                state = self.load_project(state_path)
                saved_identity = dict(state.settings.get("input_video_identity") or {})
                if saved_identity.get("path") and saved_identity.get("path") == identity.get("path") and saved_identity.get("sample_sha1") == identity.get("sample_sha1"):
                    return state
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                pass
        return None

    @staticmethod
    def _input_video_identity(video_path: str) -> dict[str, Any]:
        """Cheap content identity that detects a different file at one path."""
        path = os.path.abspath(str(video_path or ""))
        try:
            stat = os.stat(path)
            sample_size = 1024 * 1024
            digest = hashlib.sha1()
            with open(path, "rb") as handle:
                digest.update(handle.read(sample_size))
                if stat.st_size > sample_size:
                    handle.seek(max(0, stat.st_size - sample_size))
                    digest.update(handle.read(sample_size))
            return {
                "path": os.path.normcase(path),
                "size": int(stat.st_size),
                "sample_sha1": digest.hexdigest(),
            }
        except OSError:
            return {"path": os.path.normcase(path), "size": -1, "sample_sha1": ""}

    def load_project(self, state_path: str) -> ProjectState:
        with open(state_path, "r", encoding="utf-8") as handle:
            state = ProjectState.from_dict(json.load(handle))
        if not state.display_name:
            state.display_name = os.path.basename(state.input_video) or state.project_id or "Untitled Project"
        return state

    def save_project(self, state: ProjectState) -> str:
        self._ensure_project_dirs(state.project_root)
        state.touch()
        state_path = self.project_file(state.project_root)
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state.to_dict(), handle, ensure_ascii=False, indent=2)
        return state_path

    def save_json_artifact(
        self,
        state: ProjectState,
        artifact_name: str,
        relative_path: str,
        payload: Any,
    ) -> str:
        output_path = os.path.join(state.project_root, relative_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        state.set_artifact(artifact_name, output_path)
        self.save_project(state)
        return output_path

    def save_segment_artifact(
        self,
        state: ProjectState,
        artifact_name: str,
        relative_path: str,
        segments: list[Segment],
    ) -> str:
        return self.save_json_artifact(
            state,
            artifact_name,
            relative_path,
            [segment.to_dict() for segment in coerce_segments(segments)],
        )

    def load_json_artifact(self, state: ProjectState, artifact_name: str, default=None):
        path = state.artifacts.get(artifact_name, "")
        if not path or not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def load_segment_artifact(self, state: ProjectState, artifact_name: str) -> list[Segment]:
        payload = self.load_json_artifact(state, artifact_name, default=[])
        return coerce_segments(payload or [])

    def update_step(self, state: ProjectState, step_name: str, status: str, *, save: bool = True) -> ProjectState:
        state.set_step_status(step_name, status)
        if save:
            self.save_project(state)
        return state

    def update_artifact(self, state: ProjectState, artifact_name: str, path: str, *, save: bool = True) -> ProjectState:
        state.set_artifact(artifact_name, path)
        if save:
            self.save_project(state)
        return state

    def project_file(self, project_root: str) -> str:
        return os.path.join(project_root, "project.json")

    def build_path(self, state: ProjectState, *parts: str) -> str:
        return os.path.join(state.project_root, *parts)

    def _ensure_project_dirs(self, project_root: str) -> None:
        for relative_dir in (
            "source",
            "analysis",
            "translation",
            os.path.join("audio", "separated"),
            os.path.join("audio", "tts_segments"),
            "subtitle",
            os.path.join("preview", "cache"),
            "export",
            "logs",
        ):
            os.makedirs(os.path.join(project_root, relative_dir), exist_ok=True)

    def _build_project_id(self, video_path: str) -> str:
        video_name = os.path.splitext(os.path.basename(video_path))[0] or "project"
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", video_name).strip("_").lower() or "project"
        digest = hashlib.sha1(os.path.abspath(video_path).encode("utf-8")).hexdigest()[:8]
        return f"{slug}_{digest}"

    def _hash_payload(self, payload: Any) -> str:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(serialized.encode("utf-8")).hexdigest()

    def _file_signature(self, path: str) -> dict[str, Any]:
        normalized = str(path or "").strip()
        if not normalized:
            return {"path": "", "exists": False}
        try:
            stat = os.stat(normalized)
            return {
                "path": os.path.abspath(normalized),
                "exists": True,
                "size": int(stat.st_size),
                "mtime_ns": int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
            }
        except OSError:
            return {"path": os.path.abspath(normalized), "exists": False}

    def build_translation_signature(
        self,
        source_segments,
        *,
        src_lang: str = "auto",
        target_lang: str = "vi",
        enable_polish: bool = True,
        optimize_subtitles: bool = False,
        style_instruction: str = "",
    ) -> str:
        provider = str(os.getenv("OPENAI_PROVIDER") or os.getenv("AI_POLISHER_PROVIDER") or "google").strip().lower()
        model_env_names = {
            "google_ai_studio": "GOOGLE_AI_STUDIO_MODEL",
            "deepseek": "DEEPSEEK_MODEL",
            "openai": "OPENAI_MODEL",
            "ollama": "OLLAMA_MODEL",
            "custom": "CUSTOM_AI_MODEL",
        }
        provider_model: Any
        if provider == "llama_app":
            provider_model = self._file_signature(os.getenv("LLAMA_APP_MODEL", ""))
        else:
            provider_model = str(os.getenv(model_env_names.get(provider, ""), "") or "").strip()
        payload = {
            # Translation behavior includes the contextual-reasoning prompt.
            # Bump this when prompt semantics change so projects do not reuse
            # older, literal translations from the cache.
            "translation_prompt_version": 6,
            "translation_provider": provider,
            "translation_provider_model": provider_model,
            "src_lang": str(src_lang or "auto").strip().lower(),
            "target_lang": str(target_lang or "vi").strip().lower(),
            "enable_polish": bool(enable_polish),
            "optimize_subtitles": bool(optimize_subtitles),
            "style_instruction": str(style_instruction or "").strip(),
            "segments": [
                {
                    "start": round(float((seg or {}).get("start", 0.0) or 0.0), 3),
                    "end": round(float((seg or {}).get("end", 0.0) or 0.0), 3),
                    "text": str((seg or {}).get("source_text") or (seg or {}).get("text") or "").strip(),
                }
                for seg in list(source_segments or [])
            ],
        }
        return self._hash_payload(payload)

    def build_voice_signature(
        self,
        segments,
        *,
        audio_handling_mode: str = "fast",
        voice_name: str = "",
        voice_speed: float = 1.0,
        timing_sync_mode: str = "off",
        background_path: str = "",
        original_volume: int = 50,
        dub_volume: int = 100,
    ) -> str:
        safe_voice_speed = max(0.5, min(1.30, float(voice_speed or 1.0)))
        def _segment_voice_text(seg) -> str:
            current = dict(seg or {})
            subtitle_text = str(current.get("text") or "").strip()
            if bool(current.get("voice_edited")):
                edited_text = str(current.get("tts_text") or current.get("dubbing_vi") or "").strip()
                if edited_text:
                    return edited_text
            return subtitle_text
        payload = {
            # Bump whenever timing-fit semantics change so projects do not
            # silently reuse a voice track produced by an older algorithm.
            "voice_timing_revision": 4,
            "audio_handling_mode": str(audio_handling_mode or "fast").strip().lower(),
            "voice_name": str(voice_name or "").strip(),
            "voice_speed": round(safe_voice_speed, 3),
            "timing_sync_mode": str(timing_sync_mode or "off").strip().lower(),
            "background": self._file_signature(background_path),
            "original_volume": int(original_volume or 50),
            "dub_volume": int(dub_volume or 100),
            "segments": [
                {
                    "start": round(float((seg or {}).get("start", 0.0) or 0.0), 3),
                    "end": round(float((seg or {}).get("end", 0.0) or 0.0), 3),
                    "text": _segment_voice_text(seg),
                    "group_id": str((seg or {}).get("tts_group_id") or "").strip(),
                    # Per-speaker selections are resolved onto the segment by
                    # the editor.  They must participate in this signature so
                    # an assignment change cannot reuse an old voice track.
                    "voice_name": str((seg or {}).get("voice_name") or "").strip(),
                }
                for seg in list(segments or [])
            ],
        }
        return self._hash_payload(payload)

    def build_extraction_signature(self, video_path: str) -> str:
        return self._hash_payload(
            {
                "video": self._file_signature(video_path),
            }
        )

    def build_ocr_transcription_signature(self, video_path: str, *, region: str = "bottom") -> str:
        """Fingerprint all inputs that affect video-subtitle OCR output."""
        return self._hash_payload(
            {
                # OCR text filtering and temporal merging are part of the
                # transcription result, not just a display concern.
                "version": 5,
                "video": self._file_signature(video_path),
                "region": str(region or "bottom").strip().lower(),
                "subtitle_rect": str(os.getenv("OCR_SUBTITLE_RECT") or "").strip(),
                "crop_ratio": str(os.getenv("OCR_CROP_RATIO") or "0.30").strip(),
                "sampling_fps": str(os.getenv("OCR_SAMPLING_FPS") or "auto").strip().lower(),
            }
        )

    def build_separation_signature(self, extracted_audio_path: str, *, audio_handling_mode: str = "fast") -> str:
        return self._hash_payload(
            {
                "version": 2,
                "audio_handling_mode": str(audio_handling_mode or "fast").strip().lower(),
                "extracted_audio": self._file_signature(extracted_audio_path),
            }
        )

    def build_transcription_signature(
        self,
        audio_path: str,
        *,
        whisper_model: str,
        source_language: str = "auto",
        audio_handling_mode: str = "fast",
    ) -> str:
        return self._hash_payload(
            {
                "audio": self._file_signature(audio_path),
                "whisper_model": str(whisper_model or "").strip(),
                "source_language": str(source_language or "auto").strip().lower(),
                "audio_handling_mode": str(audio_handling_mode or "fast").strip().lower(),
            }
        )
