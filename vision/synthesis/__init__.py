"""
VISION Speech Synthesis (TTS) subsystem.
"""

from vision.synthesis.base import BaseTTS
from vision.synthesis.cartesia_tts import CartesiaTTS
from vision.synthesis.piper_tts import PiperTTS
from vision.synthesis.player import audio_player, AudioPlayer

__all__ = ["BaseTTS", "CartesiaTTS", "PiperTTS", "audio_player", "AudioPlayer"]
