"""
Centralized Configuration Validator for JARVIS.
Runs at startup to ensure all critical environment variables and APIs are accessible.
"""

import os
import sys
import logging
import requests
from dotenv import load_dotenv

# We setup a basic console logger specifically for the startup sequence
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("JARVIS.Config")

def validate_environment():
    """
    Validates the environment configuration.
    Raises SystemExit if a critical misconfiguration is found.
    """
    # Always load the latest .env
    load_dotenv(override=True)
    logger.info("Running pre-flight environment checks...")

    # 1. Check LiveKit (CRITICAL)
    livekit_key = os.getenv("LIVEKIT_API_KEY", "").strip()
    livekit_secret = os.getenv("LIVEKIT_API_SECRET", "").strip()
    livekit_url = os.getenv("LIVEKIT_URL", "").strip()
    
    if not livekit_key or not livekit_secret or not livekit_url:
        logger.error("CRITICAL: LiveKit configuration is missing!")
        logger.error("Please ensure LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and LIVEKIT_URL are set in your .env file.")
        sys.exit(1)

    # 2. Check Groq API (WARNING)
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        logger.warning("GROQ_API_KEY is not set. Cloud LLM features will fail.")
        
    # 3. Check Cartesia TTS (FALLBACK)
    cartesia_key = os.getenv("CARTESIA_API_KEY", "").strip()
    if not cartesia_key:
        logger.warning("CARTESIA_API_KEY is missing. JARVIS will safely fall back to local Piper TTS.")
        # Set a flag that agent.py can use instead of doing os.getenv again
        os.environ["FORCE_PIPER_TTS"] = "1"
    else:
        # Clear the flag if it exists from a previous run
        if "FORCE_PIPER_TTS" in os.environ:
            del os.environ["FORCE_PIPER_TTS"]
        
    # 4. Check Local LLM Health (LM Studio) — informational only. This used to
    # block startup for up to 3s waiting on a network call; the agent's own
    # FallbackAdapter already handles a genuinely-down local LLM at call time,
    # so there's no need to hold up boot for a health check that's just a log
    # line. Runs in the background and logs whenever it resolves.
    local_llm_url = os.getenv("LOCAL_LLM_URL", "").strip()
    if local_llm_url:
        import threading

        def _check_local_llm():
            try:
                base_url = local_llm_url
                if base_url.endswith("/chat/completions"):
                    base_url = base_url.replace("/chat/completions", "")
                if base_url.endswith("/v1"):
                    health_url = base_url + "/models"
                else:
                    health_url = base_url + "/v1/models"

                resp = requests.get(health_url, timeout=3)
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    if models:
                        logger.info(f"Local LLM is online. Model loaded: {models[0].get('id')}")
                    else:
                        logger.warning("Local LLM is online, but NO MODELS ARE LOADED in LM Studio! Code generation tools will fail.")
                else:
                    logger.warning(f"Local LLM returned unexpected status code: {resp.status_code}")
            except Exception as e:
                logger.warning(f"Local LLM offline at {local_llm_url} ({e}). Will fall back to Cloud LLM models (Groq / NVIDIA NIM) automatically if needed.")

        threading.Thread(target=_check_local_llm, daemon=True).start()

    logger.info("Pre-flight checks complete. Booting JARVIS...\n")

if __name__ == "__main__":
    validate_environment()
