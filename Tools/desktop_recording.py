"""Desktop screen recording tool."""

import logging
import os
import time
import threading
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Global flag to allow stopping recordings early if needed
_recording_active = False

def _record_task(duration: int, filename: str, fps: int = 30):
    global _recording_active
    try:
        import cv2
        import numpy as np
        import mss
        
        # Ensure it's saved to the desktop or a safe directory
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        filepath = os.path.join(desktop_dir, filename)
        if not filepath.endswith(".mp4"):
            filepath += ".mp4"
            
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            width = monitor["width"]
            height = monitor["height"]
            
            # Using mp4v codec
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
            
            frame_duration = 1.0 / fps
            start_time = time.time()
            frames_captured = 0
            
            _recording_active = True
            logger.info(f"Started recording screen to {filepath} for {duration} seconds at {fps} FPS")
            
            while _recording_active and (time.time() - start_time) < duration:
                loop_start = time.time()
                
                # Grab the screen
                img = sct.grab(monitor)
                # Convert to numpy array
                frame = np.array(img)
                # Convert BGRA to BGR
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                out.write(frame)
                frames_captured += 1
                
                # Sleep to maintain framerate
                elapsed = time.time() - loop_start
                if elapsed < frame_duration:
                    time.sleep(frame_duration - elapsed)
                    
            out.release()
            _recording_active = False
            logger.info(f"Finished recording. Captured {frames_captured} frames.")
            
    except ImportError:
        logger.error("Missing dependencies for screen recording. Install opencv-python and mss.")
    except Exception as e:
        logger.error(f"Recording failed: {e}")
        _recording_active = False

@function_tool
async def record_screen(duration_seconds: int, filename: str = "JARVIS_Recording.mp4") -> str:
    """
    Records a video of the desktop screen for a specified duration.
    
    Args:
        duration_seconds: The length of the recording in seconds.
        filename: The output filename (will be saved to the Desktop). Default is 'JARVIS_Recording.mp4'.
    """
    if duration_seconds > 300:
        return "I can only record up to 5 minutes (300 seconds) at a time to prevent resource drain."
        
    global _recording_active
    if _recording_active:
        return "A recording is already active."
        
    # Start in a background thread so we don't block the agent
    t = threading.Thread(target=_record_task, args=(duration_seconds, filename, 30))
    t.daemon = True
    t.start()
    
    return f"Screen recording started for {duration_seconds} seconds. It will be saved to your Desktop as '{filename}'."

@function_tool
async def stop_recording() -> str:
    """
    Manually stops an active screen recording before its duration expires.
    """
    global _recording_active
    if not _recording_active:
        return "There is no active recording to stop."
        
    _recording_active = False
    return "Screen recording stopped."
