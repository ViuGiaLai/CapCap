import random
import time
from urllib.parse import quote

import requests

from ..errors import TranslationProviderError


class GoogleWebTranslatorProvider:
    ENDPOINTS = [
        "https://translate.googleapis.com/translate_a/single",
        "https://clients5.google.com/translate_a/t",
        "https://translate.google.com/translate_a/single",
    ]
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Edge/120.0.0.0",
    ]
    BATCH_CHUNK_SIZE = 15

    def is_configured(self) -> bool:
        return True

    def _get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "*/*",
            "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
        }

    def translate_batch(
        self,
        texts: list[str],
        *,
        src_lang: str,
        target_lang: str,
        timeout: int = 20,
        max_retries: int = 3,
    ) -> list[str]:
        if not texts:
            return []

        results = []
        for i in range(0, len(texts), self.BATCH_CHUNK_SIZE):
            chunk = texts[i : i + self.BATCH_CHUNK_SIZE]
            chunk_results = self._translate_chunk_joined(
                chunk,
                src_lang=src_lang,
                target_lang=target_lang,
                timeout=timeout,
                max_retries=max_retries,
            )
            if chunk_results and len(chunk_results) == len(chunk):
                results.extend(chunk_results)
            else:
                for text in chunk:
                    res = self._translate_single_text_with_fallbacks(
                        text=text,
                        src_lang=src_lang,
                        target_lang=target_lang,
                        timeout=timeout,
                        max_retries=max_retries,
                    )
                    results.append(res)
            if i + self.BATCH_CHUNK_SIZE < len(texts):
                time.sleep(0.15)

        return results

    def _translate_chunk_joined(
        self,
        texts: list[str],
        *,
        src_lang: str,
        target_lang: str,
        timeout: int,
        max_retries: int,
    ) -> list[str] | None:
        """Translate multiple sentences in a single HTTP request using special newline delimiter."""
        if not texts:
            return []
        
        delimiter = "\n\n"
        joined_text = delimiter.join(str(t or "").strip() for t in texts)
        if not joined_text.strip():
            return ["" for _ in texts]

        for endpoint in self.ENDPOINTS:
            for attempt in range(1, max_retries + 1):
                try:
                    headers = self._get_headers()
                    if "clients5.google.com" in endpoint:
                        url = f"{endpoint}?client=dict-chrome-ex&sl={src_lang}&tl={target_lang}&q={quote(joined_text)}"
                        response = requests.get(url, headers=headers, timeout=timeout)
                    else:
                        url = f"{endpoint}?client=gtx&sl={src_lang}&tl={target_lang}&dt=t"
                        response = requests.post(url, data={"q": joined_text}, headers=headers, timeout=timeout)

                    if response.status_code == 200:
                        payload = response.json()
                        translated_text = self._extract_text(payload)
                        if translated_text:
                            lines = [line.strip() for line in translated_text.split("\n\n") if line.strip()]
                            if len(lines) == len(texts):
                                return lines
                            lines_single = [line.strip() for line in translated_text.split("\n") if line.strip()]
                            if len(lines_single) == len(texts):
                                return lines_single
                    elif response.status_code == 429:
                        break
                except Exception:
                    pass
                time.sleep(attempt * 0.3)

        return None

    def _translate_single_text_with_fallbacks(
        self,
        *,
        text: str,
        src_lang: str,
        target_lang: str,
        timeout: int,
        max_retries: int,
    ) -> str:
        clean_text = str(text or "").strip()
        if not clean_text:
            return ""

        last_error = ""
        for endpoint in self.ENDPOINTS:
            for attempt in range(1, max_retries + 1):
                try:
                    headers = self._get_headers()
                    if "clients5.google.com" in endpoint:
                        url = f"{endpoint}?client=dict-chrome-ex&sl={src_lang}&tl={target_lang}&q={quote(clean_text)}"
                        response = requests.get(url, headers=headers, timeout=timeout)
                    else:
                        url = f"{endpoint}?client=gtx&sl={src_lang}&tl={target_lang}&dt=t"
                        response = requests.post(url, data={"q": clean_text}, headers=headers, timeout=timeout)

                    if response.status_code == 200:
                        payload = response.json()
                        translated = self._extract_text(payload)
                        if translated:
                            return translated
                    elif response.status_code == 429:
                        last_error = "Rate limited (429)"
                        break
                    else:
                        last_error = f"HTTP {response.status_code}"
                except Exception as exc:
                    last_error = str(exc)

                time.sleep(attempt * 0.2)

        # Fallback to MyMemory API if all Google endpoints fail
        try:
            mymemory_url = f"https://api.mymemory.translated.net/get?q={quote(clean_text)}&langpair={src_lang}|{target_lang}"
            res = requests.get(mymemory_url, timeout=timeout)
            if res.status_code == 200:
                data = res.json()
                trans = data.get("responseData", {}).get("translatedText")
                if trans and not str(trans).startswith("MYMEMORY WARNING"):
                    return str(trans).strip()
        except Exception:
            pass

        # Never report an untranslated source line as a successful
        # translation.  Returning ``clean_text`` here made a network outage
        # silently produce Chinese (or another source language) in the final
        # subtitle track and let later stages synthesize the wrong text.
        detail = f" ({last_error})" if last_error else ""
        raise TranslationProviderError(
            f"Google Translate could not translate the subtitle after trying all endpoints{detail}."
        )

    def _extract_text(self, payload) -> str:
        if isinstance(payload, str):
            return payload.strip()
        if not isinstance(payload, list) or not payload:
            return ""
        sentences = payload[0]
        if isinstance(sentences, str):
            return sentences.strip()
        if not isinstance(sentences, list):
            return ""
        parts = []
        for item in sentences:
            if isinstance(item, list) and item:
                chunk = item[0]
                if isinstance(chunk, str):
                    parts.append(chunk)
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts).strip()
