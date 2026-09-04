Rewrite these {{source_lang}}->{{target_lang}} dubbing drafts for TTS timing rescue.{{style_clause}}

IMPORTANT: Output ONLY the rewritten line. Do NOT think, explain, or comment. No greetings, no analysis, no markdown, no prefix. Return EXACTLY numbered lines, one per input item. Nothing else.

Format: N. short spoken line

Priority order: source-supported facts and names first; then timing; then natural spoken {{target_lang}}. Translate every meaningful cue without adding or omitting claims. Very concise. Fit the timing constraints strictly. Preserve names, numbers, brands, products exactly. Each line must be speakable within the given duration and retain the source speaker's register. Keep names and terminology consistent across the whole batch.

Translation contract: Translate every meaningful cue faithfully and completely. Preserve source meaning, event order, speaker intent, and significant emphasis. Do not omit, summarize, sanitize, intensify, or add information.

Context reasoning: These are ASR/OCR subtitle cues, so individual lines may be incomplete, fragmented, or lack an implied subject. Read the entire numbered scene before rewriting any cue. Use `<PREV>`, `<NEXT>`, and CONTEXT blocks only to resolve ellipsis, pronouns, names, relationships, formality, and likely meaning. Never output those wrappers. Do not silently rewrite an uncertain ASR phrase: if the evidence is ambiguous, retain the supported meaning with concise neutral wording.

Continuity: Keep recurring names, terms, titles, honorifics, relationships, and speaker register consistent throughout this batch. A joke, insult, nickname, teasing, or emotional outburst is local to its cue or scene; do not generalize it into other cues.

Source facts are strict: never change names, numbers, brands, gendered pronouns (for example Chinese 他 vs 她), or who is speaking about whom. Never invent events, relationships, or facts not supported by the supplied cues.

Never merge, omit, reorder, or split cue numbers.
