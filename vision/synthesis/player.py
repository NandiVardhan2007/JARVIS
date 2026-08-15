"""
Low-latency audio playback engine for synthesized speech chunks.
"""

from io import BytesIO
from vision.core.event_bus import event_bus
from vision.constants import VisionEvents
from vision.logger import logger

try:
    import sounddevice as sd
    import soundfile as sf
except ImportError:
    sd = None
    sf = None


class AudioPlayer:
    def __init__(self):
        self.is_playing = False

    def play_wav_bytes(self, audio_data: bytes):
        """Play WAV audio bytes through default output sound device."""
        if not audio_data:
            return
        if sd is None or sf is None:
            logger.warning("[AudioPlayer] sounddevice or soundfile not installed. Skipping audio output.")
            return
        try:
            self.is_playing = True
            with BytesIO(audio_data) as f:
                data, fs = sf.read(f, dtype='float32')
                sd.play(data, fs)
                sd.wait()
        except Exception as e:
            logger.error(f"[AudioPlayer] Playback error: {e}")
        finally:
            self.is_playing = False


audio_player = AudioPlayer()
