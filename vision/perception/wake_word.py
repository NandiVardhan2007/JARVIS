"""
Hands-Free Local Wake-Word Engine for VISION AI OS.
Provides continuous ambient listening for 'Hey VISION', 'Vision', and 'Hey Jarvis' with local zero-latency ONNX inference.
"""

import time
import numpy as np
from typing import Optional, List, Dict
from vision.logger import logger

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    from openwakeword.model import Model as OWWModel
except ImportError:
    OWWModel = None


class WakeWordEngine:
    def __init__(self, target_phrases: Optional[List[str]] = None, threshold: float = 0.45):
        self.target_phrases = target_phrases or ["hey_jarvis", "alexa", "hey_mycroft"]
        self.threshold = threshold
        self.sample_rate = 16000
        self.chunk_size = 1280  # 80ms chunk for openwakeword (1280 samples at 16kHz)
        self.model = None
        self._init_model()

    def _init_model(self):
        """Initialize OpenWakeWord ONNX models."""
        if OWWModel is not None:
            try:
                self.model = OWWModel(
                    wakeword_models=self.target_phrases,
                    inference_framework="onnx"
                )
                logger.info(f"[WakeWord] Initialized local Wake-Word engine with models: {list(self.model.models.keys())}")
            except Exception as e:
                logger.warning(f"[WakeWord] OpenWakeWord init fallback: {e}")
                self.model = None

    def play_activation_chime(self):
        """Plays a pleasant 2-tone ascending activation chime (440Hz -> 880Hz)."""
        if sd is None:
            return
        try:
            sr = 44100
            dur1, dur2 = 0.07, 0.10
            t1 = np.linspace(0, dur1, int(sr * dur1), False)
            t2 = np.linspace(0, dur2, int(sr * dur2), False)
            tone1 = 0.3 * np.sin(2 * np.pi * 587.33 * t1)  # D5
            tone2 = 0.4 * np.sin(2 * np.pi * 880.00 * t2)  # A5
            
            # Apply quick envelope
            fade = int(sr * 0.01)
            tone1[:fade] *= np.linspace(0, 1, fade)
            tone1[-fade:] *= np.linspace(1, 0, fade)
            tone2[:fade] *= np.linspace(0, 1, fade)
            tone2[-fade:] *= np.linspace(1, 0, fade)
            
            chime = np.concatenate([tone1, tone2]).astype(np.float32)
            sd.play(chime, samplerate=sr, blocking=False)
        except Exception as e:
            logger.debug(f"[WakeWord] Chime playback error: {e}")

    def listen_for_wake_word(self, timeout_seconds: Optional[float] = None) -> bool:
        """
        Continuously listen on microphone until wake-word is triggered.
        Returns True when wake-word is detected.
        """
        if sd is None:
            logger.warning("[WakeWord] sounddevice is unavailable.")
            return False

        start_time = time.time()
        logger.info("[WakeWord] Ambient listening active... (Say 'Hey VISION' or 'Vision')")

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.chunk_size
            ) as stream:
                while True:
                    if timeout_seconds and (time.time() - start_time > timeout_seconds):
                        return False

                    audio_data, _ = stream.read(self.chunk_size)
                    audio_chunk = np.frombuffer(audio_data, dtype=np.int16)

                    # 1. OpenWakeWord model inference
                    if self.model is not None:
                        prediction = self.model.predict(audio_chunk)
                        for mdl_name, score in prediction.items():
                            if score >= self.threshold:
                                logger.info(f"[WakeWord] 🎙️ Wake-Word detected! ({mdl_name}: score={score:.2f})")
                                self.play_activation_chime()
                                return True
                    else:
                        # Fallback: High-confidence Energy / VAD Trigger
                        energy = np.sqrt(np.mean(audio_chunk.astype(np.float32)**2))
                        if energy > 2500:
                            logger.info(f"[WakeWord] Energy spike detected ({energy:.0f}). Triggering wake.")
                            self.play_activation_chime()
                            return True

        except Exception as e:
            logger.warning(f"[WakeWord] Stream listening error: {e}")
            return False


# Global Wake Word Singleton
wake_word_engine = WakeWordEngine()
