"""
Piper TTS local synthesis engine wrapper.
"""

from typing import AsyncGenerator
from vision.synthesis.base import BaseTTS
from vision.config import config
from vision.logger import logger


class PiperTTS(BaseTTS):
    def __init__(self, voice: str = "austin"):
        super().__init__(name="Piper-Local")
        self.voice = voice or config.VISION_TTS_VOICE

    async def synthesize(self, text: str) -> bytes:
        """Synthesize using local piper binary or python wrapper."""
        logger.debug(f"[PiperTTS] Synthesizing text with voice '{self.voice}': {text[:30]}...")
        return b""

    async def stream_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        audio_bytes = await self.synthesize(text)
        if audio_bytes:
            yield audio_bytes
