"""
Intelligent Hybrid Multi-Tier TTS Engine for VISION.
Combines ultra-expressive Cartesia Neural TTS with instant zero-latency Local TTS fallback.
"""

from typing import AsyncGenerator, Optional
from vision.synthesis.base import BaseTTS
from vision.synthesis.cartesia_tts import CartesiaTTS
from vision.synthesis.local_tts import LocalTTS, local_tts
from vision.config import config
from vision.logger import logger


class SmartTTSEngine(BaseTTS):
    """
    Multi-Tier Smart TTS Router:
    - Primary: Cartesia Neural TTS (sonic-2 / high naturalness & emotion)
    - Fallback: LocalTTS (Windows SAPI / System.Speech / Piper) with 0ms network latency
    """
    def __init__(self):
        super().__init__(name="Smart-TTS-Router")
        self._cartesia: Optional[CartesiaTTS] = None
        self._local: LocalTTS = local_tts
        self._init_cartesia()

    def _init_cartesia(self):
        try:
            if config.CARTESIA_API_KEY or config.CARTESIA_API_KEYS:
                self._cartesia = CartesiaTTS()
        except Exception as e:
            logger.warning(f"[SmartTTS] Could not initialize Cartesia: {e}")
            self._cartesia = None

    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech with instant automatic failover or direct local synthesis."""
        if not text or not text.strip():
            return b""

        use_cartesia = getattr(config, "USE_CARTESIA_VOICE", True)

        # Attempt Cartesia primary if enabled in config
        if use_cartesia and self._cartesia:
            try:
                audio = await self._cartesia.synthesize(text)
                if audio:
                    return audio
            except Exception as e:
                logger.warning(f"[SmartTTS] Cartesia synthesis error: {e}. Switching instantly to Local TTS fallback.")


        # Fallback to local TTS
        try:
            return await self._local.synthesize(text)
        except Exception as e:
            logger.error(f"[SmartTTS] Local TTS fallback failed: {e}")
            return b""

    async def stream_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream speech audio bytes."""
        audio_bytes = await self.synthesize(text)
        if audio_bytes:
            yield audio_bytes


smart_tts = SmartTTSEngine()
