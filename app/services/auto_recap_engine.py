from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class AutoRecapConfig:
    """Configuration for CapCap Auto Edit Recap Engine (12 Core Rules)."""
    enabled: bool = True
    editing_style: str = "Balanced"  # "Subtle" (105%), "Balanced" (110%), "Dynamic" (115%)
    max_zoom_percent: float = 110.0  # 105%, 110%, 115%
    allow_smart_zoom: bool = True
    allow_pan_reframe: bool = True
    allow_horizontal_flip: bool = True
    allow_speed_change: bool = True
    allow_freeze_frame: bool = True
    ducking_preset: str = "Balanced"  # "Light" (-6dB), "Balanced" (-12dB), "Strong" (-16dB)
    audio_ducking_db: float = -12.0
    min_shot_duration: float = 1.0
    max_shot_duration: float = 7.0
    cooldown_shots: int = 2
    safety_blacklist_text: bool = True
    strict_flip_safety: bool = True  # Strict: UNSAFE / UNKNOWN -> Don't Flip


@dataclass
class ShotDecision:
    """Represents the Edit Decision for a single video shot."""
    shot_index: int
    start_time: float
    end_time: float
    duration: float
    importance_score: float  # 0.0 to 100.0
    action_type: str  # "KEEP", "TRIM", "CUT"
    zoom_scale: float = 1.0  # 1.0, 1.05, 1.10, 1.15
    pan_direction: str = "none"  # "left_right", "right_left", "top_bottom", "bottom_top", "none"
    crop_mode: str = "none"  # "speaker", "main_character", "object", "wide", "none"
    speed: float = 1.0  # 1.0, 1.15, 0.90
    freeze_duration: float = 0.0  # 0.3s - 0.6s
    horizontal_flip: bool = False
    audio_ducking: bool = True
    motion_limited_by_subtitle: bool = False
    keep_original: bool = False
    source_clip_id: str = ""
    recap_notes: str = ""

    @property
    def output_duration(self) -> float:
        """Duration of this shot after speed and freeze-frame processing."""
        if self.action_type == "CUT" or self.duration <= 0:
            return 0.0
        speed = self.speed if self.speed > 0 else 1.0
        return max(0.0, (self.duration / speed) + self.freeze_duration)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shot_index": self.shot_index,
            "start_time": round(self.start_time, 2),
            "end_time": round(self.end_time, 2),
            "duration": round(self.duration, 2),
            "importance_score": round(self.importance_score, 1),
            "action_type": self.action_type,
            "zoom_scale": self.zoom_scale,
            "pan_direction": self.pan_direction,
            "crop_mode": self.crop_mode,
            "speed": self.speed,
            "freeze_duration": round(self.freeze_duration, 2),
            "horizontal_flip": self.horizontal_flip,
            "audio_ducking": self.audio_ducking,
            "motion_limited_by_subtitle": self.motion_limited_by_subtitle,
            "keep_original": self.keep_original,
            "source_clip_id": self.source_clip_id,
            "recap_notes": self.recap_notes,
        }


class FootageReuseManager:
    """Manages footage reuse history and determines composition variation strategies."""

    def __init__(self):
        self.history: Dict[str, List[Dict[str, Any]]] = {}

    def get_reuse_strategy(self, clip_id: str, is_safe_for_flip: bool) -> Dict[str, Any]:
        uses = self.history.get(clip_id, [])
        count = len(uses)
        if count == 0:
            strategy = {"flip": False, "crop": "none", "zoom": 1.05, "note": "Original 1st Use"}
        elif count == 1:
            strategy = {"flip": False, "crop": "speaker", "zoom": 1.10, "note": "Reused 2nd: Crop/Reframe"}
        elif count == 2 and is_safe_for_flip:
            strategy = {"flip": True, "crop": "none", "zoom": 1.05, "note": "Reused 3rd: Horizontal Flip (Safe)"}
        elif count == 3 and is_safe_for_flip:
            strategy = {"flip": True, "crop": "main_character", "zoom": 1.10, "note": "Reused 4th: Flip + Crop"}
        else:
            strategy = {"flip": False, "crop": "wide", "zoom": 1.0, "note": "Reused 5th+: Wide / Keep Original"}

        record = {"usage_index": count + 1, **strategy}
        if clip_id not in self.history:
            self.history[clip_id] = []
        self.history[clip_id].append(record)
        return strategy


