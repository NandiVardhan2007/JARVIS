"""
VISION STT module with Smart Routing & Dual-Layer Accuracy Fallback.
"""

from vision.perception.stt.base import BaseSTT
from vision.perception.stt.groq_stt import GroqSTT
from vision.perception.stt.local_whisper import LocalWhisperSTT, local_stt
from vision.config import config
from vision.logger import logger


# Common Whisper hallucinations triggered by silence / background noise
NOISE_HALLUCINATIONS = {
    "thank you", "thank you.", "thanks", "thanks for watching", "thanks for watching.",
    "subtitles by", "amara.org", "you", "you.", "bye", "bye.", "goodbye", "goodbye.",
    "mm", "uh", "um", "yeah", "yeah.", "silence", "...", ".", "..", "?", "!",
    "okay", "okay.", "ok", "ok.", "[music]", "[applause]", "[silence]", "[laughter]",
    "reuters", "transcription by", "transcribed by", "vision", "jarvis"
}


def is_valid_speech_text(text: str) -> bool:
    """Validate if transcribed text is authentic speech rather than a noise artifact."""
    if not text:
        return False
    cleaned = text.strip().lower()
    # Strip punctuation for check
    stripped = "".join(c for c in cleaned if c.isalnum() or c.isspace()).strip()
    if not stripped or len(stripped) < 2:
        return False
    if cleaned in NOISE_HALLUCINATIONS or stripped in NOISE_HALLUCINATIONS:
        return False
    return True


class SmartSTTEngine(BaseSTT):
    """
    Intelligent STT router:
    - Primary: Groq Whisper Large-v3-Turbo (Ultra-high 99% accuracy, sub-250ms cloud latency)
    - Fallback / Offline: Local CTranslate2 Faster-Whisper (Int8)
    Can be inverted if VISION_STT_ENGINE is explicitly configured to 'local'.
    """
    def __init__(self):
        super().__init__(name="Smart-STT-Router")
        self._groq = None
        self._local = None

    def _get_groq(self) -> GroqSTT:
        if self._groq is None:
            self._groq = GroqSTT()
        return self._groq

    def _get_local(self) -> LocalWhisperSTT:
        if self._local is None:
            self._local = local_stt
        return self._local

    async def transcribe(self, audio_data: bytes, language: str = "en", filename: str = None, prompt: str = None) -> str:
        engine_pref = (getattr(config, "VISION_STT_ENGINE", "groq") or "groq").lower().strip()

        if engine_pref == "local":
            primary = self._get_local()
            fallback = self._get_groq() if config.GROQ_API_KEY else None
        else:
            primary = self._get_groq() if config.GROQ_API_KEY else self._get_local()
            fallback = self._get_local() if config.GROQ_API_KEY else None

        try:
            res = await primary.transcribe(audio_data, language=language, filename=filename, prompt=prompt)
            if res and is_valid_speech_text(res):
                return res.strip()
            elif res:
                logger.debug(f"[SmartSTT] Filtered out noise hallucination: '{res}'")
        except Exception as e:
            logger.warning(f"[SmartSTT] Primary STT ({primary.name}) error: {e}. Attempting fallback...")

        if fallback:
            try:
                res = await fallback.transcribe(audio_data, language=language, filename=filename, prompt=prompt)
                if res and is_valid_speech_text(res):
                    return res.strip()
                elif res:
                    logger.debug(f"[SmartSTT] Fallback filtered out noise hallucination: '{res}'")
            except Exception as e:
                logger.error(f"[SmartSTT] Fallback STT ({fallback.name}) failed: {e}")

        return ""


smart_stt = SmartSTTEngine()

__all__ = ["BaseSTT", "GroqSTT", "LocalWhisperSTT", "local_stt", "SmartSTTEngine", "smart_stt", "is_valid_speech_text"]

