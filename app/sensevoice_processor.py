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
    """Keep decode padding separate from the real speech timeline.

    ``start``/``end`` remain the padded decode window so recognition does not
    clip consonants. ``speech_start``/``speech_end`` are the unpadded VAD
    bounds and must be used for subtitle timestamps.
    """
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
            padded.append({
                "start": round(padded_start, 3),
                "end": round(padded_end, 3),
                "speech_start": round(start, 3),
                "speech_end": round(end, 3),
            })
    return padded


def _read_mono_16k(audio_path: str) -> np.ndarray:
    """Read a WAV as contiguous mono float32 audio at 16 kHz."""
    sr, audio = wavfile.read(audio_path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if audio.dtype != np.float32:
        if np.issubdtype(audio.dtype, np.integer):
            info = np.iinfo(audio.dtype)
            scale = float(max(abs(info.min), info.max))
            audio = audio.astype(np.float32) / scale
        else:
            audio = audio.astype(np.float32)
    if sr != 16000:
        from scipy.signal import resample
        audio = resample(audio, int(len(audio) * 16000 / sr)).astype(np.float32)
    return np.ascontiguousarray(audio, dtype=np.float32)


def _detect_speech_segments(audio: np.ndarray) -> list[dict]:
    """Run the speech VAD used as the mandatory SenseVoice input gate."""
    from vad_processor import get_speech_segments

    return _pad_and_merge_vad_segments(
        get_speech_segments(audio, 16000),
        float(len(audio)) / 16000.0,
    )


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
    load_model(model_dir, language=language)
    audio = _read_mono_16k(audio_path)
    segments = _detect_speech_segments(audio)
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
                "start": round(float(seg.get("speech_start", seg["start"])), 3),
                "end": round(float(seg.get("speech_end", seg["end"])), 3),
                "text": text,
                "speech_detected": True,
                "speech_gate": "silero_vad",
            })

    return results


def transcribe_presegmented_audio_batch(
    audio_paths: list[str],
    model_dir: str,
    *,
    language: str = "auto",
    batch_size: int | None = None,
    progress_callback=None,
) -> list[list[dict]]:
    """VAD-gate every chunk, then batch-decode only real speech regions.

    ``ChunkingService`` uses FFmpeg amplitude silence detection to make files;
    background music and effects can therefore remain in a chunk.  It is not
    a speech detector.  Silero VAD is mandatory here so silent/non-speech
    spans cannot produce SenseVoice hallucinations.  The resulting VAD bounds
    are also the real local timestamps; no text-proportional timing is used.
    """
    load_model(model_dir, language=language)
    paths = [str(path) for path in (audio_paths or [])]
    if not paths:
        return []
    size = max(1, min(16, int(batch_size or _sensevoice_thread_count())))
    all_results: list[list[dict]] = [[] for _ in paths]
    work_items: list[dict] = []
    last_work_index_by_file: dict[int, int] = {}
    files_without_speech = set()

    for file_index, audio_path in enumerate(paths):
        audio = _read_mono_16k(audio_path)
        speech_segments = _detect_speech_segments(audio)
        if progress_callback is not None:
            progress_callback(file_index + 1, len(paths) * 2)
        if not speech_segments:
            files_without_speech.add(file_index)
            continue
        for segment in speech_segments:
            start_sample = max(0, int(round(float(segment["start"]) * 16000)))
            end_sample = min(len(audio), int(round(float(segment["end"]) * 16000)))
            if end_sample <= start_sample:
                continue
            work_items.append({
                "file_index": file_index,
                "start": round(float(segment.get("speech_start", start_sample / 16000.0)), 3),
                "end": round(float(segment.get("speech_end", end_sample / 16000.0)), 3),
                "audio": audio[start_sample:end_sample],
            })
            last_work_index_by_file[file_index] = len(work_items) - 1
        if file_index not in last_work_index_by_file:
            files_without_speech.add(file_index)

    reported_done = -1
    for batch_start in range(0, len(work_items), size):
        batch_items = work_items[batch_start:batch_start + size]
        streams = []
        for item in batch_items:
            stream = _recognizer.create_stream()
            stream.accept_waveform(16000, item["audio"])
            streams.append(stream)

        if hasattr(_recognizer, "decode_streams"):
            _recognizer.decode_streams(streams)
        else:
            for stream in streams:
                _recognizer.decode_stream(stream)

        for stream, item in zip(streams, batch_items):
            text = str(stream.result.text or "").strip()
            if text:
                all_results[item["file_index"]].append({
                    "start": item["start"],
                    "end": item["end"],
                    "text": text,
                    "speech_detected": True,
                    "speech_gate": "silero_vad",
                })
        if progress_callback is not None:
            processed_work = batch_start + len(batch_items) - 1
            completed_files = len(files_without_speech) + sum(
                1 for last_index in last_work_index_by_file.values()
                if last_index <= processed_work
            )
            completed_files = min(completed_files, len(paths))
            if completed_files != reported_done:
                progress_callback(len(paths) + completed_files, len(paths) * 2)
                reported_done = completed_files

    if progress_callback is not None and reported_done != len(paths):
        progress_callback(len(paths) * 2, len(paths) * 2)

    return all_results
