#!/bin/bash

echo "Stopping JARVIS..."
# Terminate the launcher and all child processes spawned by it
pkill -f "jarvis_launcher.py"
# Stop the WebSocket bridge and the Flutter frontend
pkill -f "jarvis_bridge.py"
pkill -f "jarvis_face"
pkill -f "flutter run" 2>/dev/null
echo "Done."
