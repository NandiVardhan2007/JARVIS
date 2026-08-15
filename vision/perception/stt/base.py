"""
Abstract base class for Speech-to-Text (STT) providers.
"""

from abc import ABC, abstractmethod


class BaseSTT(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def transcribe(self, audio_data: bytes, language: str = "en") -> str:
        """Transcribe raw or WAV audio bytes to text."""
        pass
