"""
Webcam Gesture Control & Live Visual Context Analyzer for VISION.
Uses OpenCV + MediaPipe (optional) — uses lazy imports so missing
packages never crash the main app at startup.
"""

import os
import time
import asyncio
import logging
import threading
import base64
import requests
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Active session trackers
_camera_active = False
_camera_thread = None
_latest_frame = None  # Holds raw numpy array of last frame
_latest_encoded_frame = None  # Holds JPEG encoded bytes for live HTTP stream
_http_server = None

# Signalled by _camera_loop once the camera has actually been opened (or has
# definitively failed to open), so start_webcam_guard can report the TRUE
# outcome instead of claiming success the instant the background thread is
# launched, before it's had any chance to actually open a device.
_camera_ready_event = threading.Event()
_camera_open_failed = False
_uinput_available = False
_mouse_backend_status = ""

# Last time the frontend actually pulled a frame (snapshot/video_feed hit).
# The idle-timeout in _camera_loop only releases the camera when BOTH no
# hand has been seen AND nobody's actively viewing the feed — otherwise a
# user just watching their camera preview (not gesturing) would see the
# feed silently die after 5 minutes, which looks like a broken video feed
# rather than the intentional CPU/GPU-saving pause it actually is.
_last_frame_requested = 0.0

# UDP client to send commands back to VISION session
import socket
_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def _send_action_command(action_text: str):
    """Sends a text command back to VISION via internal UDP port."""
    try:
        import json
        payload = json.dumps({'type': 'text_input', 'text': action_text}).encode("utf-8")
        _sock.sendto(payload, ("127.0.0.1", 5004))
        _sock.sendto(payload, ("127.0.0.1", 5016))
    except Exception as e:
        logger.debug(f"_send_action_command UDP broadcast error: {e}")


def _get_screen_size():
    try:
        import pyautogui
        return pyautogui.size()
    except Exception:
        return 1920, 1080

_cached_standby_frame = None

def _get_standby_frame_bytes():
    global _cached_standby_frame
    if _cached_standby_frame is not None:
        return _cached_standby_frame
    try:
        import cv2
        import numpy as np
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(img, (15, 15), (625, 465), (50, 40, 20), 2)
        cv2.putText(img, "VISION VISUAL CORE - STANDBY", (100, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 212, 0), 2)
        cv2.putText(img, "Say 'start webcam' or tap 'Start Cam' to activate", (75, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        _, buf = cv2.imencode('.jpg', img)
        _cached_standby_frame = buf.tobytes()
        return _cached_standby_frame
    except Exception:
        return b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\x27 ",#\x1c\x1c(7),01444\x1f\x279=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'

def _start_mjpeg_stream_server():
    global _http_server
    if _http_server is not None:
        return

    from http.server import HTTPServer, BaseHTTPRequestHandler
    from socketserver import ThreadingMixIn

    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True
        allow_reuse_address = True


    class CamHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            global _last_frame_requested
            if self.path.startswith('/snapshot') or self.path.startswith('/frame'):
                _last_frame_requested = time.time()
                try:
                    if _camera_active and _latest_encoded_frame is not None:
                        frame_bytes = _latest_encoded_frame
                    else:
                        frame_bytes = _get_standby_frame_bytes()

                    self.send_response(200)
                    self.send_header('Content-type', 'image/jpeg')
                    self.send_header('Content-length', str(len(frame_bytes)))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                    self.end_headers()
                    self.wfile.write(frame_bytes)
                except Exception as stream_err:
                    logger.debug(f"HTTP MJPEG handler snapshot write error: {stream_err}")
                return

            if self.path.startswith('/video_feed') or self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=jpgboundary')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                while True:
                    try:
                        _last_frame_requested = time.time()
                        if _camera_active and _latest_encoded_frame is not None:
                            frame_bytes = _latest_encoded_frame
                        else:
                            frame_bytes = _get_standby_frame_bytes()

                        self.wfile.write(b'--jpgboundary\r\n')
                        self.send_header('Content-type', 'image/jpeg')
                        self.send_header('Content-length', str(len(frame_bytes)))
                        self.end_headers()
                        self.wfile.write(frame_bytes)
                        self.wfile.write(b'\r\n')
                        time.sleep(0.04)
                    except Exception:
                        break


        def log_message(self, format, *args):
            pass  # Suppress HTTP access logging in stdout

    try:
        _http_server = ThreadedHTTPServer(('0.0.0.0', 5055), CamHandler)
        t = threading.Thread(target=_http_server.serve_forever, daemon=True)
        t.start()
        logger.info("Live MJPEG video stream server running at http://127.0.0.1:5055/video_feed")
    except Exception as e:
        _http_server = True
        logger.error(
            f"Could not bind the video feed HTTP server on port 5055 ({e}). "
            f"The frontend video widget will show a standby image instead of the live feed. "
            f"Check if another process is already using port 5055."
        )



def _get_hand_tracker():
    try:
        import mediapipe as mp
        # 1. Try legacy solutions API first if present
        if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'hands'):
            logger.info("MediaPipe: Using mp.solutions.hands legacy API")
            return ('legacy', mp.solutions.hands.Hands(max_num_hands=1, min_detection_confidence=0.6), mp)
        
        # 2. MediaPipe 0.10+ Tasks API
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision
        
        model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "hand_landmarker.task")
        if not os.path.exists(model_path):
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
            import urllib.request
            logger.info("Downloading MediaPipe hand_landmarker.task model...")
            urllib.request.urlretrieve(url, model_path)
            
        base_options = mp_tasks.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        landmarker = vision.HandLandmarker.create_from_options(options)
        logger.info("MediaPipe 0.10+ HandLandmarker Tasks API initialized successfully!")
        return ('tasks', landmarker, mp)
    except Exception as e:
        logger.warning(f"MediaPipe hand tracking initialization error ({e}). Gesture tracking disabled.")
        return (None, None, None)

