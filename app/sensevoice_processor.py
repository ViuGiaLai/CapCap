import os
import threading
import numpy as np
import scipy.io.wavfile as wavfile

_ENABLED = False
_recognizer = None
_current_model_dir = ""
_current_language = ""
_lock = threading.Lock()
_SUPPORTED_LANGUAGE_CODES = {"auto", "zh", "yue", "en", "ja", "ko"}


def _sensevoice_thread_count() -> int:
    """Use the available CPU without making the desktop unresponsive."""
    configured = str(os.getenv("VIUSTUDIO_ASR_THREADS", "") or "").strip()
    if configured:
        try:
            return max(1, min(16, int(configured)))
        except ValueError:
            pass
    logical_cpus = int(os.cpu_count() or 4)
    return max(2, min(8, logical_cpus - 2 if logical_cpus > 4 else logical_cpus))


def is_available() -> bool:
    global _ENABLED
    if _ENABLED:
        return True
    try:
        import sherpa_onnx
        _ENABLED = True
    except ImportError:
        _ENABLED = False
    return _ENABLED


def supports_language(code: str) -> bool:
    normalized = str(code or "auto").strip().lower().split("-")[0]
    return normalized in _SUPPORTED_LANGUAGE_CODES


def requires_multilingual_whisper(code: str) -> bool:
    normalized = str(code or "auto").strip().lower().split("-")[0]
    # SenseVoice can auto-detect only among its own small language set. The
    # application's Auto Detect promises all source languages, so Whisper is
    # the accurate choice when the language is unknown.
    return normalized in {"", "auto"} or not supports_language(normalized)


def _lang_code(code: str) -> str:
    if not code or code in ("auto", ""):
        return "auto"
    # SenseVoice does not have a Vietnamese language lock. Mapping Vietnamese
    # to Chinese forces the wrong decoder vocabulary; automatic detection is
    # safer for unsupported languages.
    m = {"vi": "auto", "en": "en", "ja": "ja", "ko": "ko", "zh": "zh", "yue": "yue"}
    return m.get(code.split("-")[0].strip().lower(), "auto")


def _pad_and_merge_vad_segments(
    segments: list[dict],
    audio_duration: float,
    *,
    merge_gap: float = 0.18,
    start_padding: float = 0.22,
    end_padding: float = 0.18,
) -> list[dict]:
    """Keep short word onsets from being clipped by hard VAD boundaries."""
    ordered = []
    for segment in segments or []:
        start = max(0.0, float(segment.get("start", 0.0) or 0.0))
        end = min(float(audio_duration), float(segment.get("end", start) or start))
        if end > start:
            ordered.append([start, end])
    ordered.sort(key=lambda value: value[0])
    merged: list[list[float]] = []
    for start, end in ordered:
        if merged and start - merged[-1][1] <= merge_gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    padded = []
    for index, (start, end) in enumerate(merged):
        padded_start = max(0.0, start - start_padding)
        padded_end = min(float(audio_duration), end + end_padding)
        if index and padded_start < padded[-1]["end"]:
            boundary = (start + merged[index - 1][1]) * 0.5
            padded[-1]["end"] = min(padded[-1]["end"], boundary)
            padded_start = max(padded_start, boundary)
        if padded_end > padded_start:
            padded.append({"start": round(padded_start, 3), "end": round(padded_end, 3)})
    return padded


def load_model(model_dir: str, language: str = "auto"):
    global _recognizer, _current_model_dir, _current_language
    import sherpa_onnx

    lang = _lang_code(language)
    with _lock:
        if _recognizer is not None and _current_model_dir == model_dir and _current_language == lang:
            return
        tokens_path = os.path.join(model_dir, "tokens.txt")
        if not os.path.exists(tokens_path):
            raise FileNotFoundError(f"SenseVoice tokens not found: {tokens_path}")
        onnx_files = [f for f in os.listdir(model_dir) if f.endswith(".onnx")]
        if not onnx_files:
            raise FileNotFoundError(f"No .onnx model found in {model_dir}")
        pref = "model.int8.onnx" if "model.int8.onnx" in onnx_files else onnx_files[0]
        model_path = os.path.join(model_dir, pref)

        try:
            _recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=model_path,
                tokens=tokens_path,
                num_threads=_sensevoice_thread_count(),
                use_itn=True,
                sense_voice_language=lang,
            )
        except TypeError:
            _recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=model_path,
                tokens=tokens_path,
                num_threads=_sensevoice_thread_count(),
                use_itn=True,
            )
        _current_model_dir = model_dir
        _current_language = lang


