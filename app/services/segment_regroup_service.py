from __future__ import annotations

import re
from math import ceil
from difflib import SequenceMatcher


class SegmentRegroupService:
    VERSION = "segment-regroup-v3"

    def regroup(self, segments: list[dict], *, max_gap_seconds: float = 0.35, max_duration_seconds: float = 8.0) -> list[dict]:
        # Step 1: Deduplicate & stitch boundary overlapping segments on the whole cues first
        deduped = self.deduplicate_and_clamp_timeline(segments)

        # Step 2: Split oversized segments (> 8.0s) on clean, unified sentences
        regrouped: list[dict] = []
        for segment in deduped or []:
            text = str(segment.get("text", "") or "").strip()
            if not text:
                continue
            regrouped.extend(
                self._split_oversized_segment(
                    segment,
                    max_duration_seconds=max_duration_seconds,
                )
            )

        normalized = []
        for index, segment in enumerate(regrouped, start=1):
            payload = self._clone_segment(segment)
            payload["id"] = index
            payload["text"] = self._normalize_sentence_text(payload.get("text", ""))
            normalized.append(payload)
        return normalized

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

    @classmethod
    def deduplicate_and_clamp_timeline(
        cls,
        segments: list[dict],
        *,
        min_gap_seconds: float = 0.02,
        similarity_threshold: float = 0.85,
    ) -> list[dict]:
        """Remove duplicate, near-duplicate, and prefix/suffix overlapping cues,

        and enforce clean non-overlapping timeline boundaries.
        """
        if not segments:
            return []

        cleaned: list[dict] = []
        for raw in segments:
            text = str(raw.get("text", "") or "").strip()
            if not text:
                continue
            start = float(raw.get("start", 0.0) or 0.0)
            end = max(start + 0.1, float(raw.get("end", start) or start))
            item = dict(raw)
            item["start"] = start
            item["end"] = end
            item["text"] = text

            if not cleaned:
                cleaned.append(item)
                continue

            prev = cleaned[-1]
            prev_text = prev["text"].strip()
            item_text = item["text"].strip()

            prev_norm = re.sub(r"[^\w]", "", prev_text.lower())
            item_norm = re.sub(r"[^\w]", "", item_text.lower())

            overlap = max(0.0, min(prev["end"], item["end"]) - max(prev["start"], item["start"]))
            time_gap = item["start"] - prev["end"]

            # Check for duplication / prefix-containment if they overlap or are very close (gap < 0.5s)
            if overlap > 0.0 or time_gap < 0.5:
                # Case 1: Exact or near-exact duplicate (>= similarity_threshold)
                sim = SequenceMatcher(None, prev_norm, item_norm).ratio() if prev_norm and item_norm else 0.0
                if sim >= similarity_threshold:
                    if (item["end"] - item["start"]) > (prev["end"] - prev["start"]):
                        cleaned[-1] = item
                    continue

                prev_old_end = float(prev.get("end", 0.0) or 0.0)
                # Case 2: item is an extension/completion of prev (fuzzy prefix)
                if cls._is_near_prefix(item_norm, prev_norm):
                    cleaned[-1] = item
                    continue

                # Case 3: prev is an extension of item (fuzzy prefix)
                if cls._is_near_prefix(prev_norm, item_norm):
                    continue

                # Case 4: Suffix-prefix overlap (end of prev is start of item) -> STITCH, not just clamp!
                if overlap > 0.15 or (0.0 <= item["start"] - prev["end"] <= 0.3):
                    overlap_len, _ = cls._find_suffix_prefix_overlap(prev_text, item_text)
                    if overlap_len >= 2:
                        stitched_text = cls._stitch_text(prev_text, item_text, overlap_len)
                        prev["text"] = stitched_text
                        prev["end"] = max(float(prev["end"]), float(item["end"]))
                        if item.get("words"):
                            prev["words"] = list(prev.get("words") or []) + [
                                w for w in (item.get("words") or [])
                                if float(w.get("start", 0.0)) >= prev_old_end - 0.05
                            ]
                        continue  # Merged into prev, do NOT append item separately

            # Only adjust minor sub-frame rounding jitter (<= 0.15s) without truncating genuine dialogue
            if 0.0 < overlap <= 0.15:
                prev["end"] = max(prev["start"] + 0.1, item["start"] - min_gap_seconds)
                if prev.get("words"):
                    for w in prev["words"]:
                        if float(w.get("end", 0.0)) > prev["end"]:
                            w["end"] = round(prev["end"], 3)

            cleaned.append(item)

        return cleaned

    def _split_oversized_segment(
        self,
        segment: dict,
        *,
        max_duration_seconds: float,
    ) -> list[dict]:
        """Keep ASR boundaries unless one cue is too long for dialogue/TTS.

        Whisper word timestamps are authoritative when available. Engines
        without word timing (notably SenseVoice) use sentence boundaries and
        finally a proportional text/time split. The fallback is deliberately
        limited to oversized cues; short acknowledgements are never merged or
        rewritten.
        """
        payload = self._clone_segment(segment)
        start = float(payload.get("start", 0.0))
        end = max(start, float(payload.get("end", start)))
        limit = max(0.5, float(max_duration_seconds or 0.0))
        if end - start <= limit + 0.01:
            return [payload]

        words = self._valid_words(payload.get("words"), start=start, end=end)
        if words:
            pieces = self._split_by_words(payload, words, limit=limit)
            if len(pieces) > 1:
                return pieces
        return self._split_text_proportionally(payload, limit=limit)

    @staticmethod
    def _valid_words(words, *, start: float, end: float) -> list[dict]:
        valid: list[dict] = []
        for word in words or []:
            try:
                word_start = max(start, float(word.get("start", start)))
                word_end = min(end, max(word_start, float(word.get("end", word_start))))
            except (AttributeError, TypeError, ValueError):
                continue
            text = str(word.get("text", word.get("word", "")) or "").strip()
            if text and word_end >= word_start:
                valid.append({"start": word_start, "end": word_end, "text": text})
        return sorted(valid, key=lambda item: (item["start"], item["end"]))

    def _split_by_words(self, payload: dict, words: list[dict], *, limit: float) -> list[dict]:
        groups: list[list[dict]] = []
        current: list[dict] = []
        group_start = float(payload["start"])
        for word in words:
            if current and float(word["end"]) - group_start > limit:
                groups.append(current)
                current = []
                group_start = float(word["start"])
            if not current:
                group_start = float(word["start"])
            current.append(word)
            if re.search(r"[.!?\u3002\uff01\uff1f\uff1b;]\s*$", str(word["text"])):
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        if len(groups) <= 1:
            return []

        pieces: list[dict] = []
        original_start = float(payload["start"])
        original_end = float(payload["end"])
        for index, group in enumerate(groups):
            piece = self._clone_segment(payload)
            piece["start"] = original_start if index == 0 else float(group[0]["start"])
            piece["end"] = original_end if index == len(groups) - 1 else float(group[-1]["end"])
            piece["text"] = self._join_word_text(group)
            piece["words"] = list(group)
            piece["split_from_long_asr"] = True
            pieces.append(piece)
        return pieces

    @staticmethod
    def _join_word_text(words: list[dict]) -> str:
        values = [str(word.get("text", "") or "").strip() for word in words]
        if values and all(re.search(r"[\u3400-\u9fff\uf900-\ufaff]", value) for value in values):
            return "".join(values)
        return " ".join(values).strip()

    def _split_text_proportionally(self, payload: dict, *, limit: float) -> list[dict]:
        text = str(payload.get("text", "") or "").strip()
        start = float(payload["start"])
        end = float(payload["end"])
        part_count = max(2, int(ceil((end - start) / limit)))
        tokens = self._text_tokens(text)
        if len(tokens) < part_count:
            return [payload]

        duration = end - start
        while True:
            groups: list[list[str]] = []
            cursor = 0
            for part_index in range(part_count):
                remaining_parts = part_count - part_index
                remaining_tokens = len(tokens) - cursor
                take = max(1, int(ceil(remaining_tokens / remaining_parts)))
                if part_index < part_count - 1:
                    take = self._prefer_sentence_boundary(tokens, cursor, take)
                    # Leave at least one token for every remaining piece.
                    take = min(take, remaining_tokens - (remaining_parts - 1))
                groups.append(tokens[cursor:cursor + take])
                cursor += take
            if cursor < len(tokens):
                groups[-1].extend(tokens[cursor:])
            total_units = float(sum(max(1, len("".join(group))) for group in groups))
            longest_duration = duration * max(
                max(1, len("".join(group))) for group in groups
            ) / total_units
            if longest_duration <= limit + 0.01 or part_count >= len(tokens):
                break
            part_count += 1

        pieces: list[dict] = []
        consumed_units = 0.0
        for index, group in enumerate(groups):
            units = float(max(1, len("".join(group))))
            piece = self._clone_segment(payload)
            piece["start"] = start + duration * (consumed_units / total_units)
            consumed_units += units
            piece["end"] = end if index == len(groups) - 1 else start + duration * (consumed_units / total_units)
            piece["text"] = self._join_text_tokens(group)
            piece.pop("words", None)
            piece["split_from_long_asr"] = True
            pieces.append(piece)
        return pieces

    @staticmethod
    def _text_tokens(text: str) -> list[str]:
        if re.search(r"[\u3400-\u9fff\uf900-\ufaff]", text) and not re.search(r"\s", text):
            return list(text)
        return re.findall(r"\S+", text)

    @staticmethod
    def _prefer_sentence_boundary(tokens: list[str], start: int, take: int) -> int:
        target = min(len(tokens), start + take)
        lower = max(start + 1, target - max(2, take // 3))
        upper = min(len(tokens) - 1, target + max(2, take // 3))
        for index in range(target, lower - 1, -1):
            if re.search(r"[,.!?;:\u3002\uff0c\uff01\uff1f\uff1b]$", tokens[index - 1]):
                return index - start
        for index in range(target + 1, upper + 1):
            if re.search(r"[,.!?;:\u3002\uff0c\uff01\uff1f\uff1b]$", tokens[index - 1]):
                return index - start
        return take

    @staticmethod
    def _join_text_tokens(tokens: list[str]) -> str:
        if tokens and all(re.search(r"[\u3400-\u9fff\uf900-\ufaff]", token) for token in tokens):
            return "".join(tokens)
        return " ".join(tokens).strip()

    def _clone_segment(self, segment: dict) -> dict:
        payload = {
            "start": float(segment.get("start", 0.0)),
            "end": float(segment.get("end", 0.0)),
            "text": str(segment.get("text", "") or "").strip(),
        }
        if segment.get("words"):
            payload["words"] = list(segment.get("words") or [])
        if segment.get("chunk_id"):
            payload["chunk_id"] = segment.get("chunk_id")
        for key in (
            "speaker", "language", "confidence", "split_from_long_asr",
            "speech_detected", "speech_gate",
        ):
            if key in segment:
                payload[key] = segment[key]
        return payload

    def _normalize_sentence_text(self, text: str) -> str:
        value = re.sub(r"\s+", " ", str(text or "").strip())
        return value
