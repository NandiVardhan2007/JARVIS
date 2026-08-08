#!/usr/bin/env python3
"""
voice_client.py — Headless native audio client for VISION.

This replaces the old `dynamic_island.py` PyQt "Dynamic Island" HUD, which
mixed three unrelated responsibilities into one 2,500-line file:

    1. A LiveKit room client that captured the microphone and played back
       the agent's synthesized speech (pyaudio in, pyaudio out).
    2. A UDP state receiver (port 5005) that turned agent status messages
       into HUD state (idle / listening / thinking / speaking, transcript,
       active tool, etc.).
    3. A hand-painted Qt desktop overlay ("Dynamic Island") that rendered
       that state as a pill-shaped HUD, toasts, and a history drawer.

The React frontend (`vision_react/`) is now the one and only visual UI —
it already renders state, transcripts, tool activity, and now-playing media
by connecting to `vision_bridge.py`. Responsibility (3) above (the Qt
overlay itself) has therefore been removed entirely, together with its
PyQt5 dependency.

Responsibilities (1) and (2) are still required for VISION to actually
hear you and speak back, so they live on here in a small headless module
with no GUI toolkit dependency at all. It:

  - Connects to the LiveKit room as a lightweight participant, captures the
    microphone via `sounddevice`, and publishes it as an audio track.
  - Subscribes to the agent's outgoing audio track and plays it through the
    default output device.
  - Listens on udp://127.0.0.1:5005 for state pings from agent.py and
    forwards a normalized snapshot to vision_bridge.py on
    udp://127.0.0.1:5016, exactly like the old HUD's `_mirror_to_bridge()`.

Run directly, or via `python vision_launcher.py ui <room_name>`.
"""

import asyncio
import json
import logging
import math
import os
import socket
import struct
import threading
import time

from dotenv import load_dotenv

class LiveKitLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "ignoring byte stream" in msg or "lk.agent.session" in msg or "no callback attached" in msg:
            return False
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [voice_client]  %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger().addFilter(LiveKitLogFilter())

for _lg in ("livekit", "livekit.rtc", "livekit.agents", "livekit.api"):
    logging.getLogger(_lg).setLevel(logging.WARNING)

log = logging.getLogger("voice_client")

STATE_UDP_PORT = 5005    # agent.py -> us (state pings)
BRIDGE_UDP_PORT = 5016   # us -> vision_bridge.py (React mirror)
MEDIA_PORTS = range(5006, 5011)

# Suppress the mic for a short hangover after VISION stops speaking so
# trailing reverb/echo picked up by the mic can't re-trigger a false
# interruption (same half-duplex guard the old HUD used).
_MIC_GATE_HANGOVER_SEC = 0.35
_AI_LEVEL_ACTIVE_THRESHOLD = 0.06


class VoiceClientState:
    """Plain-data holder for the state this process mirrors to the bridge."""

    def __init__(self):
        self.state = "idle"
        self.tool_name = ""
        self.tool_cat = ""
        self.tool_desc = ""
        self.transcript = ""
        self.last_response = ""
        self.mic_muted = False
        self.mic_level = 0.0
        self.target_mic_level = 0.0
        self.ai_level = 0.0
        self.target_ai_level = 0.0
        self._mic_gate_until = 0.0


def _rms_level(pcm16_bytes: bytes, divisor: float) -> float:
    """Cheap RMS-based amplitude estimate for a 16-bit PCM chunk, 0..1."""
    count = len(pcm16_bytes) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", pcm16_bytes)
    rms = math.sqrt(sum(s * s for s in samples) / count)
    return min(1.0, rms / divisor)


# ══════════════════════════════════════════════════════════
#  State-ping receiver (agent.py -> this process)
# ══════════════════════════════════════════════════════════
class StateUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, state: VoiceClientState):
        self.state = state

    def datagram_received(self, data: bytes, addr):
        try:
            d = json.loads(data.decode("utf-8"))
        except Exception:
            return
        s = d.get("state")
        if s and s != "heartbeat":
            self.state.state = s
        self.state.tool_name = d.get("tool_name", self.state.tool_name)
        self.state.tool_cat = d.get("category", self.state.tool_cat)
        self.state.tool_desc = d.get("description", self.state.tool_desc)
        if "transcript" in d:
            if d.get("context") == "response":
                self.state.last_response = d["transcript"]
            else:
                self.state.transcript = d["transcript"]


# ══════════════════════════════════════════════════════════
#  Bridge mirror (this process -> vision_bridge.py -> React)
# ══════════════════════════════════════════════════════════
async def _mirror_loop(state: VoiceClientState):
    """Forward live state + audio levels to vision_bridge.py, ~15 fps."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        while True:
            payload = {
                "state": state.state,
                "ai_level": round(float(state.ai_level), 3),
                "mic_level": round(float(state.mic_level), 3),
                "mic_muted": bool(state.mic_muted),
                "category": state.tool_cat or "",
                "tool_name": state.tool_name or "",
                "description": state.tool_desc or "",
                "transcript": state.transcript or "",
                "last_response": state.last_response or "",
            }
            try:
                sock.sendto(json.dumps(payload).encode("utf-8"), ("127.0.0.1", BRIDGE_UDP_PORT))
            except OSError:
                pass
            await asyncio.sleep(1 / 15)
    finally:
        sock.close()


# ══════════════════════════════════════════════════════════
#  LiveKit audio bridge (mic in / agent speech out)
# ══════════════════════════════════════════════════════════
async def _livekit_audio_task(state: VoiceClientState):
    pass


async def _state_receiver_task(state: VoiceClientState):
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(
        lambda: StateUDPProtocol(state),
        local_addr=("127.0.0.1", STATE_UDP_PORT),
    )
    log.info("Listening for agent state on udp://127.0.0.1:%d", STATE_UDP_PORT)
    await asyncio.Future()  # run forever


async def main_async():
    state = VoiceClientState()
    await asyncio.gather(
        _state_receiver_task(state),
        _mirror_loop(state),
    )


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        log.info("voice_client stopped")


if __name__ == "__main__":
    main()
