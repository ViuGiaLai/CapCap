from __future__ import annotations

import time
import re

from openai import OpenAI
from services.local_translation_config import selected_model_info

from services.local_translation_runtime import (
    get_local_translation_runtime,
    local_translation_assets_ready,
    local_translation_model_name,
)

from ..errors import TranslationConfigError, TranslationProviderError, TranslationValidationError
from ..srt_utils import parse_numbered_line_items, validate_texts


class LocalGGUFTranslatorProvider:
    provider_id = "local_hymt"

    @property
    def display_name(self) -> str:
        info = selected_model_info()
        return f"CapCap Local AI ({info.get('filename') or 'GGUF'})"

    @property
    def model_name(self) -> str:
        return local_translation_model_name()

    def is_configured(self) -> bool:
        return local_translation_assets_ready()

    def polish_batch(
        self,
        *,
        source_texts: list[str],
        translated_texts: list[str] | None = None,
        src_lang: str,
        target_lang: str,
        style_instruction: str = "",
        timeout: int = 300,
        max_retries: int = 2,
        max_tokens: int = 2048,
    ) -> tuple[list[str], list[str], str]:
        normalized_source = str(src_lang or "").strip().lower()
        normalized_target = str(target_lang or "").strip().lower()
        if normalized_source not in {"zh", "zh-hans", "zh-cn", "en"}:
            raise TranslationConfigError("Local AI currently supports Chinese and English source subtitles only.")
        if normalized_target not in {"vi", "en"}:
            raise TranslationConfigError("Local AI currently supports Vietnamese and English output only.")
        if not self.is_configured():
            raise TranslationConfigError(
                "Local AI translation is not installed. Download it from Manage Resources."
            )
        runtime = get_local_translation_runtime()
        base_url = runtime.ensure_ready()
        model_info = selected_model_info()
        if "hy-mt" in str(model_info.get("filename") or "").lower():
            user_msg = self._build_hymt_prompt(source_texts, target_lang)
        else:
            user_msg = self._build_generic_prompt(source_texts, src_lang, target_lang)
        last_error = ""
        for attempt in range(1, max_retries + 1):
            try:
                client = OpenAI(api_key="capcap-local", base_url=base_url, timeout=timeout)
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": user_msg}],
                    temperature=0.7,
                    top_p=0.6,
                    max_tokens=max(512, min(3072, int(max_tokens or 2048))),
                    extra_body={"top_k": 20, "repeat_penalty": 1.05},
                )
                text = str(response.choices[0].message.content or "").strip()
                numbered_items = self._parse_hymt_output(text)
                expected_ids = list(range(1, len(source_texts) + 1))
                actual_ids = [number for number, _line in numbered_items]
                lines = [line for _number, line in numbered_items]
                if actual_ids != expected_ids or not validate_texts(lines, len(source_texts)):
                    raise TranslationValidationError(
                        f"Local AI returned incomplete subtitles: expected IDs 1..{len(source_texts)}, got {actual_ids[:8]}."
                    )
                return lines, [], self.provider_id
            except TranslationValidationError:
                raise
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    time.sleep(attempt)
        raise TranslationProviderError(f"{self.display_name} failed: {last_error}")

    @staticmethod
    def _build_hymt_prompt(source_texts: list[str], target_lang: str) -> str:
        target_name = {"vi": "越南语", "en": "英语"}.get(str(target_lang).lower(), target_lang)
        source_block = "\n".join(str(text or "") for text in source_texts)
        terminology = ""
        if str(target_lang).lower() == "vi":
            glossary = {
                "贤侄": "hiền điệt",
                "断后": "chặn hậu",
                "道友": "đạo hữu",
                "宗主": "tông chủ",
                "长老": "trưởng lão",
            }
            matched_terms = [
                f"{source_term} 翻译成 {target_term}"
                for source_term, target_term in glossary.items()
                if source_term in source_block
            ]
            if "贤侄" in source_block and "你先撤" in source_block:
                matched_terms.append("你先撤 翻译成 cháu rút lui trước")
            if "贤侄" in source_block and "我断后" in source_block:
                matched_terms.append("我断后 翻译成 ta sẽ chặn hậu")
            if matched_terms:
                terminology = "参考下面的翻译：\n" + "\n".join(matched_terms) + "\n\n"
        tagged_lines = "\n".join(
            f"<sn>{index}.</sn>{' '.join(str(text or '').splitlines())}"
            for index, text in enumerate(source_texts, start=1)
        )
        return (
            terminology
            +
            f"将以下<source></source>之间的字幕逐条翻译为{target_name}。准确理解完整上下文、称谓、"
            "代词、成语和动作含义，不要逐字误译，不要增加或遗漏信息。原文中的<sn></sn>标签是字幕编号，"
            "必须在译文中原样保留。只输出<target></target>及其内容，不要解释。\n\n"
            f"<source>\n{tagged_lines}\n</source>\n\n"
            f"输出格式：<target>\n<sn>1.</sn>{target_name}译文\n</target>"
        )

    @staticmethod
    def _parse_hymt_output(text: str) -> list[tuple[int, str]]:
        tagged = re.findall(
            r"<sn>\s*(\d+)\.?\s*</sn>\s*(.*?)(?=<sn>|</target>|$)",
            str(text or ""),
            flags=re.IGNORECASE | re.DOTALL,
        )
        if tagged:
            return [
                (
                    int(number),
                    " ".join(
                        re.sub(r"</?(?:sn|target)[^>]*>", "", value, flags=re.IGNORECASE)
                        .strip()
                        .splitlines()
                    ).strip(),
                )
                for number, value in tagged
            ]
        return parse_numbered_line_items(text)

    @staticmethod
    def _build_generic_prompt(source_texts: list[str], src_lang: str, target_lang: str) -> str:
        source_name = {"zh": "Chinese", "zh-hans": "Chinese", "en": "English"}.get(
            str(src_lang).lower(), src_lang
        )
        target_name = {"vi": "Vietnamese", "en": "English"}.get(str(target_lang).lower(), target_lang)
        numbered = "\n".join(f"{index}. {text}" for index, text in enumerate(source_texts, start=1))
        return (
            f"Translate these subtitles from {source_name} to natural, accurate {target_name}. "
            "Use all lines as context. Preserve meaning, names, relationships, pronouns, idioms, and numbering. "
            "Output exactly one translated line for each input in the format `N. translation`; no explanation.\n\n"
            f"{numbered}"
        )
