"""
Cartesia TTS Provider Adapter for ultra-low latency hyper-realistic voice streaming.
"""

from typing import AsyncGenerator
from vision.synthesis.base import BaseTTS
from vision.config import config
from vision.logger import logger

try:
    import httpx
except ImportError:
    httpx = None


class CartesiaTTS(BaseTTS):
    def __init__(self, api_key: str = None, voice_id: str = None):
        super().__init__(name="Cartesia-Sonic")
        self.api_key = api_key or config.CARTESIA_API_KEY
        self.voice_id = voice_id or config.CARTESIA_VOICE_ID
        self.base_url = "https://api.cartesia.ai/tts/bytes"

    async def synthesize(self, text: str) -> bytes:
        if not self.api_key:
            raise RuntimeError("Cartesia API Key is not configured.")
        if httpx is None:
            raise RuntimeError("httpx package is not installed.")

        headers = {
            "X-API-Key": self.api_key,
            "Cartesia-Version": "2024-06-10",
            "Content-Type": "application/json"
        }
        payload = {
            "model_id": "sonic-english",
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": self.voice_id
            },
            "output_format": {
                "container": "wav",
                "encoding": "pcm_s16le",
                "sample_rate": 24000
            }
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            logger.debug(f"[CartesiaTTS] Synthesized {len(text)} chars -> {len(response.content)} audio bytes.")
            return response.content

    async def stream_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        audio_bytes = await self.synthesize(text)
        yield audio_bytes
