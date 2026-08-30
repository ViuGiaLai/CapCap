"""Reproducible synthetic benchmark for CapCap projects lasting 1-5 hours."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import struct
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "app")]

from app.audio_mixer import build_voice_track_from_srt_segments, mix_original_with_dub, voice_track_storage_plan
from app.audio_waveform import build_waveform_envelope
from app.translation.orchestrator import TranslationOrchestrator


def _working_set_mb() -> tuple[float, float]:
    if os.name != "nt":
        return 0.0, 0.0

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    scale = 1024.0 * 1024.0
    return counters.WorkingSetSize / scale, counters.PeakWorkingSetSize / scale


def _create_sparse_pcm_wav(path: str, hours: int, sample_rate: int = 16000) -> None:
    frames = int(hours * 3600 * sample_rate)
    data_size = frames * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + data_size, b"WAVE", b"fmt ",
        16, 1, 1, sample_rate, sample_rate * 2, 2, 16, b"data", data_size,
    )
    with open(path, "wb") as handle:
        handle.write(header)
        handle.truncate(44 + data_size)
        for index in range(1200):
            frame = min(frames - 1, int(index * frames / 1200))
            handle.seek(44 + frame * 2)
            handle.write(struct.pack("<h", 12000))


def run(hours_to_test: list[int], write_voice_hours: int, mix_hours: int) -> dict:
    report = {"waveform": [], "translation_planning": [], "voice_track": None, "audio_mix": None}
    with tempfile.TemporaryDirectory(prefix="capcap_long_media_") as temp_dir:
        for hours in hours_to_test:
            wav_path = os.path.join(temp_dir, f"sparse_{hours}h.wav")
            _create_sparse_pcm_wav(wav_path, hours)
            before, _ = _working_set_mb()
            started = time.perf_counter()
            waveform, duration = build_waveform_envelope(wav_path)
            elapsed = time.perf_counter() - started
            current, peak = _working_set_mb()
            report["waveform"].append({
                "hours": hours, "duration_seconds": round(duration, 3), "buckets": len(waveform),
                "seconds": round(elapsed, 3), "working_set_before_mb": round(before, 1),
                "working_set_after_mb": round(current, 1), "process_peak_mb": round(peak, 1),
            })
            cue_count = hours * 1800
            cues = [f"Dialogue cue {index}: context-aware subtitle text." for index in range(cue_count)]
            started = time.perf_counter()
            batches, full_context = TranslationOrchestrator._build_ai_batches(
                source_texts=cues, translated_texts=None, requested_max_segments=80,
            )
            report["translation_planning"].append({
                "hours": hours, "cues": cue_count, "batches": len(batches),
                "full_context": full_context,
                "seconds": round(time.perf_counter() - started, 3),
            })
        if write_voice_hours > 0:
            output = os.path.join(temp_dir, f"voice_{write_voice_hours}h.wav")
            before, _ = _working_set_mb()
            started = time.perf_counter()
            build_voice_track_from_srt_segments(
                segments=[], tts_wav_paths=[], output_wav_path=output,
                total_duration_ms=write_voice_hours * 3600 * 1000,
            )
            elapsed = time.perf_counter() - started
            current, peak = _working_set_mb()
            report["voice_track"] = {
                "hours": write_voice_hours, "seconds": round(elapsed, 3),
                "output_mb": round(os.path.getsize(output) / 1024 / 1024, 1),
                "working_set_before_mb": round(before, 1), "working_set_after_mb": round(current, 1),
                "process_peak_mb": round(peak, 1),
                "storage_plan": voice_track_storage_plan(write_voice_hours * 3600),
            }
        if mix_hours > 0:
            first = os.path.join(temp_dir, f"mix_first_{mix_hours}h.wav")
            second = os.path.join(temp_dir, f"mix_second_{mix_hours}h.wav")
            output = os.path.join(temp_dir, f"mix_output_{mix_hours}h.wav")
            _create_sparse_pcm_wav(first, mix_hours)
            _create_sparse_pcm_wav(second, mix_hours)
            before, _ = _working_set_mb()
            started = time.perf_counter()
            mix_original_with_dub(original_wav_path=first, dub_wav_path=second, output_wav_path=output)
            elapsed = time.perf_counter() - started
            current, peak = _working_set_mb()
            report["audio_mix"] = {
                "hours": mix_hours, "seconds": round(elapsed, 3),
                "output_mb": round(os.path.getsize(output) / 1024 / 1024, 1),
                "working_set_before_mb": round(before, 1), "working_set_after_mb": round(current, 1),
                "process_peak_mb": round(peak, 1),
            }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", nargs="+", type=int, default=[1, 2, 3, 5])
    parser.add_argument("--write-voice-hours", type=int, default=0)
    parser.add_argument("--mix-hours", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(run(args.hours, args.write_voice_hours, args.mix_hours), indent=2))
