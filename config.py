"""
Centralized Configuration Validator for VISION.
Runs at startup to ensure all critical environment variables and APIs are accessible.
"""

import os
import sys
import logging
import requests
from dotenv import load_dotenv

# We setup a basic console logger specifically for the startup sequence
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("VISION.Config")

def validate_environment(strict: bool = True) -> bool:
    """
    Validates the environment configuration.
    If strict is True, raises SystemExit if a critical misconfiguration is found.
    Returns True if environment is fully valid, False otherwise.
    """
    # Always load the latest .env
    load_dotenv(override=True)
    logger.info("Running pre-flight environment checks...")

    is_valid = True

    # 1. Check LiveKit (CRITICAL)
    livekit_key = os.getenv("LIVEKIT_API_KEY", "").strip()
    livekit_secret = os.getenv("LIVEKIT_API_SECRET", "").strip()
    livekit_url = os.getenv("LIVEKIT_URL", "").strip()
    
    if not livekit_key or not livekit_secret or not livekit_url:
        logger.error("CRITICAL: LiveKit configuration is missing!")
        logger.error("Please ensure LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and LIVEKIT_URL are set in your .env file.")
        is_valid = False
        if strict:
            sys.exit(1)

    # 2. Check Groq API (WARNING)
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        logger.warning("GROQ_API_KEY is not set. Cloud LLM features will fail.")
        
    # 3. Check Cartesia TTS (FALLBACK)
    cartesia_key = os.getenv("CARTESIA_API_KEY", "").strip()
    if not cartesia_key:
        logger.warning("CARTESIA_API_KEY is missing. VISION will safely fall back to local Piper TTS.")
        # Set a flag that agent.py can use instead of doing os.getenv again
        os.environ["FORCE_PIPER_TTS"] = "1"
    else:
        # Clear the flag if it exists from a previous run
        if "FORCE_PIPER_TTS" in os.environ:
            del os.environ["FORCE_PIPER_TTS"]
        
    # 4. Initialize & Validate Online AI API Load Balancer Pool
    try:
        from ai_load_balancer import get_global_balancer
        balancer = get_global_balancer()
        status = balancer.get_status()
        if status["total_endpoints"] > 0:
            providers = set(e["provider"] for e in status["endpoints"])
            logger.info(
                f"AI API Load Balancer online: {status['total_endpoints']} active endpoints "
                f"across providers {list(providers)} using strategy '{status['strategy']}'."
            )
        else:
            logger.warning("No LLM API keys found for OpenRouter, NVIDIA NIM, Groq, Gemini, or Local LLM!")
    except Exception as e:
        logger.warning(f"Failed to initialize AI Load Balancer: {e}")

    logger.info("Pre-flight checks complete. Booting VISION...\n")

if __name__ == "__main__":
    validate_environment()
