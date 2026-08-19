"""
Cartesia Neural TTS Provider for ultra-low latency hyper-realistic voice synthesis.
Fully powers VISION voice output with Sonic-2 streaming architecture and multi-key failover.
"""

import asyncio
from typing import AsyncGenerator, List, Optional
import httpx
from vision.synthesis.base import BaseTTS
from vision.config import config
from vision.logger import logger


class CartesiaTTS(BaseTTS):
    """
    Direct ultra-low latency Cartesia Neural TTS Engine.
    Features:
    - Sonic-2 Neural Voice model with sub-150ms TTFT
    - Automated API key rotation across key pool on quota/rate-limits
    - Emotion and speed modulation
    - Direct PCM WAV stream synthesis
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None
    ):
        super().__init__(name="Cartesia-Sonic")
        self.api_keys: List[str] = list(config.CARTESIA_API_KEYS)
        if api_key and api_key not in self.api_keys:
            self.api_keys.insert(0, api_key)
        self.current_key_index: int = 0
        self.voice_id: str = voice_id or config.CARTESIA_VOICE_ID
        self.model_id: str = model_id or getattr(config, "CARTESIA_MODEL_ID", "sonic-2")
        self.base_url: str = "https://api.cartesia.ai/tts/bytes"
        self._client: Optional[httpx.AsyncClient] = None

    def _get_active_api_key(self) -> Optional[str]:
        if not self.api_keys:
            return config.CARTESIA_API_KEY
        return self.api_keys[self.current_key_index % len(self.api_keys)]

    def _rotate_api_key(self):
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            logger.info(f"[CartesiaTTS] Rotated to API Key index {self.current_key_index + 1}/{len(self.api_keys)}")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=3.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10, keepalive_expiry=60.0)
            )
        return self._client

    async def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        """Synthesize text to 24kHz PCM WAV bytes using Cartesia Sonic Neural Voice."""
        if not text or not text.strip():
            return b""

        active_voice = voice_id or self.voice_id
        speed = getattr(config, "CARTESIA_SPEED", "normal")
        emotion = getattr(config, "CARTESIA_EMOTION", ["positivity:high"])

        attempts = max(1, len(self.api_keys))
        client = await self._get_client()

        for attempt in range(attempts):
            api_key = self._get_active_api_key()
            if not api_key:
                raise RuntimeError("[CartesiaTTS] No Cartesia API key configured in CARTESIA_API_KEY or CARTESIA_API_KEYS.")

            headers = {
                "X-API-Key": api_key,
                "Cartesia-Version": "2024-06-10",
                "Content-Type": "application/json"
            }

            payload = {
                "model_id": self.model_id,
                "transcript": text.strip(),
                "voice": {
                    "mode": "id",
                    "id": active_voice
                },
                "output_format": {
                    "container": "wav",
                    "encoding": "pcm_s16le",
                    "sample_rate": 24000
                },
                "language": "en"
            }

            # Optional voice controls
            voice_controls = {}
            if speed and speed != "normal":
                voice_controls["speed"] = speed
            if emotion and isinstance(emotion, list) and len(emotion) > 0:
                voice_controls["emotion"] = emotion
            if voice_controls:
                payload["voice"]["__experimental_controls"] = voice_controls

            try:
                response = await client.post(self.base_url, headers=headers, json=payload)
                if response.status_code == 200:
                    audio_bytes = response.content
                    logger.debug(f"[CartesiaTTS] Synthesized '{text[:30]}...' -> {len(audio_bytes)} bytes WAV.")
                    return audio_bytes

                # Handle quota / rate limit / bad key errors with rotation
                if response.status_code in (401, 402, 429):
                    logger.warning(
                        f"[CartesiaTTS] Key returned HTTP {response.status_code}: {response.text}. Rotating key."
                    )
                    self._rotate_api_key()
                    continue
                else:
                    response.raise_for_status()

            except httpx.HTTPStatusError as e:
                logger.warning(f"[CartesiaTTS] HTTP error ({e.response.status_code}): {e}")
                self._rotate_api_key()
            except Exception as e:
                logger.error(f"[CartesiaTTS] Synthesis request error: {e}")
                if attempt == attempts - 1:
                    raise e

        raise RuntimeError("[CartesiaTTS] All Cartesia API keys exhausted or failed to synthesize.")

    async def stream_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream synthesized audio bytes."""
        audio_bytes = await self.synthesize(text)
        if audio_bytes:
            yield audio_bytes

    async def close(self):
        """Close underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Global Cartesia TTS singleton
cartesia_tts = CartesiaTTS()
