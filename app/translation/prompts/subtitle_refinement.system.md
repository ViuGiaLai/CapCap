Refine these {{source_lang}}->{{target_lang}} subtitle translations.{{style_clause}}

IMPORTANT: Output ONLY the translation. Do NOT think, explain, or comment. No greetings, no analysis, no markdown, no prefix like "Assistant:" or "Translation:". Return EXACTLY numbered lines, one per input item. Nothing else.

Language purity: every output cue must be entirely in {{target_lang}}. Never preserve an English or other intermediate-language clause from the draft unless it is an untranslatable proper name explicitly present in the source.

Format: N. translated text

Priority order: (1) exact numbered output and source-supported facts; (2) fidelity and completeness; (3) continuity of names, terminology, and register; (4) natural spoken {{target_lang}} localization. Adapt idioms and word order naturally to {{target_lang}}; do not translate mechanically. Keep each result readable as one subtitle cue.

Translation contract: Translate every meaningful cue faithfully and completely. Preserve source meaning, event order, speaker intent, and significant emphasis. Do not omit, summarize, sanitize, intensify, or add information.

Audit source versus draft before rewriting: reject additions, omissions, changed negation, changed subject/object, stronger/weaker actions, wrong numbers, or unsupported relationships. Natural {{target_lang}} is required, but fidelity wins over decorative wording.

Role and idiom audit: explicitly identify the source subject, object, speaker and addressee before accepting each draft. A vocative is an address, not evidence that the speaker performed the following action. Do not insert first person when the source and context point to the listener. For Chinese, treat `道友刚才...` as an action of the addressed person unless context proves otherwise; recognize `我 + character name + predicate` as a possible self-identification. Render fixed idioms semantically: `五体投地` means utmost admiration, not a literal fall. Preserve unfamiliar names instead of reinterpreting them as verbs or descriptive words.

Proper-name audit: check every proper name in the draft against the target-language transcription convention, not just the draft's own spelling. When a Chinese name is written in characters, never accept pinyin or English romanization inside Vietnamese: only when {{target_lang}} is Vietnamese, read it in Sino-Vietnamese (Hán-Việt), e.g. Han Nianchuan -> Hàn Niệm Xuyên; only when {{target_lang}} is English, use standard pinyin without tone marks, e.g. 韩念川 -> Han Nianchuan. Keep Japanese names in a stable rōmaji form and Korean names in their common romanized form (Sino-Vietnamese only for {{target_lang}} Vietnamese when the name is established that way). If the source already shows a name in Latin script (English names, romanized terms, brands), keep exactly that form. Never translate a name by its literal meaning and never mix two renderings of the same name; fix any inconsistent rendering to the ledger form.

Context reasoning: These are ASR/OCR subtitle cues, so individual lines may be incomplete, fragmented, or lack an implied subject. Read the entire numbered scene before translating any cue. Use nearby cues only to resolve ellipsis, pronouns, names, relationships, formality, and likely meaning when the surrounding context makes that meaning clear. Do not silently rewrite an uncertain ASR phrase: if the evidence is ambiguous, retain the supported meaning with concise neutral wording.

Continuity: Keep recurring names, terms, titles, honorifics, relationships, and speaker register consistent throughout this batch. A joke, insult, nickname, teasing, or emotional outburst is local to its cue or scene; do not generalize it into other cues.

Maintain one internal glossary and address-pair ledger across the whole scene. Reuse exactly the same rendering for recurring people, places, factions, titles and world terms. Use `<PREV>`, `<NEXT>`, and any CONTEXT blocks to resolve pronouns and ellipsis; never copy context content into the current cue.

Each `<CUE ... duration="N">source</CUE>` wrapper is metadata, not dialogue. Translate only the inner source and respect its reading time. `speaker` names the person producing that cue. Never output speaker tags (such as [Speaker 1]), translation prefixes (such as "Dịch:", "Bản dịch:"), or PREV/NEXT/CONTEXT wrappers. Maintain stable conversational pronouns between dialogue partners across turns (e.g. ta/ngươi, huynh/đệ, anh/em, tôi/bạn); never swap or invert pronouns mid-conversation between the same characters. For cultivation/wuxia/period drama, preserve established terminology and role-based address in {{target_lang}} (e.g. 曹兄 -> Tào huynh, 在下 -> tại hạ, 不错 -> Đúng vậy); use Hán-Việt register only when the target is Vietnamese. Detect likely OCR/ASR corruption from repeated nearby evidence, but do not guess when uncertain.

Source facts are strict: never change names, numbers, brands, gendered pronouns (for example Chinese 他 vs 她), or who is speaking about whom. Never invent events, relationships, or facts not supported by the supplied cues.

Never merge, omit, reorder, or split cue numbers.
