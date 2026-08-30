import os
import subprocess
import wave

from runtime_paths import bin_path, subprocess_text_kwargs


def _ffmpeg_path():
    return bin_path("ffmpeg", "ffmpeg.exe")


def _ffprobe_path():
    return bin_path("ffmpeg", "ffprobe.exe")


def extract_audio_from_video(video_path: str, output_wav_path: str, sample_rate: int = 44100) -> str:
    """Extract audio track from a video file to a WAV file using ffmpeg.

    Args:
        video_path: Path to the source video file.
        output_wav_path: Destination WAV path.
        sample_rate: Output sample rate (default 44100 to preserve quality).

    Returns:
        output_wav_path on success, raises RuntimeError on failure.
    """
    ffmpeg = _ffmpeg_path()
    if not os.path.exists(ffmpeg):
        raise FileNotFoundError(f"FFmpeg not found at {ffmpeg}")
    os.makedirs(os.path.dirname(output_wav_path) or ".", exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-vn",               # strip video
        "-ar", str(sample_rate),
        "-ac", "2",          # stereo
        "-sample_fmt", "s16",
        output_wav_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, **subprocess_text_kwargs())
    if proc.returncode != 0:
        raise RuntimeError(
            f"FFmpeg audio extraction failed:\n{proc.stderr or proc.stdout}"
        )
    return output_wav_path


def _subprocess_run_kwargs() -> dict:
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startupinfo
    return kwargs


def _probe_wav_duration_seconds(wav_path: str) -> float:
    with wave.open(wav_path, "rb") as wav_file:
        frame_rate = wav_file.getframerate() or 16000
        frame_count = wav_file.getnframes()
    return max(0.0, float(frame_count) / float(frame_rate))


def ffprobe_wav_duration(wav_path: str) -> float:
    """Return the actual duration of a wav file via ffprobe.

    Uses ffprobe's `format=duration` for the most accurate reading —
    important for segment preview/regenerate flows where the wav
    may have been re-encoded and the wave header is stale. Returns
    0.0 if ffprobe is missing or the call fails.
    """
    ffprobe = _ffprobe_path()
    if not os.path.exists(ffprobe):
        return 0.0
    try:
        out = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                wav_path,
            ],
            capture_output=True, timeout=10,
            **subprocess_text_kwargs(),
        )
        if out.returncode != 0:
            return 0.0
        return max(0.0, float(out.stdout.strip()))
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return 0.0


def _build_atempo_filter(speed_ratio: float) -> str:
    ratio = max(0.01, float(speed_ratio))
    filters = []
    while ratio < 0.5 or ratio > 2.0:
        if ratio < 0.5:
            filters.append("atempo=0.5")
            ratio /= 0.5
        else:
            filters.append("atempo=2.0")
            ratio /= 2.0
    filters.append(f"atempo={ratio:.6f}")
    return ",".join(filters)


