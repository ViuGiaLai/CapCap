import os
import threading
import numpy as np
import scipy.io.wavfile as wavfile

_ENABLED = False
_recognizer = None
_current_model_dir = ""
_current_language = ""
_lock = threading.Lock()


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
                num_threads=4,
                use_itn=True,
                sense_voice_language=lang,
            )
        except TypeError:
            _recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=model_path,
                tokens=tokens_path,
                num_threads=4,
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
