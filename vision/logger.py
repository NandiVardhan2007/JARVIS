"""
Unified Logger with loguru or standard library logging fallback.
"""

import sys
import logging

try:
    from loguru import logger
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s - %(message)s",
        stream=sys.stdout
    )
    logger = logging.getLogger("VISION")

__all__ = ["logger"]
