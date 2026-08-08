"""
Standalone Piper TTS Engine (Zero LiveKit Dependency)
Provides fast, sub-second local text-to-speech synthesis with support for English & Telugu models.
"""

import os
import re
import asyncio
import logging
from typing import AsyncGenerator, List, Tuple
from piper import PiperVoice

logger = logging.getLogger("piper_tts")
logging.getLogger("piper.voice").setLevel(logging.INFO)

# Regex to split text into speakable sentence chunks for streaming TTS.
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?…])\s+')


def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 22050, num_channels: int = 1) -> bytes:
    """Convert raw 16-bit PCM bytes into standard WAV bytes."""
    import io, wave
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentence-sized chunks for streaming synthesis."""
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


class PiperTTS:
    """Standalone Piper TTS Engine."""

    def __init__(
        self,
        english_model: str = "models/en_US-ryan-high.onnx",
        telugu_model: str = "models/te_IN-venkatesh-medium.onnx"
    ):
        base_dir = os.path.dirname(__file__)

        if not os.path.isabs(english_model):
            english_model = os.path.join(base_dir, english_model)
        
        logger.info(f"Loading English Piper voice: {english_model}")
        self.voice_en = PiperVoice.load(english_model)

        if not os.path.isabs(telugu_model):
            telugu_model = os.path.join(base_dir, telugu_model)
            
        try:
            self.voice_te = PiperVoice.load(telugu_model)
            logger.info("Loaded Telugu Piper voice successfully.")
        except Exception as e:
            logger.warning(f"Failed to load Telugu Piper voice: {e}")
            self.voice_te = None

        self.sample_rate = getattr(self.voice_en.config, 'sample_rate', 22050)
        self.num_channels = 1

    def _select_voice(self, text: str) -> Tuple[PiperVoice, int]:
        """Select English or Telugu model based on text script."""
        is_telugu = bool(re.search(r'[\u0c00-\u0c7f]', text))
        active_voice = self.voice_te if (is_telugu and self.voice_te) else self.voice_en
        sample_rate = getattr(active_voice.config, 'sample_rate', 22050)
        return active_voice, sample_rate

    def synthesize_sentence_sync(self, text: str) -> bytes:
        """Synchronously synthesize a single sentence into PCM int16 bytes."""
        voice, _ = self._select_voice(text)
        pcm_chunks = []
        for chunk in voice.synthesize(text):
            pcm_chunks.append(chunk.audio_int16_bytes)
        return b''.join(pcm_chunks)

    async def synthesize_sentence_async(self, text: str) -> bytes:
        """Asynchronously synthesize a single sentence to PCM int16 bytes."""
        return await asyncio.to_thread(self.synthesize_sentence_sync, text)

    async def synthesize_stream(self, text: str) -> AsyncGenerator[Tuple[bytes, int], None]:
        """
        Yields (pcm_bytes, sample_rate) for each sentence in text.
        Allows the audio engine to start playing sentence #1 while sentence #2 is being synthesized.
        """
        sentences = split_into_sentences(text)
        if not sentences:
            sentences = [text]

        for sentence in sentences:
            voice, sample_rate = self._select_voice(sentence)
            pcm = await self.synthesize_sentence_async(sentence)
            if pcm:
                yield pcm, sample_rate
