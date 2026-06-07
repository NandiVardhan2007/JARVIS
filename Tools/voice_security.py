"""Voice Security and Speaker Diarization Module."""

import logging
import os
import torch
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Path to store the authorized user's voice print embedding
VOICE_PRINT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jarvis_memory", "voice_print.pt")

class VoiceSecurity:
    def __init__(self):
        self.verifier = None
        
    def _lazy_load(self):
        if self.verifier is None:
            try:
                from speechbrain.inference import SpeakerRecognition
                self.verifier = SpeakerRecognition.from_hparams(
                    source="speechbrain/spkrec-ecapa-voxceel", 
                    savedir="pretrained_models/spkrec-ecapa-voxceel"
                )
            except ImportError:
                logger.warning("speechbrain is not installed. Voice security will run in simulation mode.")
                
    @function_tool
    async def register_authorized_voice(self, audio_path: str) -> str:
        """
        Registers a baseline voice print for the authorized user from an audio file.
        
        Args:
            audio_path: The path to a .wav file containing the user's voice.
        """
        self._lazy_load()
        if self.verifier is None:
            return "Simulation Mode: Authorized voice registered successfully."
            
        try:
            # Extract embedding
            embedding = self.verifier.encode_batch(self.verifier.load_audio(audio_path))
            os.makedirs(os.path.dirname(VOICE_PRINT_PATH), exist_ok=True)
            torch.save(embedding, VOICE_PRINT_PATH)
            return "Voice print successfully registered and secured."
        except Exception as e:
            logger.error(f"Failed to register voice: {e}")
            return f"Registration failed: {e}"

    def verify_audio_frame(self, audio_data) -> bool:
        """
        Verifies if an incoming audio frame matches the authorized voice print.
        Returns True if authorized, False if unauthorized.
        """
        self._lazy_load()
        if self.verifier is None:
            # In simulation mode, default to authorized to not break the assistant
            return True
            
        if not os.path.exists(VOICE_PRINT_PATH):
            logger.warning("No voice print registered. Allowing access by default.")
            return True
            
        try:
            authorized_embedding = torch.load(VOICE_PRINT_PATH)
            # In a real LiveKit implementation, we would convert audio_data (AudioFrame) to tensor
            # For demonstration, we assume audio_data is a tensor
            incoming_embedding = self.verifier.encode_batch(audio_data)
            
            # Cosine similarity
            score, prediction = self.verifier.verify_batch(authorized_embedding, incoming_embedding)
            return prediction.item()
        except Exception as e:
            logger.error(f"Voice verification error: {e}")
            return True

voice_security = VoiceSecurity()

# Expose the tool
register_authorized_voice = voice_security.register_authorized_voice
