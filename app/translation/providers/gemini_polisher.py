import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

from ..errors import TranslationConfigError, TranslationProviderError, TranslationValidationError
from ..prompt_builder import build_translation_messages
from ..srt_utils import parse_numbered_line_items, validate_texts


class OpenAICompatiblePolisherProvider:
    """Reusable numbered-subtitle provider for OpenAI-compatible services."""

    def __init__(self, *, provider_id: str, display_name: str, env_prefix: str,
                 default_base_url: str, default_model: str = ""):
        self.provider_id = provider_id
        self.display_name = display_name
        self.api_key = os.getenv(f"{env_prefix}_API_KEY", "").strip()
        self.model_name = os.getenv(f"{env_prefix}_MODEL", default_model).strip()
        self.base_url = os.getenv(f"{env_prefix}_BASE_URL", default_base_url).strip()
        self._client = None

    def is_configured(self) -> bool:
        if self.provider_id in ("ollama", "llama_app"):
            return bool(self.model_name and self.base_url)
        return bool(self.api_key and self.model_name and self.base_url)

    def _get_client(self):
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key or "dummy-local-key", base_url=self.base_url)
        return self._client

    def polish_batch(
        self,
        *,
        source_texts: list[str],
        translated_texts: list[str] = None,
        src_lang: str,
        target_lang: str,
        style_instruction: str = "",
        timeout: int = 120,
        max_retries: int = 2,
        max_tokens: int = 4096,
    ) -> tuple[list[str], list[str], str]:
        if not self.is_configured():
            raise TranslationConfigError(f"{self.display_name} is not configured. Set its API key and model in Settings.")

        # HY-MT is a dedicated machine-translation model, not a general
        # instruction-following chat model. Its official prompt is one
        # segment per request. Sending the large numbered system prompt made
        # it echo Chinese unchanged, after which the app silently used Google.
        if self.provider_id == "llama_app" and re.match(r"(?i)^hy[-_]?mt", os.path.basename(self.model_name)):
            return self._translate_hy_mt_batch(
                source_texts=source_texts,
                target_lang=target_lang,
                timeout=timeout,
                max_retries=max_retries,
            )

        system_msg, user_msg = self._build_messages(
            source_texts=source_texts,
            translated_texts=translated_texts,
            src_lang=src_lang,
            target_lang=target_lang,
            style_instruction=style_instruction,
        )

        client = self._get_client()
        last_error = ""
        for attempt in range(1, max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.2,
                    max_tokens=max(1024, int(max_tokens or 4096)),
                    timeout=timeout,
                )
                text = response.choices[0].message.content.strip()
                if not text:
                    raise Exception("Empty response text")

                numbered_items = parse_numbered_line_items(text)
                expected = len(source_texts)
                expected_ids = list(range(1, expected + 1))
                actual_ids = [number for number, _line in numbered_items]
                if actual_ids != expected_ids:
                    raise TranslationValidationError(
                        f"Malformed or incomplete numbered output: expected IDs 1..{expected}, got {actual_ids[:8]}..."
                    )
                lines = [line for _number, line in numbered_items]
                if not validate_texts(lines, expected):
                    raise TranslationValidationError(
                        f"Expected {expected} lines, got {len(lines)}"
                    )
                return lines, [], self.provider_id
            except TranslationValidationError:
                # Retrying the exact same oversized request cannot restore a
                # truncated numbered response.  The orchestrator can instead
                # recover by switching immediately to ordered batches.
                raise
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    time.sleep(attempt)
                    continue

        raise TranslationProviderError(f"{self.display_name} failed: {last_error}")

    @staticmethod
    def _plain_source_text(value: str) -> str:
        text = str(value or "").strip()
        match = re.fullmatch(r"<CUE\b[^>]*>(.*)</CUE>", text, flags=re.IGNORECASE | re.DOTALL)
        return str(match.group(1) if match else text).strip()

    def _translate_hy_mt_batch(self, *, source_texts, target_lang: str, timeout: int, max_retries: int):
        language_names = {
            "vi": "Vietnamese", "en": "English", "ja": "Japanese", "ko": "Korean",
            "th": "Thai", "id": "Indonesian", "es": "Spanish", "fr": "French",
            "de": "German", "pt": "Portuguese", "ru": "Russian", "ar": "Arabic",
            "zh-cn": "Simplified Chinese", "zh-tw": "Traditional Chinese",
        }
        target_name = language_names.get(str(target_lang or "").strip().lower(), str(target_lang or "Vietnamese"))
        sources = [self._plain_source_text(value) for value in source_texts]
        client = self._get_client()

        def translate_one(source: str) -> str:
            glossary = ""
            if target_name == "Vietnamese":
                terms = [
                    ("师兄", "sư huynh"), ("师姐", "sư tỷ"), ("前辈", "tiền bối"),
                    ("晚辈", "vãn bối"), ("师尊", "sư tôn"), ("师父", "sư phụ"),
                    ("神域", "Thần Vực"), ("魔族", "Ma tộc"), ("妖族", "Yêu tộc"),
                    ("灵力", "linh lực"), ("修为", "tu vi"), ("境界", "cảnh giới"),
                ]
                present = [f"{src}={dst}" for src, dst in terms if src in source]
                if present:
                    glossary = " Use these required terms: " + ", ".join(present) + "."
            prompt = (
                f"Translate the following segment into {target_name}, without additional explanation."
                f"{glossary}：{source}"
            )
            last_error = ""
            for attempt in range(1, max(1, int(max_retries)) + 1):
                try:
                    response = client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=512,
                        timeout=timeout,
                    )
                    translated = str(response.choices[0].message.content or "").strip()
                    if translated:
                        return translated
                    last_error = "empty response"
                except Exception as exc:
                    last_error = str(exc)
                    if attempt < max_retries:
                        time.sleep(attempt)
            raise TranslationProviderError(f"{self.display_name} failed: {last_error}")

        workers = max(1, min(4, len(sources)))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="hy-mt") as executor:
            translated = list(executor.map(translate_one, sources))
        if not validate_texts(translated, len(sources)):
            raise TranslationValidationError(
                f"HY-MT returned {len(translated)} translations for {len(sources)} cues."
            )
        return translated, [], self.provider_id

    def _build_messages(
        self, source_texts, translated_texts, src_lang, target_lang, style_instruction
    ) -> tuple[str, str]:
        return build_translation_messages(
            source_texts=source_texts,
            translated_texts=translated_texts,
            src_lang=src_lang,
            target_lang=target_lang,
            style_instruction=style_instruction,
        )
