"""
Test suite for configuration loading and validation.
"""

from vision.config import VisionConfig


def test_config_defaults():
    cfg = VisionConfig()
    assert cfg.VISION_LLM_MODEL == "llama-3.3-70b-versatile"
    assert cfg.VISION_NIM_LLM_MODEL == "meta/llama-3.1-8b-instruct"
    assert cfg.VISION_LOAD_BALANCER_STRATEGY == "least_busy"
    assert isinstance(cfg.GROQ_API_KEYS, list)
    assert isinstance(cfg.NVIDIA_API_KEYS, list)
