"""AI image and video generation via Pollinations.ai."""

import logging
import os
import time
import urllib.parse
import requests
from datetime import datetime
from typing import Literal, Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

IMAGE_BASE = "https://image.pollinations.ai"
VIDEO_BASE = "https://video.pollinations.ai"
COMFYUI_URL = "http://127.0.0.1:8188"
COMFYUI_OUTPUT_DIR = r"D:\Outside_Folders\StabilityMatrix\Data\Packages\ComfyUI\output"




@function_tool
async def generate_ai_video(
    prompt: str,
    output_path: Optional[str] = None,
    duration: int = 3,
    fps: int = 24,
    model: str = "runway",
    timeout: int = 120,
) -> str:
    """
    Generates an AI video from a text prompt using Pollinations.ai.

    Args:
        prompt: English description of the video to generate.
        output_path: Where to save the video (defaults to Desktop/jarvis_videos/).
        duration: Length in seconds (default: 3).
        fps: Frames per second (default: 24).
        model: AI model to use (default: "runway").
        timeout: Maximum wait time in seconds (default: 120).
    """
    if not output_path:
        save_dir = os.path.join(os.path.expanduser("~/Desktop"), "jarvis_videos")
        os.makedirs(save_dir, exist_ok=True)
        output_path = os.path.join(save_dir, f"jarvis_{datetime.now().strftime('%H%M%S')}.mp4")

    url = (f"{VIDEO_BASE}/prompt/{urllib.parse.quote(prompt)}"
           f"?duration={duration}&model={model}")

    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        if resp.status_code != 200:
            return "Video generation failed. Try a shorter duration or simpler prompt."

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)

        size_str = f"{os.path.getsize(output_path) // 1024} KB"
        try:
            os.startfile(output_path)
        except Exception:
            pass

        return (
            f"Video generated successfully.\n"
            f"Duration: {duration}s | FPS: {fps} | Size: {size_str}\n"
            f"Saved to: {output_path}"
        )
    except Exception as e:
        return f"Video generation failed: {e}"


@function_tool
async def generate_local_image_comfyui(prompt: str, model_name: str = "novaRealityXL_ilV90.safetensors", negative_prompt: str = "", seed: int = -1, steps: int = 20) -> str:
    """
    Generates an AI image locally using your PC's ComfyUI installation.
    Always use this tool whenever the user asks to generate, create, or draw an image.
    
    CRITICAL: If the user provides a short prompt (e.g. "a boy playing with a puppy"), you MUST expand it into a highly detailed, descriptive, comma-separated SDXL prompt before sending it. Realistic AI models have biases (like defaulting to drawing women), so you must be highly explicit about gender, age, lighting, camera angle, and quality tags.
    Example: "A realistic photo of a young male child, little boy, playing with a golden retriever puppy in a sunny park, cinematic lighting, 8k resolution, highly detailed"
    
    CRITICAL NEGATIVE PROMPT: You MUST use the `negative_prompt` parameter to counteract the model's biases. For example, if the user asks for a boy or man, your negative prompt MUST include "girl, woman, female, lady".
    
    Args:
        prompt: English description of the image to generate.
        model_name: The SDXL checkpoint model to use. MUST be either 'novaRealityXL_ilV90.safetensors' or 'epicrealismXL_pureFix.safetensors'.
        negative_prompt: Things you DO NOT want in the image (e.g., "girl, female" if generating a boy).
        seed: Random seed. -1 for random.
        steps: Quality steps. Defaults to 20.
    """
    import json
    import random
    import aiofiles
    
    if seed is None or int(seed) <= 0:
        seed = random.randint(1, 9999999999)
        
    if steps is None or int(steps) <= 0:
        steps = 20
        
    # Check if user provided a custom workflow, otherwise use fallback SDXL workflow
    workflow_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "comfy_api.json")
    
    if os.path.exists(workflow_path):
        async with aiofiles.open(workflow_path, "r") as f:
            content = await f.read()
            workflow = json.loads(content)
            # Naive prompt replacement if we find a CLIP node
            for node_id, node in workflow.items():
                if node.get("class_type") == "CLIPTextEncode" and "positive" in str(node.get("_meta", {}).get("title", "")).lower() or node_id == "6":
                    if "text" in node["inputs"]:
                        node["inputs"]["text"] = prompt
                if node.get("class_type") == "KSampler":
                    node["inputs"]["seed"] = seed
    else:
        workflow = {
          "3": {"inputs": {"seed": seed, "steps": steps, "cfg": 7, "sampler_name": "euler", "scheduler": "normal", "denoise": 1, "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}, "class_type": "KSampler"},
          "4": {"inputs": {"ckpt_name": model_name}, "class_type": "CheckpointLoaderSimple"},
          "5": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}, "class_type": "EmptyLatentImage"},
          "6": {"inputs": {"text": prompt, "clip": ["4", 1]}, "class_type": "CLIPTextEncode"},
          "7": {"inputs": {"text": f"{negative_prompt}, text, watermark, ugly, deformed, poorly drawn", "clip": ["4", 1]}, "class_type": "CLIPTextEncode"},
          "8": {"inputs": {"samples": ["3", 0], "vae": ["4", 2]}, "class_type": "VAEDecode"},
          "9": {"inputs": {"filename_prefix": "jarvis_wa", "images": ["8", 0]}, "class_type": "SaveImage"}
        }

    try:
        req = urllib.request.Request(f"{COMFYUI_URL}/prompt", data=json.dumps({"prompt": workflow}).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            resp_data = json.loads(response.read().decode('utf-8'))
            prompt_id = resp_data.get("prompt_id")
            if not prompt_id:
                return "Failed to queue ComfyUI prompt."
                
        # Poll for completion (up to 300 seconds)
        for _ in range(150):
            time.sleep(2)
            hist_req = urllib.request.Request(f"{COMFYUI_URL}/history/{prompt_id}")
            with urllib.request.urlopen(hist_req) as hist_resp:
                hist_data = json.loads(hist_resp.read().decode('utf-8'))
                if prompt_id in hist_data:
                    # Completed!
                    outputs = hist_data[prompt_id].get("outputs", {})
                    for node_id, output in outputs.items():
                        if "images" in output:
                            filename = output["images"][0]["filename"]
                            file_path = os.path.join(COMFYUI_OUTPUT_DIR, filename)
                            return f"Image generated via Local ComfyUI successfully.\nSaved to: {file_path}"
                    return "ComfyUI generation completed, but no image output found."
                    
        return "ComfyUI generation timed out after 300 seconds."
        
    except Exception as e:
        return f"ComfyUI generation failed. Is ComfyUI running? Error: {e}"


@function_tool
async def get_generation_presets() -> str:
    """
    Returns the available AI generation presets and model options.
    """
    return (
        "Image Generation Presets:\n"
        "  Models: flux (best quality), turbo (fastest)\n"
        "  Quality: fast, balanced, high\n"
        "  Sizes: 512–2048 px\n\n"
        "Video Generation:\n"
        "  Duration: 1–10 seconds\n"
        "  FPS: 24 (default)\n"
        "  Model: runway\n\n"
        "Tip: Use English prompts for best results."
    )
