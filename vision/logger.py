"""
Unified Logger with loguru or standard library logging fallback.
Maintains a dedicated log file ('vision.log') in the project root that is automatically reset on every run.
"""

import sys
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent.parent / "vision.log"

try:
    from loguru import logger

    # Remove default handlers to prevent duplicate outputs
    logger.remove()

    # 1. Console / Stdout Handler
    logger.add(
        sys.stdout,
        level="DEBUG",
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )

    # 2. Dedicated Run Log File Handler (mode="w" automatically resets on every run)
    logger.add(
        str(LOG_FILE),
        mode="w",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8"
    )

except ImportError:
    import logging

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-7s | %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(LOG_FILE), mode="w", encoding="utf-8")
        ]
    )
    logger = logging.getLogger("VISION")

__all__ = ["logger", "LOG_FILE"]
