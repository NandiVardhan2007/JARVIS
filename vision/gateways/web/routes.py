"""
FastAPI REST routes for VISION web dashboard and API access.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from vision.core.engine import vision_engine
from vision.perception.stt.groq_stt import GroqSTT
from vision.perception.vision.screen import screen_capture
from vision.tools.registry import tool_registry
from vision.config import config
from vision.cognitive.load_balancer import load_balancer

router = APIRouter()
stt = GroqSTT()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "web_session"
    synthesize_voice: Optional[bool] = False


class ToolExecRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}


@router.get("/health")
async def health():
    return {
        "status": "online",
        "load_balancer_endpoints": len(load_balancer.providers),
        "tools_registered": len(tool_registry.get_all_schemas())
    }


@router.post("/chat")
async def chat(req: ChatRequest):
    try:
        result = await vision_engine.process_user_input(
            user_text=req.message,
            session_id=req.session_id or "web_session",
            synthesize_voice=req.synthesize_voice or False
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def list_tools():
    return {"tools": tool_registry.get_all_schemas()}


@router.post("/tools/execute")
async def execute_tool(req: ToolExecRequest):
    result = await tool_registry.execute(req.tool_name, req.arguments)
    return {"tool": req.tool_name, "result": result}


@router.post("/audio/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    contents = await file.read()
    text = await stt.transcribe(contents)
    return {"text": text}


@router.get("/vision/screenshot")
async def get_screenshot():
    jpeg_bytes = screen_capture.capture_screen()
    if not jpeg_bytes:
        raise HTTPException(status_code=500, detail="Failed to capture screen.")
    from fastapi.responses import Response
    return Response(content=jpeg_bytes, media_type="image/jpeg")