def fit_wav_to_duration(
    *,
    input_wav_path: str,
    output_wav_path: str,
    target_duration_seconds: float,
    mode: str = "off",
    smart_min_ratio: float = 0.77,
    smart_max_ratio: float = 1.15,
) -> str:
    mode_key = (mode or "off").strip().lower()
    if mode_key == "force fit":
        mode_key = "force"
    if mode_key not in {"smart", "force", "timeline"}:
        return input_wav_path
    if not os.path.exists(input_wav_path):
        raise FileNotFoundError(f"Input wav not found: {input_wav_path}")

    source_duration = _probe_wav_duration_seconds(input_wav_path)
    target_duration = max(0.0, float(target_duration_seconds))
    if source_duration <= 0.0 or target_duration <= 0.0:
        return input_wav_path

    fit_ratio = target_duration / source_duration
    ffmpeg = _ffmpeg_path()
    if not os.path.exists(ffmpeg):
        raise FileNotFoundError(f"FFmpeg not found at {ffmpeg}")

    os.makedirs(os.path.dirname(output_wav_path) or ".", exist_ok=True)

    if mode_key == "timeline":
        # Timeline Priority: always cut the audio to the segment
        # window. The end of the speech may be skipped if it exceeds
        # the segment duration — playback continues with the next
        # segment immediately after. No atempo, no early return.
        if abs(fit_ratio - 1.0) < 0.02:
            return input_wav_path
        cmd = [
            ffmpeg, "-y", "-i", input_wav_path,
            "-t", str(target_duration),
            "-ar", "16000", "-ac", "1",
            output_wav_path,
        ]
    elif mode_key == "smart":
        # ``fit_ratio`` is target/source.  The old branches treated it as
        # source/target, so short speech was sent through ``-t`` (which cannot
        # add duration) and the subtitle stayed visible after speech ended.
        # Use atempo in both directions, but only inside the natural-sounding
        # safety band.
        if abs(fit_ratio - 1.0) < 0.02:
            return input_wav_path
        source_to_target_ratio = source_duration / target_duration
        if source_duration > target_duration:
            # Speech is longer: speed it up only when the required change is
            # within the configured safe range.
            if fit_ratio < smart_min_ratio:
                return input_wav_path
            atempo_ratio = source_to_target_ratio
        else:
            # Speech is shorter: slow it down to fill the subtitle window.
            # Very large slow-downs sound robotic, so those are handled later
            # by aligning the visual subtitle end to the real speech end.
            if source_to_target_ratio < smart_min_ratio:
                return input_wav_path
            atempo_ratio = source_to_target_ratio
        filter_chain = _build_atempo_filter(atempo_ratio)
        cmd = [
            ffmpeg, "-y", "-i", input_wav_path,
            "-filter:a", filter_chain,
            "-ar", "16000", "-ac", "1",
            output_wav_path,
        ]
    else:
        # Force mode: use atempo to speed up the audio so it fits the
        # target duration. This is the legacy behaviour.
        if abs(fit_ratio - 1.0) < 0.02:
            return input_wav_path
        if fit_ratio > 1.0 and fit_ratio > smart_max_ratio:
            return input_wav_path
        filter_chain = _build_atempo_filter(1.0 / fit_ratio)
        cmd = [
            ffmpeg, "-y", "-i", input_wav_path,
            "-filter:a", filter_chain,
            "-ar", "16000", "-ac", "1",
            output_wav_path,
        ]

    proc = subprocess.run(cmd, capture_output=True, timeout=120, **subprocess_text_kwargs())
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg fit failed:\n{proc.stderr or proc.stdout}")
    return output_wav_path


def change_wav_speed(
    *,
    input_wav_path: str,
    output_wav_path: str,
    speed_ratio: float,
) -> str:
    if not os.path.exists(input_wav_path):
        raise FileNotFoundError(f"Input wav not found: {input_wav_path}")

    ratio = max(0.01, float(speed_ratio))
    if abs(ratio - 1.0) < 0.02:
        return input_wav_path

    ffmpeg = _ffmpeg_path()
    if not os.path.exists(ffmpeg):
        raise FileNotFoundError(f"FFmpeg not found at {ffmpeg}")

    os.makedirs(os.path.dirname(output_wav_path) or ".", exist_ok=True)
    filter_chain = _build_atempo_filter(ratio)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        input_wav_path,
        "-filter:a",
        filter_chain,
        "-ar",
        "16000",
        "-ac",
        "1",
        output_wav_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=120, **subprocess_text_kwargs())
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg speed adjustment failed:\n{proc.stderr or proc.stdout}")
    return output_wav_path


def trim_trailing_silence(
    *,
    input_wav_path: str,
    output_wav_path: str,
    silence_threshold: float = -40.0,
    min_silence_duration: float = 0.5,
) -> str:
    """Remove trailing silence from a wav file using ffmpeg
    silencedetect. Keeps audio up to the last detected sound, then
    trims after a short padding. Returns output_wav_path if trimming
    was applied, or input_wav_path if the file has no trailing silence.
    """
    if not os.path.exists(input_wav_path):
        return input_wav_path
    ffmpeg = _ffmpeg_path()
    if not os.path.exists(ffmpeg):
        return input_wav_path
    os.makedirs(os.path.dirname(output_wav_path) or ".", exist_ok=True)
    detect_cmd = [
        ffmpeg, "-y", "-i", input_wav_path,
        "-af", f"silencedetect=noise={silence_threshold}dB:d={min_silence_duration}",
        "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(
            detect_cmd, capture_output=True, timeout=60,
            **subprocess_text_kwargs(),
        )
    except subprocess.TimeoutExpired:
        return input_wav_path
    if proc.returncode != 0:
        return input_wav_path

    last_end = 0.0
    for line in proc.stderr.splitlines():
        if "silence_end" in line:
            try:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "silence_end":
                        last_end = float(parts[i + 1])
                        break
            except (ValueError, IndexError):
                continue
    if last_end <= 0.0:
        return input_wav_path

    padding = 0.1
    trim_to = last_end + padding
    cmd = [
        ffmpeg, "-y", "-i", input_wav_path,
        "-t", str(trim_to),
        "-ar", "16000", "-ac", "1",
        output_wav_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=120, **subprocess_text_kwargs())
    if proc.returncode != 0:
        return input_wav_path
    return output_wav_path


