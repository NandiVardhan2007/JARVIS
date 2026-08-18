"""
FastAPI Server and WebSocket Gateway for real-time bidirectional communication.
"""

import json
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from vision.gateways.web.routes import router as api_router
from vision.core.engine import vision_engine
from vision.core.event_bus import event_bus
from vision.constants import VisionEvents
from vision.logger import logger

app = FastAPI(title="VISION Autonomous OS", version="1.0.0")

# CORS middleware for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.on_event("startup")
async def on_startup():
    await vision_engine.initialize()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await event_bus.publish(VisionEvents.WEB_CLIENT_CONNECTED)
    logger.info("[WebSocket] Client connected.")

    async def push_event(data):
        try:
            await websocket.send_text(json.dumps(data))
        except Exception:
            pass

    event_bus.subscribe(VisionEvents.LLM_STREAM_CHUNK, push_event)
    event_bus.subscribe(VisionEvents.TOOL_CALL_DETECTED, push_event)
    event_bus.subscribe(VisionEvents.TOOL_EXECUTION_COMPLETED, push_event)

    try:
        while True:
            raw_data = await websocket.receive_text()
            payload = json.loads(raw_data)
            action = payload.get("action")

            if action == "chat":
                user_msg = payload.get("message", "")
                session_id = payload.get("session_id", "ws_session")
                synth = payload.get("synthesize_voice", True)
                response = await vision_engine.process_user_input(
                    user_text=user_msg,
                    session_id=session_id,
                    channel="web",
                    synthesize_voice=synth
                )
                await websocket.send_text(json.dumps({"type": "chat_response", "data": response}))
            elif action == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "time": json.dumps(str(raw_data))}))
    except WebSocketDisconnect:
        logger.info("[WebSocket] Client disconnected.")
    except Exception as e:
        logger.error(f"[WebSocket] Error: {e}")
    finally:
        event_bus.unsubscribe(VisionEvents.LLM_STREAM_CHUNK, push_event)
        event_bus.unsubscribe(VisionEvents.TOOL_CALL_DETECTED, push_event)
        event_bus.unsubscribe(VisionEvents.TOOL_EXECUTION_COMPLETED, push_event)
        await event_bus.publish(VisionEvents.WEB_CLIENT_DISCONNECTED)


# ── Serve Frontend Static Files ──────────────────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend"

if FRONTEND_DIR.exists():
    @app.get("/")
    async def serve_frontend():
        """Serve the VISION dashboard SPA."""
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    # Mount entire frontend directory for CSS, JS, and any other static assets
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend_static")

    logger.info(f"[Server] Frontend dashboard mounted from '{FRONTEND_DIR}'")
else:
    logger.warning(f"[Server] Frontend directory not found at '{FRONTEND_DIR}' — skipping static mount.")

