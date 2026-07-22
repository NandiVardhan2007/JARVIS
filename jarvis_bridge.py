#!/usr/bin/env python3
"""
jarvis_bridge.py — WebSocket bridge between the JARVIS backend and the Flutter
frontend (jarvis_face/).

What it does
------------
1. Serves a WebSocket on ws://127.0.0.1:8765 that the Flutter app connects to.
2. Receives live state + audio levels from the running PyQt HUD
   (dynamic_island.py) over UDP 127.0.0.1:5016 — see `_mirror_to_bridge()`
   which the HUD calls every frame — and rebroadcasts it, as JSON, to every
   connected Flutter client.
3. Derives the discrete face state (idle / listening / thinking / speaking)
   from audio amplitude, since the agent itself doesn't emit those.
4. Relays commands from Flutter back to the backend:
      - text_input / action  -> UDP 127.0.0.1:5004  (agent command server)
      - media playpause/stop  -> UDP 127.0.0.1:5006-5010 (media listener)

This runs ALONGSIDE the existing HUD and changes nothing about how JARVIS
works. If the HUD isn't running, the bridge simply has nothing to forward and
the Flutter app stays in its self-contained demo mode.

Requires:  pip install websockets
Run:       python jarvis_bridge.py
"""

import asyncio
import json
import logging
import socket

try:
    import websockets
except ImportError:  # pragma: no cover
    raise SystemExit(
        "The 'websockets' package is required.\n"
        "Install it with:  pip install websockets"
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [bridge]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("jarvis_bridge")

WS_HOST = "127.0.0.1"
WS_PORT = 8765
MIRROR_UDP_PORT = 5016          # HUD -> bridge (state + levels)
AGENT_CMD_PORT = 5004           # bridge -> agent (text_input / action)
MEDIA_PORTS = range(5006, 5011)  # bridge -> media listener (playpause/stop/…)

# Thresholds for deriving discrete state from amplitude.
SPEAK_THRESHOLD = 0.06
LISTEN_THRESHOLD = 0.08

_FACE_STATES = ("idle", "listening", "thinking", "speaking", "input", "alert")


class Hub:
    """Tracks connected Flutter clients and the last known snapshot."""

    def __init__(self):
        self.clients: set = set()
        self.last_payload: dict = {}
        self._cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # ── client management ───────────────────────────────────────────────
    def add(self, ws):
        self.clients.add(ws)
        log.info("Flutter client connected (%d total)", len(self.clients))

    def remove(self, ws):
        self.clients.discard(ws)
        log.info("Flutter client disconnected (%d total)", len(self.clients))

    async def broadcast(self, payload: dict):
        self.last_payload = payload
        if not self.clients:
            return
        msg = json.dumps(payload)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove(ws)

    # ── outbound to backend ─────────────────────────────────────────────
    def send_agent(self, obj: dict):
        try:
            self._cmd_sock.sendto(
                json.dumps(obj).encode("utf-8"), ("127.0.0.1", AGENT_CMD_PORT)
            )
        except Exception as e:
            log.warning("agent send failed: %s", e)

    def send_media(self, cmd: str):
        data = cmd.encode("utf-8")
        for port in MEDIA_PORTS:
            try:
                self._cmd_sock.sendto(data, ("127.0.0.1", port))
            except Exception:
                pass


def derive_state(raw: dict) -> str:
    """Pick the face state from the HUD state + live audio levels."""
    hud_state = str(raw.get("state", "idle")).lower()
    ai = float(raw.get("ai_level", 0.0) or 0.0)
    mic = float(raw.get("mic_level", 0.0) or 0.0)
    muted = bool(raw.get("mic_muted", False))

    state = hud_state if hud_state in _FACE_STATES else "idle"
    if ai > SPEAK_THRESHOLD:
        state = "speaking"
    elif not muted and mic > LISTEN_THRESHOLD:
        state = "listening"
    return state


def build_payload(raw: dict) -> dict:
    """Normalise a raw HUD mirror packet into the Flutter wire format."""
    payload = {
        "state": derive_state(raw),
        "ai_level": float(raw.get("ai_level", 0.0) or 0.0),
        "mic_level": float(raw.get("mic_level", 0.0) or 0.0),
        "mouth": float(raw.get("mouth", 0.0) or 0.0),
        "mic_muted": bool(raw.get("mic_muted", False)),
        "category": raw.get("category", "") or "",
        "tool_name": raw.get("tool_name", "") or "",
        "description": raw.get("description", "") or "",
        "transcript": raw.get("transcript", "") or "",
        "response": raw.get("last_response", raw.get("response", "")) or "",
        "connected": True,
    }
    # now_playing may arrive pre-built from the HUD; pass it through, else
    # allow an explicit null to clear it.
    if "now_playing" in raw:
        payload["now_playing"] = raw["now_playing"]
    return payload


class MirrorProtocol(asyncio.DatagramProtocol):
    """Receives UDP state packets from the HUD and forwards to the hub."""

    def __init__(self, hub: Hub, loop: asyncio.AbstractEventLoop):
        self.hub = hub
        self.loop = loop

    def datagram_received(self, data: bytes, addr):
        try:
            raw = json.loads(data.decode("utf-8"))
        except Exception:
            return
        payload = build_payload(raw)
        asyncio.run_coroutine_threadsafe(self.hub.broadcast(payload), self.loop)


async def ws_handler(ws, hub: Hub):
    hub.add(ws)
    try:
        # Send the last known snapshot immediately so a fresh client isn't blank.
        if hub.last_payload:
            try:
                await ws.send(json.dumps(hub.last_payload))
            except Exception:
                pass
        async for message in ws:
            try:
                obj = json.loads(message)
            except Exception:
                continue
            _route_command(obj, hub)
    except Exception:
        pass
    finally:
        hub.remove(ws)


def _route_command(obj: dict, hub: Hub):
    kind = obj.get("type")
    if kind == "text_input":
        text = str(obj.get("text", "")).strip()
        if text:
            hub.send_agent({"type": "text_input", "text": text})
            log.info("→ agent text_input: %s", text)
    elif kind == "action":
        action = str(obj.get("action", ""))
        if action:
            hub.send_agent({"type": "action", "action": action})
            log.info("→ agent action: %s", action)
    elif kind == "media":
        cmd = str(obj.get("cmd", ""))
        if cmd:
            hub.send_media(cmd)
            log.info("→ media: %s", cmd)
    elif kind == "mute":
        # The HUD owns mute locally; forward as a best-effort action.
        hub.send_agent({"type": "action", "action": "mute"})


async def main():
    loop = asyncio.get_running_loop()
    hub = Hub()

    # UDP listener for HUD mirror packets.
    await loop.create_datagram_endpoint(
        lambda: MirrorProtocol(hub, loop),
        local_addr=("127.0.0.1", MIRROR_UDP_PORT),
    )
    log.info("Listening for HUD mirror on udp://127.0.0.1:%d", MIRROR_UDP_PORT)

    async def handler(ws):
        await ws_handler(ws, hub)

    async with websockets.serve(handler, WS_HOST, WS_PORT):
        log.info("WebSocket ready on ws://%s:%d", WS_HOST, WS_PORT)
        log.info("Start the Flutter app (jarvis_face) to connect.")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("bridge stopped")
