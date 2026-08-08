"""
Ultra-Stable Virtual Air Mouse & Gesture Engine for VISION (Windows Native).
Features:
- One-Euro / Velocity-Adaptive Dynamic Low-Pass Filtering
- Micro-Jitter Deadzone Filtering (0 jitter when stationary)
- Click Stabilization Position Lock (prevents click drift)
- Coordinate Clamping & Boundary Safety
- Smooth Dual-Axis Scrolling & Drag/Drop
- Robust Camera Capture & Thread Error Safeguards
"""

import os
import time
import math
import asyncio
import logging
import threading
from typing import Optional, Tuple
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Thread Safety & Control Flags
_state_lock = threading.Lock()
_gesture_active = False
_gesture_thread: Optional[threading.Thread] = None
_gesture_stop_event = threading.Event()

_sensitivity_scale = 1.3
_last_click_time = 0.0
_click_cooldown = 0.28  # seconds

_status_info = {
    "active": False,
    "fps": 0,
    "current_gesture": "None",
    "tracking_mode": "Ultra-Stable Air Mouse",
    "sensitivity": 1.3,
    "last_error": None
}

def _get_screen_dimensions() -> Tuple[int, int]:
    """Returns Windows screen resolution."""
    try:
        import pyautogui
        w, h = pyautogui.size()
        return max(800, w), max(600, h)
    except Exception:
        import ctypes
        user32 = ctypes.windll.user32
        w, h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        return max(800, w), max(600, h)

def _fast_set_cursor_pos(x: int, y: int):
    """Low-latency native Windows API cursor dispatch, falling back to pyautogui."""
    try:
        import ctypes
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
    except Exception:
        import pyautogui
        pyautogui.moveTo(int(x), int(y))

class PrecisionAdaptiveFilter:
    """
    Advanced Velocity-Adaptive Filter (One-Euro style) with soft exponential damping.
    Prevents cursor stickiness on small UI targets while eliminating tremor when stationary.
    """
    def __init__(self, min_alpha: float = 0.12, max_alpha: float = 0.88, soft_deadzone_px: float = 1.5):
        self.min_alpha = min_alpha
        self.max_alpha = max_alpha
        self.soft_deadzone_px = soft_deadzone_px
        self.prev_x: Optional[float] = None
        self.prev_y: Optional[float] = None
        self.last_time = time.time()

    def update(self, target_x: float, target_y: float) -> Tuple[float, float]:
        now = time.time()
        dt = max(0.005, now - self.last_time)
        self.last_time = now

        if self.prev_x is None or self.prev_y is None:
            self.prev_x = target_x
            self.prev_y = target_y
            return target_x, target_y

        dx = target_x - self.prev_x
        dy = target_y - self.prev_y
        dist = math.hypot(dx, dy)

        if dist < 1e-6:
            return self.prev_x, self.prev_y

        # Soft exponential damping for micro-movements instead of hard freeze
        if dist < self.soft_deadzone_px:
            damped_ratio = (dist / self.soft_deadzone_px) ** 1.5
            dx *= damped_ratio
            dy *= damped_ratio
            dist *= damped_ratio

        # Speed calculation (pixels per second)
        speed = dist / dt
        speed_norm = min(1.0, speed / 1800.0)
        
        # Adaptive smoothing factor (One-Euro curve)
        alpha = self.min_alpha + (self.max_alpha - self.min_alpha) * (speed_norm ** 1.3)

        filtered_x = self.prev_x + alpha * dx
        filtered_y = self.prev_y + alpha * dy

        self.prev_x = filtered_x
        self.prev_y = filtered_y
        return filtered_x, filtered_y

    def reset(self):
        self.prev_x = None
        self.prev_y = None
        self.last_time = time.time()

