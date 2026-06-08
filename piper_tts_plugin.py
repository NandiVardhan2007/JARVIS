import asyncio
import queue
import threading
import time
from typing import AsyncIterable

from livekit.agents import tts
from livekit import rtc
from piper import PiperVoice
from livekit.agents.tts.tts import DEFAULT_API_CONNECT_OPTIONS
import logging

# Suppress the spammy phoneme debug logs from piper
logging.getLogger("piper.voice").setLevel(logging.INFO)

class PiperChunkedStream(tts.ChunkedStream):
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        try:
            import re
            # Stream audio chunks as they're synthesized instead of collecting
            # all of them first. This dramatically reduces time-to-first-audio.
            chunk_queue = queue.Queue()

            def generate_audio():
                # Detect Telugu characters (Unicode range 0x0C00 - 0x0C7F)
                is_telugu = bool(re.search(r'[\u0c00-\u0c7f]', self.input_text))
                active_voice = self._tts.voice_te if (is_telugu and self._tts.voice_te) else self._tts.voice_en

                for chunk in active_voice.synthesize(self.input_text):
                    chunk_queue.put(chunk.audio_int16_bytes)
                chunk_queue.put(None)  # sentinel to signal completion

            thread = threading.Thread(target=generate_audio, daemon=True)
            thread.start()

            # We use the config from the active voice, but usually they share sample_rate
            is_telugu = bool(re.search(r'[\u0c00-\u0c7f]', self.input_text))
            active_voice = self._tts.voice_te if (is_telugu and self._tts.voice_te) else self._tts.voice_en
            sample_rate = getattr(active_voice.config, 'sample_rate', 22050)

            output_emitter.initialize(
                request_id="piper_tts",
                sample_rate=sample_rate,
                num_channels=self._tts.num_channels,
                mime_type="audio/pcm"
            )

            while True:
                # Fetch from queue in a non-blocking way for asyncio
                try:
                    chunk = await asyncio.to_thread(chunk_queue.get, timeout=30)
                except queue.Empty:
                    logger.error("TTS generation timeout waiting for piper")
                    break
                
                if chunk is None:
                    break
                output_emitter.push(chunk)

            output_emitter.flush()
                
        except Exception as e:
            self._emit_error(e, recoverable=False)
            raise e

class PiperTTS(tts.TTS):
    def __init__(self, english_model: str = "models/en_US-ryan-high.onnx", 
                 telugu_model: str = "models/te_IN-venkatesh-medium.onnx"):
        import os
        base_dir = os.path.dirname(__file__)

        if not os.path.isabs(english_model):
            english_model = os.path.join(base_dir, english_model)
        self.voice_en = PiperVoice.load(english_model)
        
        if not os.path.isabs(telugu_model):
            telugu_model = os.path.join(base_dir, telugu_model)
            
        try:
            self.voice_te = PiperVoice.load(telugu_model)
        except Exception as e:
            logger.warning(f"Failed to load Telugu Piper voice: {e}")
            self.voice_te = None
        
        # Piper provides sample_rate in config, always 1 channel
        sample_rate = getattr(self.voice_en.config, 'sample_rate', 22050)
        num_channels = 1
        
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=num_channels,
        )
        self._model_path = english_model
        
    @property
    def model(self) -> str:
        return "piper-multilingual"

    @property
    def provider(self) -> str:
        return "piper"
        
    def synthesize(self, text: str, *, conn_options = None) -> tts.ChunkedStream:
        if conn_options is None:
            conn_options = DEFAULT_API_CONNECT_OPTIONS
        return PiperChunkedStream(tts=self, input_text=text, conn_options=conn_options)
