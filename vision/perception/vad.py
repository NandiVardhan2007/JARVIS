"""
Silero Voice Activity Detection (VAD) & Neural Speech Segmenter.
Provides deep-learning neural VAD (Silero) with automatic 16kHz resampling and adaptive fallback.
"""

from typing import Optional
from vision.logger import logger

try:
    import torch
    import silero_vad
    from silero_vad import load_silero_vad, VADIterator
    import numpy as np
except ImportError:
    torch = None
    silero_vad = None
    load_silero_vad = None
    VADIterator = None
    np = None


class VADDetector:
    def __init__(self, energy_threshold: float = 0.015, silero_threshold: float = 0.45):
        self.energy_threshold = energy_threshold
        self.silero_threshold = silero_threshold
        self.model = None
        self.vad_iterator = None
        self._init_silero()

    def _init_silero(self):
        if load_silero_vad and torch:
            try:
                self.model = load_silero_vad()
                if VADIterator:
                    self.vad_iterator = VADIterator(
                        self.model,
                        threshold=self.silero_threshold,
                        sampling_rate=16000,
                        min_silence_duration_ms=800,
                        speech_pad_ms=250
                    )
                logger.info("[VAD] Silero Neural VAD model and VADIterator loaded successfully.")
            except Exception as e:
                logger.warning(f"[VAD] Failed to initialize Silero VAD: {e}. Using Energy VAD fallback.")
                self.model = None

    def reset_states(self):
        """Reset internal recurrent neural states for a new conversational turn."""
        if self.vad_iterator is not None:
            try:
                self.vad_iterator.reset_states()
            except Exception:
                pass
        elif self.model is not None:
            try:
                self.model.reset_states()
            except Exception:
                pass

    def resample_to_16k(self, audio_data: "np.ndarray", orig_sr: int) -> "np.ndarray":
        """Fast linear interpolation resampling to 16,000 Hz required by Silero."""
        if orig_sr == 16000 or len(audio_data) == 0:
            return audio_data
        target_length = int(len(audio_data) * 16000 / orig_sr)
        return np.interp(
            np.linspace(0, len(audio_data), target_length, endpoint=False),
            np.arange(len(audio_data)),
            audio_data
        ).astype(np.float32)

    def is_speech(self, audio_chunk: bytes, sample_rate: int = 16000) -> bool:
        """Evaluate if an audio chunk contains active human voice activity."""
        if not audio_chunk:
            return False

        if np is None:
            return True

        samples = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        if len(samples) == 0:
            return False

        # Fast RMS energy check
        rms = float(np.sqrt(np.mean(samples**2)))

        # 1. High-accuracy Silero Neural VAD Inference
        if self.model is not None and torch is not None:
            try:
                # Resample to 16kHz if needed
                samples_16k = self.resample_to_16k(samples, sample_rate) if sample_rate != 16000 else samples
                
                # Silero expects chunks of at least 512 samples at 16kHz
                if len(samples_16k) >= 512:
                    # Take latest 512 samples for instant detection
                    chunk_512 = samples_16k[-512:]
                    tensor = torch.from_numpy(chunk_512).float()
                    speech_prob = self.model(tensor, 16000).item()
                    return speech_prob > self.silero_threshold
            except Exception:
                pass

        # 2. Fast Energy RMS VAD Fallback
        return rms > self.energy_threshold


vad_detector = VADDetector()
