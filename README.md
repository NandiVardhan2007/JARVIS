# JARVIS — Just A Rather Very Intelligent System

A LiveKit Agents-powered voice assistant for Windows desktop control, combined with a Telegram Bot and a WhatsApp Webhook (WAHA) integration.  

**Fully Localized AI Stack:** JARVIS is designed to run completely offline/locally, maximizing privacy and avoiding API limits.

### Dynamic Island UI
Features a premium, Apple-inspired Dynamic Island desktop HUD that provides contextual alerts, microphone levels, and tool execution status. 
- **Hover-Only Expansion**: Keeps your workspace clean by expanding only when hovered.
- **Smooth Transitions**: Fluid spring-physics based animations.
- **History Drawer**: Long-press to see recent tool usage.

---

## AI Stack

| Layer | Engine |
|---|---|
| **LLM** | Local Server (e.g. LM Studio / vLLM) on `http://localhost:1234/v1` |
| **STT** | NVIDIA NIM `parakeet-1.1b` (Streaming via LiveKit) or Local |
| **TTS** | **Piper TTS** (Fully Local) |
| **Image Generation** | **Local ComfyUI** (SDXL Models) |

---

## Core Integrations

### WhatsApp Webhook (WAHA)
JARVIS actively listens to WhatsApp messages via a WAHA (WhatsApp HTTP API) Webhook running on port `5006`.
- **Owner Mode**: If you (the owner) text JARVIS, you have full remote control over your PC. You can trigger PC commands, open apps, etc.
- **Guest Mode**: If a friend or stranger texts JARVIS, it will auto-reply politely on your behalf. PC control tools are strictly disabled for security, but guests are allowed to use the AI Image Generation tool!
- **Voice Notes**: JARVIS automatically intercepts and transcribes incoming WhatsApp voice notes using Groq STT APIs.

### Telegram Bot
JARVIS also spins up a Telegram bot on boot, allowing you to interface with it on the go.

### ComfyUI Image Generation
JARVIS generates images natively on your GPU using ComfyUI. 
- It analyzes your prompt and decides the best model to use (e.g. `novaRealityXL_ilV90` or `epicrealismXL_pureFix`).
- It automatically expands short prompts into highly detailed comma-separated tags to ensure the model produces exactly what you want.
- It dynamically injects counter-bias tags into the negative prompt to ensure gender and attributes match your exact request.
- Generated images are seamlessly pushed back to the user via the WAHA `/api/sendFile` webhook.

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

> **Windows extras required:**
> - [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) — for `click_on_text` tool
> - `pycaw` needs Windows audio stack for volume control
> - **ComfyUI** running locally (for image generation)
> - **WAHA Server** running locally (for WhatsApp integration)
> - **LM Studio** running locally on port 1234 (for the LLM)

### 2. Configure credentials
```bash
cp .env.example .env
# Fill in LIVEKIT_*, WAHA_URL, COMFYUI_URL, etc.
```

### 3. Run JARVIS
```bash
python jarvis_launcher.py
```
*(This sets up the isolated LiveKit room, Webhook servers, and the HUD).*

---

## Project Structure
```
jarvis/
├── jarvis_launcher.py    # Main entry point — starts servers and LiveKit
├── agent.py              # LiveKit Agent config, TTS, STT, and LLM routing
├── whatsapp_webhook.py   # WAHA integration, intent classification, security routing
├── telegram_bot.py       # Telegram bot polling and tools interface
├── requirements.txt      # All dependencies
├── .env.example          # Configuration template
└── Tools/
    ├── __init__.py       # Tool registry — exports get_all_tools()
    ├── ai_image.py       # Local ComfyUI integration
    ├── system_control.py # Power, volume, brightness, clipboard, antivirus
    ├── window_manager.py # Window manage/list/snap
    ├── open_app.py       # Launch apps via Start Menu
    ├── media.py          # YouTube playback
    ├── desktop_control.py # Scroll, desktop, keyboard, OCR click
    ├── iot_control.py    # ESP32 AC bulb control
    └── ...               # And many more PC control tools!
```

---

## Adding New Tools

1. Create `Tools/your_tool.py` with `@function_tool` decorated functions.
2. Import and add to `get_all_tools()` in `Tools/__init__.py`.
3. If the tool is destructive or exposes private system data, ensure it is restricted from the `active_tools` list for non-owners in `whatsapp_webhook.py`.
