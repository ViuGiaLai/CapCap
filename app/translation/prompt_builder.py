from __future__ import annotations

import re

from .prompt_loader import render_prompt


_CUE_INNER_RE = re.compile(r"<CUE\b[^>]*>(.*)</CUE>", flags=re.IGNORECASE | re.DOTALL)
_CUE_SPEAKER_RE = re.compile(r'\bspeaker="([^"]+)"', flags=re.IGNORECASE)


def _strip_cue_id(value: str) -> str:
    return re.sub(r'\s+id="[^"]*"', "", str(value), count=1, flags=re.IGNORECASE)


def plain_cue_text(value: str) -> str:
    """Return the spoken/source text from a CUE wrapper or continuity line."""
    text = str(value or "").strip()
    if " => " in text:
        text = text.split(" => ", 1)[0].strip()
    match = _CUE_INNER_RE.fullmatch(text)
    if match:
        text = str(match.group(1) or "").strip()
    return " ".join(text.split())


def context_cue_text(value: str) -> str:
    """Return spoken text with speaker label if available for scene context."""
    text = str(value or "").strip()
    if " => " in text:
        parts = text.split(" => ", 1)
        src = parts[0].strip()
        trans = parts[1].strip()
        return f"{context_cue_text(src)} => {plain_cue_text(trans)}"
    speaker = ""
    speaker_match = _CUE_SPEAKER_RE.search(text)
    if speaker_match:
        speaker = speaker_match.group(1).strip()
    inner = plain_cue_text(text)
    if speaker:
        return f"[{speaker}] {inner}"
    return inner


def _neighbor_window(
    source_texts: list[str],
    context_before: list[str] | None,
    context_after: list[str] | None,
) -> list[str]:
    before = [context_cue_text(item) for item in (context_before or [])]
    current = [context_cue_text(text) for text in source_texts]
    after = [context_cue_text(item) for item in (context_after or [])]
    return before + current + after


def _numbered_scene_lines(
    *,
    source_texts: list[str],
    translated_texts: list[str] | None,
    context_before: list[str] | None,
    context_after: list[str] | None,
) -> list[str]:
    window = _neighbor_window(source_texts, context_before, context_after)
    offset = len(context_before or [])
    lines: list[str] = []
    drafts = list(translated_texts or [])
    for index, source in enumerate(source_texts):
        global_index = offset + index
        previous = window[global_index - 1] if global_index > 0 else ""
        following = window[global_index + 1] if global_index + 1 < len(window) else ""
        cue = _strip_cue_id(source)
        if translated_texts is None:
            lines.append(
                f"{index + 1}. <PREV>{previous}</PREV> {cue} <NEXT>{following}</NEXT>"
            )
        else:
            draft = drafts[index] if index < len(drafts) else ""
            lines.append(
                f"{index + 1}. <PREV>{previous}</PREV> {cue} ||| {draft} <NEXT>{following}</NEXT>"
            )
    return lines


def _format_user_message(
    lines: list[str],
    *,
    context_before: list[str] | None,
    context_after: list[str] | None,
) -> str:
    parts: list[str] = []
    if context_before:
        rendered = "\n".join(f"- {item}" for item in context_before)
        parts.append(f"<CONTEXT_BEFORE>\n{rendered}\n</CONTEXT_BEFORE>")
    parts.append("<TRANSLATE>\n" + "\n".join(lines) + "\n</TRANSLATE>")
    if context_after:
        rendered = "\n".join(f"- {item}" for item in context_after)
        parts.append(f"<CONTEXT_AFTER>\n{rendered}\n</CONTEXT_AFTER>")
    return "\n\n".join(parts)


def build_translation_messages(
    *,
    source_texts: list[str],
    translated_texts: list[str] | None,
    src_lang: str,
    target_lang: str,
    style_instruction: str = "",
    context_before: list[str] | None = None,
    context_after: list[str] | None = None,
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
        user_message = "\n".join(lines)
    elif is_direct:
        prompt_key = "subtitle_translation"
        lines = _numbered_scene_lines(
            source_texts=source_texts,
            translated_texts=None,
            context_before=context_before,
            context_after=context_after,
        )
        user_message = _format_user_message(
            lines, context_before=context_before, context_after=context_after
        )
    else:
        prompt_key = "dubbing_rewrite" if dubbing_mode else "subtitle_refinement"
        lines = _numbered_scene_lines(
            source_texts=source_texts,
            translated_texts=translated_texts,
            context_before=context_before,
            context_after=context_after,
        )
        user_message = _format_user_message(
            lines, context_before=context_before, context_after=context_after
        )

    values = {
        "source_lang": str(src_lang or "auto"),
        "target_lang": str(target_lang or "vi"),
        "style_clause": style_clause,
    }
    system_message = render_prompt(f"{prompt_key}.system.md", **values)
    return system_message, user_message
