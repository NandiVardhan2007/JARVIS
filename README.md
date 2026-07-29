# VISION — Just A Rather Very Intelligent System (Windows Native & Vision Core)

A LiveKit Agents-powered Vision and Voice assistant for **Windows Desktop Control**,
featuring real-time visual perception, OpenCV & MediaPipe hand gesture control, live animated
Flutter frontend, local voice biometric security, and a large Windows-native tool set spanning system
administration, application launching, document writing, browser automation, RAG, and multi-agent
task orchestration.

**Fully local-first AI stack:** LLM, STT, and TTS can all run entirely
offline (LM Studio + Piper), with cloud (Groq / NVIDIA NIM) as an automatic
fallback.

---

## 🚀 How to Run on Windows

To start VISION on Windows, simply run either the Batch script or the PowerShell script:

```cmd
:: Using Command Prompt (Batch)
start.bat

:: Or using PowerShell
.\start.ps1
```

To stop all VISION services:
```cmd
:: Using Command Prompt (Batch)
stop_vision.bat

:: Or using PowerShell
.\stop_vision.ps1
```

---


## Architecture

```
                     ┌──────────────────┐
                     │   agent.py       │  LiveKit Agent: STT → LLM → TTS,
                     │  (voice pipeline)│  tool-calling, personality, memory
                     └────────┬─────────┘
                              │ UDP state pings
                     ┌────────▼─────────┐
                     │ voice_client.py  │  Headless: mic capture + speech
                     │ (native audio)   │  playback (LiveKit room client)
                     └────────┬─────────┘
                              │ UDP mirror
                     ┌────────▼─────────┐
                     │ vision_bridge.py │  WebSocket bridge (localhost:8765)
                     └────────┬─────────┘
                              │ WebSocket
                     ┌────────▼─────────┐
                     │  vision_face/    │  Flutter frontend — animated
                     │  (Flutter app)   │  avatar, dashboard, controls
                     └──────────────────┘
```

`vision_launcher.py` starts `agent.py` and `voice_client.py` as separate
processes with a watchdog that restarts the agent if it crashes. The
Flutter app is a separate process you run yourself (`flutter run`) and
connects over WebSocket — it also runs a believable demo-mode animation
automatically if the backend isn't running yet, and switches to live data
the moment it connects.

---

## Key Features

### Voice authentication
On first launch with no master voice enrolled, VISION walks you through
registering one: it displays and speaks a short sample paragraph, records
you reading it, and stores the voiceprint locally (resemblyzer embeddings,
cosine similarity — nothing leaves your machine). Destructive actions
(shutdown, deleting files, killing processes) re-check your live voice
right before executing, not just once at session start. Re-enrollment is
available through conversation ("VISION, re-register my voice").

### Animated avatar
`vision_face/lib/face/` — a hand-built vector avatar (not a canned GIF/video):
real audio-amplitude-driven lip sync, 11 emotions inferred from live
conversation state and transcript content, natural blinking/gaze/breathing,
subtle head movement, and state-reactive effects (thinking particles,
speaking waveform, listening mic-ring). Dark and light themes, toggleable
from the top bar.

### Gesture control
Webcam-based hand tracking (MediaPipe): cursor movement, left/right click,
drag-and-drop, two-finger scroll, and an open-palm swipe to switch windows.
Auto-releases the camera after a period of no hand detected, to avoid
running continuous CPU/GPU-intensive tracking for no reason.

### Multi-agent task orchestration
Tools are organized into named, specialized agents (Research, Browser,
Terminal, Coding, File Management, Automation, Memory, Vision, Voice,
Communication, System, Calendar & Finance — see `list_available_agents`).
`execute_agent_tasks` dispatches multi-step plans with genuine parallel
execution for independent subtasks. Named, reusable **workflows** can be
saved once and re-run by name, or scheduled to run automatically.

### RAG / knowledge base
Local ChromaDB vector store for personal documents, PDFs, notes, and whole
folders (incremental — unchanged files are skipped on re-index). A
separate codebase index for semantic code search. Conversation history is
also incrementally indexed in the background, so you can ask "what did we
discuss about X" and get a real answer.

### Ubuntu system integration
Package search/install/remove, system updates, systemd service
monitoring/control, journal log reading, Docker container control, file
permissions, and startup-app management. Anything requiring root goes
through `pkexec` — you authenticate via the OS's own dialog; VISION never
handles a password.

### Automatic system optimization
Background monitor for RAM/CPU/storage/thermal that clears known-safe,
fully-regenerable caches automatically when usage gets high. Heavy
processes are only ever *suggested*, never auto-closed — killing an app
risks losing unsaved work, so that step always waits for you to say yes.

### File management
Natural-language file search across common folders ("find my resume",
"show screenshots from last week"), folder auto-organization, duplicate
detection, and bulk renaming — all reversible, all with a confirm step
before anything destructive happens.

---

## AI Stack

