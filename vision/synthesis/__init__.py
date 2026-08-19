"""
VISION Speech Synthesis (TTS) subsystem.
"""

from vision.synthesis.base import BaseTTS
from vision.synthesis.cartesia_tts import CartesiaTTS
from vision.synthesis.piper_tts import PiperTTS
from vision.synthesis.local_tts import LocalTTS, local_tts
from vision.synthesis.smart_tts import SmartTTSEngine, smart_tts
from vision.synthesis.player import audio_player, AudioPlayer

__all__ = [
    "BaseTTS",
    "CartesiaTTS",
    "PiperTTS",
    "LocalTTS",
    "local_tts",
    "SmartTTSEngine",
    "smart_tts",
    "audio_player",
    "AudioPlayer"
]

