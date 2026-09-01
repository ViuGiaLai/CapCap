from __future__ import annotations

import re

from .prompt_loader import render_prompt


def _strip_cue_id(value: str) -> str:
    return re.sub(r'\s+id="[^"]*"', "", str(value), count=1, flags=re.IGNORECASE)


def build_translation_messages(
    *,
    source_texts: list[str],
    translated_texts: list[str] | None,
    src_lang: str,
    target_lang: str,
    style_instruction: str = "",
) -> tuple[str, str]:
    """Build the system/user message pair from editable Markdown templates."""
    style_value = str(style_instruction or "").strip()
    style_clause = f" Style: {style_value}" if style_value else ""
    lowered_style = style_value.lower()
    dubbing_mode = "[mode=dubbing_rewrite]" in lowered_style
    ocr_capture_mode = "[mode=ocr_capture]" in lowered_style
    is_direct = not translated_texts

    if is_direct and ocr_capture_mode:
        prompt_key = "ocr_translation"
        lines = [
            f"{index + 1}. <OCR_TEXT>{' '.join(str(text or '').splitlines())}</OCR_TEXT>"
            for index, text in enumerate(source_texts)
        ]
    elif is_direct:
        prompt_key = "subtitle_translation"
        lines = [
            f"{index + 1}. {_strip_cue_id(text)}"
            for index, text in enumerate(source_texts)
        ]
    else:
        prompt_key = "dubbing_rewrite" if dubbing_mode else "subtitle_refinement"
        lines = [
            f"{index + 1}. {_strip_cue_id(source)} ||| {draft}"
            for index, (source, draft) in enumerate(zip(source_texts, translated_texts or []))
        ]

    values = {
        "source_lang": str(src_lang or "auto"),
        "target_lang": str(target_lang or "vi"),
        "style_clause": style_clause,
    }
    system_message = render_prompt(f"{prompt_key}.system.md", **values)
    user_message = "\n".join(lines)
    return system_message, user_message
