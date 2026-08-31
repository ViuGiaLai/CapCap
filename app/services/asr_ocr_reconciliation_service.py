from __future__ import annotations

import re
import unicodedata


_SCRIPT_PATTERNS = {
    "han": re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"),
    "japanese": re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff]"),
    "korean": re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af\u3400-\u4dbf\u4e00-\u9fff]"),
    "latin": re.compile(r"[A-Za-z\u00c0-\u024f]"),
    "cyrillic": re.compile(r"[\u0400-\u052f]"),
    "arabic": re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]"),
    "thai": re.compile(r"[\u0e00-\u0e7f]"),
}
_LANGUAGE_FAMILIES = {
    "zh": "han", "cmn": "han", "yue": "han",
    "ja": "japanese", "ko": "korean",
    "en": "latin", "vi": "latin", "id": "latin", "es": "latin",
    "fr": "latin", "de": "latin", "pt": "latin",
    "ru": "cyrillic", "ar": "arabic", "th": "thai",
}
_SUSPICIOUS_LENGTH = {
    "han": 2, "japanese": 2, "korean": 3, "latin": 4,
    "cyrillic": 4, "arabic": 4, "thai": 4,
}
# Latin substrings are especially collision-prone (``he`` inside ``the``),
# so require complete tokens there. Other supported scripts commonly attach
# particles/prefixes without spaces and need compact matching.
_WORD_BASED_FAMILIES = {"latin"}


