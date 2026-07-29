"""
Hand Gesture Control Module for JARVIS (Windows Native).
Uses OpenCV and MediaPipe Hands to track hand movements and gestures in real time,
controlling the Windows desktop mouse cursor, clicking, scrolling, and dragging.
"""

import os
import time
import asyncio
import logging
import threading
from typing import Optional, Tuple
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Control Flags & State
_gesture_active = False
_gesture_thread: Optional[threading.Thread] = None
_gesture_stop_event = threading.Event()

_cursor_smoothing = 0.45  # Exponential moving average factor
_sensitivity_scale = 1.2
_last_click_time = 0.0
_click_cooldown = 0.35  # seconds

_status_info = {
    "active": False,
    "fps": 0,
    "current_gesture": "None",
    "tracking_mode": "Pointer & Click",
    "sensitivity": 1.2,
    "last_error": None
}

def _get_screen_dimensions() -> Tuple[int, int]:
    """Returns the Windows screen width and height."""
    try:
        import pyautogui
        return pyautogui.size()
    except Exception:
        import ctypes
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

def _gesture_loop():
    """Background thread running OpenCV frame capture and MediaPipe gesture processing."""
    global _gesture_active, _last_click_time, _status_info

    try:
        import cv2
        import numpy as np
        import pyautogui
        import mediapipe as mp
    except ImportError as e:
        logger.error(f"Hand gesture control missing dependency: {e}")
        _status_info["last_error"] = str(e)
        _gesture_active = False
        return

    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.01

    screen_w, screen_h = _get_screen_dimensions()
    
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.65,
        min_tracking_confidence=0.65
    )

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Hand gesture control: Could not open default camera (index 0).")
        _status_info["last_error"] = "Camera index 0 unavailable"
        _gesture_active = False
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    prev_x, prev_y = pyautogui.position()
    frame_count = 0
    start_time = time.time()
    is_dragging = False

    logger.info("Hand Gesture Control loop started on Windows.")
    _status_info["active"] = True

    while not _gesture_stop_event.is_set() and _gesture_active:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        frame_count += 1
        now = time.time()
        if now - start_time >= 1.0:
            _status_info["fps"] = frame_count
            frame_count = 0
            start_time = now

        # Flip horizontally for intuitive mirrored movement
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        gesture_label = "No Hand Detected"

        if results.multi_hand_landmarks:
            landmarks = results.multi_hand_landmarks[0].landmark

            # Key Landmark Points
            wrist = landmarks[0]
            thumb_tip = landmarks[4]
            index_tip = landmarks[8]
            middle_tip = landmarks[12]
            ring_tip = landmarks[16]
            pinky_tip = landmarks[20]

            index_pip = landmarks[6]
            middle_pip = landmarks[10]
            ring_pip = landmarks[14]
            pinky_pip = landmarks[18]

            # Calculate Finger Extended States
            index_up = index_tip.y < index_pip.y
            middle_up = middle_tip.y < middle_pip.y
            ring_up = ring_tip.y < ring_pip.y
            pinky_up = pinky_tip.y < pinky_pip.y

            # Distance Calculations (Normalized Coordinates)
            pinch_dist = np.hypot(index_tip.x - thumb_tip.x, index_tip.y - thumb_tip.y)
            middle_pinch_dist = np.hypot(middle_tip.x - thumb_tip.x, middle_tip.y - thumb_tip.y)

            # 1. Open Palm -> Pause Gesture Tracking
            if index_up and middle_up and ring_up and pinky_up and pinch_dist > 0.12:
                gesture_label = "Palm (Paused)"
                if is_dragging:
                    pyautogui.mouseUp()
                    is_dragging = False

            # 2. Pinch (Index + Thumb) -> Left Click or Drag
            elif pinch_dist < 0.045:
                gesture_label = "Pinch (Left Click / Drag)"
                if not is_dragging:
                    if (now - _last_click_time) > _click_cooldown:
                        pyautogui.mouseDown()
                        is_dragging = True
                        _last_click_time = now
                
                # Move cursor while dragging
                target_x = np.interp(index_tip.x, (0.1, 0.9), (0, screen_w))
                target_y = np.interp(index_tip.y, (0.1, 0.9), (0, screen_h))
                curr_x = prev_x + (target_x - prev_x) * _cursor_smoothing
                curr_y = prev_y + (target_y - prev_y) * _cursor_smoothing
                pyautogui.moveTo(int(curr_x), int(curr_y))
                prev_x, prev_y = curr_x, curr_y

            # 3. Middle + Thumb Pinch -> Right Click
            elif middle_pinch_dist < 0.045:
                gesture_label = "Middle Pinch (Right Click)"
                if is_dragging:
                    pyautogui.mouseUp()
                    is_dragging = False
                if (now - _last_click_time) > _click_cooldown:
                    pyautogui.rightClick()
                    _last_click_time = now

            # 4. Two Fingers Up (Index + Middle) -> Vertical Scroll
            elif index_up and middle_up and not ring_up and not pinky_up:
                gesture_label = "Two Fingers (Scroll)"
                if is_dragging:
                    pyautogui.mouseUp()
                    is_dragging = False
                
                # Scroll based on vertical position delta of index tip
                dy = (index_pip.y - index_tip.y) * 50
                if abs(dy) > 0.5:
                    scroll_amount = int(np.sign(dy) * min(abs(dy) * 15, 120))
                    pyautogui.scroll(scroll_amount)

            # 5. Pointing (Index Finger Only Up) -> Mouse Cursor Movement
            elif index_up and not middle_up and not ring_up and not pinky_up:
                gesture_label = "Pointing (Cursor Move)"
                if is_dragging:
                    pyautogui.mouseUp()
                    is_dragging = False

                # Map camera coordinates (0.1..0.9 range for margin ease) to screen coordinates
                target_x = np.interp(index_tip.x, (0.1, 0.9), (0, screen_w))
                target_y = np.interp(index_tip.y, (0.1, 0.9), (0, screen_h))

                # Smooth cursor motion using exponential smoothing
                curr_x = prev_x + (target_x - prev_x) * _cursor_smoothing
                curr_y = prev_y + (target_y - prev_y) * _cursor_smoothing
                pyautogui.moveTo(int(curr_x), int(curr_y))
                prev_x, prev_y = curr_x, curr_y

            else:
                if is_dragging:
                    pyautogui.mouseUp()
                    is_dragging = False
                gesture_label = "Tracking Hand"

        else:
            if is_dragging:
                pyautogui.mouseUp()
                is_dragging = False

        _status_info["current_gesture"] = gesture_label
        time.sleep(0.015)

    if is_dragging:
        pyautogui.mouseUp()

    cap.release()
    hands.close()
    _status_info["active"] = False
    _status_info["current_gesture"] = "Stopped"
    logger.info("Hand Gesture Control loop stopped.")

