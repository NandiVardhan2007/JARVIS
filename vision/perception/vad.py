"""
Silero Voice Activity Detection (VAD) & Energy Speech Segmenter.
Provides deep-learning neural VAD (Silero) with fallback to energy-based thresholding.
"""

from typing import Optional
from vision.logger import logger

try:
    import torch
    import silero_vad
    import numpy as np
except ImportError:
    torch = None
    silero_vad = None
    np = None


class VADDetector:
    def __init__(self, energy_threshold: float = 0.015, silero_threshold: float = 0.5):
        self.energy_threshold = energy_threshold
        self.silero_threshold = silero_threshold
        self.model = None
        self._init_silero()

    def _init_silero(self):
        if silero_vad and torch:
            try:
                self.model = silero_vad.load_silero_vad()
                logger.info("[VAD] Silero VAD neural model loaded successfully.")
            except Exception as e:
                logger.warning(f"[VAD] Failed to initialize Silero VAD model: {e}. Using Energy VAD fallback.")
                self.model = None

    def is_speech(self, audio_chunk: bytes, sample_rate: int = 16000) -> bool:
        """Evaluate if an audio chunk contains human voice activity."""
        if not audio_chunk:
            return False

        if np is None:
            return True

        samples = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        if len(samples) == 0:
            return False

        # 1. High-accuracy Silero Neural VAD
        if self.model is not None and torch is not None and len(samples) >= 512:
            try:
                tensor = torch.from_numpy(samples).float()
                # Run silero model inference
                speech_prob = self.model(tensor, sample_rate).item()
                return speech_prob > self.silero_threshold
            except Exception:
                pass

        # 2. Fast Energy RMS VAD fallback
        rms = np.sqrt(np.mean(samples**2))
        return rms > self.energy_threshold


vad_detector = VADDetector()