class AsrOcrReconciliationService:
    """Repair clearly truncated ASR cues using matching burned-in subtitles.

    Audio remains authoritative for timing. OCR may replace only a very short
    cue in the same writing system when the longer on-screen text contains the
    complete ASR token(s) and is visible at the same time. This keeps titles,
    logos, and unrelated signs out of the spoken transcript.
    """

    VERSION = "multilingual-truncated-cue-v3-two-frame-consensus"
    MAX_TIME_SLOP_SECONDS = 0.45
    MAX_OCR_LENGTH = 80
    MAX_SCAN_RANGES = 32

    @staticmethod
    def _language_family(source_language: str) -> str:
        code = str(source_language or "auto").strip().lower().split("-")[0]
        return _LANGUAGE_FAMILIES.get(code, "")

    @staticmethod
    def _detect_family(value: object) -> str:
        text = str(value or "")
        counts = {
            family: len(pattern.findall(text))
            for family, pattern in _SCRIPT_PATTERNS.items()
        }
        return max(counts, key=counts.get) if counts and max(counts.values()) > 0 else ""

    @staticmethod
    def _normalized(value: object, family: str) -> str:
        text = unicodedata.normalize("NFKC", str(value or "")).casefold()
        tokens = []
        current = []
        for char in text:
            if char.isalpha() or char.isdigit():
                current.append(char)
            elif current:
                tokens.append("".join(current))
                current = []
        if current:
            tokens.append("".join(current))
        separator = " " if family in _WORD_BASED_FAMILIES else ""
        return separator.join(tokens)

    @classmethod
    def _is_family_text(cls, value: object, family: str) -> bool:
        if family not in _SCRIPT_PATTERNS:
            return False
        text = str(value or "")
        letters = sum(1 for char in text if char.isalpha())
        script_chars = len(_SCRIPT_PATTERNS[family].findall(text))
        return letters > 0 and script_chars / letters >= 0.7

    @classmethod
    def _is_suspicious(cls, value: object, family: str) -> bool:
        if family not in _SUSPICIOUS_LENGTH or not cls._is_family_text(value, family):
            return False
        normalized = cls._normalized(value, family)
        compact = normalized.replace(" ", "")
        if not compact or len(compact) > _SUSPICIOUS_LENGTH[family]:
            return False
        if family in _WORD_BASED_FAMILIES and len(normalized.split()) != 1:
            return False
        return True

    @classmethod
    def should_scan(cls, asr_segments: list[dict], source_language: str) -> bool:
        explicit_family = cls._language_family(source_language)
        language = str(source_language or "auto").strip().lower()
        if not explicit_family and language not in {"", "auto"}:
            return False
        return any(
            cls._is_suspicious(
                segment.get("text", ""),
                explicit_family or cls._detect_family(segment.get("text", "")),
            )
            for segment in asr_segments or []
        )

    @classmethod
    def suspicious_time_ranges(
        cls,
        asr_segments: list[dict],
        *,
        source_language: str = "auto",
        padding_seconds: float = 0.75,
    ) -> list[tuple[float, float]]:
        explicit_family = cls._language_family(source_language)
        pending = []
        for segment in asr_segments or []:
            family = explicit_family or cls._detect_family(segment.get("text", ""))
            if not cls._is_suspicious(segment.get("text", ""), family):
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
        return ranges[:cls.MAX_SCAN_RANGES]

    @classmethod
    def suspicious_cue_ranges(
        cls,
        asr_segments: list[dict],
        *,
        source_language: str = "auto",
        padding_seconds: float = 0.15,
    ) -> list[tuple[float, float]]:
        """Return one tight OCR window per suspect cue without merging cues."""
        explicit_family = cls._language_family(source_language)
        ranges = []
        for segment in asr_segments or []:
            family = explicit_family or cls._detect_family(segment.get("text", ""))
            if not cls._is_suspicious(segment.get("text", ""), family):
                continue
            start = max(0.0, float(segment.get("start", 0.0) or 0.0) - padding_seconds)
            end = max(start, float(segment.get("end", start) or start) + padding_seconds)
            ranges.append((start, end))
            if len(ranges) >= cls.MAX_SCAN_RANGES:
                break
        return ranges

    @staticmethod
    def _interval_match(asr: dict, ocr: dict) -> tuple[float, float]:
        asr_start = float(asr.get("start", 0.0) or 0.0)
        asr_end = max(asr_start, float(asr.get("end", asr_start) or asr_start))
        ocr_start = float(ocr.get("start", 0.0) or 0.0)
        ocr_end = max(ocr_start, float(ocr.get("end", ocr_start) or ocr_start))
        overlap = max(0.0, min(asr_end, ocr_end) - max(asr_start, ocr_start))
        midpoint_distance = abs((asr_start + asr_end) * 0.5 - (ocr_start + ocr_end) * 0.5)
        return overlap, midpoint_distance

    @staticmethod
    def _contains_complete_cue(asr_text: str, ocr_text: str, family: str) -> bool:
        if family in _WORD_BASED_FAMILIES:
            asr_words = asr_text.split()
            ocr_words = ocr_text.split()
            width = len(asr_words)
            return bool(width) and any(
                ocr_words[index:index + width] == asr_words
                for index in range(len(ocr_words) - width + 1)
            )
        return bool(asr_text) and asr_text in ocr_text

    @classmethod
    def reconcile(
        cls,
        asr_segments: list[dict],
        ocr_segments: list[dict],
        *,
        source_language: str = "auto",
    ) -> tuple[list[dict], int]:
        repaired: list[dict] = []
        replacement_count = 0
        explicit_family = cls._language_family(source_language)

        for source in asr_segments or []:
            item = dict(source)
            asr_text = str(item.get("text", "") or "").strip()
            family = explicit_family or cls._detect_family(asr_text)
            asr_normalized = cls._normalized(asr_text, family)
            if not cls._is_suspicious(asr_text, family):
                repaired.append(item)
                continue

            candidates = []
            for ocr in ocr_segments or []:
                ocr_text = str(ocr.get("text", "") or "").strip()
                if not cls._is_family_text(ocr_text, family):
                    continue
                ocr_normalized = cls._normalized(ocr_text, family)
                if not ocr_normalized or len(ocr_normalized.replace(" ", "")) > cls.MAX_OCR_LENGTH:
                    continue
                if len(ocr_normalized) <= len(asr_normalized):
                    continue
                if not cls._contains_complete_cue(asr_normalized, ocr_normalized, family):
                    continue
                overlap, midpoint_distance = cls._interval_match(item, ocr)
                if overlap <= 0.0 and midpoint_distance > cls.MAX_TIME_SLOP_SECONDS:
                    continue
                candidates.append((overlap > 0.0, overlap, -midpoint_distance, -len(ocr_normalized), ocr))

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
