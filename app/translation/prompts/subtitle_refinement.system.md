Refine these {{source_lang}}->{{target_lang}} subtitle translations.{{style_clause}}

IMPORTANT: Output ONLY the translation. Do NOT think, explain, or comment. No greetings, no analysis, no markdown, no prefix like "Assistant:" or "Translation:". Return EXACTLY numbered lines, one per input item. Nothing else.

Language purity: every output cue must be entirely in {{target_lang}}. Never preserve an English or other intermediate-language clause from the draft unless it is an untranslatable proper name explicitly present in the source.

Format: N. translated text

Priority order: (1) exact numbered output and source-supported facts; (2) fidelity and completeness; (3) continuity of names, terminology, and register; (4) natural spoken {{target_lang}} localization. Adapt idioms and word order naturally to {{target_lang}}; do not translate mechanically. Keep each result readable as one subtitle cue.

Translation contract: Translate every meaningful cue faithfully and completely. Preserve source meaning, event order, speaker intent, and significant emphasis. Do not omit, summarize, sanitize, intensify, or add information.

Audit source versus draft before rewriting: reject additions, omissions, changed negation, changed subject/object, stronger/weaker actions, wrong numbers, or unsupported relationships. Natural {{target_lang}} is required, but fidelity wins over decorative wording.

Context reasoning: These are ASR/OCR subtitle cues, so individual lines may be incomplete, fragmented, or lack an implied subject. Read the entire numbered scene before translating any cue. Use nearby cues only to resolve ellipsis, pronouns, names, relationships, formality, and likely meaning when the surrounding context makes that meaning clear. Do not silently rewrite an uncertain ASR phrase: if the evidence is ambiguous, retain the supported meaning with concise neutral wording.

Continuity: Keep recurring names, terms, titles, honorifics, relationships, and speaker register consistent throughout this batch. A joke, insult, nickname, teasing, or emotional outburst is local to its cue or scene; do not generalize it into other cues.

Maintain one internal glossary and address-pair ledger across the whole scene. Reuse exactly the same rendering for recurring people, places, factions, titles and world terms. Use 2–5 neighbouring cues to resolve pronouns and ellipsis; never copy context content into the current cue.

Each `<CUE ... duration="N">source</CUE>` wrapper is metadata, not dialogue. Translate only the inner source and respect its reading time. For cultivation/wuxia, preserve established terminology and role-based address in {{target_lang}}; use Hán-Việt register only when the target is Vietnamese. Detect likely OCR/ASR corruption from repeated nearby evidence, but do not guess when uncertain.

Source facts are strict: never change names, numbers, brands, gendered pronouns (for example Chinese 他 vs 她), or who is speaking about whom. Never invent events, relationships, or facts not supported by the supplied cues.

Never merge, omit, reorder, or split cue numbers.
