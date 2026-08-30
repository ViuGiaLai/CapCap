from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QFileDialog, QListWidgetItem, QMessageBox

from app.services.timeline_video_sequence import (
    append_video,
    move_video,
    ordered_video_layers,
    remove_video,
    resolve_timeline_time,
    timeline_video_clips,
)


class MultiVideoTimelineMixin:
    """Coordinate the sequential source videos stored directly on V1."""

    def get_timeline_video_clips(self, *, existing_only: bool = False) -> list[dict]:
        model = getattr(getattr(self, "timeline", None), "_timeline", None)
        return [clip.to_dict() for clip in timeline_video_clips(model, existing_only=existing_only)]

    def timeline_position_seconds(self) -> float:
        clips = self.get_timeline_video_clips()
        if len(clips) > 1:
            return max(0.0, float(getattr(self, "_timeline_global_position_ms", 0)) / 1000.0)
        return max(0.0, float(self.media_player.position()) / 1000.0)

    def refresh_source_video_list(self) -> None:
        widget = getattr(self, "source_video_list", None)
        timeline = getattr(getattr(self, "timeline", None), "_timeline", None)
        if widget is None:
            return
        if timeline is not None:
            from app.services.timeline_video_sequence import normalize_v1_sequence
            normalize_v1_sequence(timeline)
        selected_id = ""
        current = widget.currentItem()
        if current is not None:
            selected_id = str(current.data(Qt.UserRole) or "")
        widget.blockSignals(True)
        widget.clear()
        for index, layer in enumerate(ordered_video_layers(timeline), 1):
            duration = max(0.0, float(layer.end) - float(layer.start))
            minutes, seconds = divmod(int(round(duration)), 60)
            item = QListWidgetItem(
                f"{index}. {os.path.basename(layer.source)}   {minutes:02d}:{seconds:02d}"
            )
            item.setData(Qt.UserRole, layer.id)
            item.setToolTip(layer.source)
            widget.addItem(item)
            if layer.id == selected_id:
                widget.setCurrentItem(item)
        widget.blockSignals(False)
        count = widget.count()
        if hasattr(self, "source_video_summary_label"):
            total = float(getattr(timeline, "duration", 0.0) or 0.0)
            hours, remainder = divmod(int(round(total)), 3600)
            minutes, seconds = divmod(remainder, 60)
            total_text = f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
            self.source_video_summary_label.setText(f"{count} video · {total_text}")
        self._update_source_video_buttons()

    def _selected_source_video_layer_id(self) -> str:
        widget = getattr(self, "source_video_list", None)
        item = widget.currentItem() if widget is not None else None
        return str(item.data(Qt.UserRole) or "") if item is not None else ""

    def _update_source_video_buttons(self) -> None:
        widget = getattr(self, "source_video_list", None)
        row = widget.currentRow() if widget is not None else -1
        count = widget.count() if widget is not None else 0
        if hasattr(self, "move_up_source_video_btn"):
            self.move_up_source_video_btn.setEnabled(row > 0)
        if hasattr(self, "move_down_source_video_btn"):
            self.move_down_source_video_btn.setEnabled(0 <= row < count - 1)
        if hasattr(self, "remove_source_video_btn"):
            self.remove_source_video_btn.setEnabled(row >= 0 and count > 1)

    def add_videos_to_timeline(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Videos to Timeline",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.m4v)",
        )
        if not paths:
            return
        timeline_widget = getattr(self, "timeline", None)
        model = getattr(timeline_widget, "_timeline", None)
        if timeline_widget is None or model is None:
            QMessageBox.warning(self, "Add Video", "Timeline is not ready.")
            return
        added = 0
        for path in paths:
            duration = float(timeline_widget._probe_video_duration(path))
            if duration <= 0:
                self.log(f"[Timeline] Skipped unreadable video: {path}")
                continue
            append_video(model, path, duration)
            added += 1
        if not added:
            QMessageBox.warning(self, "Add Video", "No readable video was selected.")
            return
        timeline_widget.set_duration(int(model.duration * 1000))
        timeline_widget._redraw()
        self.refresh_source_video_list()
        self.persist_current_timeline_project_data()
        self.schedule_timeline_visual_refresh(waveform=True, thumbnails=True)
        self.log(f"[Timeline] Added {added} video(s) to V1.")

    def move_selected_source_video(self, offset: int) -> None:
        layer_id = self._selected_source_video_layer_id()
        model = getattr(getattr(self, "timeline", None), "_timeline", None)
        if not layer_id or model is None or not move_video(model, layer_id, offset):
            return
        self.timeline.set_duration(int(model.duration * 1000))
        self.timeline._selected_layer_id = layer_id
        self.timeline._redraw()
        self.refresh_source_video_list()
        self.persist_current_timeline_project_data()

    def remove_selected_source_video(self) -> None:
        layer_id = self._selected_source_video_layer_id()
        model = getattr(getattr(self, "timeline", None), "_timeline", None)
        if not layer_id or model is None:
            return
        if len(ordered_video_layers(model)) <= 1:
            QMessageBox.information(self, "Remove Video", "A project must keep at least one video on V1.")
            return
        if not remove_video(model, layer_id):
            return
        self.timeline.set_duration(int(model.duration * 1000))
        self.timeline._selected_layer_id = ""
        self.timeline._redraw()
        self.refresh_source_video_list()
        self.persist_current_timeline_project_data()

    def select_source_video_in_timeline(self) -> None:
        layer_id = self._selected_source_video_layer_id()
        if not layer_id or not hasattr(self, "timeline"):
            return
        self.timeline._selected_layer_id = layer_id
        self.timeline.viewport().update()
        _track, layer = self.timeline._find_layer_by_id(layer_id)
        if layer is not None:
            self.timeline.set_playhead(float(layer.start))
            self.seek_timeline_video(float(layer.start))

    def seek_timeline_video(self, global_seconds: float) -> None:
        model = getattr(getattr(self, "timeline", None), "_timeline", None)
        clip, local_seconds = resolve_timeline_time(model, global_seconds)
        if clip is None or not os.path.isfile(clip.source):
            return
        current = os.path.abspath(str(getattr(self, "_timeline_preview_source", "") or ""))
        wanted = os.path.abspath(clip.source)
        if current != wanted:
            self._timeline_preview_source = wanted
            self.media_player.setSource(QUrl.fromLocalFile(wanted))
            if hasattr(self, "sync_preview_audio_track_to_output"):
                self.sync_preview_audio_track_to_output(apply_to_player=True, force=True)
            elif hasattr(self.media_player, "set_original_audio_file"):
                self.media_player.set_original_audio_file(wanted)
        global_ms = int(max(0.0, global_seconds) * 1000)
        self._timeline_global_position_ms = global_ms
        if hasattr(self, "timeline"):
            if hasattr(self.timeline, "set_playhead"):
                self.timeline.set_playhead(max(0.0, global_seconds))
            if hasattr(self.timeline, "set_position"):
                self.timeline.set_position(global_ms)
        clips = self.get_timeline_video_clips(existing_only=True)
        if clips:
            total_ms = int(float(clips[-1]["timeline_end"]) * 1000)
            self.update_duration_label(global_ms, total_ms)
        self.media_player.setPosition(int(local_seconds * 1000))
        if hasattr(self, "refresh_timed_layer_preview"):
            self.refresh_timed_layer_preview(global_ms)
        if hasattr(self, "update_playback_subtitle_highlight"):
            self.update_playback_subtitle_highlight(global_ms)

    def handle_sequence_position_changed(self, local_position_ms: int) -> bool:
        clips = self.get_timeline_video_clips(existing_only=True)
        if len(clips) <= 1:
            return False
        current_source = os.path.abspath(str(getattr(getattr(self, "media_player", None), "_source_path", "") or ""))
        preview_source = os.path.abspath(str(getattr(self, "last_preview_video_path", "") or ""))
        if preview_source and current_source == preview_source:
            return False
        source = os.path.abspath(str(getattr(self, "_timeline_preview_source", "") or ""))
        clip = next((item for item in clips if os.path.abspath(item["source"]) == source), clips[0])
        local_seconds = max(0.0, float(local_position_ms) / 1000.0)
        global_seconds = float(clip["timeline_start"]) + max(
            0.0, (local_seconds - float(clip["source_start"])) / max(0.01, float(clip["speed"]))
        )
        global_seconds = min(float(clip["timeline_end"]), global_seconds)
        global_ms = int(global_seconds * 1000)
        self._timeline_global_position_ms = global_ms
        self.timeline.set_position(global_ms)
        self.update_duration_label(global_ms, int(float(clips[-1]["timeline_end"]) * 1000))
        self.refresh_timed_layer_preview(global_ms)
        self.update_playback_subtitle_highlight(global_ms)

        at_clip_end = local_seconds >= (
            float(clip["source_start"]) + float(clip["source_duration"]) - 0.12
        )
        if at_clip_end:
            index = clips.index(clip)
            if index + 1 < len(clips):
                was_playing = getattr(self.timeline, "_is_playing", False) or bool(self.media_player.is_playing())
                next_clip = clips[index + 1]
                self.seek_timeline_video(float(next_clip["timeline_start"]))
                if was_playing:
                    self.media_player.play()
        return True