def _find_webcam_capture(cv2):
    """Probes multiple video device indices, backends, and FOURCC formats to open an available camera."""
    attempts_log = []

    for idx in [0, 1, 2, 3]:
        # 1. Try V4L2 with MJPG pixel format (required by Sonix and laptop webcams)
        try:
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                ret, frame = cap.read()
                if ret and frame is not None:
                    logger.info(f"Webcam opened successfully on index {idx} (V4L2 MJPG)")
                    return cap
                attempts_log.append(f"idx={idx} V4L2/MJPG: opened but read() returned no frame")
                cap.release()
            else:
                attempts_log.append(f"idx={idx} V4L2/MJPG: could not open (no such device or in use)")
        except Exception as e:
            attempts_log.append(f"idx={idx} V4L2/MJPG: exception — {e}")

        # 2. Fallback to default backend with MJPG
        try:
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                ret, frame = cap.read()
                if ret and frame is not None:
                    logger.info(f"Webcam opened successfully on index {idx} (MJPG)")
                    return cap
                attempts_log.append(f"idx={idx} default/MJPG: opened but read() returned no frame")
                cap.release()
            else:
                attempts_log.append(f"idx={idx} default/MJPG: could not open")
        except Exception as e:
            attempts_log.append(f"idx={idx} default/MJPG: exception — {e}")

        # 3. Fallback to default backend standard
        try:
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    logger.info(f"Webcam opened successfully on index {idx}")
                    return cap
                attempts_log.append(f"idx={idx} default: opened but read() returned no frame")
                cap.release()
            else:
                attempts_log.append(f"idx={idx} default: could not open")
        except Exception as e:
            attempts_log.append(f"idx={idx} default: exception — {e}")

    # 4. GStreamer/libcamerasrc — tried once, not per-index. Some newer laptop
    # cameras (MIPI/IPU6, common on recent Wayland-first hardware) only
    # expose themselves via libcamera/PipeWire and don't work through
    # classic V4L2 at all. libcamerasrc auto-selects the first camera rather
    # than taking a numeric index the way V4L2 does.
    try:
        pipeline = "libcamerasrc ! video/x-raw,width=640,height=480 ! videoconvert ! appsink"
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                logger.info("Webcam opened successfully via GStreamer/libcamerasrc")
                return cap
            attempts_log.append("gstreamer/libcamerasrc: opened but read() returned no frame")
            cap.release()
        else:
            attempts_log.append("gstreamer/libcamerasrc: could not open (GStreamer/libcamera may not be installed)")
    except Exception as e:
        attempts_log.append(f"gstreamer/libcamerasrc: exception — {e}")

    logger.error(
        "Could not open any webcam after trying indices 0-3 across V4L2/default backends, "
        "plus a GStreamer/libcamerasrc fallback:\n"
        + "\n".join(f"  - {a}" for a in attempts_log)
    )
    return None


