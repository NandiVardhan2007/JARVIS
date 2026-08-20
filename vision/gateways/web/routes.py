"""
FastAPI REST routes for VISION web dashboard and API access.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import time
import os
import psutil
from datetime import datetime

from vision.core.engine import vision_engine
from vision.perception.stt import smart_stt
from vision.perception.vision.screen import screen_capture
from vision.tools.registry import tool_registry
from vision.config import config
from vision.cognitive.load_balancer import load_balancer
from vision.memory.mag_engine import mag_engine
from vision.memory.cag_engine import cag_engine
from vision.memory.working_memory import working_memory
from vision.logger import logger

router = APIRouter()
stt = smart_stt

START_TIME = time.time()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "web_session"
    synthesize_voice: Optional[bool] = True


class ToolExecRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}


class RememberRequest(BaseModel):
    content: str
    category: Optional[str] = "user_preference"
    tags: Optional[str] = ""


class ForgetRequest(BaseModel):
    query: str


class SynthesizeRequest(BaseModel):
    text: str


@router.get("/health")
async def health():
    return {
        "status": "online",
        "load_balancer_endpoints": len(load_balancer.providers),
        "tools_registered": len(tool_registry.get_all_schemas()),
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "model": config.VISION_LLM_MODEL,
        "mode": "autonomous_os"
    }


@router.get("/system/stats")
async def get_system_stats():
    """Retrieve real-time hardware telemetry and load balancer status."""
    try:
        # CPU
        cpu_overall = psutil.cpu_percent(interval=None)
        cpu_cores = psutil.cpu_percent(interval=None, percpu=True)
        cpu_freq = psutil.cpu_freq()
        
        # RAM
        vmem = psutil.virtual_memory()
        
        # Battery
        battery = psutil.sensors_battery()
        battery_data = None
        if battery:
            battery_data = {
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
                "secs_left": battery.secsleft if battery.secsleft > 0 else None
            }
            
        # Storage
        disks = []
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "total_gb": round(usage.total / (1024**3), 1),
                    "used_gb": round(usage.used / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent": usage.percent
                })
            except Exception:
                pass

        # Top processes
        top_processes = []
        try:
            for p in sorted(
                psutil.process_iter(['name', 'cpu_percent', 'memory_info']),
                key=lambda x: x.info.get('memory_info').rss if x.info.get('memory_info') else 0,
                reverse=True
            )[:5]:
                try:
                    top_processes.append({
                        "name": p.info['name'],
                        "cpu": p.info.get('cpu_percent', 0.0),
                        "mem_mb": round(p.info['memory_info'].rss / (1024 * 1024), 1) if p.info.get('memory_info') else 0
                    })
                except Exception:
                    pass
        except Exception:
            pass

        # Net I/O
        net = psutil.net_io_counters()

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "uptime_seconds": round(time.time() - START_TIME),
            "cpu": {
                "percent": cpu_overall,
                "cores": cpu_cores,
                "core_count": psutil.cpu_count(logical=True),
                "frequency_ghz": round(cpu_freq.current / 1000, 2) if cpu_freq else 0
            },
            "ram": {
                "percent": vmem.percent,
                "total_gb": round(vmem.total / (1024**3), 1),
                "used_gb": round(vmem.used / (1024**3), 1),
                "free_gb": round(vmem.available / (1024**3), 1)
            },
            "battery": battery_data,
            "storage": disks,
            "network": {
                "bytes_sent_mb": round(net.bytes_sent / (1024 * 1024), 1),
                "bytes_recv_mb": round(net.bytes_recv / (1024 * 1024), 1)
            },
            "top_processes": top_processes,
            "load_balancer": {
                "strategy": config.VISION_LOAD_BALANCER_STRATEGY,
                "primary_model": config.VISION_LLM_MODEL,
                "nim_model": config.VISION_NIM_LLM_MODEL,
                "provider_count": len(load_balancer.providers)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to gather system stats: {e}")


@router.get("/memory/stats")
async def get_memory_stats():
    """Retrieve full MAG and CAG memory telemetry and records."""
    try:
        memories = mag_engine.list_all(limit=50)
        events = mag_engine.get_recent_events(limit=20)
        cag_stats = cag_engine.get_stats()
        working_stats = {
            "recent_files_count": len(working_memory.recent_files),
            "indexed_files_count": len(working_memory.file_index),
            "last_directory": working_memory.last_directory,
            "last_opened_app": working_memory.last_opened_app
        }
        return {
            "semantic_memories": memories,
            "episodic_events": events,
            "cag_cache": cag_stats,
            "working_memory": working_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load memory telemetry: {e}")



@router.post("/memory/remember")
async def remember_memory(req: RememberRequest):
    mem_id = mag_engine.remember(req.content, category=req.category, tags=req.tags)
    return {"status": "success", "id": mem_id, "content": req.content}


@router.post("/memory/forget")
async def forget_memory(req: ForgetRequest):
    deleted = mag_engine.forget(req.query)
    return {"status": "success", "deleted_count": deleted}


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


@router.post("/speech/synthesize")
async def synthesize_speech(req: SynthesizeRequest):
    if not vision_engine.tts:
        raise HTTPException(status_code=400, detail="Cartesia TTS engine not configured (API key missing).")
    try:
        audio_bytes = await vision_engine.tts.synthesize(req.text)
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech synthesis error: {e}")


@router.post("/audio/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        if not contents or len(contents) < 400:
            return {"text": ""}
        text = await stt.transcribe(contents, filename=file.filename)
        return {"text": text or ""}
    except Exception as e:
        logger.warning(f"[STT] Transcribe endpoint warning: {e}")
        return {"text": ""}


@router.post("/audio/stop")
async def stop_audio_playback():
    """Immediately stop TTS speech playback on server (Barge-In)."""
    try:
        from vision.synthesis.player import audio_player
        from vision.core.engine import vision_engine
        audio_player.stop()
        if hasattr(vision_engine, "stop_speech"):
            await vision_engine.stop_speech()
        return {"status": "stopped"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/vision/screenshot")
async def get_screenshot():
    jpeg_bytes = screen_capture.capture_screen()
    if not jpeg_bytes:
        raise HTTPException(status_code=500, detail="Failed to capture screen.")
    return Response(content=jpeg_bytes, media_type="image/jpeg")