def _require_pydub():
    try:
        ffmpeg = _ffmpeg_path()
        ffprobe = _ffprobe_path()
        ffmpeg_dir = os.path.dirname(ffmpeg)
        if ffmpeg_dir and os.path.isdir(ffmpeg_dir):
            current_path = os.environ.get("PATH", "")
            path_entries = current_path.split(os.pathsep) if current_path else []
            normalized_dir = os.path.normcase(os.path.normpath(ffmpeg_dir))
            normalized_entries = {
                os.path.normcase(os.path.normpath(entry))
                for entry in path_entries
                if entry
            }
            if normalized_dir not in normalized_entries:
                os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path if current_path else ffmpeg_dir

        from pydub import AudioSegment
        # Point pydub to our bundled ffmpeg to avoid PATH warnings on Windows.
        if os.path.exists(ffmpeg):
            AudioSegment.converter = ffmpeg
            AudioSegment.ffmpeg = ffmpeg
        if os.path.exists(ffprobe):
            AudioSegment.ffprobe = ffprobe
    except Exception as e:
        raise ImportError(
            "Missing dependency 'pydub'.\n"
            "Please run:\n"
            "python -m pip install pydub\n"
            f"Original error: {e}"
        ) from e


def _merge_ducking_ranges(
    *,
    segments: list,
    audio_length_ms: int,
    attack_ms: int,
    release_ms: int,
) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for seg in segments or []:
        try:
            start_ms = int(max(0.0, float(seg.get("start", 0.0))) * 1000.0)
            end_ms = int(max(0.0, float(seg.get("end", 0.0))) * 1000.0)
        except (TypeError, ValueError, AttributeError):
            continue
        if end_ms <= start_ms:
            continue
        duck_start = max(0, start_ms - max(0, attack_ms))
        duck_end = min(audio_length_ms, end_ms + max(0, release_ms))
        if duck_end <= duck_start:
            continue
        if not ranges or duck_start > ranges[-1][1]:
            ranges.append((duck_start, duck_end))
        else:
            prev_start, prev_end = ranges[-1]
            ranges[-1] = (prev_start, max(prev_end, duck_end))
    return ranges


def _apply_timeline_ducking(
    *,
    background_audio,
    ducking_ranges: list[tuple[int, int]],
    duck_amount_db: float,
    attack_ms: int,
    release_ms: int,
):
    if not ducking_ranges:
        return background_audio

    processed = background_audio
    for duck_start, duck_end in ducking_ranges:
        clip = processed[duck_start:duck_end]
        if len(clip) <= 0:
            continue

        attenuated = clip + float(duck_amount_db)
        fade_in_ms = min(max(0, attack_ms), len(attenuated))
        fade_out_ms = min(max(0, release_ms), len(attenuated))
        if fade_in_ms > 0:
            attenuated = attenuated.fade(from_gain=0.0, to_gain=float(duck_amount_db), start=0, duration=fade_in_ms)
        if fade_out_ms > 0:
            fade_out_start = max(0, len(attenuated) - fade_out_ms)
            attenuated = attenuated.fade(
                from_gain=float(duck_amount_db),
                to_gain=0.0,
                start=fade_out_start,
                duration=fade_out_ms,
            )
        processed = processed[:duck_start] + attenuated + processed[duck_end:]
    return processed


