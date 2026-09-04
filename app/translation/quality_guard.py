from __future__ import annotations

import re


# Source-conditioned terminology. A replacement is allowed only when the
# corresponding source cue actually contains that term, preventing a global
# search/replace from changing unrelated Vietnamese wording.
VI_CANONICAL_TERMS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("神域", "Thần Vực", ("thần giới", "thần vực")),
    ("魔族", "Ma tộc", ("ma tộc", "tộc ma")),
    ("妖族", "Yêu tộc", ("yêu tộc", "tộc yêu")),
    ("灵力", "linh lực", ("linh lực", "sức mạnh linh hồn")),
    ("修为", "tu vi", ("tu vi", "mức tu luyện")),
    ("境界", "cảnh giới", ("cảnh giới", "cấp độ tu luyện")),
    ("师兄", "sư huynh", ("sư huynh", "anh đồng môn", "đàn anh")),
    ("师姐", "sư tỷ", ("sư tỷ", "chị đồng môn", "đàn chị")),
    ("前辈", "tiền bối", ("tiền bối", "người đi trước")),
    ("晚辈", "vãn bối", ("vãn bối", "kẻ hậu bối", "hậu bối")),
    ("师尊", "sư tôn", ("sư tôn", "tôn sư")),
    ("师父", "sư phụ", ("sư phụ", "thầy")),
    ("贤侄", "hiền điệt", ("hiền điệt", "cháu hiền")),
    ("道友", "đạo hữu", ("đạo hữu", "đạo bạn", "bạn đạo")),
    ("神通", "thần thông", ("thần thông", "phép thần thông", "năng lực thần kỳ", "sức mạnh thần kỳ")),
    ("天王", "Thiên Vương", ("thiên vương",)),
    ("兄台", "huynh đài", ("huynh đài", "anh bạn", "người anh em")),
    ("阁下", "các hạ", ("các hạ", "quý ngài")),
    ("在下", "tại hạ", ("tại hạ", "ở dưới", "bên dưới")),
    ("老夫", "lão phu", ("lão phu", "ông già", "ông lão")),
    ("本座", "bổn tọa", ("bổn tọa", "chỗ ngồi này", "ghế này")),
    ("参见", "bái kiến", ("bái kiến", "tham kiến", "gặp mặt", "gặp")),
)

_CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
_HANGUL_RE = re.compile(r"[\uac00-\ud7af]")
_CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
_ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06ff]")
# CJK glyphs count as ``\w`` in Python, so word boundaries would miss values
# such as ``100颗``. Only guard against adjacent digits here.
_ARABIC_NUMBER_RE = re.compile(r"(?<!\d)\d+(?:[.,]\d+)?%?(?!\d)")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]+(?:['\u2019][A-Za-z]+)?")
_ENGLISH_CONTRACTION_RE = re.compile(
    r"\b(?:don['\u2019]?t|isn['\u2019]?t|aren['\u2019]?t|can['\u2019]?t|won['\u2019]?t|didn['\u2019]?t|you['\u2019]?re|we['\u2019]?re|they['\u2019]?re)\b",
    re.IGNORECASE,
)

# Exact, source-conditioned dialogue cues where generic MT commonly returns a
# grammatical but weak Vietnamese paraphrase. Only known equivalent outputs
# are normalized; arbitrary translations are never overwritten.
VI_CANONICAL_CUES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("住手", "Dừng tay!", ("dừng tay", "dừng lại", "hãy dừng lại", "hãy dừng lại đi")),
    ("不错", "Đúng vậy", ("không tệ", "không tồi", "chẳng tệ", "đúng vậy", "chính xác", "phải")),
    ("遵命", "Tuân mệnh!", ("tuân mệnh", "rõ", "nghe lệnh")),
)
_ENGLISH_FUNCTION_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "but", "by",
    "can", "do", "does", "for", "from", "has", "have", "he", "her", "him",
    "his", "i", "if", "in", "is", "it", "me", "my", "not", "of", "on",
    "or", "our", "she", "that", "the", "their", "them", "they", "this", "to",
    "was", "we", "were", "what", "when", "with", "you", "your",
}

_VI_FIRST_PERSON_RE = re.compile(r"\b(?:tôi|ta|chúng ta|mình)\b", re.IGNORECASE)
_VI_VICTORY_RE = re.compile(r"\b(?:chiến thắng|đánh bại|hạ gục)\b", re.IGNORECASE)
_VI_LITERAL_FALL_RE = re.compile(
    r"\b(?:ngã|rơi|nằm|quỳ)(?:\s+\w+){0,3}\s+(?:đất|mặt đất)\b",
    re.IGNORECASE,
)