def _camera_loop():
    global _camera_active, _latest_frame, _latest_encoded_frame, _camera_open_failed
    global _uinput_available, _mouse_backend_status

    try:
        import cv2
        import numpy as np
    except ImportError:
        logger.error("opencv-python not installed. Cannot start webcam.")
        return

    screen_w, screen_h = _get_screen_size()
    uinput_mouse = None
    uinput_error = ""
    import sys
    if sys.platform != "win32":
        try:
            from evdev import UInput, ecodes as e
            cap_events = {
                e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL],
                e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
            }
            uinput_mouse = UInput(cap_events, name='vision-air-mouse')
            uinput_mouse.write(e.EV_REL, e.REL_X, 0)
            uinput_mouse.syn()
            logger.info("Kernel /dev/uinput virtual relative mouse initialized for GNOME Wayland!")
        except Exception as _ue:
            uinput_error = str(_ue)
            logger.warning(f"uinput mouse unavailable: {_ue}")
            if uinput_mouse:
                try: uinput_mouse.close()
                except Exception as close_err: logger.debug(f"uinput mouse close error: {close_err}")
            uinput_mouse = None

    mouse = None
    pynput_error = ""
    try:
        from pynput.mouse import Controller, Button
        mouse = Controller()
    except Exception as e:
        pynput_error = str(e)
        logger.warning(f"pynput mouse controller unavailable ({e}). Cursor control disabled.")

    if sys.platform != "win32" and not uinput_mouse and mouse:
        logger.warning(
            "Only pynput is available for cursor control, no uinput. On native Wayland "
            "(GNOME), pynput's absolute positioning frequently does not move the real "
            "system cursor at all, even though it initializes without error — gestures "
            "will still be DETECTED (static poses like palm/fist will still fire), but "
            "the cursor itself likely won't move. Fix uinput permissions for reliable "
            "Wayland cursor control — see get_webcam_diagnostics for details."
        )

    _uinput_available = uinput_mouse is not None
    if uinput_mouse:
        _mouse_backend_status = "uinput (reliable on Wayland)"
    elif mouse:
        _mouse_backend_status = (
            f"pynput only (uinput failed: {uinput_error or 'unknown error'}) — "
            f"cursor movement will likely NOT work on native Wayland"
        )
    else:
        _mouse_backend_status = f"NONE available (uinput: {uinput_error or 'failed'}; pynput: {pynput_error or 'failed'})"

    logger.info("Starting webcam monitoring loop with hand mouse control...")
    cap = _find_webcam_capture(cv2)
    if cap is None or not cap.isOpened():
        logger.error("Could not open any webcam device.")
        _camera_open_failed = True
        _camera_active = False
        _camera_ready_event.set()
        if uinput_mouse:
            try: uinput_mouse.close()
            except Exception as close_err: logger.debug(f"uinput mouse close error on camera fail: {close_err}")
        return

    _camera_open_failed = False
    _camera_ready_event.set()

    _start_mjpeg_stream_server()

    tracker_mode, tracker, mp_module = _get_hand_tracker()

    screen_w, screen_h = _get_screen_size()
    prev_x, prev_y = screen_w // 2, screen_h // 2
    margin = 0.15  # Bounding margin to easily reach screen corners

    try:
        from Tools.hand_gesture_control import PrecisionAdaptiveFilter, _fast_set_cursor_pos
        adaptive_filter = PrecisionAdaptiveFilter(min_alpha=0.14, max_alpha=0.88, soft_deadzone_px=1.5)
    except Exception:
        adaptive_filter = None
        _fast_set_cursor_pos = None

    is_dragging = False
    click_lock_pos = None
    pinch_start_time = 0.0
    last_click_time = 0.0
    last_right_click_time = 0.0
    was_right_pinched = False

    # Two-finger (index+middle) scroll tracking
    scroll_ref_y = None
    did_scroll_this_hold = False
    SCROLL_MOVE_THRESHOLD = 0.018   # normalized y-delta per frame to register as a scroll tick
    SCROLL_TICKS_PER_UNIT = 3       # scroll wheel "clicks" per gesture tick

    # Open-palm swipe (window switching) tracking
    swipe_ref_x = None
    swipe_start_time = 0.0
    did_swipe_this_hold = False
    last_swipe_time = 0.0
    SWIPE_MIN_DISTANCE = 0.16       # normalized x-distance to count as a swipe
    SWIPE_MAX_DURATION = 0.5        # must happen within this many seconds
    SWIPE_COOLDOWN = 1.0

    last_action_gesture = ""
    last_action_time = 0.0
    action_cooldown = 1.0


    # Load OpenCV Face Classifier
    face_cascade = None
    try:
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        if os.path.exists(cascade_path):
            face_cascade = cv2.CascadeClassifier(cascade_path)
    except Exception as cascade_err:
        logger.debug(f"Haar cascade face classifier load error: {cascade_err}")

    # Auto-release: continuous camera capture + per-frame hand tracking is a
    # real CPU/GPU cost. If no hand gesture has been seen AND nobody's
    # actively viewing the video feed for this long, stop the loop and
    # release the camera rather than running it forever on the off-chance a
    # hand appears. Re-enable any time with start_webcam_guard. Checking
    # BOTH signals (not just hand detection) matters: someone watching their
    # camera preview without gesturing shouldn't see it silently die.
    idle_timeout = float(os.getenv("VISION_GESTURE_IDLE_TIMEOUT_SEC", "300"))
    last_hand_seen = time.time()
    global _last_frame_requested
    _last_frame_requested = time.time()

    while _camera_active:
        idle_for = time.time() - max(last_hand_seen, _last_frame_requested)
        if idle_for > idle_timeout:
            logger.info(f"No hand gesture or feed activity for {idle_timeout:.0f}s — releasing webcam to save CPU/GPU.")
            try:
                from agent import send_hud_state
                send_hud_state({
                    "state": "notify",
                    "description": "Gesture control paused (idle) — camera released.",
                })
            except Exception as hud_err:
                logger.debug(f"HUD state update failed in webcam loop: {hud_err}")
            _camera_active = False
            break

        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        now = time.time()


        # Save raw frame before annotations
        _latest_frame = frame.copy()

        # Mirror frame for natural camera preview
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # Face Recognition / Detection
        if face_cascade is not None:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
                for (fx, fy, fw, fh) in faces:
                    cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (0, 212, 255), 2)
                    cv2.rectangle(frame, (fx, fy - 22), (fx + fw, fy), (0, 212, 255), cv2.FILLED)
                    cv2.putText(frame, "MASTER FACE CONFIRMED", (fx + 4, fy - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)
            except Exception as face_err:
                logger.debug(f"Face cascade detection error: {face_err}")

        landmarks = None


        if tracker is not None:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            if tracker_mode == 'tasks':
                mp_image = mp_module.Image(image_format=mp_module.ImageFormat.SRGB, data=rgb_frame)
                results = tracker.detect(mp_image)
                if results.hand_landmarks:
                    landmarks = results.hand_landmarks[0]
            elif tracker_mode == 'legacy':
                results = tracker.process(rgb_frame)
                if results.multi_hand_landmarks:
                    landmarks = results.multi_hand_landmarks[0].landmark

            if landmarks:
                last_hand_seen = time.time()
                # Landmark 8: Index Tip, Landmark 4: Thumb Tip, Landmark 0: Wrist, Landmark 9: Middle MCP
                index_x, index_y = landmarks[8].x, landmarks[8].y
                thumb_x, thumb_y = landmarks[4].x, landmarks[4].y
                wrist_x, wrist_y = landmarks[0].x, landmarks[0].y

                # Calculate hand scale (Index to Wrist distance) to adapt pinch threshold automatically
                hand_scale = np.hypot(index_x - wrist_x, index_y - wrist_y) + 1e-5

                # Normalize index tip position to screen coordinates with comfortable margin (0.12)
                norm_x = np.clip((index_x - margin) / (1.0 - 2 * margin), 0.0, 1.0)
                norm_y = np.clip((index_y - margin) / (1.0 - 2 * margin), 0.0, 1.0)

                target_x = int(norm_x * screen_w)
                target_y = int(norm_y * screen_h)

                # Adaptive One-Euro smoothing with soft exponential damping
                if adaptive_filter:
                    filt_x, filt_y = adaptive_filter.update(target_x, target_y)
                    curr_x = int(max(0, min(screen_w - 1, filt_x)))
                    curr_y = int(max(0, min(screen_h - 1, filt_y)))
                else:
                    curr_x, curr_y = target_x, target_y

                rel_dx = curr_x - prev_x
                rel_dy = curr_y - prev_y
                prev_x, prev_y = curr_x, curr_y

                # Move desktop cursor — send relative deltas via uinput (GNOME Wayland)
                if uinput_mouse and (rel_dx != 0 or rel_dy != 0):
                    try:
                        from evdev import ecodes as e
                        uinput_mouse.write(e.EV_REL, e.REL_X, int(rel_dx))
                        uinput_mouse.write(e.EV_REL, e.REL_Y, int(rel_dy))
                        uinput_mouse.syn()
                    except Exception as ev_err:
                        logger.debug(f"uinput mouse write error: {ev_err}")

                # Adaptive Pinch Distance (Index tip to Thumb tip relative to hand scale)
                pinch_raw = np.hypot(index_x - thumb_x, index_y - thumb_y)
                rel_pinch = pinch_raw / hand_scale
                now = time.time()

                # PINCH CLICK & DRAG WINDOW LOGIC
                is_pinched = (rel_pinch < 0.28) or (pinch_raw < 0.045)

                ix_px, iy_px = int(index_x * w), int(index_y * h)
                tx_px, ty_px = int(thumb_x * w), int(thumb_y * h)

                if is_pinched:
                    if click_lock_pos is None:
                        click_lock_pos = (curr_x, curr_y)

                    if not is_dragging:
                        is_dragging = True
                        pinch_start_time = now
                        if uinput_mouse:
                            try:
                                from evdev import ecodes as e
                                uinput_mouse.write(e.EV_KEY, e.BTN_LEFT, 1)
                                uinput_mouse.syn()
                            except Exception as ev_err: logger.debug(f"uinput mouse BTN_LEFT press error: {ev_err}")
                        if mouse:
                            try:
                                mouse.press(Button.left)
                            except Exception as m_err: logger.debug(f"mouse press error: {m_err}")

                    # Position cursor — drag follows movement, click locks position to suppress drift
                    active_pos = (curr_x, curr_y) if (now - pinch_start_time > 0.18) else click_lock_pos
                    if _fast_set_cursor_pos:
                        _fast_set_cursor_pos(active_pos[0], active_pos[1])
                    elif mouse:
                        try: mouse.position = active_pos
                        except Exception: pass

                    # Draw vibrant active pinch indicator (Cyan-Green glowing line)
                    cv2.line(frame, (ix_px, iy_px), (tx_px, ty_px), (255, 212, 0), 4)
                    cv2.circle(frame, (ix_px, iy_px), 12, (255, 212, 0), cv2.FILLED)
                    cv2.putText(frame, "PINCH CLICK / GRAB ACTIVE", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 212, 0), 2)
                else:
                    click_lock_pos = None
                    if _fast_set_cursor_pos:
                        _fast_set_cursor_pos(curr_x, curr_y)
                    elif mouse:
                        try: mouse.position = (curr_x, curr_y)
                        except Exception: pass

                    if is_dragging:
                        is_dragging = False
                        pinch_duration = now - pinch_start_time
                        if uinput_mouse:
                            try:
                                from evdev import ecodes as e
                                uinput_mouse.write(e.EV_KEY, e.BTN_LEFT, 0)
                                uinput_mouse.syn()
                            except Exception as ev_err: logger.debug(f"uinput mouse BTN_LEFT release error: {ev_err}")
                        if mouse:
                            try:
                                mouse.release(Button.left)
                            except Exception as m_err: logger.debug(f"mouse release error: {m_err}")

                        # Short tap pinch (<0.35s) = Click / Double Click
                        if pinch_duration < 0.35:
                            if (now - last_click_time) < 0.4:
                                logger.info("Double pinch detected -> Double Click")
                                if mouse:
                                    try:
                                        mouse.click(Button.left, 2)
                                    except Exception as click_err: logger.debug(f"mouse double click error: {click_err}")
                            else:
                                logger.info("Short pinch detected -> Single Click")
                                if mouse:
                                    try:
                                        mouse.click(Button.left, 1)
                                    except Exception as click_err: logger.debug(f"mouse single click error: {click_err}")

                            last_click_time = now

                    # Draw green pointer circle at index tip position
                    cv2.circle(frame, (ix_px, iy_px), 8, (0, 255, 0), cv2.FILLED)
                    cv2.putText(frame, f"INDEX CURSOR ({curr_x}, {curr_y})", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                    # RIGHT-CLICK: thumb + middle-finger pinch (only when not also
                    # doing a left-click/drag pinch with the index finger).
                    middle_x, middle_y = landmarks[12].x, landmarks[12].y
                    right_pinch_raw = np.hypot(middle_x - thumb_x, middle_y - thumb_y)
                    is_right_pinched = (right_pinch_raw / hand_scale) < 0.28

                    if is_right_pinched and not was_right_pinched and (now - last_right_click_time) > 0.5:
                        logger.info("Thumb-middle pinch detected -> Right Click")
                        if mouse:
                            try:
                                mouse.click(Button.right, 1)
                            except Exception as rclick_err:
                                logger.debug(f"mouse right click error: {rclick_err}")
                        last_right_click_time = now
                        cv2.putText(frame, "RIGHT CLICK", (20, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 140, 255), 2)
                    was_right_pinched = is_right_pinched

                # Action Gestures (Victory, Fist, Palm, Thumbs Up/Down, Point Up, Rock On)
                gesture = _analyze_gesture(landmarks)
                if gesture:
                    cv2.putText(frame, f"GESTURE: {gesture}", (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)

                # SCROLL: hold a two-finger "VICTORY" pose and move the hand up/down
                # to scroll continuously — direct pynput call, no LLM round-trip,
                # so it stays low-latency.
                if gesture == "VICTORY":
                    scroll_y = (landmarks[8].y + landmarks[12].y) / 2.0
                    if scroll_ref_y is None:
                        scroll_ref_y = scroll_y
                        did_scroll_this_hold = False
                    else:
                        dy = scroll_y - scroll_ref_y
                        if abs(dy) > SCROLL_MOVE_THRESHOLD:
                            # Screen y grows downward; scroll wheel "up" is positive.
                            direction = -1 if dy > 0 else 1
                            if mouse:
                                try:
                                    mouse.scroll(0, direction * SCROLL_TICKS_PER_UNIT)
                                except Exception as scroll_err:
                                    logger.debug(f"mouse scroll error: {scroll_err}")
                            scroll_ref_y = scroll_y
                            did_scroll_this_hold = True
                            cv2.putText(frame, "SCROLLING", (20, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)
                else:
                    scroll_ref_y = None

                # WINDOW SWITCH: hold an open PALM and swipe the hand horizontally
                # (fast, short motion) to switch to the next/previous window.
                if gesture == "PALM":
                    if swipe_ref_x is None:
                        swipe_ref_x = wrist_x
                        swipe_start_time = now
                    else:
                        dx_swipe = wrist_x - swipe_ref_x
                        elapsed = now - swipe_start_time
                        if elapsed <= SWIPE_MAX_DURATION and abs(dx_swipe) >= SWIPE_MIN_DISTANCE and (now - last_swipe_time) > SWIPE_COOLDOWN:
                            # Mirrored frame: hand moving screen-right = dx_swipe > 0
                            forward = dx_swipe > 0
                            try:
                                import pyautogui
                                if forward:
                                    pyautogui.hotkey("alt", "tab")
                                else:
                                    pyautogui.hotkey("alt", "shift", "tab")
                                logger.info(f"Palm swipe detected -> window switch ({'next' if forward else 'previous'})")
                                cv2.putText(frame, "WINDOW SWITCH", (20, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 0, 255), 2)
                            except Exception as _swipe_e:
                                logger.debug(f"Window-switch swipe failed: {_swipe_e}")
                            did_swipe_this_hold = True
                            last_swipe_time = now
                            swipe_ref_x = wrist_x
                            swipe_start_time = now
                        elif elapsed > SWIPE_MAX_DURATION:
                            # Rolling window: forget stale reference, start a fresh one
                            swipe_ref_x = wrist_x
                            swipe_start_time = now
                else:
                    swipe_ref_x = None

                if gesture:
                    # Only fire discrete one-shot action if this hold wasn't actually used
                    # for continuous scrolling/swiping.
                    suppressed = (gesture == "VICTORY" and did_scroll_this_hold) or \
                                 (gesture == "PALM" and did_swipe_this_hold)
                    action_cooldown = 5.0  # Require 5s minimum between discrete static gesture actions
                    if not suppressed and gesture != last_action_gesture and (now - last_action_time) > action_cooldown:
                        last_action_time = now
                        last_action_gesture = gesture
                        logger.info(f"Gesture detected: {gesture}")
                        _handle_gesture_action(gesture)
                else:
                    did_scroll_this_hold = False
                    did_swipe_this_hold = False
                    if (now - last_action_time) > 2.0:
                        last_action_gesture = ""




        # Encode frame to JPEG for HTTP video stream
        try:
            _, buffer = cv2.imencode('.jpg', frame)
            _latest_encoded_frame = buffer.tobytes()
        except Exception as enc_err:
            logger.debug(f"cv2 frame imencode JPEG error: {enc_err}")

        # Show live feedback desktop window
        try:
            cv2.imshow("VISION Visual Core — Press 'q' to exit", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
        except Exception as show_err:
            logger.debug(f"cv2.imshow display error: {show_err}")

    # Safety release when loop exits
    if mouse and is_dragging:
        try:
            mouse.release(Button.left)
        except Exception as rel_err:
            logger.debug(f"mouse release on loop exit error: {rel_err}")

    cap.release()
    cv2.destroyAllWindows()
    logger.info("Webcam monitoring stopped.")
    _latest_frame = None

def _analyze_gesture(landmarks) -> str | None:
    try:
        index_up   = landmarks[8].y  < landmarks[6].y
        middle_up  = landmarks[12].y < landmarks[10].y
        ring_up    = landmarks[16].y < landmarks[14].y
        pinky_up   = landmarks[20].y < landmarks[18].y
        thumb_up   = landmarks[4].y  < landmarks[3].y
        thumb_down = landmarks[4].y  > landmarks[2].y and landmarks[4].y > landmarks[8].y

        # FIST: all main fingers down
        if not index_up and not middle_up and not ring_up and not pinky_up and not thumb_up:
            return "FIST"

        # PALM: all 4 fingers up
        if index_up and middle_up and ring_up and pinky_up:
            return "PALM"

        # VICTORY: index & middle up, ring & pinky down
        if index_up and middle_up and not ring_up and not pinky_up:
            return "VICTORY"

        # THUMBS_UP: thumb pointing up, other 4 fingers folded
        if thumb_up and not index_up and not middle_up and not ring_up and not pinky_up:
            return "THUMBS_UP"

        # THUMBS_DOWN: thumb pointing down, other 4 fingers folded
        if thumb_down and not index_up and not middle_up and not ring_up and not pinky_up:
            return "THUMBS_DOWN"

        # POINT_UP: index up, all others down
        if index_up and not middle_up and not ring_up and not pinky_up:
            return "POINT_UP"

        # ROCK_ON: index & pinky up, middle & ring down
        if index_up and pinky_up and not middle_up and not ring_up:
            return "ROCK_ON"

    except Exception as analyze_err:
        logger.debug(f"Gesture analysis exception: {analyze_err}")
    return None

def _handle_gesture_action(gesture: str):
    mapping = {
        "FIST":        "pause playback",
        "PALM":        "take a screenshot",
        "VICTORY":     "get system status info",
        "THUMBS_UP":   "resume playback",
        "THUMBS_DOWN": "mute volume",
        "POINT_UP":    "increase volume by 10 percent",
        "ROCK_ON":     "scan system for viruses",
    }
    action = mapping.get(gesture)
    if action:
        logger.info(f"Gesture '{gesture}' → triggering action: {action}")
        try:
            from agent import send_hud_state
            send_hud_state({
                "state": "thinking",
                "category": "VISION",
                "tool_name": f"GESTURE_{gesture}",
                "description": f"Triggering gesture action: {action}",
            })
        except Exception as hud_err:
            logger.debug(f"send_hud_state for gesture action failed: {hud_err}")
        _send_action_command(action)



@function_tool
async def start_webcam_guard() -> str:
    """
    Activates your webcam to monitor hand gestures and live visual context.
    Also required before asking VISION to analyze what is in front of the camera.
    """
    global _camera_active, _camera_thread

    import importlib.util
    if importlib.util.find_spec("cv2") is None:
        return ("OpenCV is not installed. Run:\n"
                "  pip install opencv-python mediapipe --break-system-packages")

    if _camera_active:
        return "Webcam monitoring is already active, sir."

    _camera_ready_event.clear()
    _camera_active = True
    _camera_thread = threading.Thread(target=_camera_loop, daemon=True)
    _camera_thread.start()

    # Wait briefly for _camera_loop to actually confirm the camera opened (or
    # failed) before claiming success — previously this returned "I have
    # visual contact" immediately, regardless of whether the background
    # thread went on to fail silently a moment later.
    loop = asyncio.get_event_loop()
    opened_in_time = await loop.run_in_executor(None, lambda: _camera_ready_event.wait(timeout=6.0))

    if not opened_in_time:
        return (
            "Still trying to open the webcam — it's taking longer than expected. "
            "It may still connect in the background; ask me to check again in a moment, "
            "or ask for webcam diagnostics if this keeps happening."
        )

    if _camera_open_failed:
        return (
            "I couldn't open any webcam device, sir. Run `ls /dev/video*` to check if a camera "
            "device exists, and make sure you're in the 'video' group (sudo usermod -aG video $USER, "
            "then re-log in). Ask for webcam diagnostics for more detail on what was tried."
        )

    cursor_note = ""
    if not _uinput_available:
        cursor_note = (
            "\n\nHeads up: cursor movement may not actually work — "
            f"{_mouse_backend_status}. Static gestures (palm, fist, etc.) will still work fine "
            "regardless, since those don't need mouse control. Ask for webcam diagnostics for details."
        )

    return ("Webcam activated. I have visual contact, sir." + cursor_note + "\n"
            "Cursor & clicks:\n"
            "  ☝️ Index finger → move cursor\n"
            "  🤏 Thumb+Index pinch (tap) → left click / double-click\n"
            "  🤏 Thumb+Index pinch (hold+move) → drag and drop\n"
            "  🤏 Thumb+Middle pinch (tap) → right click\n"
            "  ✌️ Victory pose, move up/down → scroll\n"
            "  ✋ Open palm, quick swipe left/right → switch window\n"
            "Static shortcuts (hold pose still):\n"
            "  ✊ FIST → pause playback\n"
            "  ✋ PALM (held still) → take screenshot\n"
            "  ✌️ VICTORY (held still) → system status\n"
            "  👍 THUMBS UP → resume playback\n"
            "  👎 THUMBS DOWN → mute volume\n"
            "  👆 POINT UP → volume up\n"
            "  🤟 ROCK ON → virus scan")


@function_tool
async def stop_webcam_guard() -> str:
    """Deactivates the webcam monitoring session."""
    global _camera_active
    if not _camera_active:
        return "Webcam is not currently active."
    _camera_active = False
    return "Webcam tracking offline. Visual core suspended."


@function_tool
async def get_webcam_diagnostics() -> str:
    """
    Runs a full diagnostic check on the webcam/gesture-control pipeline and
    reports exactly what's working and what isn't — session type (X11 vs
    Wayland), video devices found, a live camera-open test across all
    backends, mouse-input backend availability (uinput vs pynput), and the
    video feed HTTP server status. Use this when video feed or gesture
    control isn't working and you need to know WHY, not just that it isn't.
    """
    lines = ["Webcam/gesture-control diagnostics:"]

    # Session type — matters because pynput's default backend doesn't work
    # under native Wayland (no X11 to talk to), while uinput works regardless.
    session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
    wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
    x_display = os.environ.get("DISPLAY", "")
    lines.append(f"• Session: XDG_SESSION_TYPE={session_type}, WAYLAND_DISPLAY={wayland_display or '(unset)'}, DISPLAY={x_display or '(unset)'}")

    # Video devices actually present at the OS level.
    try:
        video_devices = sorted(f for f in os.listdir("/dev") if f.startswith("video"))
    except OSError:
        video_devices = []
    lines.append(f"• Video devices in /dev: {', '.join(video_devices) if video_devices else '(none found)'}")

    # Is the current user in the 'video' group? (common permission gate for /dev/video*)
    try:
        import grp
        video_group_members = grp.getgrnam("video").gr_mem
        current_user = os.environ.get("USER", "")
        in_video_group = current_user in video_group_members
        lines.append(f"• User '{current_user}' in 'video' group: {in_video_group}")
    except Exception as grp_err:
        logger.debug(f"User video group check failed: {grp_err}")

    # Live camera-open test — reuses the same probing logic start_webcam_guard uses.
    try:
        import cv2
        was_active = _camera_active
        if not was_active:
            cap = _find_webcam_capture(cv2)
            if cap is not None:
                lines.append("• Camera open test: SUCCESS (a backend was able to open and read a frame)")
                cap.release()
            else:
                lines.append("• Camera open test: FAILED — see VISION's logs for the detailed per-attempt error list just logged")
        else:
            lines.append("• Camera open test: skipped (webcam guard is already running — stop it first to test cleanly)")
    except ImportError:
        lines.append("• Camera open test: opencv-python is not installed")

    # Input backends for gesture cursor control.
    uinput_ok, uinput_err = False, ""
    try:
        from evdev import UInput, ecodes as e
        test_device = UInput({e.EV_REL: [e.REL_X, e.REL_Y]}, name='vision-diagnostic-test')
        test_device.close()
        uinput_ok = True
    except Exception as ue:
        uinput_err = str(ue)
    lines.append(f"• uinput virtual mouse (works on Wayland): {'OK' if uinput_ok else f'FAILED — {uinput_err}'}")
    if not uinput_ok:
        lines.append("  → run: bash setup_uinput_permissions.sh (in the VISION project directory), then log out and back in")

    pynput_ok, pynput_err = False, ""
    try:
        from pynput.mouse import Controller
        Controller()
        pynput_ok = True
    except Exception as pe:
        pynput_err = str(pe)
    lines.append(f"• pynput mouse controller (X11/XWayland only): {'OK' if pynput_ok else f'unavailable — {pynput_err}'}")

    if not uinput_ok and not pynput_ok:
        lines.append("  ⚠ NEITHER mouse backend works — gesture cursor control cannot function until at least one is fixed.")
    elif session_type == "wayland" and not uinput_ok:
        lines.append("  ⚠ On Wayland, pynput alone usually can't move the cursor — fixing uinput access is the real fix here.")

    # Video feed HTTP server status.
    lines.append(f"• Video feed HTTP server bound: {_http_server is not None and _http_server is not True}")
    lines.append(f"• Gesture guard currently active: {_camera_active}")
    if _camera_active:
        lines.append(f"• Live cursor-control backend in use right now: {_mouse_backend_status or '(not yet determined)'}")
    if _camera_active:
        idle_for = time.time() - _last_frame_requested if _last_frame_requested else None
        if idle_for is not None:
            lines.append(f"• Seconds since video feed was last requested by a client: {idle_for:.0f}")

    return "\n".join(lines)


@function_tool
async def analyze_webcam_frame_vlm(user_question: str) -> str:
    """
    Looks through the active webcam and answers the user's question about the image
    (e.g., 'What book am I holding?', 'What am I doing right now?').

    Args:
        user_question: What you want VISION to look for or describe (e.g. 'Read the text on the object I am holding').
    """
    # If camera is not active, boot it temporarily, capture, and stop it
    try:
        import cv2
    except ImportError:
        return "Vision features require opencv-python to be installed."

    if _latest_frame is None:
        logger.info("Vision: Camera not running. Spinning up temporary frame capture...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "Failed to open webcam for visual check."
        # Let scanner warm up
        for _ in range(5):
            ret, frame = cap.read()
        cap.release()
        if not ret:
            return "Failed to capture visual frame from webcam."
    else:
        frame = _latest_frame.copy()

    # Encode frame to base64
    try:
        _, buffer = cv2.imencode('.jpg', frame)
        base64_image = base64.b64encode(buffer).decode('utf-8')
    except Exception as e:
        return f"Failed to process image capture: {e}"

    # VLM request to local LM Studio (running LlaVA or Moondream)
    local_llm_url = os.getenv("LOCAL_LLM_URL", "http://localhost:1234/v1")
    # Clean completions endpoint to get models url
    base_url = local_llm_url.replace("/chat/completions", "")
    if not base_url.endswith("/v1"):
        base_url += "/v1"

    headers = {"Content-Type": "application/json"}
    payload = {
        "model": "local-model", # Default model alias in LM Studio
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"You are VISION's visual cortex. Answer this user request directly, wittily, and in a human way: {user_question}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        "temperature": 0.4
    }

    try:
        logger.info(f"Sending image to Local VLM ({base_url}/chat/completions)...")
        resp = requests.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            result = resp.json()
            description = result["choices"][0]["message"]["content"]
            return description
        else:
            return f"The local vision server returned an error: Code {resp.status_code}. Make sure LM Studio is running a Vision-enabled model."
    except Exception as e:
        logger.error(f"Local VLM connection failed: {e}")
        return f"I couldn't contact my visual sub-agent at {base_url}. Make sure LM Studio (or your configured LOCAL_LLM_URL) is active."


@function_tool
async def analyze_what_master_is_doing() -> str:
    """
    Analyzes the current webcam frame and describes the master's activity.
    Use this when the user asks something like 'what am I doing', 'what do you see'.
    """
    return await analyze_webcam_frame_vlm(
        "Look at this image and describe in 1-2 sentences what the person in front of the camera is doing right now. Be playful and precise, like VISION would be."
    )

# Auto-start HTTP MJPEG stream server on port 5005
try:
    _start_mjpeg_stream_server()
except Exception as _err:
    logger.warning(f"Could not auto-start MJPEG server: {_err}")