def transcribe_audio(audio_path: str, model_dir: str, *, language: str = "auto") -> list[dict]:
    import sherpa_onnx

    load_model(model_dir, language=language)
    sr, audio = wavfile.read(audio_path)
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32) / 32768.0
    if sr != 16000:
        from scipy.signal import resample
        target_len = int(len(audio) * 16000 / sr)
        audio = resample(audio, target_len)

    from vad_processor import get_speech_segments

    segments = _pad_and_merge_vad_segments(
        get_speech_segments(audio, 16000),
        float(len(audio)) / 16000.0,
    )
    results = []
    for seg in segments:
        start_s = int(seg["start"] * 16000)
        end_s = int(seg["end"] * 16000)
        chunk = audio[start_s:end_s]
        # Do not discard short VAD turns here. A short acknowledgement may
        # be a complete, valid subtitle; the recognizer decides whether it
        # can produce text from the audio.
        if len(chunk) == 0:
            continue

        stream = _recognizer.create_stream()
        stream.accept_waveform(16000, chunk)
        _recognizer.decode_stream(stream)
        text = stream.result.text.strip()
        if text:
            results.append({
                "start": round(seg["start"], 3),
                "end": round(seg["end"], 3),
                "text": text,
            })

    if not results:
        stream = _recognizer.create_stream()
        stream.accept_waveform(16000, audio)
        _recognizer.decode_stream(stream)
        text = stream.result.text.strip()
        if text:
            duration = float(len(audio)) / 16000.0
            results.append({"start": 0.0, "end": round(duration, 3), "text": text})

    return results


def transcribe_presegmented_audio_batch(
    audio_paths: list[str],
    model_dir: str,
    *,
    language: str = "auto",
    batch_size: int | None = None,
    progress_callback=None,
) -> list[list[dict]]:
    """Decode speech-focused WAV chunks in batches with one loaded model.

    ``ChunkingService`` has already applied VAD and bounded these files, so
    running Silero VAD again for every file only duplicates work.  Sherpa's
    multi-stream decoder lets the ONNX runtime use its worker threads across
    several chunks while preserving one result list per input file.
    """
    load_model(model_dir, language=language)
    paths = [str(path) for path in (audio_paths or [])]
    if not paths:
        return []
    size = max(1, min(16, int(batch_size or _sensevoice_thread_count())))
    all_results: list[list[dict]] = []

    for batch_start in range(0, len(paths), size):
        batch_paths = paths[batch_start:batch_start + size]
        streams = []
        durations = []
        for audio_path in batch_paths:
            sr, audio = wavfile.read(audio_path)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if audio.dtype != np.float32:
                if np.issubdtype(audio.dtype, np.integer):
                    scale = float(max(abs(np.iinfo(audio.dtype).min), np.iinfo(audio.dtype).max))
                    audio = audio.astype(np.float32) / scale
                else:
                    audio = audio.astype(np.float32)
            if sr != 16000:
                from scipy.signal import resample
                audio = resample(audio, int(len(audio) * 16000 / sr)).astype(np.float32)
            audio = np.ascontiguousarray(audio, dtype=np.float32)
            stream = _recognizer.create_stream()
            stream.accept_waveform(16000, audio)
            streams.append(stream)
            durations.append(float(len(audio)) / 16000.0)

        if hasattr(_recognizer, "decode_streams"):
            _recognizer.decode_streams(streams)
        else:
            for stream in streams:
                _recognizer.decode_stream(stream)

        for stream, duration in zip(streams, durations):
            text = str(stream.result.text or "").strip()
            all_results.append(
                [{"start": 0.0, "end": round(duration, 3), "text": text}] if text else []
            )
        if progress_callback is not None:
            progress_callback(min(batch_start + len(batch_paths), len(paths)), len(paths))

    return all_results
