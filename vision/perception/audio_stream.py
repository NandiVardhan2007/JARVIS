"""
Audio Stream Capture & Voice Listener from local microphone with Silero Voice Activity Detection.
Supports adaptive device selection, PortAudio fallback, and graceful error handling.
"""

import io
import time
import wave
from typing import Optional
from vision.perception.vad import vad_detector
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
        self._mic_error_logged = False

    def is_mic_available(self) -> bool:
        if sd is None or np is None:
            return False
        try:
            dev = sd.query_devices(kind='input')
            return dev is not None
        except Exception:
            return False

    def record_phrase(
        self,
        energy_threshold: float = 0.012,
        silence_timeout: float = 1.1,
        max_duration: float = 25.0
    ) -> Optional[bytes]:
        """
        Listen on the microphone until speech is detected via Silero/Energy VAD,
        record the utterance, and stop automatically after silence_timeout of silence.
        """
        if sd is None or np is None:
            return None

        from collections import deque
        frames = []
        is_speaking = False
        silence_start_time = None
        start_time = time.time()

        try:
            dev_info = sd.query_devices(kind='input')
            native_rate = int(dev_info.get('default_samplerate', self.sample_rate))
            native_channels = min(self.channels, dev_info.get('max_input_channels', 1))

            pre_roll_chunks = int(0.35 * (native_rate / self.chunk_size))  # ~350ms pre-roll
            pre_roll = deque(maxlen=max(2, pre_roll_chunks))

            with sd.InputStream(
                samplerate=native_rate,
                channels=native_channels,
                dtype="float32",
                blocksize=self.chunk_size
            ) as stream:
                self._mic_error_logged = False
                while True:
                    if time.time() - start_time > max_duration:
                        break

                    data, _ = stream.read(self.chunk_size)
                    rms = np.sqrt(np.mean(data**2))
                    
                    # Convert to int16 bytes for VAD check
                    int16_chunk = (data * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
                    speech_active = (rms > energy_threshold) or vad_detector.is_speech(int16_chunk, native_rate)

                    if speech_active:
                        if not is_speaking:
                            is_speaking = True
                            # Prepend pre-roll buffer so the start of the first word is not clipped
                            frames.extend(list(pre_roll))
                        frames.append(data.copy())
                        silence_start_time = None
                    else:
                        if is_speaking:
                            frames.append(data.copy())
                            if silence_start_time is None:
                                silence_start_time = time.time()
                            elif time.time() - silence_start_time >= silence_timeout:
                                break
                        else:
                            pre_roll.append(data.copy())

            if not frames or not is_speaking:
                return None

            audio_array = np.concatenate(frames, axis=0)
            int16_data = (audio_array * 32767).clip(-32768, 32767).astype(np.int16)

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(native_channels)
                wf.setsampwidth(2)
                wf.setframerate(native_rate)
                wf.writeframes(int16_data.tobytes())

            return wav_buffer.getvalue()

        except Exception as e:
            if not self._mic_error_logged:
                logger.warning(f"[AudioStream] Microphone capture unavailable ({e}). Please ensure Windows Microphone permissions are enabled.")
                self._mic_error_logged = True
            return None


audio_stream = AudioStreamManager()
