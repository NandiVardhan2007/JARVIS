"""
Abstract base class for Text-to-Speech (TTS) engines.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseTTS(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize text into raw WAV / MP3 audio bytes."""
        pass

    @abstractmethod
    async def stream_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream synthesized audio chunks."""
        pass
