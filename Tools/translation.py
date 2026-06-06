"""
Translation Utility — cascading free API fallback.
Internal helper (NOT a @function_tool).  Used by WhatsApp and other tools
that need to handle non-ASCII text before passing it to pyautogui.write().
"""

import logging
import aiohttp
import json

logger = logging.getLogger(__name__)


def is_ascii(text: str) -> bool:
    """Return True if every character is basic ASCII (Latin letters, digits, punctuation)."""
    try:
        return all(ord(ch) < 128 for ch in text)
    except TypeError:
        return True


async def _try_google_translate(text: str) -> str | None:
    """Unofficial Google Translate gtx endpoint — no API key needed."""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": text}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0:
                        parts = [p[0] for p in data[0] if p[0]]
                        return "".join(parts)
    except Exception as exc:
        logger.debug(f"Google Translate failed: {exc}")
    return None


async def _try_mymemory(text: str) -> str | None:
    """MyMemory free translation API."""
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {"q": text, "langpair": "auto|en"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("responseStatus") == 200:
                        return data["responseData"]["translatedText"]
    except Exception as exc:
        logger.debug(f"MyMemory failed: {exc}")
    return None


async def _try_libretranslate(text: str) -> str | None:
    """LibreTranslate — tries multiple public instances."""
    instances = [
        "https://libretranslate.de/translate",
        "https://translate.argosopentech.com/translate",
    ]
    payload = json.dumps({"q": text, "source": "auto", "target": "en", "format": "text"})
    headers = {"Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            for url in instances:
                try:
                    async with session.post(url, data=payload, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            result = data.get("translatedText")
                            if result:
                                return result
                except Exception:
                    continue
    except Exception as exc:
        logger.debug(f"LibreTranslate failed: {exc}")
    return None


async def translate_to_english(text: str) -> str:
    """
    Translate *text* to English using free APIs.

    Cascade order:
      1. Google Translate (unofficial)
      2. MyMemory
      3. LibreTranslate

    Returns the original text unchanged if it is already ASCII or if
    every translation service fails.
    """
    if not text or not text.strip():
        return text
    if is_ascii(text):
        return text

    for fn in (_try_google_translate, _try_mymemory, _try_libretranslate):
        result = await fn(text)
        if result:
            logger.info(f"Translated '{text[:30]}…' → '{result[:30]}…'")
            return result

    logger.warning(f"All translators failed for '{text[:40]}…' — returning original text.")
    return text
