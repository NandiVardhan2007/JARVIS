import time
from typing import AsyncGenerator, List, Optional, Dict
from vision.synthesis.base import BaseTTS
from vision.config import config
from vision.logger import logger

try:
    import httpx
except ImportError:
    httpx = None


class CartesiaTTS(BaseTTS):
    def __init__(self, api_key: str = None, voice_id: str = None, speed: Optional[str] = None, emotion: Optional[List[str]] = None):
        super().__init__(name="Cartesia-Sonic")
        self.voice_id = voice_id or config.CARTESIA_VOICE_ID
        self.speed = speed or config.CARTESIA_SPEED
        self.emotion = emotion or getattr(config, "CARTESIA_EMOTION", ["positivity:high"])
        self.base_url = "https://api.cartesia.ai/tts/bytes"
        # Collect all valid Cartesia keys
        all_keys = [config.CARTESIA_API_KEY] + config.CARTESIA_API_KEYS
        self.keys: List[str] = list(dict.fromkeys([k for k in all_keys if k]))
        self._key_index = 0
        self._key_cooldowns: Dict[str, float] = {}

    def _get_active_keys(self) -> List[str]:
        now = time.time()
        # Active keys not on cooldown
        active = [k for k in self.keys if now >= self._key_cooldowns.get(k, 0)]
        return active if active else self.keys

    def _mask_key(self, key: str) -> str:
        if len(key) <= 12:
            return key[:4] + "..."
        return f"{key[:8]}...{key[-4:]}"

    async def synthesize(self, text: str) -> bytes:
        if not self.keys:
            raise RuntimeError("No Cartesia API Keys configured.")
        if httpx is None:
            raise RuntimeError("httpx package is not installed.")

        candidate_keys = self._get_active_keys()
        last_err = None

        for i in range(len(candidate_keys)):
            idx = (self._key_index + i) % len(candidate_keys)
            api_key = candidate_keys[idx]
            masked = self._mask_key(api_key)

            headers = {
                "X-API-Key": api_key,
                "Cartesia-Version": "2024-06-10",
                "Content-Type": "application/json"
            }
            controls = {"speed": self.speed}
            if self.emotion:
                controls["emotion"] = self.emotion

            payload = {
                "model_id": "sonic-2",
                "transcript": text,
                "voice": {
                    "mode": "id",
                    "id": self.voice_id,
                    "__experimental_controls": controls
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
                    
                    if response.status_code in (402, 429):
                        # Quota exceeded or rate limit: mark cooldown for 15 mins
                        self._key_cooldowns[api_key] = time.time() + 900
                        logger.warning(f"[CartesiaTTS] Key [{masked}] returned {response.status_code} ({response.text[:60]}). Marking on 15m cooldown.")
                        continue

                    response.raise_for_status()
                    self._key_index = (idx + 1) % len(candidate_keys)
                    # Clear cooldown on success
                    self._key_cooldowns.pop(api_key, None)
                    logger.debug(f"[CartesiaTTS] Synthesized {len(text)} chars (speed: {self.speed}, key: {masked}) -> {len(response.content)} audio bytes.")
                    return response.content
            except Exception as e:
                self._key_cooldowns[api_key] = time.time() + 300
                logger.warning(f"[CartesiaTTS] Key [{masked}] failed: {e}. Trying next available key...")
                last_err = e

        raise RuntimeError(f"All Cartesia TTS keys failed or on cooldown. Last error: {last_err}")

    async def stream_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        audio_bytes = await self.synthesize(text)
        yield audio_bytes
