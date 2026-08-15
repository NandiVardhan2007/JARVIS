"""
FastAPI Server and WebSocket Gateway for real-time bidirectional communication.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from vision.gateways.web.routes import router as api_router
from vision.core.engine import vision_engine
from vision.core.event_bus import event_bus
from vision.constants import VisionEvents
from vision.logger import logger
import json

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
                synth = payload.get("synthesize_voice", False)
                response = await vision_engine.process_user_input(
                    user_text=user_msg,
                    session_id=session_id,
                    channel="web",
                    synthesize_voice=synth
                )
                await websocket.send_text(json.dumps({"type": "chat_response", "data": response}))
    except WebSocketDisconnect:
        logger.info("[WebSocket] Client disconnected.")
        await event_bus.publish(VisionEvents.WEB_CLIENT_DISCONNECTED)
    except Exception as e:
        logger.error(f"[WebSocket] Error: {e}")
