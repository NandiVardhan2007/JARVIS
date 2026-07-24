"""
Webcam Gesture Control & Live Visual Context Analyzer for JARVIS.
Uses OpenCV + MediaPipe (optional) — uses lazy imports so missing
packages never crash the main app at startup.
"""

import os
import time
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

# UDP client to send commands back to JARVIS session
import socket
_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def _send_action_command(action_text: str):
    """Sends a text command back to JARVIS via internal UDP port."""
    try:
        import json
        payload = json.dumps({'type': 'text_input', 'text': action_text}).encode("utf-8")
        _sock.sendto(payload, ("127.0.0.1", 5004))
    except Exception:
        pass

def _get_screen_size():
    try:
        from Xlib import display
        d = display.Display()
        s = d.screen()
        return s.width_in_pixels, s.height_in_pixels
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
        cv2.putText(img, "JARVIS VISUAL CORE - STANDBY", (100, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 212, 0), 2)
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

    class CamHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/video_feed') or self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=jpgboundary')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                while True:
                    try:
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
        _http_server = ThreadedHTTPServer(('0.0.0.0', 5005), CamHandler)
        t = threading.Thread(target=_http_server.serve_forever, daemon=True)
        t.start()
        logger.info("Live MJPEG video stream server running at http://127.0.0.1:5005/video_feed")
    except Exception as e:
        logger.warning(f"Could not start MJPEG HTTP server on port 5005: {e}")


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
    """Probes multiple video device indices to open an available camera."""
    for idx in [0, 1, 2, 3]:
        try:
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    logger.info(f"Webcam opened successfully on index {idx} (V4L2)")
                    return cap
                cap.release()
        except Exception:
            pass

        try:
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    logger.info(f"Webcam opened successfully on index {idx}")
                    return cap
                cap.release()
        except Exception:
            pass
    return None

