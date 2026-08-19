"""
Cartesia TTS Router for VISION.
Fully powered by Cartesia Sonic Neural Voice.
"""

from vision.synthesis.cartesia_tts import CartesiaTTS, cartesia_tts

SmartTTSEngine = CartesiaTTS
smart_tts = cartesia_tts

__all__ = ["SmartTTSEngine", "smart_tts"]
