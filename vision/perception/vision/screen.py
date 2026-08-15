"""
Desktop Screen Capture for Multimodal Vision perception.
"""

from io import BytesIO
from typing import Optional
from vision.logger import logger

try:
    from PIL import ImageGrab, Image
except ImportError:
    ImageGrab = None
    Image = None


class ScreenCapture:
    @staticmethod
    def capture_screen(quality: int = 85, resize_max_dim: int = 1280) -> Optional[bytes]:
        """Capture screenshot and return JPEG bytes."""
        if ImageGrab is None or Image is None:
            logger.warning("[ScreenCapture] PIL / Pillow is not installed.")
            return None
        try:
            img: Image.Image = ImageGrab.grab()
            if max(img.size) > resize_max_dim:
                scale = resize_max_dim / max(img.size)
                new_size = (int(img.width * scale), int(img.height * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            buffer = BytesIO()
            img.convert("RGB").save(buffer, format="JPEG", quality=quality)
            logger.debug(f"[ScreenCapture] Screen snapshot taken ({len(buffer.getvalue())} bytes).")
            return buffer.getvalue()
        except Exception as e:
            logger.error(f"[ScreenCapture] Failed to grab screen: {e}")
            return None


screen_capture = ScreenCapture()
