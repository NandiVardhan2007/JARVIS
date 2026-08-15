"""
Gemini Multimodal Vision Processor for Screen and Camera image analysis.
"""

from typing import Optional, Dict, Any
from io import BytesIO
from vision.config import config
from vision.logger import logger

try:
    from PIL import Image
    import google.generativeai as genai
except ImportError:
    Image = None
    genai = None


class GeminiVisionAnalyzer:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if self.api_key and genai:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model_name="gemini-2.0-flash")
        else:
            self.model = None

    async def analyze_image(self, image_bytes: bytes, prompt: str = "Describe what you see on this screen or camera feed.") -> str:
        """Send image bytes to Gemini Multimodal Vision API."""
        if not self.model or not Image:
            raise RuntimeError("Gemini API key or PIL not configured for Vision analysis.")

        try:
            pil_img = Image.open(BytesIO(image_bytes))
            response = await self.model.generate_content_async([prompt, pil_img])
            return response.text
        except Exception as e:
            logger.error(f"[GeminiVision] Analysis failed: {e}")
            raise e


gemini_vision = GeminiVisionAnalyzer()
