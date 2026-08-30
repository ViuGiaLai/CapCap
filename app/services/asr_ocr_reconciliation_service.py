from __future__ import annotations

import re


_HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_TEXT_RE = re.compile(r"[^\w\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+", re.UNICODE)


class AsrOcrReconciliationService:
    """Repair clearly truncated Chinese ASR cues using burned-in subtitles.

    Audio remains authoritative for timing. OCR is only allowed to replace a
    very short Han cue when the longer on-screen text contains that cue and is
    visible at the same time. This intentionally does not turn OCR into the
    primary transcription engine or copy unrelated titles/watermarks.
    """

    VERSION = "zh-truncated-cue-v1"
    MAX_TIME_SLOP_SECONDS = 0.45
    MAX_OCR_HAN_LENGTH = 16

    @staticmethod
    def _normalized(value: object) -> str:
        return _TEXT_RE.sub("", str(value or "")).lower()

    @staticmethod
    def _han_count(value: str) -> int:
        return len(_HAN_RE.findall(value))

    @classmethod
    def should_scan(cls, asr_segments: list[dict], source_language: str) -> bool:
        language = str(source_language or "auto").strip().lower()
        if language.startswith(("zh", "cmn", "yue")):
            return any(cls._is_suspicious(seg.get("text", "")) for seg in asr_segments or [])
        if language not in {"", "auto"}:
            return False
        # In automatic-language mode, only opt in when SenseVoice already
        # produced Han text. This prevents Chinese signs in non-Chinese video
        # from changing an English/Vietnamese transcript.
        return any(
            cls._han_count(cls._normalized(seg.get("text", ""))) > 0
            and cls._is_suspicious(seg.get("text", ""))
            for seg in asr_segments or []
        )

    @classmethod
    def suspicious_time_ranges(
        cls,
        asr_segments: list[dict],
        *,
        padding_seconds: float = 0.75,
    ) -> list[tuple[float, float]]:
        pending = []
        for segment in asr_segments or []:
            if not cls._is_suspicious(segment.get("text", "")):
                continue
            start = max(0.0, float(segment.get("start", 0.0) or 0.0) - padding_seconds)
            end = max(start, float(segment.get("end", start) or start) + padding_seconds)
            pending.append((start, end))
        ranges = []
        for start, end in sorted(pending):
            if ranges and start - ranges[-1][1] <= cls.MAX_TIME_SLOP_SECONDS:
                ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
            else:
                ranges.append((start, end))
        return ranges

    @classmethod
    def _is_suspicious(cls, value: object) -> bool:
        text = cls._normalized(value)
        han_count = cls._han_count(text)
        return bool(text) and han_count == len(text) and han_count <= 2

    @staticmethod
    def _interval_match(asr: dict, ocr: dict) -> tuple[float, float]:
        asr_start = float(asr.get("start", 0.0) or 0.0)
        asr_end = max(asr_start, float(asr.get("end", asr_start) or asr_start))
        ocr_start = float(ocr.get("start", 0.0) or 0.0)
        ocr_end = max(ocr_start, float(ocr.get("end", ocr_start) or ocr_start))
        overlap = max(0.0, min(asr_end, ocr_end) - max(asr_start, ocr_start))
        midpoint_distance = abs((asr_start + asr_end) * 0.5 - (ocr_start + ocr_end) * 0.5)
        return overlap, midpoint_distance

    @classmethod
    def reconcile(cls, asr_segments: list[dict], ocr_segments: list[dict]) -> tuple[list[dict], int]:
        repaired: list[dict] = []
        replacement_count = 0
        clean_ocr = []
        for segment in ocr_segments or []:
            normalized = cls._normalized(segment.get("text", ""))
            han_count = cls._han_count(normalized)
            if not normalized or han_count != len(normalized):
                continue
            if not 2 <= han_count <= cls.MAX_OCR_HAN_LENGTH:
                continue
            clean_ocr.append((segment, normalized, han_count))

        for source in asr_segments or []:
            item = dict(source)
            asr_text = str(item.get("text", "") or "").strip()
            asr_normalized = cls._normalized(asr_text)
            if not cls._is_suspicious(asr_text):
                repaired.append(item)
                continue

            candidates = []
            for ocr, ocr_normalized, ocr_han_count in clean_ocr:
                if asr_normalized not in ocr_normalized or ocr_han_count <= len(asr_normalized):
                    continue
                overlap, midpoint_distance = cls._interval_match(item, ocr)
                if overlap <= 0.0 and midpoint_distance > cls.MAX_TIME_SLOP_SECONDS:
                    continue
                candidates.append((overlap > 0.0, overlap, -midpoint_distance, -ocr_han_count, ocr))

            if candidates:
                best = max(candidates, key=lambda candidate: candidate[:4])[-1]
                ocr_text = str(best.get("text", "") or "").strip()
                item["asr_text_original"] = asr_text
                item["ocr_text"] = ocr_text
                item["text_source"] = "ocr_reconciled"
                item["text"] = ocr_text
                replacement_count += 1
            repaired.append(item)

        return repaired, replacement_count