def build_voice_track_from_srt_segments(
    *,
    segments: list,
    tts_wav_paths: list,
    output_wav_path: str,
    total_duration_ms: int | None = None,
    gain_db: float = 0.0,
) -> str:
    """
    Build a single voice track by overlaying each segment wav at its start time.

    Optimized for long videos (>1-3 hours) using pre-allocated numpy audio buffer
    instead of repeated pydub AudioSegment.overlay() copies.
    """
    _require_pydub()
    from pydub import AudioSegment
    import numpy as np

    if len(segments) != len(tts_wav_paths):
        raise ValueError("segments and tts_wav_paths length mismatch")

    def _seg_val(s, key, default=0.0):
        if isinstance(s, dict):
            return s.get(key, default)
        return getattr(s, key, default)

    if total_duration_ms is None:
        max_end = 0.0
        for seg in segments:
            max_end = max(max_end, float(_seg_val(seg, "end", 0.0) or 0.0))
        total_duration_ms = int(max_end * 1000) + 500

    sr = 16000
    total_samples = int(max(0, total_duration_ms) * sr / 1000) + sr  # add 1s safety buffer
    audio_buffer = np.zeros(total_samples, dtype=np.int32)

    for idx, (seg, wav_path) in enumerate(zip(segments, tts_wav_paths)):
        if not wav_path or not os.path.exists(wav_path):
            continue
        start_ms = int(float(_seg_val(seg, "start", 0.0) or 0.0) * 1000)
        end_ms = int(float(_seg_val(seg, "end", 0.0) or 0.0) * 1000)
        max_len = max(0, end_ms - start_ms)

        try:
            clip = AudioSegment.from_file(wav_path)
            clip = clip.set_frame_rate(sr).set_channels(1)
            if gain_db:
                clip = clip + gain_db

            if max_len > 0:
                clip_len = len(clip)
                if clip_len < max_len:
                    gap_ms = max_len - clip_len
                    clip_end_ms = start_ms + clip_len
                    if idx + 1 < len(segments):
                        next_start_ms = int(float(_seg_val(segments[idx + 1], "start", 0.0) or 0.0) * 1000)
                        next_gap = next_start_ms - clip_end_ms
                        if 0 < next_gap <= 20:
                            overlap_ms = 10
                            extend_ms = min(next_gap + overlap_ms, clip_len)
                            clip = clip.fade_out(duration=extend_ms)
                            clip = clip + AudioSegment.silent(duration=extend_ms, frame_rate=sr)
                            gap_ms = 0
                    if gap_ms > 0:
                        fade_ms = min(gap_ms, 50)
                        clip = clip.fade_out(duration=fade_ms)
                        silent_ms = gap_ms - fade_ms
                        if silent_ms > 0:
                            clip = clip + AudioSegment.silent(duration=silent_ms, frame_rate=sr)

            clip_samples = np.frombuffer(clip.raw_data, dtype=np.int16)
            start_sample = int(max(0, start_ms) * sr / 1000)
            end_sample = start_sample + len(clip_samples)

            if end_sample > len(audio_buffer):
                # Dynamically expand buffer if needed
                pad = np.zeros(end_sample - len(audio_buffer) + sr, dtype=np.int32)
                audio_buffer = np.concatenate([audio_buffer, pad])

            # In-place add samples (mixing overlaps cleanly)
            audio_buffer[start_sample:end_sample] += clip_samples.astype(np.int32)
        except Exception as e:
            print(f"[audio_mixer] Error processing segment {idx} wav: {e}")

    # Clip to int16 range to prevent overflow distortion
    np.clip(audio_buffer, -32768, 32767, out=audio_buffer)
    final_pcm = audio_buffer.astype(np.int16).tobytes()

    os.makedirs(os.path.dirname(output_wav_path) or ".", exist_ok=True)
    with wave.open(output_wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(final_pcm)

    return output_wav_path


def mix_voice_with_background(
    *,
    background_wav_path: str,
    voice_wav_path: str,
    output_wav_path: str,
    background_gain_db: float = 0.0,
    voice_gain_db: float = 0.0,
    ducking_mode: str = "off",
    ducking_segments: list | None = None,
    ducking_amount_db: float = 0.0,
    ducking_threshold: float = 0.015,
    ducking_ratio: float = 10.0,
    ducking_attack_ms: float = 15.0,
    ducking_release_ms: float = 350.0,
) -> str:
    if not os.path.exists(background_wav_path):
        raise FileNotFoundError(f"Background file not found: {background_wav_path}")
    if not os.path.exists(voice_wav_path):
        raise FileNotFoundError(f"Voice file not found: {voice_wav_path}")

    mode_key = str(ducking_mode or "off").strip().lower()
    if mode_key in {"timeline", "segments", "subtitle"}:
        _require_pydub()
        from pydub import AudioSegment

        bg = AudioSegment.from_file(background_wav_path).set_frame_rate(16000).set_channels(1)
        vc = AudioSegment.from_file(voice_wav_path).set_frame_rate(16000).set_channels(1)

        if background_gain_db:
            bg = bg + background_gain_db
        if voice_gain_db:
            vc = vc + voice_gain_db

        if len(vc) > len(bg):
            bg = bg + AudioSegment.silent(duration=(len(vc) - len(bg)), frame_rate=16000)
        elif len(bg) > len(vc):
            vc = vc + AudioSegment.silent(duration=(len(bg) - len(vc)), frame_rate=16000)

        ducking_ranges = _merge_ducking_ranges(
            segments=list(ducking_segments or []),
            audio_length_ms=len(bg),
            attack_ms=int(max(0.0, float(ducking_attack_ms))),
            release_ms=int(max(0.0, float(ducking_release_ms))),
        )
        ducked_bg = _apply_timeline_ducking(
            background_audio=bg,
            ducking_ranges=ducking_ranges,
            duck_amount_db=float(ducking_amount_db),
            attack_ms=int(max(0.0, float(ducking_attack_ms))),
            release_ms=int(max(0.0, float(ducking_release_ms))),
        )

        mixed = ducked_bg.overlay(vc)
        os.makedirs(os.path.dirname(output_wav_path) or ".", exist_ok=True)
        mixed.export(output_wav_path, format="wav")
        return output_wav_path

    if mode_key in {"auto", "duck", "ducking", "sidechain"}:
        ffmpeg = _ffmpeg_path()
        if not os.path.exists(ffmpeg):
            raise FileNotFoundError(f"FFmpeg not found at {ffmpeg}")

        os.makedirs(os.path.dirname(output_wav_path) or ".", exist_ok=True)
        bg_volume = f"volume={float(background_gain_db):+.2f}dB"
        voice_volume = f"volume={float(voice_gain_db):+.2f}dB"
        filter_complex = (
            f"[0:a]{bg_volume}[bg];"
            f"[1:a]{voice_volume},asplit=2[vc_sc][vc_mix];"
            f"[bg][vc_sc]sidechaincompress="
            f"threshold={max(0.0001, float(ducking_threshold)):.4f}:"
            f"ratio={max(1.0, float(ducking_ratio)):.2f}:"
            f"attack={max(0.0, float(ducking_attack_ms)):.1f}:"
            f"release={max(0.0, float(ducking_release_ms)):.1f}:"
            f"makeup=1[ducked];"
            "[ducked][vc_mix]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[mixed]"
        )
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            background_wav_path,
            "-i",
            voice_wav_path,
            "-filter_complex",
            filter_complex,
            "-map",
            "[mixed]",
            "-ar",
            "16000",
            "-ac",
            "1",
            output_wav_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=300, **subprocess_text_kwargs())
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg ducking mix failed:\n{proc.stderr or proc.stdout}")
        return output_wav_path

    _require_pydub()
    from pydub import AudioSegment

    bg = AudioSegment.from_file(background_wav_path).set_frame_rate(16000).set_channels(1)
    vc = AudioSegment.from_file(voice_wav_path).set_frame_rate(16000).set_channels(1)

    if background_gain_db:
        bg = bg + background_gain_db
    if voice_gain_db:
        vc = vc + voice_gain_db

    # Ensure output covers the longer one
    if len(vc) > len(bg):
        bg = bg + AudioSegment.silent(duration=(len(vc) - len(bg)), frame_rate=16000)
    elif len(bg) > len(vc):
        vc = vc + AudioSegment.silent(duration=(len(bg) - len(vc)), frame_rate=16000)

    mixed = bg.overlay(vc)
    os.makedirs(os.path.dirname(output_wav_path) or ".", exist_ok=True)
    mixed.export(output_wav_path, format="wav")
    return output_wav_path


