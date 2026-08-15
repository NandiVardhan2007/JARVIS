"""
Audio Stream Capture from local microphone using sounddevice with graceful fallback.
"""

import asyncio
from typing import Optional
from vision.core.event_bus import event_bus
from vision.constants import VisionEvents
from vision.logger import logger

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    sd = None
    np = None


class AudioStreamManager:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, chunk_size: int = 1024):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self._stream = None
        self.is_recording = False

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"[AudioStream] Status: {status}")
        if self.is_recording and np is not None:
            audio_bytes = (indata * 32767).astype(np.int16).tobytes()
            asyncio.run_coroutine_threadsafe(
                event_bus.publish(VisionEvents.AUDIO_CHUNK_RECORDED, audio_bytes),
                asyncio.get_event_loop()
            )

    def start(self):
        if sd is None:
            logger.warning("[AudioStream] sounddevice is not installed.")
            return
        if self.is_recording:
            return
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=self.chunk_size,
                callback=self._audio_callback
            )
            self._stream.start()
            self.is_recording = True
            logger.info("[AudioStream] Microphone capture stream started.")
        except Exception as e:
            logger.error(f"[AudioStream] Failed to start microphone stream: {e}")

    def stop(self):
        if self._stream and sd is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self.is_recording = False
        logger.info("[AudioStream] Microphone capture stream stopped.")


audio_stream = AudioStreamManager()
