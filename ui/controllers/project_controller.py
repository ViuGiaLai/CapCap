import os
import shutil
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication, QMessageBox
try:
    from utils.display_utils import cleanup_temp_preview_files as cleanup_temp_preview_files_impl, show_processed_files as show_processed_files_impl
    from utils.file_dialog_utils import open_folder as open_folder_impl
except ImportError:
    from ui.utils.display_utils import cleanup_temp_preview_files as cleanup_temp_preview_files_impl, show_processed_files as show_processed_files_impl
    from ui.utils.file_dialog_utils import open_folder as open_folder_impl


class ProjectController:
    """Manages project runtime state, resetting, cleaning, and workspace file utilities."""

    def __init__(self, gui):
        self.gui = gui

    def open_folder(self, path):
        open_folder_impl(self.gui, path)

    def show_processed_files(self):
        show_processed_files_impl(self.gui)

    def cleanup_temp_preview_files(self):
        cleanup_temp_preview_files_impl(self.gui)

    def path_within_root(self, path: str, root: str) -> bool:
        try:
            normalized_path = os.path.normcase(os.path.abspath(path))
            normalized_root = os.path.normcase(os.path.abspath(root))
            return os.path.commonpath([normalized_path, normalized_root]) == normalized_root
        except Exception:
            return False

    def remove_path_if_safe(self, path: str, *, allowed_roots: list[str], removed: list[str]) -> None:
        normalized = self.gui._normalize_local_file_path(path)
        if not normalized or not os.path.exists(normalized):
            return
        if not any(self.path_within_root(normalized, root) for root in allowed_roots if root):
            return

        def _on_remove_error(func, target, exc_info):
            try:
                os.chmod(target, 0o777)
                func(target)
            except OSError:
                return

        try:
            if os.path.isdir(normalized):
                shutil.rmtree(normalized, onerror=_on_remove_error)
            else:
                os.remove(normalized)
        except OSError:
            return
        if not os.path.exists(normalized):
            removed.append(normalized)

    def reset_project_runtime_state(self) -> None:
        self.gui.current_project_state = None
        self.gui.current_segment_models = []
        self.gui.current_translated_segment_models = []
        self.gui.current_segments = []
        self.gui.current_translated_segments = []
        self.gui.processed_artifacts = {}
        self.gui.last_extracted_audio = ""
        self.gui.last_vocals_path = ""
        self.gui.last_music_path = ""
        self.gui.last_original_srt_path = ""
        self.gui.last_translated_srt_path = ""
        self.gui.last_voice_vi_path = ""
        self.gui.last_mixed_vi_path = ""
        self.gui.last_preview_video_path = ""
        self.gui.last_styled_preview_path = ""
        self.gui.last_styled_preview_signature = ""
        self.gui.last_exported_video_path = ""
        self.gui.last_exact_preview_5s_path = ""
        self.gui.last_exact_preview_frame_path = ""
        self.gui.live_preview_subtitle_path = ""
        self.gui.live_preview_ass_path = ""
        self.gui.live_preview_segments = []
        self.gui.live_preview_editor_name = ""
        self.gui._live_preview_signature = None
        self.gui._timeline_waveform_cache_key = None
        self.gui._timeline_waveform_samples = []
        self.gui._timeline_waveform_duration_s = 0.0
        self.gui._desired_timeline_waveform_request = None
        self.gui._timeline_video_thumb_cache_key = None
        self.gui._timeline_video_thumbnails = []
        self.gui._desired_timeline_thumbnail_request = None
        self.gui._allow_post_pipeline_preview_assets = False
        self.gui._pending_timeline_waveform_refresh = False
        self.gui._pending_timeline_thumbnail_refresh = False
        if hasattr(self.gui, "transcript_text"):
            self.gui.transcript_text.clear()
        if hasattr(self.gui, "translated_text"):
            self.gui.translated_text.clear()
        if hasattr(self.gui, "audio_source_edit"):
            self.gui.audio_source_edit.clear()
        if hasattr(self.gui, "bg_music_edit"):
            self.gui.bg_music_edit.clear()
        if hasattr(self.gui, "mixed_audio_edit"):
            self.gui.mixed_audio_edit.clear()
        if hasattr(self.gui, "video_path_edit"):
            self.gui.video_path_edit.clear()
        if hasattr(self.gui, "timeline"):
            # set_segments([]) only clears TS1 and leaves V1/A1/optional
            # layers from the previous video alive. A true project switch
            # needs a fresh model or the next project's subtitles/voice can
            # be displayed over the previous project's source.
            init_tracks = getattr(self.gui.timeline, "_init_default_tracks", None)
            if callable(init_tracks):
                init_tracks()
            else:
                self.gui.timeline.set_segments([])
            self.gui.timeline.set_duration(0)
            self.gui.timeline.set_waveform_data([], 0.0)
            self.gui.timeline.set_video_thumbnails([])
            self.gui.timeline.set_playing(False)
        if hasattr(self.gui, "media_player"):
            try:
                self.gui.media_player.clear_subtitle()
                self.gui.media_player.stop()
                self.gui.media_player.setSource(QUrl())
            except Exception:
                pass
        if hasattr(self.gui, "video_view"):
            try:
                self.gui.video_view.clear_blur_region()
            except Exception:
                pass
        if hasattr(self.gui, "progress_bar") and self.gui.progress_bar is not None:
            self.gui.progress_bar.setValue(0)
        self.gui._clear_segment_editor_rows()
        self.gui._segment_editor_rows = []
        self.gui._selected_segment_index = -1
        self.gui.sync_segment_editor_rows()
        self.gui.update_progress_checklist()
        self.gui.refresh_ui_state()
        QApplication.processEvents()

    def has_cleanable_project_data(self) -> bool:
        project_root = str(getattr(getattr(self.gui, "current_project_state", None), "project_root", "") or "").strip()
        candidates = [
            self.gui.last_extracted_audio,
            self.gui.last_vocals_path,
            self.gui.last_music_path,
            self.gui.last_voice_vi_path,
            self.gui.last_mixed_vi_path,
            self.gui.live_preview_subtitle_path,
            self.gui.live_preview_ass_path,
            self.gui.last_preview_video_path,
            self.gui.last_styled_preview_path,
            self.gui.last_exact_preview_5s_path,
            self.gui.last_exact_preview_frame_path,
            self.gui.get_project_temp_path("tts"),
            self.gui.get_project_temp_path("segment_audio_preview"),
            self.gui.get_project_temp_path("voice_sample_preview"),
            self.gui.get_project_temp_path("htdemucs"),
            self.gui.get_project_temp_path("timeline_video_thumbs"),
            self.gui.get_project_temp_root(),
            project_root,
        ]
        for candidate in candidates:
            normalized = self.gui._normalize_local_file_path(candidate)
            if normalized and os.path.exists(normalized):
                return True
        return False

    def exit_to_launcher(self):
        self.gui._return_to_launcher(project_removed_from_recent=False)

    def clean_current_project(self):
        project_state = getattr(self.gui, "current_project_state", None)
        if not self.has_cleanable_project_data():
            QMessageBox.information(self.gui, "Clean Project", "There is no generated project data to clean right now.")
            return

        confirmation = QMessageBox.question(
            self.gui,
            "Clean Project",
            "This will remove intermediate project files, temp previews, separated audio, cached TTS files, and this video's timeline media cache.\n\n"
            "It will keep your source video, imported assets, and final exported video.\n\n"
            "Do you want to continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirmation != QMessageBox.Yes:
            return

        removed_paths = []
        removed_groups = {
            "Project folder": [],
            "Generated voice files": [],
            "Separated audio": [],
            "Preview temp files": [],
            "TTS cache": [],
            "Temp folders": [],
            "Timeline media cache": [],
            "Launcher media cache": [],
        }
        project_temp_root = self.gui.get_project_temp_root()
        output_root = os.path.join(self.gui.workspace_root, "output")
        project_root = str(getattr(project_state, "project_root", "") or "").strip()
        project_id = str(getattr(project_state, "project_id", "") or "").strip()
        if not project_id and project_root:
            project_id = os.path.basename(os.path.normpath(project_root))
        video_path = self.gui.video_path_edit.text().strip() if hasattr(self.gui, "video_path_edit") else ""

        # Remove temp files safely
        allowed_roots = [project_temp_root, project_root, output_root]
        for candidate in [
            self.gui.last_extracted_audio,
            self.gui.last_vocals_path,
            self.gui.last_music_path,
            self.gui.last_voice_vi_path,
            self.gui.last_mixed_vi_path,
            self.gui.live_preview_subtitle_path,
            self.gui.live_preview_ass_path,
            self.gui.last_preview_video_path,
            self.gui.last_styled_preview_path,
            self.gui.last_exact_preview_5s_path,
            self.gui.last_exact_preview_frame_path,
        ]:
            if candidate:
                self.remove_path_if_safe(candidate, allowed_roots=allowed_roots, removed=removed_paths)

        if project_temp_root and os.path.exists(project_temp_root):
            self.remove_path_if_safe(project_temp_root, allowed_roots=[project_temp_root], removed=removed_paths)

        self.reset_project_runtime_state()
        self.gui.log(f"[Project] Cleaned {len(removed_paths)} project artifacts.")
        QMessageBox.information(self.gui, "Clean Project", f"Project files cleaned successfully ({len(removed_paths)} items removed).")