# ── LiveKit Function Tools ────────────────────────────────────────────────────

@function_tool
async def start_hand_gesture_control() -> str:
    """
    Activates real-time webcam hand gesture control for Windows desktop mouse pointer, clicks, and scrolling.
    """
    global _gesture_active, _gesture_thread, _gesture_stop_event
    if _gesture_active and _gesture_thread and _gesture_thread.is_alive():
        return "Hand gesture control is already active, sir."

    _gesture_stop_event.clear()
    _gesture_active = True
    _gesture_thread = threading.Thread(target=_gesture_loop, daemon=True)
    _gesture_thread.start()

    return "Hand gesture control activated, sir. Point index finger to move cursor, pinch thumb and index finger to click or drag, use middle finger pinch for right click, and two fingers to scroll."

@function_tool
async def stop_hand_gesture_control() -> str:
    """
    Stops real-time webcam hand gesture control.
    """
    global _gesture_active, _gesture_stop_event
    if not _gesture_active:
        return "Hand gesture control is not currently running."

    _gesture_stop_event.set()
    _gesture_active = False
    return "Hand gesture control has been deactivated, sir."

@function_tool
async def get_gesture_control_status() -> str:
    """
    Returns the current operational status of the hand gesture control module.
    """
    active_str = "Active" if _status_info["active"] else "Inactive"
    fps = _status_info["fps"]
    gesture = _status_info["current_gesture"]
    err = f" | Last Error: {_status_info['last_error']}" if _status_info.get("last_error") else ""

    return f"Gesture Control: {active_str} | FPS: {fps} | Current Gesture: {gesture} | Sensitivity: {_status_info['sensitivity']}{err}"

@function_tool
async def set_gesture_sensitivity(sensitivity: float = 1.2) -> str:
    """
    Adjusts hand gesture tracking speed and sensitivity.

    Args:
        sensitivity: Scale factor from 0.5 (slow/precise) to 3.0 (fast). Default: 1.2.
    """
    global _sensitivity_scale, _cursor_smoothing
    val = max(0.5, min(3.0, sensitivity))
    _sensitivity_scale = val
    _cursor_smoothing = min(0.9, 0.35 * val)
    _status_info["sensitivity"] = round(val, 2)
    return f"Gesture sensitivity set to {round(val, 2)}."