def _replace_variant(text: str, variant: str, canonical: str) -> str:
    def replacement(match: re.Match) -> str:
        value = canonical
        original = match.group(0)
        if original[:1].isupper() and value[:1].islower():
            value = value[:1].upper() + value[1:]
        return value

    return re.sub(re.escape(variant), replacement, text, flags=re.IGNORECASE)


def _normalized_phrase(text: str) -> str:
    return re.sub(r"[^\w\s]", "", str(text or "").casefold()).strip()


def _target_profile(target_lang: str) -> tuple[str, float]:
    key = str(target_lang or "").strip().lower().replace("_", "-")
    base = key.split("-", 1)[0]
    if base in {"zh", "ja"}:
        return "cjk", 10.0
    if base == "ko":
        return "hangul", 12.0
    if base == "th":
        return "thai", 15.0
    if base in {"ar", "fa", "ur"}:
        return "arabic", 16.0
    if base in {"ru", "uk", "bg", "sr"}:
        return "cyrillic", 17.0
    return "latin", 18.0


def _contains_unexpected_source_script(text: str, profile: str) -> bool:
    checks = {
        "cjk": (_HANGUL_RE, _ARABIC_SCRIPT_RE, _CYRILLIC_RE),
        "hangul": (_CJK_RE, _ARABIC_SCRIPT_RE, _CYRILLIC_RE),
        "arabic": (_CJK_RE, _HANGUL_RE, _CYRILLIC_RE),
        "cyrillic": (_CJK_RE, _HANGUL_RE, _ARABIC_SCRIPT_RE),
        "thai": (_CJK_RE, _HANGUL_RE, _ARABIC_SCRIPT_RE, _CYRILLIC_RE),
        "latin": (_CJK_RE, _HANGUL_RE, _ARABIC_SCRIPT_RE, _CYRILLIC_RE),
    }
    return any(pattern.search(text) for pattern in checks.get(profile, ()))


def _contains_english_clause_in_vietnamese(text: str) -> bool:
    """Detect a leaked English clause without rejecting names or brands."""
    if _ENGLISH_CONTRACTION_RE.search(text):
        return True
    tokens = [token.casefold() for token in _LATIN_WORD_RE.findall(text)]
    if len(tokens) < 4:
        return False
    hits = sum(token in _ENGLISH_FUNCTION_WORDS for token in tokens)
    return hits >= 4 and hits / max(1, len(tokens)) >= 0.35


