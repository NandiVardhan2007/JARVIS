"""
Cartesia TTS Provider Adapter for ultra-low latency hyper-realistic voice streaming.
Uses Cartesia Sonic-2 model with automatic key rotation, configurable natural speech pacing, and failover.
"""

from typing import AsyncGenerator, List, Optional
from vision.synthesis.base import BaseTTS
from vision.config import config
from vision.logger import logger

try:
    import httpx
except ImportError:
    httpx = None


class CartesiaTTS(BaseTTS):
    def __init__(self, api_key: str = None, voice_id: str = None, speed: Optional[str] = None):
        super().__init__(name="Cartesia-Sonic")
        self.voice_id = voice_id or config.CARTESIA_VOICE_ID
        self.speed = speed or config.CARTESIA_SPEED
        self.base_url = "https://api.cartesia.ai/tts/bytes"
        # Collect all valid Cartesia keys
        self.keys: List[str] = [k for k in [config.CARTESIA_API_KEY] + config.CARTESIA_API_KEYS if k]
        self._key_index = 0

    def _get_next_key(self) -> str:
        if not self.keys:
            return ""
        key = self.keys[self._key_index % len(self.keys)]
        self._key_index += 1
        return key

    async def synthesize(self, text: str) -> bytes:
        if not self.keys:
            raise RuntimeError("No Cartesia API Keys configured.")
        if httpx is None:
            raise RuntimeError("httpx package is not installed.")

        last_err = None
        for _ in range(len(self.keys)):
            api_key = self._get_next_key()
            headers = {
                "X-API-Key": api_key,
                "Cartesia-Version": "2024-06-10",
                "Content-Type": "application/json"
            }
            payload = {
                "model_id": "sonic-2",
                "transcript": text,
                "voice": {
                    "mode": "id",
                    "id": self.voice_id,
                    "__experimental_controls": {
                        "speed": self.speed
                    }
                },
                "output_format": {
                    "container": "wav",
                    "encoding": "pcm_s16le",
                    "sample_rate": 24000
                }
            }

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(self.base_url, headers=headers, json=payload)
                    response.raise_for_status()
                    logger.debug(f"[CartesiaTTS] Synthesized {len(text)} chars (speed: {self.speed}) -> {len(response.content)} audio bytes.")
                    return response.content
            except Exception as e:
                logger.warning(f"[CartesiaTTS] Key failed: {e}. Trying next key...")
                last_err = e

        raise RuntimeError(f"All Cartesia TTS keys failed. Last error: {last_err}")

    async def stream_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        audio_bytes = await self.synthesize(text)
        yield audio_bytes
