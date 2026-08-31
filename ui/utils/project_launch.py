from __future__ import annotations

import os

from PySide6.QtCore import QUrl


def initialize_editor_from_selection(window, selection) -> None:
    """Open either a project.json selection or a legacy video selection."""
    if isinstance(selection, dict):
        state_path = str(selection.get("project_state_path", "") or "").strip()
        selected_video = str(selection.get("video_path", "") or "").strip()
    else:
        state_path = ""
        selected_video = str(selection or "").strip()

    state = None
    if state_path and os.path.isfile(state_path):
        state = window.project_service.load_project(state_path)
        window.current_project_state = state
        selected_video = str(state.input_video or selected_video or "").strip()

    selected_video = os.path.abspath(selected_video) if selected_video and os.path.isfile(selected_video) else ""
    window._current_video_path = selected_video
    window.ensure_media_backend_ready()
    window.video_path_edit.setText(selected_video)

    if state is None and selected_video:
        state = window.ensure_current_project()
    window.current_project_state = state
    if state is not None:
        window.load_project_context(state)

    clips = window.get_timeline_video_clips(existing_only=True) if hasattr(window, "get_timeline_video_clips") else []
    if not clips and selected_video and hasattr(window, "timeline"):
        duration = float(window.timeline._probe_video_duration(selected_video))
        window.timeline.set_video_source(selected_video, duration)
        clips = window.get_timeline_video_clips(existing_only=True) if hasattr(window, "get_timeline_video_clips") else []

    preview_source = str((clips[0] or {}).get("source", "") if clips else selected_video).strip()
    if preview_source and os.path.isfile(preview_source):
        window.media_player.setSource(QUrl.fromLocalFile(preview_source))
        if hasattr(window, "refresh_video_dimensions"):
            window.refresh_video_dimensions(preview_source)
    if hasattr(window, "refresh_source_video_list"):
        window.refresh_source_video_list()
    if hasattr(window, "update_project_header"):
        window.update_project_header()
    if preview_source:
        window.schedule_timeline_visual_refresh(waveform=True, thumbnails=True)

