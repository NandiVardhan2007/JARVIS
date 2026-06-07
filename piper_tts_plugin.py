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
            # Stream audio chunks as they're synthesized instead of collecting
            # all of them first. This dramatically reduces time-to-first-audio.
            chunk_queue = queue.Queue()

            def generate_audio():
                for chunk in self._tts.voice.synthesize(self.input_text):
                    chunk_queue.put(chunk.audio_int16_bytes)
                chunk_queue.put(None)  # sentinel to signal completion

            thread = threading.Thread(target=generate_audio, daemon=True)
            thread.start()

            output_emitter.initialize(
                request_id="piper_tts",
                sample_rate=self._tts.sample_rate,
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
    def __init__(self, model_path: str = "models/en_US-ryan-high.onnx"):
        import os
        if not os.path.isabs(model_path):
            model_path = os.path.join(os.path.dirname(__file__), model_path)
        self.voice = PiperVoice.load(model_path)
        
        # Piper provides sample_rate in config, always 1 channel
        sample_rate = getattr(self.voice.config, 'sample_rate', 22050)
        num_channels = 1
        
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=num_channels,
        )
        self._model_path = model_path
        
    @property
    def model(self) -> str:
        return "piper-ryan-high"

    @property
    def provider(self) -> str:
        return "piper"
        
    def synthesize(self, text: str, *, conn_options = None) -> tts.ChunkedStream:
        if conn_options is None:
            conn_options = DEFAULT_API_CONNECT_OPTIONS
        return PiperChunkedStream(tts=self, input_text=text, conn_options=conn_options)