def mix_original_with_dub(
    *,
    original_wav_path: str,
    dub_wav_path: str,
    output_wav_path: str,
    original_gain_db: float = 0.0,
    dub_gain_db: float = 0.0,
) -> str:
    """Mix original audio (A1) with dub audio (A2) at specified gain levels."""
    if not os.path.exists(original_wav_path):
        raise FileNotFoundError(f"Original file not found: {original_wav_path}")
    if not os.path.exists(dub_wav_path):
        raise FileNotFoundError(f"Dub file not found: {dub_wav_path}")

    _require_pydub()
    from pydub import AudioSegment

    original = AudioSegment.from_file(original_wav_path).set_frame_rate(16000).set_channels(1)
    dub = AudioSegment.from_file(dub_wav_path).set_frame_rate(16000).set_channels(1)

    if original_gain_db:
        original = original + original_gain_db
    if dub_gain_db:
        dub = dub + dub_gain_db

    if len(dub) > len(original):
        original = original + AudioSegment.silent(duration=(len(dub) - len(original)), frame_rate=16000)
    elif len(original) > len(dub):
        dub = dub + AudioSegment.silent(duration=(len(original) - len(dub)), frame_rate=16000)

    mixed = original.overlay(dub)
    os.makedirs(os.path.dirname(output_wav_path) or ".", exist_ok=True)
    mixed.export(output_wav_path, format="wav")
    return output_wav_path