def _camera_loop():
    global _camera_active, _latest_frame, _latest_encoded_frame

    try:
        import cv2
        import numpy as np
    except ImportError:
        logger.error("opencv-python not installed. Cannot start webcam.")
        return

    mouse = None
    try:
        from pynput.mouse import Controller, Button
        mouse = Controller()
    except Exception as e:
        logger.warning(f"pynput mouse controller unavailable ({e}). Cursor control disabled.")

    logger.info("Starting webcam monitoring loop with hand mouse control...")
    cap = _find_webcam_capture(cv2)
    if cap is None or not cap.isOpened():
        logger.error("Could not open any webcam device.")
        _camera_active = False
        return

    _start_mjpeg_stream_server()

    tracker_mode, tracker, mp_module = _get_hand_tracker()

    screen_w, screen_h = _get_screen_size()
    prev_x, prev_y = screen_w // 2, screen_h // 2
    alpha = 0.35  # Exponential moving average smoothing factor
    margin = 0.15  # Bounding margin to easily reach screen corners

    is_dragging = False
    pinch_start_time = 0.0
    last_click_time = 0.0

    last_action_gesture = ""
    last_action_time = 0.0
    action_cooldown = 2.0

    while _camera_active:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        # Save raw frame before annotations
        _latest_frame = frame.copy()

        # Mirror frame for natural camera preview
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

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
                # Landmark 8: Index Tip, Landmark 4: Thumb Tip, Landmark 12: Middle Tip
                index_x, index_y = landmarks[8].x, landmarks[8].y
                thumb_x, thumb_y = landmarks[4].x, landmarks[4].y

                # Normalize camera coordinates to screen dimensions with margin
                norm_x = np.clip((index_x - margin) / (1.0 - 2 * margin), 0.0, 1.0)
                norm_y = np.clip((index_y - margin) / (1.0 - 2 * margin), 0.0, 1.0)

                target_x = int(norm_x * screen_w)
                target_y = int(norm_y * screen_h)

                # Smooth motion using EMA
                curr_x = int(alpha * target_x + (1 - alpha) * prev_x)
                curr_y = int(alpha * target_y + (1 - alpha) * prev_y)
                prev_x, prev_y = curr_x, curr_y

                # Move cursor if mouse controller is ready
                if mouse:
                    try:
                        mouse.position = (curr_x, curr_y)
                    except Exception:
                        pass

                # Measure Pinch Distance (Index tip to Thumb tip)
                pinch_dist = np.hypot(index_x - thumb_x, index_y - thumb_y)
                now = time.time()

                # PINCH GRAB / DRAG WINDOW LOGIC
                if pinch_dist < 0.05:
                    if not is_dragging:
                        is_dragging = True
                        pinch_start_time = now
                        if mouse:
                            try:
                                from pynput.mouse import Button
                                mouse.press(Button.left)
                            except Exception:
                                pass
                    
                    # Draw visual indicator for active Grab/Drag
                    cv2.line(frame, (int(index_x * w), int(index_y * h)), (int(thumb_x * w), int(thumb_y * h)), (0, 0, 255), 4)
                    cv2.putText(frame, "GRABBING / DRAGGING WINDOW", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                else:
                    if is_dragging:
                        is_dragging = False
                        pinch_duration = now - pinch_start_time
                        if mouse:
                            try:
                                from pynput.mouse import Button
                                mouse.release(Button.left)
                            except Exception:
                                pass
                        
                        # Short tap pinch = Single / Double Click
                        if pinch_duration < 0.3:
                            if (now - last_click_time) < 0.4:
                                logger.info("Double pinch detected -> Double Click (Open App)")
                                if mouse:
                                    try:
                                        from pynput.mouse import Button
                                        mouse.click(Button.left, 2)
                                    except Exception:
                                        pass
                            else:
                                logger.info("Short pinch detected -> Single Click")
                            last_click_time = now

                    cv2.circle(frame, (int(index_x * w), int(index_y * h)), 10, (0, 255, 0), cv2.FILLED)
                    cv2.putText(frame, "CURSOR TRACKING ACTIVE", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                # Action Gestures (Victory, Fist, Palm)
                gesture = _analyze_gesture(landmarks)
                if gesture and gesture != last_action_gesture and (now - last_action_time) > action_cooldown:
                    last_action_time = now
                    last_action_gesture = gesture
                    logger.info(f"Gesture detected: {gesture}")
                    _handle_gesture_action(gesture)

        # Encode frame to JPEG for HTTP video stream
        try:
            _, buffer = cv2.imencode('.jpg', frame)
            _latest_encoded_frame = buffer.tobytes()
        except Exception:
            pass

        # Show live feedback desktop window
        try:
            cv2.imshow("JARVIS Visual Core — Press 'q' to exit", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
        except Exception:
            pass

    # Safety release when loop exits
    if mouse and is_dragging:
        try:
            from pynput.mouse import Button
            mouse.release(Button.left)
        except Exception:
            pass

    cap.release()
    cv2.destroyAllWindows()
    logger.info("Webcam monitoring stopped.")
    _latest_frame = None

def _analyze_gesture(landmarks) -> str | None:
    try:
        index_up  = landmarks[8].y  < landmarks[6].y
        middle_up = landmarks[12].y < landmarks[10].y
        ring_up   = landmarks[16].y < landmarks[14].y
        pinky_up  = landmarks[20].y < landmarks[18].y

        if not index_up and not middle_up and not ring_up and not pinky_up:
            return "FIST"
        if index_up and middle_up and ring_up and pinky_up:
            return "PALM"
        if index_up and middle_up and not ring_up and not pinky_up:
            return "VICTORY"
    except Exception:
        pass
    return None

def _handle_gesture_action(gesture: str):
    mapping = {
        "FIST":   "pause playback",
        "PALM":   "take a screenshot",
        "VICTORY": "open terminal",
    }
    action = mapping.get(gesture)
    if action:
        logger.info(f"Gesture '{gesture}' → triggering: {action}")
        _send_action_command(action)


@function_tool
async def start_webcam_guard() -> str:
    """
    Activates your webcam to monitor hand gestures and live visual context.
    Also required before asking JARVIS to analyze what is in front of the camera.
    """
    global _camera_active, _camera_thread

    try:
        import cv2
    except ImportError:
        return ("OpenCV is not installed. Run:\n"
                "  pip install opencv-python mediapipe --break-system-packages")

    if _camera_active:
        return "Webcam monitoring is already active, sir."

    _camera_active = True
    _camera_thread = threading.Thread(target=_camera_loop, daemon=True)
    _camera_thread.start()

    return ("Webcam activated. I have visual contact, sir.\n"
            "  FIST → pause playback\n"
            "  OPEN PALM → take screenshot\n"
            "  VICTORY sign → system info")

@function_tool
async def stop_webcam_guard() -> str:
    """Deactivates the webcam monitoring session."""
    global _camera_active
    if not _camera_active:
        return "Webcam is not currently active."
    _camera_active = False
    return "Webcam tracking offline. Visual core suspended."


@function_tool
async def analyze_webcam_frame_vlm(user_question: str) -> str:
    """
    Looks through the active webcam and answers the user's question about the image
    (e.g., 'What book am I holding?', 'What am I doing right now?').

    Args:
        user_question: What you want JARVIS to look for or describe (e.g. 'Read the text on the object I am holding').
    """
    global _latest_frame

    # If camera is not active, boot it temporarily, capture, and stop it
    temp_camera = False
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
                    {"type": "text", "text": f"You are JARVIS's visual cortex. Answer this user request directly, wittily, and in a human way: {user_question}"},
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
        return f"I couldn't contact my visual sub-agent at port 1234. Make sure LM Studio is active."


@function_tool
async def analyze_what_master_is_doing() -> str:
    """
    Analyzes the current webcam frame and describes the master's activity.
    Use this when the user asks something like 'what am I doing', 'what do you see'.
    """
    return await analyze_webcam_frame_vlm(
        "Look at this image and describe in 1-2 sentences what the person in front of the camera is doing right now. Be playful and precise, like JARVIS would be."
    )

# Auto-start HTTP MJPEG stream server on port 5005
try:
    _start_mjpeg_stream_server()
except Exception as _err:
    logger.warning(f"Could not auto-start MJPEG server: {_err}")