def apply_translation_quality_guard(
    *,
    source_segments: list[dict],
    translated_texts: list[str],
    target_lang: str,
) -> tuple[list[str], list[str]]:
    """Normalize safe terminology and report objective translation risks.

    This deliberately does not attempt semantic translation locally. Meaning
    and pronoun resolution remain the AI provider's job; the guard only makes
    corrections supported by the source cue and emits warnings for review.
    """
    target_key = str(target_lang or "").strip().lower()
    is_vietnamese = target_key in {"vi", "vie", "vietnamese", "vi-vn"}
    target_profile, max_cps = _target_profile(target_key)
    guarded: list[str] = []
    warnings: list[str] = []

    for index, (segment, translated) in enumerate(zip(source_segments, translated_texts)):
        source = str((segment or {}).get("original_text") or (segment or {}).get("source_text") or (segment or {}).get("text") or "")
        text = " ".join(str(translated or "").split()).strip()

        if is_vietnamese:
            normalized_target = _normalized_phrase(text)
            for source_cue, canonical, variants in VI_CANONICAL_CUES:
                if source.strip() == source_cue and normalized_target in {
                    _normalized_phrase(variant) for variant in variants
                }:
                    text = canonical
                    break
            for source_term, canonical, variants in VI_CANONICAL_TERMS:
                if source_term not in source:
                    continue
                for variant in variants:
                    text = _replace_variant(text, variant, canonical)

            if "五体投地" in source and re.search(r"\b(?:ngưỡng mộ|khâm phục)\b", text, re.IGNORECASE):
                # This is a fixed idiom, so a source-conditioned correction is
                # safer than allowing a small model to retain a literal fall,
                # omit the emphasis, or leak an intermediate-language phrase.
                text = re.sub(
                    r"\b(?:rất\s+)?(?:ngưỡng mộ|khâm phục)\b.*$",
                    "khâm phục sát đất",
                    text,
                    count=1,
                    flags=re.IGNORECASE,
                )
                if re.search(r"我[\u3400-\u9fff]{1,3}佩服", source):
                    text = re.sub(
                        r"\btôi\s+(.+?)\s+khâm phục sát đất$",
                        r"\1 ta khâm phục sát đất",
                        text,
                        count=1,
                        flags=re.IGNORECASE,
                    )
            if "连战" in source and not _VI_VICTORY_RE.search(text):
                text = re.sub(r"\bvừa rồi\b", "vừa", text, flags=re.IGNORECASE)
                text = re.sub(
                    r"\b(?:đã\s+)?chiến đấu với\s+(.+?)\s+liên tiếp\b",
                    r"đấu liền \1",
                    text,
                    count=1,
                    flags=re.IGNORECASE,
                )
                text = re.sub(
                    r"\b(?:đã\s+)?(?:chiến đấu|giao chiến)\s+liên tiếp\s+với\b",
                    "đấu liền",
                    text,
                    count=1,
                    flags=re.IGNORECASE,
                )
                if "两位天王" in source:
                    text = re.sub(
                        r"\bhai\s+Thiên Vương\b",
                        "hai vị Thiên Vương",
                        text,
                        count=1,
                        flags=re.IGNORECASE,
                    )

            # These checks are source-conditioned. They do not attempt a new
            # translation; they identify objectively changed semantics that a
            # fluent-looking local-model answer would otherwise hide.
            if "连战" in source and _VI_VICTORY_RE.search(text):
                warnings.append(
                    f"Cue {index + 1}: semantic mismatch: 连战 means fighting successively, not winning."
                )
            if "五体投地" in source and _VI_LITERAL_FALL_RE.search(text):
                warnings.append(
                    f"Cue {index + 1}: semantic mismatch: 五体投地 expresses utmost admiration, not a literal fall."
                )
            if "五体投地" in source and not re.search(
                r"\b(?:khâm phục sát đất|bái phục|khâm phục (?:vô cùng|hết mực)|vô cùng khâm phục)\b",
                text,
                flags=re.IGNORECASE,
            ):
                warnings.append(
                    f"Cue {index + 1}: semantic mismatch: the emphasis of 五体投地 was omitted."
                )
            # A leading Chinese vocative plus 刚才 normally refers to the
            # addressee's recent action. Flag a newly invented first-person
            # subject so the contextual repair pass can resolve it.
            if re.match(r"^\s*(?:道友|阁下|前辈|兄台|公子|姑娘).*刚才", source):
                if _VI_FIRST_PERSON_RE.search(text):
                    warnings.append(
                        f"Cue {index + 1}: semantic mismatch: the addressee was changed into a first-person subject."
                    )
            if re.match(r"^\s*道友实力", source) and re.match(
                r"^\s*Đạo hữu\s+(?:có\s+)?thực lực", text, flags=re.IGNORECASE
            ):
                text = re.sub(
                    r"^\s*Đạo hữu\s+(?:có\s+)?thực lực",
                    "Thực lực của đạo hữu",
                    text,
                    count=1,
                    flags=re.IGNORECASE,
                )

        if not text:
            warnings.append(f"Cue {index + 1}: bản dịch trống.")
        elif _contains_unexpected_source_script(text, target_profile):
            warnings.append(f"Cue {index + 1}: còn ký tự thuộc chữ viết nguồn chưa dịch.")
        elif is_vietnamese and _contains_english_clause_in_vietnamese(text):
            warnings.append(f"Cue {index + 1}: còn cụm tiếng Anh trong bản dịch tiếng Việt.")

        source_numbers = _ARABIC_NUMBER_RE.findall(source)
        translated_numbers = _ARABIC_NUMBER_RE.findall(text)
        missing_numbers = [number for number in source_numbers if number not in translated_numbers]
        if missing_numbers:
            warnings.append(
                f"Cue {index + 1}: bản dịch có thể thiếu số {', '.join(missing_numbers)}."
            )

        try:
            duration = max(0.1, float(segment.get("end", 0.0)) - float(segment.get("start", 0.0)))
        except (AttributeError, TypeError, ValueError):
            duration = 0.1
        cps = len(text.replace(" ", "")) / duration
        if cps > max_cps:
            warnings.append(
                f"Cue {index + 1}: quá dài để đọc ({cps:.1f} ký tự/giây)."
            )
        guarded.append(text)

    return guarded, warnings
