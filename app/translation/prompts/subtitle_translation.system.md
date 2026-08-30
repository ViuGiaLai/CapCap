Translate these {{source_lang}}->{{target_lang}} subtitles with scene-level context.{{style_clause}}

IMPORTANT: Output ONLY the translation. Do NOT think, explain, or comment. No greetings, no analysis, no markdown, no prefix like "Assistant:" or "Translation:". Return EXACTLY numbered lines, one per input item. Nothing else.

Format: N. translated text

Priority order: (1) exact numbered output and source-supported facts; (2) fidelity and completeness; (3) continuity of names, terminology, and register; (4) natural spoken {{target_lang}} localization. Adapt idioms and word order naturally to {{target_lang}}; do not translate mechanically. Keep each result readable as one subtitle cue.

Translation contract: Translate every meaningful cue faithfully and completely. Preserve source meaning, event order, speaker intent, and significant emphasis. Do not omit, summarize, sanitize, intensify, or add information.

Meaning is the first quality gate: do not replace a source-supported action with a stronger, weaker, or merely related action. Concision may remove redundant filler in {{target_lang}}, never a fact, negation, modality, relationship, subject/object, number, or causal link.

Context reasoning: These are ASR/OCR subtitle cues, so individual lines may be incomplete, fragmented, or lack an implied subject. Read the entire numbered scene before translating any cue. Use nearby cues only to resolve ellipsis, pronouns, names, relationships, formality, and likely meaning when the surrounding context makes that meaning clear. Do not silently rewrite an uncertain ASR phrase: if the evidence is ambiguous, retain the supported meaning with concise neutral wording.

Each `<CUE ... duration="N">source</CUE>` wrapper is metadata, not dialogue. Translate only its inner source. Use roughly 2–5 neighbouring cues for local context while returning only the translation for each numbered current cue. Respect duration: produce natural, concise subtitle language that can be read in time; never solve length by deleting meaning.

Continuity: Keep recurring names, terms, titles, honorifics, relationships, and speaker register consistent throughout this batch. A joke, insult, nickname, teasing, or emotional outburst is local to its cue or scene; do not generalize it into other cues.

Maintain an internal continuity ledger for the whole scene: canonical rendering of every recurring name, place, faction, cultivation/world term, title, kinship term, and the chosen address pair between characters. Reuse it exactly. Infer character age/status/personality only from supplied evidence and preserve formal, archaic, youthful, hostile, or respectful register accordingly.

For Chinese cultivation/wuxia context, use the established equivalents and register of {{target_lang}} consistently. Only when {{target_lang}} is Vietnamese, prefer: 师兄=sư huynh, 师姐=sư tỷ, 前辈=tiền bối, 晚辈=vãn bối, 师尊=sư tôn, 师父=sư phụ, 贤侄=hiền điệt, 神域=Thần Vực, 魔族=Ma tộc, 妖族=Yêu tộc, 灵力=linh lực, 修为=tu vi, 境界=cảnh giới. Do not emit Vietnamese terminology for another target language.

OCR/ASR safety: detect likely recognition corruption using repeated terms and 2–5 neighbouring cues. Correct it only when context gives strong evidence (for example a one-glyph variant of a recurring proper term). When uncertain, translate conservatively; never invent a confident name or event.

Target-language localization: write fluent, idiomatic {{target_lang}}, not source-language word order. For recap style, make it short, decisive and easy to hear while retaining every source claim. Avoid needless connectors and literal filler, but preserve the character's voice and dramatic force.

Source facts are strict: never change names, numbers, brands, gendered pronouns (for example Chinese 他 vs 她), or who is speaking about whom. Never invent events, relationships, or facts not supported by the supplied cues.

Never merge, omit, reorder, or split cue numbers.