def _gesture_loop(show_preview: bool = False):
    """Background thread running OpenCV frame capture and MediaPipe gesture tracking."""
    global _gesture_active, _last_click_time, _status_info, _sensitivity_scale

    try:
        import cv2
        import numpy as np
        import pyautogui
        import mediapipe as mp
    except ImportError as e:
        logger.error(f"Hand gesture control missing dependency: {e}")
        with _state_lock:
            _status_info["last_error"] = str(e)
            _status_info["active"] = False
            _gesture_active = False
        return

    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.0

    screen_w, screen_h = _get_screen_dimensions()
    adaptive_filter = PrecisionAdaptiveFilter(min_alpha=0.12, max_alpha=0.88, soft_deadzone_px=1.5)
    
    try:
        from Tools.webcam_guard import _get_hand_tracker
        tracker_mode, tracker, mp_module = _get_hand_tracker()
    except Exception as te:
        logger.error(f"Error importing _get_hand_tracker: {te}")
        tracker_mode, tracker, mp_module = None, None, None

    if tracker is None:
        logger.error("Hand gesture control: Could not initialize MediaPipe hand tracker.")
        with _state_lock:
            _status_info["last_error"] = "MediaPipe hand tracker unavailable"
            _status_info["active"] = False
            _gesture_active = False
        return

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        logger.error("Hand gesture control: Could not open default camera device (index 0).")
        with _state_lock:
            _status_info["last_error"] = "Camera index 0 unavailable"
            _status_info["active"] = False
            _gesture_active = False
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    try: cap.set(cv2.CAP_PROP_FPS, 60)
    except Exception: pass

    frame_count = 0
    start_time = time.time()

    is_dragging = False
    pinch_start_time = 0.0
    last_pinch_release_time = 0.0
    click_lock_pos = None

    logger.info("Ultra-Stable Virtual Air Mouse Engine started on Windows.")
    with _state_lock:
        _status_info["active"] = True

    while not _gesture_stop_event.is_set() and _gesture_active:
        try:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            frame_count += 1
            now = time.time()
            if now - start_time >= 1.0:
                with _state_lock:
                    _status_info["fps"] = frame_count
                frame_count = 0
                start_time = now

            # Flip frame horizontally for intuitive mirrored motion
            frame = cv2.flip(frame, 1)
            h_frame, w_frame, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            landmarks = None
            if tracker_mode == 'tasks':
                mp_image = mp_module.Image(image_format=mp_module.ImageFormat.SRGB, data=rgb_frame)
                res = tracker.detect(mp_image)
                if res.hand_landmarks:
                    landmarks = res.hand_landmarks[0]
            elif tracker_mode == 'legacy':
                res = tracker.process(rgb_frame)
                if res.multi_hand_landmarks:
                    landmarks = res.multi_hand_landmarks[0].landmark

            gesture_label = "No Hand Detected"

            if landmarks and len(landmarks) >= 21:
                if show_preview:
                    for lm in landmarks:
                        lx, ly = int(lm.x * w_frame), int(lm.y * h_frame)
                        cv2.circle(frame, (lx, ly), 3, (0, 255, 255), cv2.FILLED)

                # Key Landmarks
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
                index_mcp = landmarks[5]
                middle_mcp = landmarks[9]

                # Compute scale-invariant hand size metric (wrist to middle MCP distance)
                hand_scale = math.hypot(middle_mcp.x - wrist.x, middle_mcp.y - wrist.y) + 1e-5

                # Blend Index Tip (82%) + Index MCP (18%) to suppress high-frequency landmark jitter
                track_x = index_tip.x * 0.82 + index_mcp.x * 0.18
                track_y = index_tip.y * 0.82 + index_mcp.y * 0.18

                # Extended States
                index_up = index_tip.y < index_pip.y
                middle_up = middle_tip.y < middle_pip.y
                ring_up = ring_tip.y < ring_pip.y
                pinky_up = pinky_tip.y < pinky_pip.y

                # Scale-normalized distances (distance-independent)
                pinch_dist = math.hypot(index_tip.x - thumb_tip.x, index_tip.y - thumb_tip.y)
                rel_pinch = pinch_dist / hand_scale

                middle_pinch_dist = math.hypot(middle_tip.x - thumb_tip.x, middle_tip.y - thumb_tip.y)
                rel_middle_pinch = middle_pinch_dist / hand_scale

                # Dynamic sensitivity scaling
                with _state_lock:
                    sens = _sensitivity_scale
                margin_x = max(0.04, min(0.22, 0.13 / sens))
                margin_y = max(0.04, min(0.22, 0.15 / sens))

                # Interpolate to screen space
                raw_target_x = np.interp(track_x, (margin_x, 1.0 - margin_x), (0, screen_w))
                raw_target_y = np.interp(track_y, (margin_y, 1.0 - margin_y), (0, screen_h))

                # Apply Velocity-Adaptive Filter
                filt_x, filt_y = adaptive_filter.update(raw_target_x, raw_target_y)
                
                # Clamp coordinates inside screen bounds
                cursor_x = int(max(0, min(screen_w - 1, filt_x)))
                cursor_y = int(max(0, min(screen_h - 1, filt_y)))

                ix_px, iy_px = int(index_tip.x * w_frame), int(index_tip.y * h_frame)
                tx_px, ty_px = int(thumb_tip.x * w_frame), int(thumb_tip.y * h_frame)

                # 1. Open Palm -> Air Mouse Paused
                if index_up and middle_up and ring_up and pinky_up and rel_pinch > 0.45:
                    gesture_label = "Palm (Air Mouse Paused)"
                    if is_dragging:
                        pyautogui.mouseUp()
                        is_dragging = False
                    click_lock_pos = None

                # 2. Pinch (Left Click / Drag & Drop with Click Stabilization)
                elif rel_pinch < 0.28 or pinch_dist < 0.040 or (is_dragging and rel_pinch < 0.38):
                    gesture_label = "Pinch (Left Click / Drag)"

                    if click_lock_pos is None:
                        click_lock_pos = (cursor_x, cursor_y)
                        pinch_start_time = now

                    # Hold > 0.18s engages Drag Mode
                    if (now - pinch_start_time) > 0.18 and not is_dragging:
                        pyautogui.mouseDown()
                        is_dragging = True

                    if is_dragging:
                        _fast_set_cursor_pos(cursor_x, cursor_y)
                    else:
                        _fast_set_cursor_pos(click_lock_pos[0], click_lock_pos[1])

                    if show_preview:
                        cv2.line(frame, (ix_px, iy_px), (tx_px, ty_px), (255, 212, 0), 4)
                        cv2.circle(frame, (ix_px, iy_px), 12, (255, 212, 0), cv2.FILLED)

                # 3. Pinch Released -> Trigger Single or Double Click
                elif click_lock_pos is not None:
                    duration = now - pinch_start_time
                    if is_dragging:
                        pyautogui.mouseUp()
                        is_dragging = False
                    elif duration < 0.18 and (now - _last_click_time) > _click_cooldown:
                        if (now - last_pinch_release_time) < 0.35:
                            pyautogui.doubleClick()
                            gesture_label = "Double Click"
                        else:
                            pyautogui.click()
                            gesture_label = "Left Click"
                        _last_click_time = now
                        last_pinch_release_time = now

                    click_lock_pos = None

                # 4. Middle + Thumb Pinch -> Right Click
                elif rel_middle_pinch < 0.28 or middle_pinch_dist < 0.040:
                    gesture_label = "Middle Pinch (Right Click)"
                    if is_dragging:
                        pyautogui.mouseUp()
                        is_dragging = False
                    if (now - _last_click_time) > _click_cooldown:
                        pyautogui.rightClick()
                        _last_click_time = now
                    click_lock_pos = None
                    if show_preview:
                        mx_px, my_px = int(middle_tip.x * w_frame), int(middle_tip.y * h_frame)
                        cv2.line(frame, (mx_px, my_px), (tx_px, ty_px), (0, 140, 255), 4)

                # 5. Two Fingers Extended -> Smooth Scroll
                elif index_up and middle_up and not ring_up and not pinky_up:
                    gesture_label = "Two Fingers (Scroll)"
                    if is_dragging:
                        pyautogui.mouseUp()
                        is_dragging = False

                    dy = (index_pip.y - index_tip.y) * 85
                    dx = (index_mcp.x - index_tip.x) * 85

                    if abs(dy) > 0.4:
                        scroll_v = int(np.sign(dy) * min(abs(dy) * 14, 130))
                        pyautogui.scroll(scroll_v)

                    if abs(dx) > 0.8:
                        scroll_h = int(np.sign(dx) * min(abs(dx) * 10, 80))
                        pyautogui.hscroll(scroll_h)
                    click_lock_pos = None

                # 6. Pointing (Index Extended) -> Air Mouse Pointer Motion
                elif index_up and not middle_up and not ring_up and not pinky_up:
                    gesture_label = "Air Mouse Pointer Active"
                    if is_dragging:
                        pyautogui.mouseUp()
                        is_dragging = False
                    _fast_set_cursor_pos(cursor_x, cursor_y)
                    click_lock_pos = None
                    if show_preview:
                        cv2.circle(frame, (ix_px, iy_px), 10, (0, 255, 0), cv2.FILLED)

                else:
                    if is_dragging:
                        pyautogui.mouseUp()
                        is_dragging = False
                    gesture_label = "Tracking Hand"
                    click_lock_pos = None

            else:
                if is_dragging:
                    pyautogui.mouseUp()
                    is_dragging = False
                click_lock_pos = None
                adaptive_filter.reset()

            with _state_lock:
                _status_info["current_gesture"] = gesture_label

            if show_preview:
                curr_fps = _status_info.get("fps", 0)
                curr_sens = _status_info.get("sensitivity", 1.3)
                # Drawing HUD panel
                cv2.rectangle(frame, (10, 10), (460, 115), (0, 0, 0), cv2.FILLED)
                cv2.rectangle(frame, (10, 10), (460, 115), (0, 255, 0), 2)
                cv2.putText(frame, f"VISION Virtual Mouse Test (FPS: {curr_fps})", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(frame, f"Gesture: {gesture_label}", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                cv2.putText(frame, f"Cursor: ({cursor_x if 'cursor_x' in locals() else 0}, {cursor_y if 'cursor_y' in locals() else 0}) | Sens: {curr_sens}x", (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                cv2.putText(frame, "[+] / [-]: Sens  |  Press 'q' or ESC to Exit", (10, h_frame - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 255, 100), 1)

                cv2.imshow("VISION - Virtual Air Mouse Test", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord('q'), ord('Q')):
                    _gesture_stop_event.set()
                    _gesture_active = False
                    break
                elif key in (ord('+'), ord('=')):
                    set_gesture_sensitivity(_sensitivity_scale + 0.2)
                elif key in (ord('-'), ord('_')):
                    set_gesture_sensitivity(_sensitivity_scale - 0.2)

        except Exception as frame_err:
            logger.warning(f"Error in gesture loop iteration: {frame_err}")

        time.sleep(0.005)

    if is_dragging:
        try:
            pyautogui.mouseUp()
        except Exception as e:
            logger.debug(f"Error calling pyautogui.mouseUp: {e}")

    cap.release()
    if tracker and hasattr(tracker, 'close'):
        try: tracker.close()
        except Exception: pass
    if show_preview:
        try: cv2.destroyAllWindows()
        except Exception: pass

    with _state_lock:
        _status_info["active"] = False
        _status_info["current_gesture"] = "Stopped"
    logger.info("Ultra-Stable Virtual Air Mouse loop stopped.")

# ── LiveKit Function Tools ────────────────────────────────────────────────────

@function_tool
async def start_hand_gesture_control() -> str:
    """
    Activates the high-precision Virtual Air Mouse and gesture control for Windows.
    """
    global _gesture_active, _gesture_thread, _gesture_stop_event
    with _state_lock:
        if _gesture_active and _gesture_thread and _gesture_thread.is_alive():
            return "Virtual Air Mouse is already active, sir."

        _gesture_stop_event.clear()
        _gesture_active = True
        _gesture_thread = threading.Thread(target=_gesture_loop, daemon=True)
        _gesture_thread.start()

    return "Ultra-Stable Virtual Air Mouse activated, sir. Point your index finger to move the mouse cursor, pinch index and thumb to click or drag, double-pinch to double-click, middle-finger pinch for right-click, and two fingers to scroll."

@function_tool
async def stop_hand_gesture_control() -> str:
    """
    Stops the Virtual Air Mouse and gesture control.
    """
    global _gesture_active, _gesture_stop_event
    with _state_lock:
        if not _gesture_active:
            return "Virtual Air Mouse is not currently running."

        _gesture_stop_event.set()
        _gesture_active = False

    return "Virtual Air Mouse deactivated, sir."

@function_tool
async def get_gesture_control_status() -> str:
    """
    Returns the current operational status of the Virtual Air Mouse module.
    """
    with _state_lock:
        active_str = "Active" if _status_info["active"] else "Inactive"
        fps = _status_info["fps"]
        gesture = _status_info["current_gesture"]
        err = f" | Last Error: {_status_info['last_error']}" if _status_info.get("last_error") else ""
        sens = _status_info['sensitivity']

    return f"Virtual Air Mouse: {active_str} | FPS: {fps} | Gesture: {gesture} | Sensitivity: {sens}{err}"

@function_tool
async def set_gesture_sensitivity(sensitivity: float = 1.3) -> str:
    """
    Adjusts the Virtual Air Mouse speed and tracking sensitivity.

    Args:
        sensitivity: Scale factor from 0.5 (precise/slow) to 3.0 (fast). Default: 1.3.
    """
    global _sensitivity_scale
    val = max(0.5, min(3.0, sensitivity))
    _sensitivity_scale = val
    with _state_lock:
        _status_info["sensitivity"] = round(val, 2)
    return f"Air Mouse sensitivity set to {round(val, 2)}."

if __name__ == "__main__":
    print("=" * 60)
    print("        VISION - Standalone Virtual Air Mouse Test")
    print("=" * 60)
    print("Starting webcam hand tracking & cursor control...")
    print("Point index finger to move, pinch thumb & index to click/drag,")
    print("middle finger pinch for right-click, two fingers to scroll.")
    print("Press 'q' or 'ESC' in the camera window to stop.")
    print("=" * 60)

    _gesture_active = True
    _gesture_stop_event.clear()
    try:
        _gesture_loop(show_preview=True)
    except KeyboardInterrupt:
        print("\nStopping Virtual Air Mouse...")
        _gesture_stop_event.set()
        _gesture_active = False