| Layer | Primary | Fallback |
|---|---|---|
| **LLM** | Local server (LM Studio, e.g. Gemma) via `LOCAL_LLM_URL` | Groq → NVIDIA NIM |
| **STT** | Groq Whisper | NVIDIA NIM |
| **TTS** | Piper (fully local) | Groq / Cartesia |
| **Voice ID** | resemblyzer (local, 128-dim embeddings) | — |
| **Vision** | Local vision model via LM Studio | Groq vision → Gemini |

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt --break-system-packages
playwright install chromium   # for browser automation tools
```

Some tools need system packages beyond pip:
- **Tesseract OCR** — `sudo apt install tesseract-ocr` (for `click_on_text`)
- **xdotool, wmctrl** — `sudo apt install xdotool wmctrl` (window management, gesture window-switching)
- **PolicyKit** — ships by default on Ubuntu Desktop; needed for package/service management (`sudo apt install policykit-1` if missing)
- **`/dev/uinput` access (required for gesture cursor movement on Wayland)** — a fresh Ubuntu install typically restricts `/dev/uinput` to root, which silently breaks gesture *cursor movement* specifically (gesture *detection* — static poses like palm/fist — still works fine, since that doesn't touch the mouse at all). Run:
  ```bash
  bash setup_uinput_permissions.sh
  ```
  then log out and back in. Ask VISION to "run webcam diagnostics" afterward to confirm it's working.
- **LM Studio** (or any OpenAI-compatible local server) — optional, for local LLM/vision

### 2. Configure credentials
```bash
cp .env.example .env
# Fill in LIVEKIT_*, GROQ_API_KEY, and any optional integrations you want.
```

### 3. First run — voice enrollment
```bash
python vision_launcher.py
```
On first launch (no master voice enrolled yet), VISION will ask you to
read a short sentence aloud and register your voice. After that, it
verifies your voice each session before unlocking.

### 4. Run the Flutter frontend (optional but recommended)
```bash
cd vision_face
flutter pub get
flutter run -d linux   # or your target device
```

---

## Project Structure
```
vision/
├── vision_launcher.py     # Entry point — spawns agent.py + voice_client.py, watchdog
├── agent.py               # LiveKit Agent: STT/LLM/TTS pipeline, personality, voice-auth gate
├── voice_client.py        # Headless mic capture + speech playback + state mirror
├── vision_bridge.py       # WebSocket bridge to the Flutter frontend
├── config.py              # Environment validation, local-LLM health check
├── requirements.txt
├── .env.example
├── VISION_VNEXT_ROADMAP.md  # Design notes / gap analysis from the vNext pass
├── vision_face/           # Flutter frontend (animated avatar + dashboard)
│   └── lib/face/          # The avatar rig: painter, params, animation driver
└── Tools/
    ├── __init__.py        # Tool registry — get_all_tools(), AGENT_ROSTER, categories
    ├── system_control.py  # Windows power, volume, brightness, clipboard, antivirus
    ├── windows_system.py  # Windows Winget packages, updates, services, logs, Docker, registry startup apps
    ├── hand_gesture_control.py # Real-time OpenCV & MediaPipe hand gesture tracking & mouse control
    ├── system_optimizer.py # Automatic RAM/CPU/storage/thermal monitoring
    ├── resource_optimizer.py # VISION's own resource footprint + on-demand release
    ├── window_manager.py   # Windows Window manage/list/snap (win32gui, pygetwindow)
    ├── desktop_control.py  # Windows desktop toggle (win+d), key press, typing, OCR click
    ├── notepad.py          # Formatted document writer for Windows Notepad
    ├── open_app.py         # Windows App Launcher (Notepad, Chrome, Edge, VS Code, Calc, etc.)
    ├── voice_verification.py # Voice enrollment, live re-auth, re-enrollment
    ├── file_manager.py     # Smart search, organize, duplicates, bulk rename
    ├── knowledge_rag.py    # Personal document / folder RAG (ChromaDB)
    ├── codebase_rag.py     # Codebase semantic search (incremental)
    ├── conversation_memory.py # Incremental conversation-history indexing
    ├── multi_task.py       # execute_agent_tasks — parallel/sequential orchestrator
    ├── workflow_automation.py # Named, reusable, schedulable task workflows
    ├── report_generator.py # Generates Word/text reports
    ├── web_automation.py   # Interactive browser: tabs, forms, downloads, page-watching
    ├── scraper_agent.py    # Static scraping/summarization
    ├── terminal.py         # Hardened sandboxed shell (no shell=True, tight allowlist)
    └── ...                 # Email, calendar, finance, mobile/ADB, SIP calling, and more
```

---

## Security model (read this before exposing anything to the network)

- **No `shell=True` and no `os.system()` anywhere in this codebase** —
  every subprocess call is an explicit argv list.
- **Terminal tool is a tight allowlist**, deliberately excluding
  general-purpose interpreters (python/pip/node/npm) since letting an
  "allowlisted" command run arbitrary code defeats the point of a sandbox.
- **Root-requiring actions use `pkexec`**, never a password typed/spoken to
  VISION. VISION should never be asked to accept a password by voice.
- **Destructive actions require `confirm=True`**, and the highest-risk ones
  (shutdown, killing processes, deleting files) additionally re-check your
  live voice right before executing.
- **Nothing is ever permanently deleted** by VISION's own tools — file
  deletion goes through the recycle bin (`send2trash`).

---

## Adding New Tools

1. Create `Tools/your_tool.py` with `@function_tool`-decorated functions.
2. Import it in `Tools/__init__.py` and add it to `CORE_TOOLS` (always
   available) or a category in `TOOL_CATEGORIES` (loaded only when the
   conversation's intent matches, to keep the per-call tool schema small).
3. If it performs a destructive or privileged action, follow the existing
   pattern: a `confirm: bool = False` parameter, and consider
   `@requires_live_master_voice()` from `Tools.voice_verification` for
   anything genuinely high-risk.
