"""
VISION Speech Synthesis (TTS) subsystem.
Fully powered by Cartesia Sonic Neural Voice.
"""

from vision.synthesis.base import BaseTTS
from vision.synthesis.cartesia_tts import CartesiaTTS, cartesia_tts
from vision.synthesis.smart_tts import SmartTTSEngine, smart_tts
from vision.synthesis.player import audio_player, AudioPlayer

__all__ = [
    "BaseTTS",
    "CartesiaTTS",
    "cartesia_tts",
    "SmartTTSEngine",
    "smart_tts",
    "audio_player",
    "AudioPlayer"
]
