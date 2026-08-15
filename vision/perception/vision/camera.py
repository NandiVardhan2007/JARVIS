"""
Webcam and RTSP camera frame capture manager.
"""

from typing import Optional
from io import BytesIO
from vision.logger import logger

try:
    import cv2
except ImportError:
    cv2 = None


class CameraCapture:
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self._cap = None

    def capture_frame(self) -> Optional[bytes]:
        """Capture single frame from local webcam."""
        if cv2 is None:
            logger.warning("[CameraCapture] OpenCV (cv2) is not installed.")
            return None
        try:
            cap = cv2.VideoCapture(self.camera_index)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return None
            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                return jpeg.tobytes()
            return None
        except Exception as e:
            logger.error(f"[CameraCapture] Failed to grab frame: {e}")
            return None


camera_capture = CameraCapture()
