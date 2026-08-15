"""
Voice Activity Detection (VAD) buffer and speech threshold calculator.
"""

from vision.logger import logger

try:
    import numpy as np
except ImportError:
    np = None


class VADDetector:
    def __init__(self, energy_threshold: float = 0.015):
        self.energy_threshold = energy_threshold

    def is_speech(self, audio_chunk: bytes) -> bool:
        if not audio_chunk:
            return False
        if np is None:
            return True
        samples = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        rms = np.sqrt(np.mean(samples**2)) if len(samples) > 0 else 0.0
        return rms > self.energy_threshold


vad_detector = VADDetector()
