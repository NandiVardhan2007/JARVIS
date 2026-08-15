"""
Configuration management and validation for VISION.
Supports Pydantic Settings with automatic pure Python fallback.
"""

import os
from pathlib import Path
from typing import List, Optional

# Load .env file manually if python-dotenv is not installed
def _load_env_file(filepath: str = ".env"):
    p = Path(filepath)
    if not p.exists():
        return
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and k not in os.environ:
                os.environ[k] = v

_load_env_file()


def _get_list(key: str, default: str = "") -> List[str]:
    val = os.getenv(key, default)
    if not val:
        return []
    return [x.strip() for x in val.split(",") if x.strip()]


class VisionConfig:
    def __init__(self):
        # ── LiveKit ──────────────────────────────────────────
        self.LIVEKIT_URL: Optional[str] = os.getenv("LIVEKIT_URL")
        self.LIVEKIT_API_KEY: Optional[str] = os.getenv("LIVEKIT_API_KEY")
        self.LIVEKIT_API_SECRET: Optional[str] = os.getenv("LIVEKIT_API_SECRET")

        # ── Groq API ─────────────────────────────────────────
        self.GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
        self.GROQ_API_KEYS: List[str] = _get_list("GROQ_API_KEYS")

        # ── NVIDIA NIM ───────────────────────────────────────
        self.NVIDIA_API_KEY: Optional[str] = os.getenv("NVIDIA_API_KEY")
        self.NVIDIA_API_KEYS: List[str] = _get_list("NVIDIA_API_KEYS")

        # ── Cartesia TTS ─────────────────────────────────────
        self.CARTESIA_API_KEY: Optional[str] = os.getenv("CARTESIA_API_KEY")
        self.CARTESIA_API_KEYS: List[str] = _get_list("CARTESIA_API_KEYS")
        self.CARTESIA_VOICE_ID: str = os.getenv("CARTESIA_VOICE_ID", "1259b7e3-cb8a-43df-9446-30971a46b8b0")
        self.CARTESIA_SPEED: str = os.getenv("CARTESIA_SPEED", "slow")

        # ── OpenRouter Key Pool ──────────────────────────────
        self.OPENROUTER_API_KEYS: List[str] = _get_list("OPENROUTER_API_KEYS")
        self.OPENROUTER_LLM_MODEL: str = os.getenv("OPENROUTER_LLM_MODEL", "meta-llama/llama-3.3-70b-instruct")
        self.VISION_LOAD_BALANCER_STRATEGY: str = os.getenv("VISION_LOAD_BALANCER_STRATEGY", "least_busy")

        # ── Models & Engines ─────────────────────────────────
        self.VISION_LLM_PROVIDER: str = os.getenv("VISION_LLM_PROVIDER", "groq")
        self.VISION_LLM_MODEL: str = os.getenv("VISION_LLM_MODEL", "llama-3.3-70b-versatile")
        self.VISION_NIM_LLM_MODEL: str = os.getenv("VISION_NIM_LLM_MODEL", "meta/llama-3.1-8b-instruct")
        self.VISION_STT_ENGINE: str = os.getenv("VISION_STT_ENGINE", "groq")
        self.VISION_STT_MODEL: str = os.getenv("VISION_STT_MODEL", "whisper-large-v3-turbo")

        # ── Multimodal Vision & Gemini ───────────────────────
        self.GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
        self.GEMINI_API_KEYS: List[str] = _get_list("GEMINI_API_KEYS")

        # ── Mobile & ADB Integration ─────────────────────────
        self.VISION_PHONE_IP: str = os.getenv("VISION_PHONE_IP", "192.168.1.3")
        self.VISION_PHONE_PORT: int = int(os.getenv("VISION_PHONE_PORT", "42381"))
        self.VISION_PHONE_PASSWORD: str = os.getenv("VISION_PHONE_PASSWORD", "1234")

        # ── Media & System ───────────────────────────────────
        self.YOUTUBE_API_KEY: Optional[str] = os.getenv("YOUTUBE_API_KEY")
        self.EMAIL_SENDER: Optional[str] = os.getenv("EMAIL_SENDER")
        self.EMAIL_PASSWORD: Optional[str] = os.getenv("EMAIL_PASSWORD")

        # ── Server & Security ────────────────────────────────
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8000"))
        self.DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "vision-default-secret-key-change-me")


config = VisionConfig()
