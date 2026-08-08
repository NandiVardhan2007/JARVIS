"""
VISION - Standalone Virtual Air Mouse Tester
Runs the high-precision Virtual Air Mouse directly without launching the full agent backend.
"""
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

if __name__ == "__main__":
    print("=" * 60)
    print("        VISION - Standalone Virtual Air Mouse Test")
    print("=" * 60)
    print("Starting webcam hand tracking & cursor control...")
    print("Point index finger to move, pinch thumb & index to click/drag,")
    print("middle finger pinch for right-click, two fingers to scroll.")
    print("Press 'q' or 'ESC' in the camera window to stop.")
    print("Press '+' or '-' to adjust sensitivity on the fly.")
    print("=" * 60)

    import Tools.hand_gesture_control as hgc

    hgc._gesture_active = True
    hgc._gesture_stop_event.clear()
    try:
        hgc._gesture_loop(show_preview=True)
    except KeyboardInterrupt:
        print("\nStopping Virtual Air Mouse...")
        hgc._gesture_stop_event.set()
        hgc._gesture_active = False
