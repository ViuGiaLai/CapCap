"""Memory-bounded waveform extraction for long PCM WAV files."""

from __future__ import annotations

import math
import wave


def build_waveform_envelope(
    wav_path: str,
    *,
    max_buckets: int = 1200,
    min_buckets: int = 240,
) -> tuple[list[float], float]:
    """Return a normalized peak/RMS envelope without loading the whole WAV."""
    import numpy as np

    with wave.open(wav_path, "rb") as audio_file:
        frame_count = int(audio_file.getnframes())
        sample_rate = max(1, int(audio_file.getframerate()))
        channels = max(1, int(audio_file.getnchannels()))
        sample_width = int(audio_file.getsampwidth())
        duration_s = max(0.0, frame_count / sample_rate)
        if frame_count <= 0:
            return [], duration_s

        bucket_count = min(
            max(1, int(max_buckets)),
            max(1, int(min_buckets), round(duration_s * 12.0)),
            frame_count,
        )
        frames_per_bucket = max(1, int(math.ceil(frame_count / bucket_count)))
        raw_values: list[float] = []
        global_peak = 0.0

        for _index in range(bucket_count):
            raw = audio_file.readframes(frames_per_bucket)
            if not raw:
                break
            if sample_width == 1:
                samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0
            elif sample_width == 2:
                samples = np.frombuffer(raw, dtype="<i2").astype(np.float32)
            elif sample_width == 4:
                samples = np.frombuffer(raw, dtype="<i4").astype(np.float32)
            else:
                raise ValueError(f"Unsupported PCM sample width: {sample_width}")
            if channels > 1:
                usable = samples.size - (samples.size % channels)
                samples = samples[:usable].reshape(-1, channels).mean(axis=1)
            if not samples.size:
                raw_values.append(0.0)
                continue
            absolute = np.abs(samples)
            peak = float(np.max(absolute))
            rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
            global_peak = max(global_peak, peak)
            raw_values.append(max(peak, rms * 1.15))

    if global_peak <= 0.0:
        return [], duration_s
    return [
        min(1.0, max(0.03, (value / global_peak) ** 0.85))
        for value in raw_values
    ], duration_s
