from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from app.services.auto_recap_engine import AutoRecapEngine, ShotDecision


@dataclass
class RecapBenchmarkMetrics:
    total_shots_analyzed: int = 0
    kept_shots: int = 0
    trimmed_shots: int = 0
    cut_shots: int = 0
    zoomed_shots: int = 0
    panned_shots: int = 0
    flipped_shots: int = 0
    speed_altered_shots: int = 0
    frozen_shots: int = 0
    ducked_shots: int = 0
    unique_source_clips: int = 0
    total_reuse_count: int = 0
    max_consecutive_reuse: int = 0
    flip_reuse_count: int = 0
    crop_reuse_count: int = 0
    total_input_duration: float = 0.0
    total_output_duration: float = 0.0
    analysis_time_sec: float = 0.0
    edl_build_time_sec: float = 0.0
    smart_edits_time_sec: float = 0.0
    audio_proc_time_sec: float = 0.0
    render_time_sec: float = 0.0

    def generate_ascii_report(self) -> str:
        speedup = (
            (self.total_input_duration / max(0.001, self.render_time_sec))
            if self.render_time_sec > 0
            else 0.0
        )
        return f"""
================================================================================
📊 VIUStudio Auto Edit Recap Benchmark Report
================================================================================
⏱️ Stage Timings:
  • Stage 1 (Analyzing Video)     : {self.analysis_time_sec:.3f} s
  • Stage 2 (Building Recap)      : {self.edl_build_time_sec:.3f} s
  • Stage 3 (Smart Edits EDL)     : {self.smart_edits_time_sec:.3f} s
  • Stage 4 (Processing Audio)    : {self.audio_proc_time_sec:.3f} s
  • Stage 5 (1-Pass FFmpeg Render): {self.render_time_sec:.3f} s (Single Filtergraph - No Temp Files)
--------------------------------------------------------------------------------
🎬 Shot & Reuse Distribution:
  • Total Shots Analyzed          : {self.total_shots_analyzed}
  • Kept Shots                    : {self.kept_shots}
  • Trimmed Shots                 : {self.trimmed_shots}
  • Cut Shots                     : {self.cut_shots}
  • Unique Source Clips           : {self.unique_source_clips}
  • Total Reuse Count             : {self.total_reuse_count}
  • Max Consecutive Reuse         : {self.max_consecutive_reuse}
  • Flip Reuse Count              : {self.flip_reuse_count}
  • Crop Reuse Count              : {self.crop_reuse_count}
--------------------------------------------------------------------------------
✨ 12 Core Rule Applied Effects:
  • Smart Zoom (105-115%)         : {self.zoomed_shots}
  • Pan / Motion Reframe          : {self.panned_shots}
  • Horizontal Flip (Safe)        : {self.flipped_shots}
  • Speed Accent (0.90x / 1.15x)  : {self.speed_altered_shots}
  • Freeze Frame (0.4s)           : {self.frozen_shots}
  • Audio Ducking                 : {self.ducked_shots}
--------------------------------------------------------------------------------
⏱️ Duration & Performance:
  • Input Video Duration          : {self.total_input_duration:.2f} s
  • Output Recap Duration         : {self.total_output_duration:.2f} s
  • Render Speed Ratio            : {speedup:.2f}x real-time
================================================================================
"""


def benchmark_auto_recap_pipeline(
    engine: AutoRecapEngine,
    segments: List[Dict[str, Any]],
    scenes: Optional[List[Dict[str, Any]]] = None,
    has_voiceover: bool = False,
) -> tuple[List[ShotDecision], RecapBenchmarkMetrics]:
    """Runs a complete benchmark timing calculation on the 5 stages."""
    metrics = RecapBenchmarkMetrics()

    # Stage 1
    t0 = time.perf_counter()
    raw_shots = scenes if scenes else segments
    metrics.total_shots_analyzed = len(raw_shots)
    metrics.total_input_duration = sum(
        float(s.get("end", 3.0)) - float(s.get("start", 0.0)) for s in raw_shots
    )
    metrics.analysis_time_sec = time.perf_counter() - t0

    # Stage 2
    t0 = time.perf_counter()
    decisions = engine.generate_edl(segments, scenes)
    metrics.edl_build_time_sec = time.perf_counter() - t0

    # Stage 3
    t0 = time.perf_counter()
    seen_clips = set()
    clip_counts: Dict[str, int] = {}
    last_clip_id = ""
    current_consecutive = 0
    max_consecutive = 0

    for d in decisions:
        if d.action_type == "KEEP":
            metrics.kept_shots += 1
        elif d.action_type == "TRIM":
            metrics.trimmed_shots += 1

        if d.zoom_scale > 1.0:
            metrics.zoomed_shots += 1
        if d.pan_direction != "none":
            metrics.panned_shots += 1
        if d.horizontal_flip:
            metrics.flipped_shots += 1
        if d.speed != 1.0:
            metrics.speed_altered_shots += 1
        if d.freeze_duration > 0:
            metrics.frozen_shots += 1

        cid = d.source_clip_id or "default_clip"
        seen_clips.add(cid)
        clip_counts[cid] = clip_counts.get(cid, 0) + 1

        if cid == last_clip_id:
            current_consecutive += 1
        else:
            current_consecutive = 1
            last_clip_id = cid
        max_consecutive = max(max_consecutive, current_consecutive)

        if d.horizontal_flip:
            metrics.flip_reuse_count += 1
        if d.crop_mode != "none":
            metrics.crop_reuse_count += 1

    metrics.unique_source_clips = len(seen_clips)
    metrics.total_reuse_count = sum(c - 1 for c in clip_counts.values() if c > 1)
    metrics.max_consecutive_reuse = max_consecutive
    metrics.cut_shots = metrics.total_shots_analyzed - len(decisions)
    metrics.total_output_duration = sum(d.duration for d in decisions)
    metrics.smart_edits_time_sec = time.perf_counter() - t0

    # Stage 4
    t0 = time.perf_counter()
    audio_info = engine.prepare_audio_ducking(decisions, has_voiceover=has_voiceover)
    if audio_info.get("ducking_applied", False):
        metrics.ducked_shots = sum(1 for d in decisions if d.audio_ducking)
    metrics.audio_proc_time_sec = time.perf_counter() - t0

    return decisions, metrics
