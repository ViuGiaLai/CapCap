import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

from ..errors import TranslationConfigError, TranslationProviderError, TranslationValidationError
from ..prompt_builder import build_translation_messages, plain_cue_text
from ..srt_utils import parse_numbered_line_items, validate_texts


LOCAL_PROVIDER_IDS = frozenset({"ollama", "llama_app"})

# llama.cpp/Ollama serve small quantised models on CPU. Generation speed is
# typically one to two orders of magnitude slower than a cloud API, so the
# generic 120s HTTP timeout used by cloud providers aborts realistic
# subtitle batches mid-generation and then every retry repeats the same
# oversized request. Local requests therefore get a much longer budget;
# cloud providers keep the caller-supplied timeout unchanged.
LOCAL_REQUEST_TIMEOUT_SECONDS = int(os.getenv("VIUSTUDIO_LOCAL_TRANSLATION_TIMEOUT", "900") or "900")


class OpenAICompatiblePolisherProvider:
    """Reusable numbered-subtitle provider for OpenAI-compatible services."""

    def __init__(self, *, provider_id: str, display_name: str, env_prefix: str,
                 default_base_url: str, default_model: str = "", model_env: str | None = None):
        self.provider_id = provider_id
        self.display_name = display_name
        self.api_key = os.getenv(f"{env_prefix}_API_KEY", "").strip()
        # A second role model (e.g. a quality/fix model) can override the main
        # model through its own env var; otherwise the main model env applies.
        model_env = model_env or f"{env_prefix}_MODEL"
        self.model_name = os.getenv(model_env, default_model).strip()
        self.base_url = os.getenv(f"{env_prefix}_BASE_URL", default_base_url).strip()
        self._client = None
        # Set by the orchestrator when a local engine cannot be started. The
        # provider is then treated as unconfigured so callers can fall back
        # to Google Translate instead of crashing with a raw error.
        self.config_error = ""

    def is_configured(self) -> bool:
        if self.provider_id in LOCAL_PROVIDER_IDS:
            return bool(self.model_name and self.base_url)
        return bool(self.api_key and self.model_name and self.base_url)

    def _get_client(self):
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key or "dummy-local-key", base_url=self.base_url)
        return self._client

    @staticmethod
    def _effective_timeout(provider_id: str, timeout: int) -> int:
        """Give local providers a sane generation budget on slow CPUs."""
        try:
            timeout = max(1, int(timeout))
        except (TypeError, ValueError):
            timeout = 120
        if provider_id in LOCAL_PROVIDER_IDS:
            return max(timeout, LOCAL_REQUEST_TIMEOUT_SECONDS)
        return timeout

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
        context_before: list[str] | None = None,
        context_after: list[str] | None = None,
    ) -> tuple[list[str], list[str], str]:
        if not self.is_configured():
            raise TranslationConfigError(f"{self.display_name} is not configured. Set its API key and model in Settings.")

        # Local models can legitimately need several minutes per batch on CPU;
        # cloud providers keep the caller-supplied (default 120s) timeout.
        timeout = self._effective_timeout(self.provider_id, timeout)
        # ``max_retries`` is treated as the total number of attempts so that
        # 0 never produces an immediate empty failure before any request.
        attempts = max(1, int(max_retries or 1))

        # HY-MT is a dedicated machine-translation model, not a general
        # instruction-following chat model. Its official prompt is one
        # segment per request. Sending the large numbered system prompt made
        # it echo Chinese unchanged, after which the app silently used Google.
        if self.provider_id == "llama_app" and re.match(r"(?i)^hy[-_]?mt", os.path.basename(self.model_name)):
            return self._translate_hy_mt_batch(
                source_texts=source_texts,
                target_lang=target_lang,
                timeout=timeout,
                max_retries=attempts,
                context_before=context_before,
                context_after=context_after,
            )

        system_msg, user_msg = self._build_messages(
            source_texts=source_texts,
            translated_texts=translated_texts,
            src_lang=src_lang,
            target_lang=target_lang,
            style_instruction=style_instruction,
            context_before=context_before,
            context_after=context_after,
        )

        client = self._get_client()
        last_error = ""
        for attempt in range(1, attempts + 1):
            try:
                request_kwargs = dict(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.2,
                    max_tokens=max(1024, int(max_tokens or 4096)),
                    timeout=timeout,
                )
                if self.provider_id in {"llama_app", "ollama"}:
                    # Qwen3-class local models otherwise spend most of the
                    # response budget on hidden/visible reasoning, frequently
                    # timing out before producing the strict numbered subtitle
                    # payload. llama.cpp and Ollama both forward this template
                    # option to models that support thinking mode.
                    request_kwargs["extra_body"] = {
                        "chat_template_kwargs": {"enable_thinking": False}
                    }
                response = client.chat.completions.create(**request_kwargs)
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
                lines = [self._clean_translation_line(line) for _number, line in numbered_items]
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
                if self._is_quota_error(e):
                    # A rate/quota limit (e.g. the Gemini free tier's 20
                    # requests/day) will not clear within a retry window, so
                    # stop immediately with an actionable message instead of
                    # retrying and flooding the log with the raw API error.
                    raise TranslationProviderError(
                        f"{self.display_name} quota/rate limit exceeded: the provider is "
                        "refusing requests for now (free tier caps out quickly, e.g. "
                        f"20 requests/day for {self.model_name}). Wait for the limit to "
                        "reset or add billing at aistudio.google.com, then retry."
                    ) from e
                if attempt < max_retries:
                    time.sleep(attempt)
                    continue

        raise TranslationProviderError(f"{self.display_name} failed: {last_error}")

    @staticmethod
    def _is_quota_error(exc: Exception) -> bool:
        """Detect HTTP 429 / rate-limit / quota-exhausted provider errors."""
        status = getattr(exc, "status_code", None)
        if status == 429:
            return True
        text = str(exc or "").lower()
        return any(
            marker in text
            for marker in ("quota", "resource_exhausted", "rate limit", "ratelimit", "429")
        )

    @staticmethod
    def _plain_source_text(value: str) -> str:
        return plain_cue_text(value)

    @staticmethod
    def _clean_translation_line(value: str) -> str:
        """Remove source/draft scaffolding echoed by small local models."""
        text = str(value or "").strip()
        text = re.sub(r"<PREV\b[^>]*>.*?</PREV>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<NEXT\b[^>]*>.*?</NEXT>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"</?(?:PREV|NEXT)\b[^>]*>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"</?(?:TRANSLATE|CONTEXT_BEFORE|CONTEXT_AFTER)\b[^>]*>", "", text, flags=re.IGNORECASE)
        text = " ".join(text.split()).strip()
        if "|||" in text:
            text = text.rsplit("|||", 1)[-1].strip()
        cue = re.fullmatch(r"<CUE\b[^>]*>(.*)</CUE>", text, flags=re.IGNORECASE | re.DOTALL)
        if cue:
            text = str(cue.group(1) or "").strip()
        text = re.sub(
            r"^(?:(?:\[|\()?(?:Speaker|Người nói)\s*[\w\d]+(?:\]|\))?[:\s-]*|(?:Dịch|Bản dịch|Tiếng Việt|Translation|Target)\s*:\s*)",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        return text

    def _translate_hy_mt_batch(
        self,
        *,
        source_texts,
        target_lang: str,
        timeout: int,
        max_retries: int,
        context_before: list[str] | None = None,
        context_after: list[str] | None = None,
    ):
        language_names = {
            "vi": "Vietnamese", "en": "English", "ja": "Japanese", "ko": "Korean",
            "th": "Thai", "id": "Indonesian", "es": "Spanish", "fr": "French",
            "de": "German", "pt": "Portuguese", "ru": "Russian", "ar": "Arabic",
            "zh-cn": "Simplified Chinese", "zh-tw": "Traditional Chinese",
        }
        target_name = language_names.get(str(target_lang or "").strip().lower(), str(target_lang or "Vietnamese"))
        sources = [self._plain_source_text(value) for value in source_texts]
        before = [self._plain_source_text(value) for value in (context_before or [])]
        after = [self._plain_source_text(value) for value in (context_after or [])]
        window = before + sources + after
        offset = len(before)
        client = self._get_client()

        def translate_one(index: int) -> str:
            source = sources[index]
            previous = window[offset + index - 1] if offset + index > 0 else ""
            following = window[offset + index + 1] if offset + index + 1 < len(window) else ""
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
            context_bits = []
            if previous:
                context_bits.append(f"Previous source (context only, do not translate): {previous}")
            if following:
                context_bits.append(f"Upcoming source (context only, do not translate): {following}")
            context_prefix = (" ".join(context_bits) + " ") if context_bits else ""
            prompt = (
                f"{context_prefix}"
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
            translated = list(executor.map(translate_one, range(len(sources))))
        if not validate_texts(translated, len(sources)):
            raise TranslationValidationError(
                f"HY-MT returned {len(translated)} translations for {len(sources)} cues."
            )
        return translated, [], self.provider_id

    def _build_messages(
        self,
        source_texts,
        translated_texts,
        src_lang,
        target_lang,
        style_instruction,
        context_before=None,
        context_after=None,
    ) -> tuple[str, str]:
        return build_translation_messages(
            source_texts=source_texts,
            translated_texts=translated_texts,
            src_lang=src_lang,
            target_lang=target_lang,
            style_instruction=style_instruction,
            context_before=context_before,
            context_after=context_after,
        )
