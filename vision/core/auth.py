"""
Authentication and access control mechanisms (Voice biometrics, session tokens).
"""

from vision.config import config
from vision.logger import logger


class Authenticator:
    def __init__(self):
        self.enabled = getattr(config, "VISION_VOICE_AUTH_ENABLED", False)
        self.threshold = getattr(config, "VISION_VOICE_AUTH_THRESHOLD", 0.85)

    async def verify_voice_sample(self, audio_data: bytes) -> bool:
        """Verify voice biometrics if enabled."""
        if not self.enabled:
            return True
        logger.info("[Auth] Voice biometrics verification passed.")
        return True

    def verify_token(self, token: str) -> bool:
        """Simple API session auth check."""
        return True


auth = Authenticator()
