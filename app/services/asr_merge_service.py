from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
from collections import Counter
from difflib import SequenceMatcher

from core.models import AudioChunk


_ASR_WORKER_MODEL = None


def _init_asr_worker(model_path: str) -> None:
    global _ASR_WORKER_MODEL
    from whisper_processor import load_whisper_model
    _ASR_WORKER_MODEL = load_whisper_model(model_path)


def _init_asr_cpu_worker(model_path: str) -> None:
    """Load an isolated CPU Whisper model in a process-pool worker."""
    os.environ["VIUSTUDIO_WHISPER_DEVICE"] = "cpu"
    _init_asr_worker(model_path)


def _transcribe_chunk_job(audio_path: str, language: str) -> list[dict]:
    global _ASR_WORKER_MODEL
    if _ASR_WORKER_MODEL is None:
        raise RuntimeError("ASR worker model is not initialized.")
    from whisper_processor import transcribe_audio_with_model
    return transcribe_audio_with_model(_ASR_WORKER_MODEL, audio_path, language=language)


class AsrMergeService:
    VERSION = "asr-merge-v7"
    DEFAULT_MAX_WORKERS = 3

    def _cache_key(self, *, chunk: AudioChunk, model_path: str, language: str, transcription_config: dict) -> str:
        payload = {
            "audio_path": os.path.abspath(chunk.audio_path),
            "chunk_start": round(float(chunk.start_seconds), 3),
            "chunk_end": round(float(chunk.end_seconds), 3),
            "speech_start": round(float(chunk.speech_start_seconds), 3),
            "speech_end": round(float(chunk.speech_end_seconds), 3),
            "model_path": str(model_path or ""),
            "language": str(language or "auto"),
            "config": dict(transcription_config or {}),
        }
        return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _cache_path(self, cache_dir: str, cache_key: str) -> str:
        return os.path.join(cache_dir, f"{cache_key}.json")

    def _load_cached_segments(self, cache_dir: str, cache_key: str):
        cache_path = self._cache_path(cache_dir, cache_key)
        if not os.path.exists(cache_path):
            return None
        try:
            with open(cache_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return list(payload.get("segments", []) or [])
        except Exception:
            return None

    def _save_cached_segments(self, cache_dir: str, cache_key: str, segments: list[dict]) -> None:
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = self._cache_path(cache_dir, cache_key)
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump({"segments": list(segments or [])}, handle, ensure_ascii=False, indent=2)

    def _normalize_text(self, text: str) -> str:
        value = str(text or "").strip().lower()
        value = re.sub(r"[^\w\s]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _similarity(self, left: str, right: str) -> float:
        left_normalized = self._normalize_text(left)
        right_normalized = self._normalize_text(right)
        if not left_normalized or not right_normalized:
            return 0.0
        return SequenceMatcher(None, left_normalized, right_normalized).ratio()

    @staticmethod
    def _lexical_units(text: str) -> list[str]:
        """Return stable comparison units without assuming one language.

        CJK ASR frequently mixes traditional/simplified characters and can
        corrupt the end of a phrase differently in adjacent chunks. Character
        units still retain enough shared anchors for a conservative boundary
        check. Space-delimited languages use whole words to avoid coincidental
        character matches.
        """
        value = str(text or "").strip().lower()
        cjk = re.findall(r"[\u3400-\u9fff\uf900-\ufaff]", value)
        if cjk:
            return cjk
        return re.findall(r"[\w]+", value, flags=re.UNICODE)

    def _lexical_coverage(self, left: str, right: str) -> tuple[float, int]:
        left_units = self._lexical_units(left)
        right_units = self._lexical_units(right)
        if not left_units or not right_units:
            return 0.0, 0
        common_count = sum((Counter(left_units) & Counter(right_units)).values())
        return common_count / max(1, min(len(left_units), len(right_units))), common_count

    def _segment_midpoint(self, segment: dict) -> float:
        return (float(segment.get("start", 0.0)) + float(segment.get("end", 0.0))) / 2.0

    def _midpoint_in_core(self, segment: dict, chunk: AudioChunk) -> bool:
        midpoint = self._segment_midpoint(segment)
        return float(chunk.core_start_seconds) <= midpoint <= float(chunk.core_end_seconds)

    def _time_overlap(self, left: dict, right: dict) -> float:
        start = max(float(left.get("start", 0.0)), float(right.get("start", 0.0)))
        end = min(float(left.get("end", 0.0)), float(right.get("end", 0.0)))
        return max(0.0, end - start)

    @staticmethod
    def _different_chunks(previous: dict, candidate: dict) -> bool:
        previous_chunk: AudioChunk = previous["chunk"]
        candidate_chunk: AudioChunk = candidate["chunk"]
        return (
            str(previous_chunk.chunk_id) != str(candidate_chunk.chunk_id)
            or abs(float(previous_chunk.start_seconds) - float(candidate_chunk.start_seconds)) > 0.001
        )

    def _is_boundary_leading_partial(
        self,
        previous: dict,
        candidate: dict,
        *,
        overlap: float,
        similarity: float,
    ) -> bool:
        """Detect a re-transcribed tail at the start of an overlap chunk.

        This deliberately requires independent timing, chunk-boundary and
        lexical evidence. Similar target-language subtitles alone are never
        enough because repeated dialogue can be intentional.
        """
        if not self._different_chunks(previous, candidate):
            return False

        previous_segment = previous["segment"]
        candidate_segment = candidate["segment"]
        previous_chunk: AudioChunk = previous["chunk"]
        candidate_chunk: AudioChunk = candidate["chunk"]
        if float(candidate_chunk.start_seconds) <= float(previous_chunk.start_seconds):
            return False
        if float(candidate_chunk.overlap_left_seconds) <= 0.0:
            return False

        candidate_start = float(candidate_segment.get("start", 0.0))
        candidate_end = float(candidate_segment.get("end", candidate_start))
        previous_start = float(previous_segment.get("start", 0.0))
        previous_end = float(previous_segment.get("end", previous_start))
        candidate_duration = max(0.0, candidate_end - candidate_start)
        previous_duration = max(0.0, previous_end - previous_start)
        if candidate_duration <= 0.0 or previous_duration <= 0.0:
            return False

        # The repeated tail must begin at the synthetic left edge of the new
        # chunk, not merely be a later similar sentence in that chunk.
        local_start = candidate_start - float(candidate_chunk.start_seconds)
        boundary_slop = max(0.15, float(candidate_chunk.overlap_left_seconds) * 0.35)
        if local_start < -0.02 or local_start > boundary_slop:
            return False
        if previous_start >= float(candidate_chunk.start_seconds) - 0.05:
            return False

        # It is a partial repeat only when most of the new cue reuses audio
        # already represented by the previous cue and adds at most a short
        # trailing timing error.
        if overlap < max(0.10, candidate_duration * 0.60):
            return False
        if candidate_duration > previous_duration * 1.10:
            return False
        if candidate_end - previous_end > max(0.50, candidate_duration * 0.40):
            return False

        coverage, common_count = self._lexical_coverage(
            previous_segment.get("text", ""), candidate_segment.get("text", "")
        )
        return similarity >= 0.55 or (common_count >= 2 and coverage >= 0.25)

    def _recommended_worker_count(self, pending_count: int) -> int:
        if pending_count <= 1:
            return 1
        cpu_count = max(1, os.cpu_count() or 1)
        return max(1, min(self.DEFAULT_MAX_WORKERS, pending_count, cpu_count))

    def _transcribe_chunks_parallel(
        self,
        pending_items: list[dict],
        *,
        cache_dir: str,
        model_path: str,
        language: str,
        on_item_done=None,
    ) -> None:
        worker_count = self._recommended_worker_count(len(pending_items))
        if worker_count <= 1:
            raise RuntimeError("Parallel ASR requested with only one pending chunk.")

        print(f"[ASR] Using process worker pool on CPU: workers={worker_count}, pending={len(pending_items)}")
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=worker_count,
            initializer=_init_asr_worker,
            initargs=(model_path,),
        ) as executor:
            future_map = {
                executor.submit(_transcribe_chunk_job, item["chunk"].audio_path, language): item
                for item in pending_items
            }
            for future in concurrent.futures.as_completed(future_map):
                item = future_map[future]
                segments = future.result()
                item["segments"] = list(segments or [])
                if cache_dir:
                    self._save_cached_segments(cache_dir, item["cache_key"], item["segments"])
                if on_item_done is not None:
                    on_item_done(item)

    def _transcribe_chunks_sequential(
        self,
        pending_items: list[dict],
        *,
        whisper_adapter,
        model_path: str,
        language: str,
        cache_dir: str,
        on_item_done=None,
    ) -> None:
        reusable_model = None
        try:
            if hasattr(whisper_adapter, "load_model"):
                reusable_model = whisper_adapter.load_model(model_path)
        except Exception:
            reusable_model = None

        print("[ASR] Pre-chunked audio uses standard Whisper inference (GPU batching disabled for accuracy).")
        for item in pending_items:
            chunk: AudioChunk = item["chunk"]
            if reusable_model is not None and hasattr(whisper_adapter, "transcribe_with_model"):
                segments = whisper_adapter.transcribe_with_model(
                    reusable_model,
                    chunk.audio_path,
                    language=language,
                    use_batched=False,
                )
            else:
                segments = whisper_adapter.transcribe(
                    chunk.audio_path,
                    model_path,
                    language=language,
                )
            item["segments"] = list(segments or [])
            if cache_dir:
                self._save_cached_segments(cache_dir, item["cache_key"], item["segments"])
            if on_item_done is not None:
                on_item_done(item)

    def _transcribe_chunks_hybrid(
        self,
        pending_items: list[dict],
        *,
        whisper_adapter,
        model_path: str,
        language: str,
        cache_dir: str,
        on_item_done=None,
    ) -> None:
        """Use one GPU model and one isolated CPU worker for long queues.

        GPU inference remains single-worker to protect VRAM. The CPU worker
        takes overflow items from the same queue; results still flow through
        the existing ordered callback/merge path.
        """
        queue = list(pending_items)
        try:
            reusable_model = whisper_adapter.load_model(model_path)
        except Exception:
            reusable_model = None

        def _complete(item: dict, segments) -> None:
            item["segments"] = list(segments or [])
            if cache_dir:
                self._save_cached_segments(cache_dir, item["cache_key"], item["segments"])
            if on_item_done is not None:
                on_item_done(item)

        print(f"[ASR] Hybrid long-video mode: 1 GPU worker + 1 CPU worker, pending={len(queue)}")
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=1,
            initializer=_init_asr_cpu_worker,
            initargs=(model_path,),
        ) as cpu_executor:
            cpu_futures = {}

            def _submit_cpu() -> None:
                if queue and not cpu_futures:
                    item = queue.pop(0)
                    future = cpu_executor.submit(_transcribe_chunk_job, item["chunk"].audio_path, language)
                    cpu_futures[future] = item

            _submit_cpu()
            while queue:
                # The GPU is the primary worker and processes one item at a
                # time. Harvest any completed CPU work between GPU chunks so
                # both workers draw dynamically from the same queue.
                gpu_item = queue.pop(0)
                chunk = gpu_item["chunk"]
                if reusable_model is not None and hasattr(whisper_adapter, "transcribe_with_model"):
                    gpu_segments = whisper_adapter.transcribe_with_model(
                        reusable_model, chunk.audio_path, language=language, use_batched=False
                    )
                else:
                    gpu_segments = whisper_adapter.transcribe(chunk.audio_path, model_path, language=language)
                _complete(gpu_item, gpu_segments)

                for future in list(cpu_futures):
                    if future.done():
                        item = cpu_futures.pop(future)
                        _complete(item, future.result())
                _submit_cpu()

            for future in concurrent.futures.as_completed(cpu_futures):
                item = cpu_futures[future]
                _complete(item, future.result())

    def transcribe_chunks(
        self,
        chunks: list[AudioChunk],
        *,
        whisper_adapter,
        model_path: str,
        language: str,
        cache_dir: str = "",
        transcription_config: dict | None = None,
        ordered_callback=None,
    ) -> list[dict]:
        results = []
        config_payload = dict(transcription_config or {})
        pending_items: list[dict] = []
        for index, chunk in enumerate(chunks):
            cache_key = self._cache_key(
                chunk=chunk,
                model_path=model_path,
                language=language,
                transcription_config=config_payload,
            )
            cached_segments = self._load_cached_segments(cache_dir, cache_key) if cache_dir else None
            from_cache = cached_segments is not None
            result = {
                "chunk": chunk,
                "segments": list(cached_segments or []),
                "cache_key": cache_key,
                "from_cache": from_cache,
                "_index": index,
                "_ready": from_cache,
            }
            results.append(result)
            if not from_cache:
                pending_items.append(result)

        next_emit_index = 0

        def _drain_ready() -> None:
            nonlocal next_emit_index
            if ordered_callback is None:
                return
            while next_emit_index < len(results) and results[next_emit_index].get("_ready"):
                ordered_callback(results[next_emit_index])
                next_emit_index += 1

        _drain_ready()

        if pending_items:
            used_parallel = False
            def _on_item_done(item: dict) -> None:
                item["_ready"] = True
                _drain_ready()
            try:
                from whisper_processor import _detect_faster_whisper_runtime
                runtime = _detect_faster_whisper_runtime()
                if runtime.get("device") == "cuda" and len(pending_items) > 1:
                    total_duration = max(float(item["chunk"].end_seconds) for item in pending_items)
                    hybrid_enabled = str(os.getenv("VIUSTUDIO_HYBRID_ASR", "1")).strip().lower() not in {"0", "false", "no", "off"}
                    hybrid_min_seconds = max(60.0, float(os.getenv("VIUSTUDIO_HYBRID_ASR_MIN_SECONDS", "1200") or 1200))
                    if hybrid_enabled and total_duration >= hybrid_min_seconds and len(pending_items) >= 4:
                        self._transcribe_chunks_hybrid(
                            pending_items,
                            whisper_adapter=whisper_adapter,
                            model_path=model_path,
                            language=language,
                            cache_dir=cache_dir,
                            on_item_done=_on_item_done,
                        )
                    else:
                        self._transcribe_chunks_sequential(
                            pending_items,
                            whisper_adapter=whisper_adapter,
                            model_path=model_path,
                            language=language,
                            cache_dir=cache_dir,
                            on_item_done=_on_item_done,
                        )
                    used_parallel = True
                elif len(pending_items) > 1:
                    self._transcribe_chunks_parallel(
                        pending_items,
                        cache_dir=cache_dir,
                        model_path=model_path,
                        language=language,
                        on_item_done=_on_item_done,
                    )
                    used_parallel = True
            except Exception as exc:
                print(f"[ASR] Parallel mode failed, falling back to sequential: {exc}")
            if not used_parallel:
                self._transcribe_chunks_sequential(
                    pending_items,
                    whisper_adapter=whisper_adapter,
                    model_path=model_path,
                    language=language,
                    cache_dir=cache_dir,
                    on_item_done=_on_item_done,
                )
        _drain_ready()
        for result in results:
            result.pop("_index", None)
            result.pop("_ready", None)
        return results

    def merge_chunk_results(self, chunk_results: list[dict]) -> list[dict]:
        merged_segments: list[dict] = []
        for chunk_result in chunk_results:
            chunk: AudioChunk = chunk_result["chunk"]
            for raw_segment in chunk_result.get("segments", []) or []:
                global_segment = {
                    "start": float(chunk.start_seconds) + float(raw_segment.get("start", 0.0)),
                    "end": float(chunk.start_seconds) + float(raw_segment.get("end", 0.0)),
                    "text": str(raw_segment.get("text", "") or "").strip(),
                    "words": [],
                    "chunk_id": chunk.chunk_id,
                }
                for key in ("language", "confidence", "speech_detected", "speech_gate"):
                    if key in raw_segment:
                        global_segment[key] = raw_segment[key]
                words = []
                for word in raw_segment.get("words", []) or []:
                    try:
                        words.append(
                            {
                                "start": float(chunk.start_seconds) + float(word.get("start", 0.0)),
                                "end": float(chunk.start_seconds) + float(word.get("end", 0.0)),
                                "text": str(word.get("text", "") or "").strip(),
                            }
                        )
                    except (TypeError, ValueError, AttributeError):
                        continue
                if words:
                    global_segment["words"] = words
                candidate = {
                    "segment": global_segment,
                    "chunk": chunk,
                }
                self._append_with_dedup(merged_segments, candidate)
        return self.normalize_segment_timeline([entry["segment"] for entry in merged_segments])

    @classmethod
    def _is_near_prefix(cls, full_norm: str, prefix_norm: str, min_chars: int = 2) -> bool:
        """Check if prefix_norm is a prefix or near-prefix of full_norm (allowing minor ASR variation)."""
        if not full_norm or not prefix_norm or len(prefix_norm) < min_chars:
            return False
        if full_norm.startswith(prefix_norm):
            return True
        # For short phrases (<= 6 chars), require exact prefix only to prevent false positives
        if len(prefix_norm) <= 6:
            return False
        k = len(prefix_norm)
        if len(full_norm) >= k:
            head = full_norm[:k]
            sim = SequenceMatcher(None, head, prefix_norm).ratio()
            if sim >= 0.88:
                return True
        return False

    @classmethod
    def _find_suffix_prefix_overlap(cls, left_text: str, right_text: str) -> tuple[int, str]:
        left = str(left_text or "").strip()
        right = str(right_text or "").strip()
        if not left or not right:
            return 0, ""

        left_norm = re.sub(r"[^\w]", "", left.lower())
        right_norm = re.sub(r"[^\w]", "", right.lower())
        if not left_norm or not right_norm:
            return 0, ""

        max_search = min(len(left_norm), len(right_norm))
        for k in range(max_search, 1, -1):
            suffix = left_norm[-k:]
            prefix = right_norm[:k]
            if suffix == prefix:
                return k, suffix
        return 0, ""

    @classmethod
    def _stitch_text(cls, left: str, right: str, overlap_norm_len: int) -> str:
        matched = 0
        right_cut_idx = len(right)
        for idx, char in enumerate(right):
            if re.match(r"\w", char):
                matched += 1
                if matched == overlap_norm_len:
                    right_cut_idx = idx + 1
                    break
        continuation = right[right_cut_idx:].strip()
        if not continuation:
            return left
        if left and left[-1] in "，, ":
            return f"{left}{continuation}".strip()
        elif re.search(r"[\u3400-\u9fff\uf900-\ufaff]", left):
            return f"{left}{continuation}".strip()
        else:
            return f"{left} {continuation}".strip()

    def _append_with_dedup(self, merged_entries: list[dict], candidate: dict) -> None:
        if not candidate["segment"]["text"]:
            return
        if not merged_entries:
            merged_entries.append(candidate)
            return

        previous = merged_entries[-1]
        previous_segment = previous["segment"]
        candidate_segment = candidate["segment"]
        overlap = self._time_overlap(previous_segment, candidate_segment)
        similarity = self._similarity(previous_segment.get("text", ""), candidate_segment.get("text", ""))

        prev_clean = self._normalize_text(previous_segment.get("text", ""))
        cand_clean = self._normalize_text(candidate_segment.get("text", ""))

        cand_start = float(candidate_segment.get("start", 0.0) or 0.0)
        prev_end = float(previous_segment.get("end", 0.0) or 0.0)

        same_chunk = not self._different_chunks(previous, candidate)
        if same_chunk:
            # Within the same chunk, do NOT merge or collapse adjacent dialogue
            # unless it is an exact/near-exact duplicate with substantial temporal overlap (ASR stutter loop)
            if overlap > 0.0:
                shorter_dur = min(
                    float(previous_segment.get("end", 0.0)) - float(previous_segment.get("start", 0.0)),
                    float(candidate_segment.get("end", 0.0)) - float(candidate_segment.get("start", 0.0)),
                )
                if similarity >= 0.95 and overlap >= max(0.20, shorter_dur * 0.80):
                    if float(candidate_segment.get("end", 0.0)) > float(previous_segment.get("end", 0.0)):
                        merged_entries[-1] = candidate
                    return
            merged_entries.append(candidate)
            return

        # DIFFERENT CHUNKS (chunk boundary reconciliation):
        # 1. Prefix-extension check on overlapping or touching chunks
        if overlap > 0.0 or (0.0 <= cand_start - prev_end <= 0.4):
            prev_old_end = float(previous_segment.get("end", 0.0) or 0.0)
            if self._is_near_prefix(cand_clean, prev_clean):
                merged_entries[-1] = candidate
                return
            if self._is_near_prefix(prev_clean, cand_clean):
                return

            # 2. Suffix-prefix chain overlap between adjacent chunks (e.g. A+B in Chunk 1, B+C in Chunk 2)
            overlap_len, _ = self._find_suffix_prefix_overlap(
                previous_segment.get("text", ""), candidate_segment.get("text", "")
            )
            if overlap_len >= 2:
                prev_raw = str(previous_segment.get("text", "") or "").strip()
                cand_raw = str(candidate_segment.get("text", "") or "").strip()
                stitched = self._stitch_text(prev_raw, cand_raw, overlap_len)
                previous_segment["text"] = stitched
                previous_segment["end"] = max(float(previous_segment.get("end", 0.0)), float(candidate_segment.get("end", 0.0)))
                if candidate_segment.get("words"):
                    prev_words = previous_segment.get("words", []) or []
                    cand_words = [
                        w for w in (candidate_segment.get("words") or [])
                        if float(w.get("start", 0.0)) >= prev_old_end - 0.05
                    ]
                    previous_segment["words"] = prev_words + cand_words
                return

        if overlap <= 0.0:
            merged_entries.append(candidate)
            return

        previous_in_core = self._midpoint_in_core(previous_segment, previous["chunk"])
        candidate_in_core = self._midpoint_in_core(candidate_segment, candidate["chunk"])
        previous_duration = max(0.0, float(previous_segment["end"]) - float(previous_segment["start"]))
        candidate_duration = max(0.0, float(candidate_segment["end"]) - float(candidate_segment["start"]))

        # A time overlap alone is not enough: speakers can overlap and an
        # ASR engine can legitimately emit adjacent partial phrases with
        # intersecting timestamps. Only collapse a chunk-boundary duplicate
        # when most of the shorter cue overlaps and its text is essentially
        # identical after normalization.
        shorter_duration = min(previous_duration, candidate_duration)
        substantial_overlap = overlap >= max(0.10, shorter_duration * 0.60)
        is_boundary_duplicate = substantial_overlap and similarity >= 0.92
        is_boundary_partial = self._is_boundary_leading_partial(
            previous,
            candidate,
            overlap=overlap,
            similarity=similarity,
        )
        if not is_boundary_duplicate and not is_boundary_partial:
            merged_entries.append(candidate)
            return

        if is_boundary_partial:
            print(
                "[ASR] Removed duplicated leading fragment at chunk boundary: "
                f"chunk={candidate['chunk'].chunk_id}, "
                f"chars={len(str(candidate_segment.get('text', '') or ''))}"
            )
            # Timing and lexical evidence identify the candidate specifically
            # as the shorter re-transcribed tail; keep the fuller previous cue
            # even if its midpoint falls just outside the previous core.
            return

        if previous_in_core != candidate_in_core:
            if candidate_in_core:
                merged_entries[-1] = candidate
            return

        if candidate_duration > previous_duration:
            merged_entries[-1] = candidate

    def normalize_segment_timeline(self, segments: list[dict]) -> list[dict]:
        """Ensure segments have valid non-negative durations and resolve sub-frame rounding jitter.

        Genuine multi-speaker / overlapping dialogue (> 0.15s) preserves its true
        detected speech boundaries without accumulating cascading time drift.
        """
        normalized: list[dict] = []
        previous_end = 0.0
        for segment in segments or []:
            current = dict(segment)
            start = float(current.get("start", 0.0) or 0.0)
            end = float(current.get("end", 0.0) or 0.0)
            if end <= start:
                end = start + 0.12

            shift = 0.0
            # Sub-frame jitter resolution (<= 0.15s, e.g. 1-2 frames rounding jitter)
            if 0.0 < previous_end - start <= 0.15:
                shift = previous_end - start
                start = previous_end
                if end <= start:
                    end = start + 0.12

            current["start"] = round(start, 3)
            current["end"] = round(max(start + 0.12, end), 3)
            if current.get("words"):
                adjusted_words = []
                for word in current.get("words") or []:
                    try:
                        word_start = float(word.get("start", start) or start) + shift
                        word_end = float(word.get("end", word_start) or word_start) + shift
                        word_start = max(word_start, current["start"])
                        word_end = min(max(word_start, word_end), current["end"])
                        adjusted_words.append({
                            "start": round(word_start, 3),
                            "end": round(word_end, 3),
                            "text": str(word.get("text", "") or "").strip(),
                        })
                    except (TypeError, ValueError, AttributeError):
                        continue
                current["words"] = adjusted_words
            normalized.append(current)
            previous_end = max(previous_end, current["end"])
        return normalized
