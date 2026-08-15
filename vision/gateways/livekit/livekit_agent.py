"""
LiveKit RTC Voice Agent Worker for real-time audio/video interaction.
"""

from vision.config import config
from vision.core.engine import vision_engine
from vision.logger import logger


class LiveKitAgent:
    def __init__(self):
        self.url = config.LIVEKIT_URL
        self.api_key = config.LIVEKIT_API_KEY
        self.api_secret = config.LIVEKIT_API_SECRET

    async def start(self):
        """Start LiveKit RTC room worker."""
        if not self.url or not self.api_key or not self.api_secret:
            logger.warning("[LiveKit] Credentials not fully configured. Skipping LiveKit worker.")
            return
        logger.info(f"[LiveKit] Connecting to LiveKit cloud endpoint: {self.url}")


livekit_agent = LiveKitAgent()