class AutoRecapEngine:
    """Core Engine executing the 12 Rules for Auto Edit Recap in CapCap."""

    def __init__(self, config: Optional[AutoRecapConfig] = None):
        self.config = config or AutoRecapConfig()
        self.reuse_manager = FootageReuseManager()
        self._last_effects: List[str] = []
        self.last_render_error = ""

    @staticmethod
    def _media_tool_path(name: str) -> str:
        executable = f"{name}.exe" if os.name == "nt" else name
        try:
            from app.runtime_paths import bin_path

            bundled = bin_path("ffmpeg", executable)
            if bundled and os.path.exists(bundled):
                return bundled
        except ImportError:
            pass
        return shutil.which(name) or name

    def detect_scenes_ffmpeg(self, video_path: str, threshold: float = 0.3) -> List[Dict[str, Any]]:
        """Detects actual scene cut timestamps using FFmpeg scene filter."""
        if not video_path or not os.path.exists(video_path):
            return []
        
        scenes = []
        try:
            cmd = [
                self._media_tool_path("ffmpeg"), "-hide_banner", "-nostats", "-i", video_path,
                "-filter_complex", f"select='gt(scene,{threshold})',metadata=print:file=-",
                "-f", "null", "-"
            ]
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            matches = re.findall(r"pts_time:([\d\.]+)", process.stdout)
            
            timestamps = [0.0] + [float(m) for m in matches]
            # Get video duration for final scene boundary
            dur_cmd = [self._media_tool_path("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
            try:
                dur_res = subprocess.run(dur_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                total_dur = float(dur_res.stdout.strip())
                if total_dur > timestamps[-1] + 1.0:
                    timestamps.append(total_dur)
            except Exception:
                pass

            # Fallback: if no scene cuts detected (e.g. single continuous video), chunk into 3.5-second shots
            if len(timestamps) <= 2:
                total_dur = timestamps[-1] if len(timestamps) > 1 else 30.0
                step = min(3.5, max(0.5, float(self.config.max_shot_duration)))
                timestamps = [0.0]
                boundary = step
                while boundary < total_dur:
                    timestamps.append(round(boundary, 2))
                    boundary += step
                if total_dur > 0:
                    timestamps.append(round(total_dur, 2))

            for i in range(len(timestamps) - 1):
                scenes.append({
                    "start": timestamps[i],
                    "end": timestamps[i+1],
                    "text": "",
                    "source_clip_id": f"scene_{i}"
                })
        except Exception:
            pass
        return scenes

    def check_safety_blacklist(self, text: str, has_logo: bool = False, has_hard_sub: bool = False) -> bool:
        """Rule 8 Safety Check: UNSAFE or UNKNOWN -> Don't Flip (Strict Conservative Safety)."""
        if not self.config.allow_horizontal_flip:
            return False
        if not self.config.safety_blacklist_text:
            return True
        if has_logo or has_hard_sub:
            return False
        
        if any(char.isdigit() for char in text):
            return False
        words = text.split()
        if any(w.isupper() and len(w) > 1 for w in words):
            return False
        if self.config.strict_flip_safety and not text.strip():
            return False

        return True

    def calculate_importance_score(
        self,
        segment_text: str,
        duration: float,
        is_scene_cut: bool,
        voice_loudness: float = 0.5,
    ) -> float:
        """Rule 2 — Importance Score (0.0 to 100.0)."""
        score = 45.0
        text_clean = str(segment_text or "").strip().lower()

        if not text_clean:
            score -= 20.0
            if not is_scene_cut:
                score -= 15.0
        else:
            high_keywords = [
                "bất ngờ", "quan trọng", "đặc biệt", "bí mật", "cuối cùng",
                "nguy hiểm", "sự thật", "thành công", "bi kịch", "reveal",
                "secret", "important", "climax", "truth", "key", "mystery"
            ]
            if any(kw in text_clean for kw in high_keywords):
                score += 30.0
            if "!" in segment_text or "?" in segment_text:
                score += 15.0
            if len(segment_text.split()) >= 6:
                score += 10.0

        if is_scene_cut:
            score += 10.0
        if voice_loudness > 0.7:
            score += 10.0

        return max(0.0, min(100.0, score))

    def evaluate_shot(
        self,
        shot_index: int,
        start_time: float,
        end_time: float,
        segment_text: str = "",
        is_scene_cut: bool = True,
        source_clip_id: str = "clip_0",
        has_logo: bool = False,
        has_hard_sub: bool = False,
    ) -> ShotDecision:
        """Applies the 12 Core Rules to produce a ShotDecision."""
        duration = max(0.1, end_time - start_time)

        importance = self.calculate_importance_score(segment_text, duration, is_scene_cut)

        if importance < 25.0 and duration > self.config.max_shot_duration:
            action_type = "TRIM"
            effective_duration = min(duration, 3.5)
        elif importance < 15.0:
            action_type = "CUT"
            effective_duration = 0.0
        else:
            action_type = "KEEP"
            effective_duration = duration

        words_count = len(segment_text.split())
        is_long_subtitle = words_count > 12
        # Very short shots should remain stable; using word count here made
        # most normal dialogue shots static and visually identical to source.
        keep_original = duration < max(0.6, self.config.min_shot_duration)

        zoom_scale = 1.0
        if self.config.allow_smart_zoom and not keep_original and effective_duration >= 1.2:
            style = str(self.config.editing_style or "Balanced").strip().lower()
            style_zooms = {
                "subtle": (1.03, 1.05, 1.05),
                "balanced": (1.06, 1.10, 1.10),
                "dynamic": (1.08, 1.12, 1.15),
            }
            normal_zoom, important_zoom, climax_zoom = style_zooms.get(
                style, style_zooms["balanced"]
            )
            max_zoom = max(1.0, self.config.max_zoom_percent / 100.0)
            if is_long_subtitle:
                # Limit motion for readability without making the entire shot
                # visually identical to the source video.
                normal_zoom = min(normal_zoom, 1.04)
                important_zoom = min(important_zoom, 1.05)
                climax_zoom = min(climax_zoom, 1.05)
            if importance >= 85.0:
                zoom_scale = min(climax_zoom, max_zoom)
            elif importance >= 70.0:
                zoom_scale = min(important_zoom, max_zoom)
            elif importance >= 35.0:
                zoom_scale = min(normal_zoom, max_zoom)

        if self.config.cooldown_shots > 0:
            recent_zooms = [e for e in self._last_effects[-self.config.cooldown_shots:] if "zoom" in e]
            if len(recent_zooms) >= self.config.cooldown_shots:
                zoom_scale = 1.0

        pan_direction = "none"
        if self.config.allow_pan_reframe and not keep_original and zoom_scale <= 1.05 and effective_duration >= 2.0 and not is_long_subtitle:
            directions = ["left_right", "right_left", "top_bottom", "bottom_top"]
            h = int(hashlib.md5(f"{shot_index}_{importance:.0f}".encode()).hexdigest(), 16)
            pan_direction = directions[h % len(directions)]

        speed = 1.0
        if self.config.allow_speed_change and not keep_original:
            if importance >= 85.0 and effective_duration >= 2.0:
                speed = 0.90
            elif importance < 35.0 and effective_duration > 4.0:
                speed = 1.15

        freeze_duration = 0.0
        if self.config.allow_freeze_frame and importance >= 85.0 and effective_duration >= 3.0 and not keep_original:
            freeze_duration = 0.4

        is_safe_for_flip = self.check_safety_blacklist(segment_text, has_logo, has_hard_sub)
        reuse_info = self.reuse_manager.get_reuse_strategy(source_clip_id, is_safe_for_flip)

        horizontal_flip = False
        crop_mode = "none"
        if self.config.allow_horizontal_flip and reuse_info.get("flip", False) and is_safe_for_flip:
            horizontal_flip = True
        if reuse_info.get("crop", "none") != "none":
            crop_mode = reuse_info["crop"]

        audio_ducking = bool(segment_text.strip())

        effect_name = "static"
        if zoom_scale > 1.0:
            effect_name = f"zoom_{zoom_scale}"
        elif pan_direction != "none":
            effect_name = f"pan_{pan_direction}"
        self._last_effects.append(effect_name)

        notes = f"Score: {importance:.0f} | {reuse_info.get('note', '')}"
        if is_long_subtitle:
            notes += " | Subtitle-aware: Motion limited"

        return ShotDecision(
            shot_index=shot_index,
            start_time=start_time,
            end_time=end_time,
            duration=effective_duration,
            importance_score=importance,
            action_type=action_type,
            zoom_scale=zoom_scale,
            pan_direction=pan_direction,
            crop_mode=crop_mode,
            speed=speed,
            freeze_duration=freeze_duration,
            horizontal_flip=horizontal_flip,
            audio_ducking=audio_ducking,
            motion_limited_by_subtitle=is_long_subtitle,
            keep_original=keep_original,
            source_clip_id=source_clip_id,
            recap_notes=notes,
        )

    def generate_edl(self, segments: List[Dict[str, Any]], scenes: Optional[List[Dict[str, Any]]] = None) -> List[ShotDecision]:
        """Generates the full Edit Decision List (EDL) for the input segments/scenes."""
        self._last_effects.clear()
        # A generated EDL is an independent run. Reuse history must not leak
        # into a later preview/export performed with the same engine instance.
        self.reuse_manager = FootageReuseManager()
        decisions: List[ShotDecision] = []

        raw_items = scenes if scenes else segments
        if not raw_items:
            return decisions

        for idx, item in enumerate(raw_items):
            start = float(item.get("start", item.get("start_time", 0.0)))
            end = float(item.get("end", item.get("end_time", start + 3.0)))
            if not math.isfinite(start) or not math.isfinite(end) or end <= start:
                continue
            start = max(0.0, start)
            if end <= start:
                continue
            text = str(item.get("text", ""))
            # Different time ranges are different footage unless the caller
            # explicitly identifies them as reuse of the same source clip.
            clip_id = str(item.get("source_clip_id") or f"clip_{idx}")
            has_logo = bool(item.get("has_logo", False))
            has_hard_sub = bool(item.get("has_hard_sub", False))

            decision = self.evaluate_shot(
                shot_index=idx,
                start_time=start,
                end_time=end,
                segment_text=text,
                is_scene_cut=bool(item.get("is_scene_cut", True)),
                source_clip_id=clip_id,
                has_logo=has_logo,
                has_hard_sub=has_hard_sub,
            )
            if decision.action_type != "CUT":
                decisions.append(decision)

        return decisions

    def build_ffmpeg_filtergraph(
        self,
        decisions: List[ShotDecision],
        has_voiceover: bool = False,
        has_bg_music: bool = False,
        has_audio: bool = True,
    ) -> tuple[str, List[str]]:
        """Converts EDL decisions into a 1-Pass FFmpeg complex filtergraph without temp files.

        Generates:
          - Video trim + zoom + pan + hflip + speed filters per shot
          - Audio atrim + atempo per shot
          - Concat v1:a1 into single output video and audio stream
        """
        if not decisions:
            return "", []

        filter_chains = []
        v_labels = []
        a_labels = []

        for idx, d in enumerate(decisions):
            v_out = f"vout{idx}"
            a_out = f"aout{idx}"

            start, end = d.start_time, d.end_time
            if d.duration > 0 and (end - start) > d.duration:
                end = start + d.duration

            # Video filter chain for shot idx
            v_filters = [f"trim=start={start:.2f}:end={end:.2f}", "setpts=PTS-STARTPTS"]
            a_filters = [f"atrim=start={start:.2f}:end={end:.2f}", "asetpts=PTS-STARTPTS"]

            if d.horizontal_flip:
                v_filters.append("hflip")

            if d.pan_direction != "none":
                p = d.pan_direction
                dur = max(0.1, d.duration if d.duration > 0 else (d.end_time - d.start_time))
                if p == "left_right":
                    v_filters.append(f"scale=iw*1.15:ih*1.15,crop=w=iw/1.15:h=ih/1.15:x='(iw-ow)*t/{dur:.2f}':y='(ih-oh)/2'")
                elif p == "right_left":
                    v_filters.append(f"scale=iw*1.15:ih*1.15,crop=w=iw/1.15:h=ih/1.15:x='(iw-ow)*(1-t/{dur:.2f})':y='(ih-oh)/2'")
                elif p == "top_bottom":
                    v_filters.append(f"scale=iw*1.15:ih*1.15,crop=w=iw/1.15:h=ih/1.15:x='(iw-ow)/2':y='(ih-oh)*t/{dur:.2f}'")
                elif p == "bottom_top":
                    v_filters.append(f"scale=iw*1.15:ih*1.15,crop=w=iw/1.15:h=ih/1.15:x='(iw-ow)/2':y='(ih-oh)*(1-t/{dur:.2f})'")
            elif d.crop_mode != "none":
                if d.crop_mode == "speaker":
                    v_filters.append("scale=iw*1.20:ih*1.20,crop=w=iw/1.20:h=ih/1.20:x='(iw-ow)/2':y='(ih-oh)/3'")
                else:
                    v_filters.append("scale=iw*1.15:ih*1.15,crop=w=iw/1.15:h=ih/1.15:x='(iw-ow)/2':y='(ih-oh)/2'")
            elif d.zoom_scale > 1.0:
                z = d.zoom_scale
                v_filters.append(f"scale=iw*{z:.2f}:ih*{z:.2f},crop=w=iw/{z:.2f}:h=ih/{z:.2f}:x='(iw-ow)/2':y='(ih-oh)/2'")

            if d.speed != 1.0 and d.speed > 0:
                v_filters.append(f"setpts=PTS/{d.speed:.2f}")
                if has_audio:
                    a_filters.append(f"atempo={d.speed:.2f}")

            if d.freeze_duration > 0:
                v_filters.append(f"tpad=stop_mode=clone:stop_duration={d.freeze_duration:.2f}")
                if has_audio:
                    a_filters.append(f"apad=pad_dur={d.freeze_duration:.2f}")

            # Normalize dimensions for concat
            v_filters.append("scale=1280:720,setsar=1")

            filter_chains.append(f"[0:v]{','.join(v_filters)}[{v_out}]")
            v_labels.append(f"[{v_out}]")
            if has_audio:
                filter_chains.append(f"[0:a]{','.join(a_filters)}[{a_out}]")
                a_labels.append(f"[{a_out}]")

        # Concat all shots together in 1-pass
        num_shots = len(decisions)
        if has_audio:
            concat_inputs = "".join([f"{v}{a}" for v, a in zip(v_labels, a_labels)])
            filter_chains.append(f"{concat_inputs}concat=n={num_shots}:v=1:a=1[vfinal][afinal]")
            maps = ["-map", "[vfinal]", "-map", "[afinal]"]
        else:
            concat_inputs = "".join(v_labels)
            filter_chains.append(f"{concat_inputs}concat=n={num_shots}:v=1:a=0[vfinal]")
            maps = ["-map", "[vfinal]"]

        filtergraph_str = ";".join(filter_chains)
        return filtergraph_str, maps

    @staticmethod
    def _input_has_audio(input_video_path: str) -> bool:
        cmd = [
            AutoRecapEngine._media_tool_path("ffprobe"), "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=index", "-of", "csv=p=0",
            input_video_path,
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=10,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            return False

    def prepare_audio_ducking(
        self,
        decisions: List[ShotDecision],
        has_voiceover: bool = False,
        has_bg_music: bool = False,
    ) -> Dict[str, Any]:
        """Prepare audio processing parameters.

        If there is NO voiceover (e.g. video only has original audio), skip ducking logic gracefully.
        """
        if not has_voiceover:
            return {
                "ducking_applied": False,
                "reason": "No separate voiceover present (Original audio only - skipping ducking)",
                "volume_db": 0.0,
            }

        db = float(getattr(self.config, "audio_ducking_db", -12.0))
        return {
            "ducking_applied": True,
            "reason": f"Ducking background audio by {db}dB during voiceover speech",
            "volume_db": db,
        }

    def render_recap_video_1pass(
        self,
        input_video_path: str,
        output_video_path: str,
        decisions: List[ShotDecision],
        on_progress=None,
    ) -> bool:
        """Executes a 1-Pass FFmpeg render for the given EDL decisions on a real video file."""
        self.last_render_error = ""
        if not input_video_path or not os.path.exists(input_video_path) or not decisions:
            self.last_render_error = "Missing source video or Auto Recap decisions."
            return False

        has_audio = self._input_has_audio(input_video_path)
        filtergraph, maps = self.build_ffmpeg_filtergraph(decisions, has_audio=has_audio)
        if not filtergraph or not maps:
            return False
        output_dir = os.path.dirname(os.path.abspath(output_video_path))
        os.makedirs(output_dir, exist_ok=True)
        output_stem, output_ext = os.path.splitext(os.path.abspath(output_video_path))
        partial_path = f"{output_stem}.partial{output_ext or '.mp4'}"
        fd, filter_script_path = tempfile.mkstemp(
            prefix="auto_recap_", suffix=".ffgraph", dir=output_dir
        )
        os.close(fd)
        with open(filter_script_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(filtergraph)
        cmd = [
            self._media_tool_path("ffmpeg"), "-y", "-hide_banner", "-nostats",
            "-i", input_video_path,
            "-filter_complex_script", filter_script_path,
        ] + maps + [
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        ]
        if has_audio:
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        cmd += ["-movflags", "+faststart", partial_path]
        error_handle = tempfile.TemporaryFile(mode="w+b")
        try:
            if on_progress:
                on_progress(0)
            try:
                from app.runtime_paths import subprocess_hidden_kwargs

                hidden_kwargs = subprocess_hidden_kwargs()
            except ImportError:
                hidden_kwargs = {}
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=error_handle,
                **hidden_kwargs,
            )
            while proc.poll() is None:
                try:
                    from PySide6.QtCore import QCoreApplication
                    QCoreApplication.processEvents()
                except Exception:
                    pass
                time.sleep(0.05)
            proc.wait(timeout=5)
            success = (
                proc.returncode == 0
                and os.path.exists(partial_path)
                and os.path.getsize(partial_path) > 0
            )
            if success:
                os.replace(partial_path, output_video_path)
            else:
                error_handle.seek(0)
                error_text = error_handle.read().decode("utf-8", errors="replace").strip()
                self.last_render_error = error_text[-4000:] or f"FFmpeg exited with code {proc.returncode}."
            if success and on_progress:
                on_progress(100)
            return success
        except Exception as exc:
            self.last_render_error = str(exc)
            return False
        finally:
            error_handle.close()
            for temporary_path in (partial_path, filter_script_path):
                try:
                    if os.path.exists(temporary_path):
                        os.remove(temporary_path)
                except OSError:
                    pass
