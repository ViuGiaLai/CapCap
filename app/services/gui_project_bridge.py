from __future__ import annotations

import os
import re

from services.segment_service import SegmentService


class GUIProjectBridge:
    def __init__(self, project_service):
        self.project_service = project_service
        self.segment_service = SegmentService()

    def ensure_project(
        self,
        *,
        video_path: str,
        mode: str,
        translator_ai: bool,
        input_language: str,
        target_language: str = "vi",
    ):
        if not video_path or not os.path.exists(video_path):
            return None
        return self.project_service.ensure_project(
            video_path,
            mode=mode,
            translator_ai=translator_ai,
            input_language=input_language,
            target_language=target_language,
        )

    def update_step(self, state, step_name: str, status: str):
        if not state:
            return None
        return self.project_service.update_step(state, step_name, status)

    def update_artifact(self, state, artifact_name: str, path: str):
        if not state or not path:
            return None
        return self.project_service.update_artifact(state, artifact_name, path)

    def dict_segments_to_models(self, segments, *, translated: bool = False):
        return self.segment_service.segment_dicts_to_models(segments, translated=translated)

    def persist_transcription(self, state, raw_segments, srt_path: str = ""):
        if not state:
            return []
        segment_models = self.segment_service.transcript_dicts_to_models(raw_segments)
        self.project_service.save_json_artifact(
            state,
            "transcript_raw",
            os.path.join("analysis", "transcript_raw.json"),
            raw_segments,
        )
        self.project_service.save_segment_artifact(
            state,
            "transcript_segments",
            os.path.join("analysis", "transcript_segments.json"),
            segment_models,
        )
        if srt_path:
            self.update_artifact(state, "subtitle_original_srt", srt_path)
        self.update_step(state, "transcribe", "done")
        return segment_models

    def persist_translation(self, state, base_models, translated_segments, srt_path: str = ""):
        if not state:
            return []
        models = self.segment_service.apply_translations(base_models, translated_segments)

        self.project_service.save_segment_artifact(
            state,
            "translation_final",
            os.path.join("translation", "translation_final.json"),
            models,
        )
        if any(model.refined_translation for model in models):
            self.project_service.save_segment_artifact(
                state,
                "translation_refined",
                os.path.join("translation", "translation_refined.json"),
                models,
            )
            self.update_step(state, "refine_translation", "done")
        else:
            self.project_service.save_segment_artifact(
                state,
                "translation_raw",
                os.path.join("translation", "translation_raw.json"),
                models,
            )
            self.update_step(state, "refine_translation", "skipped")
        if srt_path:
            self.update_artifact(state, "subtitle_translated_srt", srt_path)
        self.update_step(state, "translate_raw", "done")
        return models

    def load_context(self, state):
        context = {
            "artifacts": {},
            "last_original_srt_path": "",
            "last_translated_srt_path": "",
            "last_extracted_audio": "",
            "last_vocals_path": "",
            "last_music_path": "",
            "last_voice_vi_path": "",
            "last_mixed_vi_path": "",
            "current_segments": [],
            "current_translated_segments": [],
            "current_segment_models": [],
            "current_translated_segment_models": [],
            # Older projects stored the measured TTS end time by mutating the
            # visible subtitle cue.  The UI uses this flag to invalidate that
            # stale dub after restoring the original subtitle timing.
            "repaired_voice_timing": False,
        }
        if not state:
            return context

        context["artifacts"] = dict(state.artifacts)
        context["last_original_srt_path"] = state.artifacts.get("subtitle_original_srt") or state.artifacts.get("srt_original") or ""
        context["last_translated_srt_path"] = state.artifacts.get("subtitle_translated_srt") or state.artifacts.get("srt_translated") or ""
        context["last_extracted_audio"] = state.artifacts.get("extracted_audio") or state.artifacts.get("audio_extracted") or ""
        context["last_vocals_path"] = state.artifacts.get("vocals", "")
        context["last_music_path"] = state.artifacts.get("music", "")
        context["last_voice_vi_path"] = state.artifacts.get("voice_vi", "")
        context["last_mixed_vi_path"] = state.artifacts.get("mixed_vi", "")

        transcript_json = state.artifacts.get("transcript_segments")
        if transcript_json and os.path.exists(transcript_json):
            transcript_models = self.project_service.load_segment_artifact(state, "transcript_segments")
            context["current_segment_models"] = transcript_models
            context["current_segments"] = [segment.to_original_subtitle_dict() for segment in transcript_models]

        translation_json = state.artifacts.get("translation_final")
        if translation_json and os.path.exists(translation_json):
            translation_models = self.project_service.load_segment_artifact(state, "translation_final")
            repaired_voice_timing = False
            transcript_models = context["current_segment_models"]

            def _source_key(value):
                return re.sub(r"\s+", "", str(value or "")).strip().lower()

            # Restore visual timing for legacy artifacts only when there is a
            # measured audio window and the cue still maps to the same source
            # text.  This avoids overwriting deliberate user timing edits.
            for index, translation_model in enumerate(translation_models):
                if index >= len(transcript_models):
                    break
                metadata = translation_model.metadata
                if metadata.get("_audio_end") is None:
                    continue
                transcript_model = transcript_models[index]
                if _source_key(translation_model.original_text) != _source_key(transcript_model.original_text):
                    continue
                try:
                    timing_changed = (
                        abs(float(translation_model.start) - float(transcript_model.start)) > 0.03
                        or abs(float(translation_model.end) - float(transcript_model.end)) > 0.03
                    )
                except (TypeError, ValueError):
                    timing_changed = False
                if not timing_changed:
                    continue
                translation_model.start = float(transcript_model.start)
                translation_model.end = float(transcript_model.end)
                metadata.pop("_audio_start", None)
                metadata.pop("_audio_end", None)
                repaired_voice_timing = True

            # Repair projects written before flat ``speaker`` metadata was
            # retained during translation persistence.  Speaker identity is
            # visualization/TTS metadata, so match the stable cue order from
            # the transcript and save the repaired project artifact once.
            repaired_speakers = False
            for index, translation_model in enumerate(translation_models):
                if index >= len(context["current_segment_models"]):
                    break
                if translation_model.metadata.get("speaker"):
                    continue
                source_speaker = str(
                    context["current_segment_models"][index].metadata.get("speaker", "") or ""
                ).strip()
                if source_speaker:
                    translation_model.metadata["speaker"] = source_speaker
                    repaired_speakers = True
            if repaired_speakers or repaired_voice_timing:
                if repaired_voice_timing:
                    # A single repaired cue means the assembled voice track is
                    # no longer trustworthy for this project.  Remove timing
                    # hints from every cue before persisting the clean visual
                    # timeline; the UI will regenerate TTS on demand.
                    for model in translation_models:
                        model.metadata.pop("_audio_start", None)
                        model.metadata.pop("_audio_end", None)
                        model.metadata.pop("_original_start", None)
                        model.metadata.pop("_original_end", None)
                    # Keep the raw/refined snapshots coherent as well.  They
                    # are not shown by the editor today, but stale timings in
                    # either cache could be selected by a later re-translate.
                    for artifact_name in ("translation_raw", "translation_refined"):
                        artifact_path = state.artifacts.get(artifact_name, "")
                        if not artifact_path or not os.path.exists(artifact_path):
                            continue
                        auxiliary_models = self.project_service.load_segment_artifact(
                            state, artifact_name
                        )
                        if len(auxiliary_models) != len(transcript_models):
                            continue
                        for model, transcript_model in zip(auxiliary_models, transcript_models):
                            if _source_key(model.original_text) != _source_key(transcript_model.original_text):
                                continue
                            model.start = float(transcript_model.start)
                            model.end = float(transcript_model.end)
                            for key in (
                                "_audio_start", "_audio_end",
                                "_original_start", "_original_end",
                            ):
                                model.metadata.pop(key, None)
                        self.project_service.save_segment_artifact(
                            state,
                            artifact_name,
                            os.path.join("translation", f"{artifact_name}.json"),
                            auxiliary_models,
                        )
                self.project_service.save_segment_artifact(
                    state,
                    "translation_final",
                    os.path.join("translation", "translation_final.json"),
                    translation_models,
                )
            if repaired_voice_timing:
                context["repaired_voice_timing"] = True
                # Do not keep a voice track whose samples were placed against
                # the now-restored legacy visual windows.
                context["last_voice_vi_path"] = ""
                context["last_mixed_vi_path"] = ""
                for artifact_name in (
                    "voice_vi", "mixed_vi", "voice_segments",
                    "preview_video", "preview_video_5s", "preview_frame",
                ):
                    state.artifacts.pop(artifact_name, None)
                state.set_step_status("generate_tts", "pending")
                state.set_step_status("mix_audio", "pending")
                state.settings.pop("voice_signature", None)
                self.project_service.save_project(state)
            context["current_translated_segment_models"] = translation_models
            context["current_translated_segments"] = [segment.to_subtitle_dict() for segment in translation_models]

        return context
