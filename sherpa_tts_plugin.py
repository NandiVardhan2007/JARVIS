"""
Sherpa-ONNX / OmniVoice TTS Plugin for VISION (k2-fsa Ecosystem)
Provides high-speed, local zero-shot voice synthesis & offline ONNX TTS.
"""

import os
import re
import asyncio
import logging
from typing import AsyncGenerator, List, Tuple

logger = logging.getLogger("sherpa_tts")

# Regex to split text into speakable sentence chunks for streaming TTS.
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?…])\s+')

def split_into_sentences(text: str) -> List[str]:
    """Split text into sentence-sized chunks for streaming synthesis."""
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


class SherpaTTS:
    """Sherpa-ONNX / OmniVoice TTS Engine wrapper."""

    def __init__(self, model_dir: str = "models/sherpa_tts"):
        self.enabled = False
        self.tts = None
        self.sample_rate = 22050
        self.num_channels = 1

        try:
            import sherpa_onnx
            base_dir = os.path.dirname(__file__)
            full_model_dir = os.path.join(base_dir, model_dir) if not os.path.isabs(model_dir) else model_dir

            vits_model = os.path.join(full_model_dir, "model.onnx")
            tokens_file = os.path.join(full_model_dir, "tokens.txt")
            data_dir = os.path.join(full_model_dir, "espeak-ng-data")
            lexicon_file = os.path.join(full_model_dir, "lexicon.txt")

            if os.path.exists(vits_model) and os.path.exists(tokens_file):
                logger.info(f"Loading Sherpa-ONNX TTS model from: {full_model_dir}")
                config = sherpa_onnx.OfflineTtsConfig(
                    model=sherpa_onnx.OfflineTtsModelConfig(
                        vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                            model=vits_model,
                            tokens=tokens_file,
                            data_dir=data_dir if os.path.exists(data_dir) else "",
                            lexicon=lexicon_file if os.path.exists(lexicon_file) else "",
                        ),
                    ),
                )
                self.tts = sherpa_onnx.OfflineTts(config)
                self.enabled = True
                self.sample_rate = getattr(self.tts, "sample_rate", 22050)
                logger.info("Sherpa-ONNX TTS loaded successfully.")
            else:
                logger.info("Sherpa-ONNX model files not found at %s. (Will fallback to Piper)", full_model_dir)

        except ImportError:
            logger.info("sherpa-onnx python package not installed. (Will fallback to Piper)")
        except Exception as e:
            logger.warning("Failed to initialize Sherpa-ONNX TTS: %s", e)

    def synthesize_sentence_sync(self, text: str) -> bytes:
        """Synchronously synthesize text to PCM int16 bytes."""
        if not self.enabled or not self.tts:
            return b""
        try:
            audio = self.tts.generate(text)
            # Audio object contains samples array
            import numpy as np
            samples = np.array(audio.samples, dtype=np.float32)
            # Convert float32 [-1.0, 1.0] to int16 PCM
            pcm_int16 = (samples * 32767).astype(np.int16).tobytes()
            self.sample_rate = getattr(audio, "sample_rate", self.sample_rate)
            return pcm_int16
        except Exception as e:
            logger.error(f"Sherpa-ONNX synthesis error: {e}")
            return b""

    async def synthesize_sentence_async(self, text: str) -> bytes:
        """Asynchronously synthesize text to PCM int16 bytes."""
        return await asyncio.to_thread(self.synthesize_sentence_sync, text)

    async def synthesize_stream(self, text: str) -> AsyncGenerator[Tuple[bytes, int], None]:
        """Yields (pcm_bytes, sample_rate) for each sentence in text."""
        sentences = split_into_sentences(text)
        if not sentences:
            sentences = [text]

        for sentence in sentences:
            pcm = await self.synthesize_sentence_async(sentence)
            if pcm:
                yield pcm, self.sample_rate
