# VISION — Autonomous Multimodal AI Voice Operating System

> **Comprehensive Technical Architecture & Pin-to-Pin System Documentation**

---

## 1. Executive Summary

**VISION** is an autonomous, full-duplex, multimodal AI voice operating system engineered for ultra-low latency interaction, deep desktop automation, proactive academic & task management, and multi-tier memory recall.

Built with a modular event-driven architecture, VISION integrates:
* **Real-Time Voice Streaming:** Silero Neural VAD + Groq Whisper STT + Cartesia Sonic / Kokoro-82M ONNX TTS with sub-millisecond barge-in interruption.
* **Cognitive Routing & Resilience:** Multi-provider load balancing (Groq, OpenAI, Gemini, Claude, Ollama) with self-healing tool calling, multi-key rate-limit cooldown tracking, and dynamic semantic tool filtering.
* **Quad-Tier Memory:** Cache-Augmented Generation (CAG), Memory-Augmented Generation (MAG), Retrieval-Augmented Generation (RAG), and Short-Term Working Memory.
* **Comprehensive Automation Suite:** 148+ native tools spanning Windows desktop control, Playwright browser manipulation, remote SSH server administration, WhatsApp messaging, academic scheduling, and sandboxed code execution.
* **Glassmorphic Web Dashboard:** Real-time WebSocket bidirectional telemetry, waveform visualizer, memory inspector, and live event monitoring.

---

## 2. System Architecture Diagram

```
                              +-------------------------+
                              |   User / Microphone     |
                              +------------+------------+
                                           |
                                           v
                             +---------------------------+
                             |     Perception Layer      |
                             | - Silero Neural VAD       |
                             | - Groq / Whisper STT      |
                             | - Screen Perception (OCR) |
                             +-------------+-------------+
                                           |
                                           v
                             +---------------------------+
                             |     Event Bus & Core      |
                             | - VisionEngine Dispatcher |
                             | - Session Manager         |
                             | - Working Memory          |
                             +------+---------------+----+
                                    |               |
               +--------------------+               +--------------------+
               |                                                         |
               v                                                         v
+-------------------------------+                         +-------------------------------+
|      Cognitive Router         |                         |         Memory Layer          |
| - Semantic Tool Filter (148+) |                         | - CAG Engine (L1/L2 Cache)    |
| - Dynamic Intent Classifier   |                         | - MAG Engine (Episodic Graph) |
+--------------+----------------+                         | - RAG Engine (Vector DB)      |
               |                                          +---------------+---------------+
               v                                                          |
+-------------------------------+                                         |
|     Load Balancer & LLMs     | <---------------------------------------+
| - Groq (LLaMA 3.3, GPT-OSS)   |
| - OpenAI / Anthropic / Gemini |
| - Key Rotation & Cooldowns    |
+--------------+----------------+
               |
               v (Tool Call Sequence / Multi-Turn Loop)
+-----------------------------------------------------------------------------------------+
|                                    Tool Registry                                        |
| [Desktop & Window] [Browser Automation] [Academic Suite] [SSH & Linux] [WhatsApp & Comms]|
+------------------------------------------+----------------------------------------------+
                                           |
                                           v (Final Synthesis)
                             +---------------------------+
                             |     Synthesis Layer       |
                             | - SmartTTS Orchestrator   |
                             | - Cartesia Sonic (Cloud)  |
                             | - Kokoro-82M ONNX (Local) |
                             | - Audio Player (Barge-in) |
                             +-------------+-------------+
                                           |
                                           v
                              +-------------------------+
                              |   Speaker / Web Client  |
                              +-------------------------+
```

---

## 3. Directory & File Structure

```
d:\VISION/
│
├── main.py                     # Primary entry point; orchestrates engine, daemons, and web server
├── start.bat                   # 1-click Windows launcher script with virtualenv auto-detection
├── requirements.txt            # Complete Python dependencies
├── .env.example                # Configuration template for API keys, voices, and credentials
├── PROJECT_DOCUMENTATION.md    # Complete system technical documentation (this file)
│
├── frontend/                   # Futuristic Glassmorphic Web Dashboard
│   ├── index.html              # Main single-page interface with real-time UI widgets
│   ├── css/
│   │   ├── style.css           # Core styling, animations, glassmorphism variables
│   │   └── components.css      # Component-level styling for widgets, modals, dials
│   └── js/
│       ├── websocket.js        # Bidirectional WebSocket handler & audio stream player
│       ├── app.js              # Application state, UI interaction, visualizer renderer
│       └── components.js       # Dynamic UI widgets (stats, logs, timetable cards)
│
├── scripts/                    # Maintenance & Diagnostics Utility Scripts
│   ├── test_voices.py          # Voice latency and quality benchmark tool
│   ├── sync_timetable.py       # Utility to populate and sync academic schedules
│   └── generate_sample_data.py # Database seeder for demo environments
│
├── tests/                      # Comprehensive Automated Test Suites
│   ├── test_voice_upgrades.py  # Tests for Cartesia + Kokoro fallback and Barge-in
│   ├── test_engine.py          # Tests for multi-turn conversational loop
│   └── test_tools.py           # Unit tests for core system automation tools
│
└── vision/                     # Main VISION Python Package
    ├── __init__.py             # Package descriptor
    ├── config.py               # Central configuration loader with .env validation
    ├── constants.py            # Event types, defaults, and system constants
    ├── logger.py               # Loguru-based structured logger with rotation
    │
    ├── core/                   # Core Orchestration Subsystem
    │   ├── engine.py           # VisionEngine: Multi-turn loop, pipeline synthesis, CAG dispatch
    │   ├── session.py          # Session and conversation history state tracking
    │   ├── event_bus.py        # Asynchronous publish/subscribe event system
    │   ├── reminder_daemon.py  # Proactive autonomous voice alarm & reminder scheduler
    │   └── auth.py             # Security and gateway token validation
    │
    ├── perception/             # Audio, Speech & Vision Input Subsystem
    │   ├── vad.py              # Silero Neural Voice Activity Detector
    │   ├── audio_stream.py     # Real-time microphone capture & buffering
    │   ├── wake_word.py        # Wake-word detection engine ("Hey Jarvis" / "Vision")
    │   ├── stt/
    │   │   ├── base.py         # Abstract base class for Speech-To-Text
    │   │   ├── groq_stt.py     # Groq Whisper-large-v3 cloud STT (<200ms transcription)
    │   │   └── local_stt.py    # Local Faster-Whisper offline fallback STT
    │   └── vision/
    │       └── screen_ocr.py   # Screen capture, bounding-box detection, and OCR
    │
    ├── cognitive/              # Cognitive Routing, LLMs & Multi-Agent Architecture
    │   ├── router.py           # Intent router: dynamically filters 148+ tools to 3-8 per query
    │   ├── load_balancer.py    # Multi-endpoint provider router with auto-failover
    │   ├── key_manager.py      # Multi-key rate-limit tracker with persistent cooldowns
    │   ├── providers/
    │   │   ├── base.py         # Abstract Base LLM Provider
    │   │   ├── groq_llm.py     # Groq LLaMA-3.3-70b provider with self-healing JSON recovery
    │   │   ├── openai_compatible.py # OpenAI / Ollama / DeepSeek provider
    │   │   └── gemini_llm.py   # Google Gemini multimodal provider
    │   └── agents/
    │       ├── base_agent.py   # Base autonomous sub-agent definition
    │       └── orchestrator.py # Multi-agent hierarchical task planner & delegator
    │
    ├── memory/                 # Multi-Tier Memory Engine
    │   ├── database.py         # SQLite connection manager with WAL mode
    │   ├── working_memory.py   # In-session ephemeral scratchpad context
    │   ├── cag_engine.py       # Cache-Augmented Generation (L1 Memory + L2 SQLite Disk)
    │   ├── mag_engine.py       # Memory-Augmented Generation (Episodic Graph & Fact Store)
    │   └── rag_engine.py       # Retrieval-Augmented Generation (Document Chunking & Vector Search)
    │
    ├── synthesis/              # Speech Synthesis & Audio Playback Subsystem
    │   ├── base.py             # Abstract base synthesizer
    │   ├── cartesia_tts.py     # Ultra-fast cloud streaming neural TTS (Sonic-2) with key pool rotation
    │   ├── smart_tts.py        # Cartesia TTS Router & backward-compatibility adapter
    │   └── player.py           # Non-blocking chunked audio player with barge-in polling
    │
    ├── gateways/               # External Access & Web Gateway
    │   └── web/
    │       └── server.py       # FastAPI application, REST endpoints & WebSocket server
    │
    └── tools/                  # 148+ Autonomous Tool Implementations
        ├── registry.py         # `@tool` decorator registry and JSON schema generator
        ├── academic_tools.py   # College timetable, Mid-1 exams, assignment tracking
        ├── window_tools.py     # Window focus, snap left/right, maximize, minimize
        ├── browser_control_tools.py # Playwright automated browser interaction
        ├── browser_navigation_tools.py # Webpage opening and tab control
        ├── remote_server_tools.py # Paramiko SSH command runner, Ubuntu server watchdog
        ├── whatsapp_tools.py   # WhatsApp automation, contacts alias, and draft confirmation
        ├── code_execution_tools.py # Sandboxed Python, Java, and C++ compiler & error fixer
        ├── hardware_tools.py   # CPU, RAM, GPU, Battery, Volume, and Brightness controls
        ├── file_tools.py       # Advanced file organizer, search, rename, move, delete
        ├── briefing_tools.py   # Morning intelligence briefing & quick daily status
        ├── network_tools.py    # Speedtest, ping, network diagnostics
        ├── media_tools.py      # YouTube search, playback, volume, and fullscreen
        ├── reminder_tools.py   # Spoken reminders, countdown timers, alarm management
        ├── input_tools.py      # Virtual keyboard, shortcuts, clipboard read/write
        ├── power_process_tools.py # Shutdown, reboot, sleep, kill processes
        ├── printer_tools.py    # A4 document bordered generator and physical printer dispatch
        ├── interview_tools.py  # Mock interview coaching with real-time feedback
        ├── archive_tools.py    # Zip compression and archive extraction
        ├── cache_tools.py      # CAG cache statistics and manual clearance
        ├── email_tools.py      # SMTP automated email sender
        ├── mobile_tools.py     # ADB Android phone connect, unlock, tap, and launch apps
        ├── web_tools.py        # DuckDuckGo web search and webpage content extractor
        └── system_tools.py     # System stats, datetime, and environment information
```

---

## 4. Subsystem Deep-Dive

### 4.1 Perception Layer (Hearing & Vision)
1. **Silero Neural VAD (`vad.py`):**
   * Uses an ONNX-quantized Silero VAD model running on a continuous 512-sample (32ms at 16kHz) ring buffer.
   * Employs adaptive energy thresholds to detect speech start and end accurately, eliminating background keyboard clicks and ambient noise.
2. **Groq STT (`groq_stt.py`):**
   * Streams audio chunks directly to Groq's high-speed Whisper Large v3 endpoint.
   * Transcribes standard conversational sentences in under **180ms**.
3. **Local Whisper Fallback (`local_stt.py`):**
   * If internet connectivity is interrupted, the system seamlessly routes audio to an offline `faster-whisper` (Base/Small) engine.
4. **Wake-Word Detector (`wake_word.py`):**
   * Continuously monitors audio stream for trigger phrases like *"Vision"* or *"Jarvis"* using lightweight template matching.

---

### 4.2 Cognitive Routing & LLM Load Balancing
1. **Dynamic Intent Router (`router.py`):**
   * Sending 148+ tool definitions to an LLM context on every query consumes excess tokens and introduces hallucinations.
   * The Router evaluates the semantic intent of the query and filters down the schema list from 148 tools to the **3 to 8 most relevant tools** before dispatching.
   * For purely conversational queries (e.g., *"Good morning"* or *"Tell me a joke"*), it provides 0 tools, ensuring ultra-fast responses.
2. **Key Manager & Multi-Key Load Balancer (`key_manager.py` & `load_balancer.py`):**
   * Manages pools of API keys for Groq, OpenAI, Gemini, and Claude.
   * Implements real-time latency scoring and least-busy request distribution.
   * If a provider returns a `429 Rate Limit` or `Quota Exceeded`, the KeyManager places that key on a persistent cooldown (e.g., 15 minutes) and instantly routes the request to the next available provider.
3. **Multi-Turn Tool Execution Loop (`engine.py`):**
   * Enables complex multi-step reasoning. For example: *"Snap Chrome to the left"* requires:
     1. `switch_to_window(app_name="chrome")`
     2. `snap_window(direction="left")`
   * The engine maintains context and allows up to 5 chained tool steps before synthesizing the final spoken response.
4. **Self-Healing Tool Recovery (`groq_llm.py`):**
   * Automatically parses malformed tool generations, JSON payloads, or XML function wrappers returned during edge cases, preventing 400 bad request aborts.

---

### 4.3 Quad-Tier Memory Architecture
1. **CAG (Cache-Augmented Generation — `cag_engine.py`):**
   * **L1 Cache:** In-memory LRU cache for instant hits (<2ms).
   * **L2 Cache:** Persistent SQLite disk storage with category-based TTL (Time-To-Live).
   * Repeated queries (e.g., *"What are my college classes today?"*) are answered with sub-10ms latency without making an LLM API call.
2. **MAG (Memory-Augmented Generation — `mag_engine.py`):**
   * **Episodic Memory:** Chronological event timeline recording every user interaction, tool execution, and system event.
   * **Declarative Memory:** Automatically extracts facts about the user (e.g., preferences, rules, names, habits) and stores them in SQLite.
   * **Procedural Rules:** Injects user-defined instructions (e.g., *"Always format code in Python 3.11"*) directly into the system prompt.
3. **RAG (Retrieval-Augmented Generation — `rag_engine.py`):**
   * Indexes local documents (PDF, DOCX, TXT, Markdown) into vectorized semantic chunks.
   * Allows VISION to search, summarize, and answer questions from local files and study materials.
4. **Working Memory (`working_memory.py`):**
   * Ephemeral context tracker that holds short-term variables, active application handles, and recent conversational entities across the session.

---

### 4.4 Synthesis Layer (Dual-Pipeline Smart TTS & Full Duplex)
1. **SmartTTS Coordinator (`smart_tts.py`):**
   * **Primary:** Cartesia Sonic-2 streaming neural cloud voice (~120ms latency, high emotional fidelity).
   * **Fallback:** Kokoro-82M ONNX offline neural engine (0ms cloud latency, runs 100% locally on CPU/DirectML).
   * If Cartesia keys encounter rate limits or quota depletion (402), SmartTTS falls back to Kokoro instantly with zero audio drop.
2. **Pipelined Sentence Synthesizer (`engine.py`):**
   * As the LLM streams text, sentences are split and synthesized ahead in a background pipeline.
   * Sentence 1 begins playing through the speakers while Sentence 2 and 3 are actively synthesizing.
3. **Barge-In Interruption (`player.py`):**
   * Audio output is streamed in 20ms PCM chunks.
   * If the user speaks while VISION is talking, Silero VAD triggers an interrupt, immediately cutting speaker output to listen to the new command.

---

### 4.5 Automation & Tool Registry (148+ Tools)

| Category | Tools Included | Description |
| :--- | :--- | :--- |
| **Window & Desktop** | `switch_to_window`, `snap_window`, `maximize_window`, `minimize_all_windows`, `restore_windows`, `show_desktop`, `close_application`, `list_running_applications` | Full control over Windows desktop layout, window snapping, and focus switching. |
| **System & Hardware** | `get_hardware_health`, `get_system_stats`, `set_volume`, `increase_volume`, `mute_volume`, `set_brightness`, `get_battery_status`, `lock_screen` | Real-time monitoring of CPU, RAM, GPU, battery life, brightness, and audio levels. |
| **Academic & College** | `get_college_timetable`, `get_mid_exam_schedule`, `get_next_upcoming_class`, `add_college_assignment`, `list_college_assignments`, `mark_assignment_done` | Tailored intelligence for college timetables (e.g., III IT A), mid exams, and homework. |
| **Browser Automation** | `browser_open`, `browser_navigate`, `browser_click`, `browser_type`, `browser_hover`, `browser_select_option`, `browser_scroll`, `browser_take_screenshot`, `browser_fill_form_and_login`, `browser_list_tabs`, `browser_switch_tab`, `browser_close`, `browser_autonomous_task` | Full Playwright-powered autonomous browser interaction, web scraping, and form filling. |
| **Remote Linux & SSH** | `ssh_execute_command`, `check_ubuntu_server_health`, `open_parking_logs_terminal`, `check_parking_logs`, `clear_parking_logs`, `restart_kpr_print_system`, `open_interactive_ssh_terminal` | Paramiko SSH suite to monitor remote Ubuntu servers, check log files, and reboot services. |
| **WhatsApp & Comms** | `prepare_whatsapp_message`, `confirm_and_send_whatsapp_draft`, `get_pending_whatsapp_draft`, `send_whatsapp_message`, `get_quick_whatsapp_templates`, `save_whatsapp_contact_alias` | Safe WhatsApp messaging pipeline with contact alias lookup and pre-send draft confirmation. |
| **Coding & Terminal** | `execute_terminal_command`, `run_python_code`, `run_code_with_input`, `diagnose_and_fix_code_error`, `compile_and_run_java_project`, `git_status_and_summary` | Multi-language code execution sandbox, error diagnosis, and Git status reporting. |
| **File Operations** | `list_files`, `find_files`, `open_file`, `read_file_content`, `create_or_write_file`, `rename_file`, `move_file`, `copy_file`, `delete_file`, `organize_downloads`, `organize_desktop` | Complete filesystem search, manipulation, and automated directory tidying. |
| **Memory & Facts** | `remember_fact`, `recall_memory`, `forget_memory`, `list_all_memories`, `query_knowledge_graph`, `add_entity_relation`, `learn_user_rule`, `sync_memories_file` | Explicit and implicit memory storage, knowledge graph query, and procedural rule learning. |
| **Media & YouTube** | `play_youtube_video`, `search_youtube_videos`, `control_youtube_playback`, `set_youtube_fullscreen`, `seek_youtube_video`, `play_media` | Search, launch, pause, seek, and fullscreen control for YouTube and local media. |
| **Mobile Device (ADB)** | `connect_phone`, `unlock_phone`, `launch_mobile_app`, `tap_phone_screen` | Android device management via ADB for opening apps and sending touch events. |
| **Document & Print** | `create_bordered_a4_document`, `print_document`, `create_and_print_bordered_document`, `summarize_document`, `search_and_read_documents` | Generates formatted A4 documents with headers/borders and sends them to physical printers. |
| **Alarms & Reminders** | `set_voice_reminder`, `set_timer`, `list_active_reminders`, `cancel_reminder` | Background spoken reminders and countdown timers that trigger voice alerts upon expiry. |
| **Power & Process** | `kill_process_by_name`, `lock_workstation`, `sleep_pc`, `shutdown_pc`, `restart_pc`, `cancel_shutdown`, `empty_recycle_bin` | Process termination and Windows power management. |
| **Network & Diagnostics**| `test_internet_speed`, `get_network_diagnostics`, `ping_host` | Network latency, packet loss, and download/upload speed diagnostics. |

---

### 4.6 Background Daemons & Event Bus
* **Asynchronous EventBus (`event_bus.py`):**
  * Decouples the engine from the UI and daemons.
All tools in VISION are decorated with `@tool` and auto-generate OpenAI/Groq function-calling JSON schemas.

* **Registry (`registry.py`):** Central directory holding schemas, argument validation, and async invocation.
* **Intent Routing (`router.py`):** Dynamically filters schemas to avoid context bloat in the LLM prompt.
* **Multi-Agent Engine (`multi_agent_engine.py`):** Complex goals generate a DAG of sub-tasks executed by specialized agents with scoped tools.

---

## 5. Getting Started & Setup

### Prerequisites
* Windows 10/11
* Python 3.10+ (Recommended: Python 3.10 virtual environment)
* FFmpeg installed and added to your system `PATH`.
* Microphone & Speakers configured as default OS audio devices.

### Installation Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/NandiVardhan2007/JARVIS.git
   cd JARVIS
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Install Playwright browser binaries:
   ```bash
   playwright install chromium
   ```
5. Open `.env` and configure your API keys (e.g. `GROQ_API_KEY`, `CARTESIA_API_KEY`, etc.).
6. Start VISION:
   ```bash
   .\start.bat
   ```

---

## 6. Key Configuration Parameters (`.env`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | `""` | Primary Groq API key for LLM and Whisper STT. |
| `GROQ_API_KEYS` | `""` | Comma-separated secondary Groq keys for automatic load balancing. |
| `CARTESIA_API_KEY` | `""` | Primary Cartesia API key for Sonic-2 streaming voice. |
| `CARTESIA_API_KEYS` | `""` | Comma-separated Cartesia API keys for automatic failover/rotation. |
| `CARTESIA_VOICE_ID` | `1259b7e3-cb8a-43df-9446-30971a46b8b0` | Cartesia voice identifier. |
| `CARTESIA_SPEED` | `normal` | Cartesia voice speed (`slow`, `normal`, `fast`). |
| `CARTESIA_MODEL_ID` | `sonic-2` | Cartesia voice model ID (`sonic-2`, `sonic-english`). |
| `DEFAULT_LLM_PROVIDER` | `groq` | Default provider (`groq`, `openai`, `gemini`, `claude`, `ollama`). |
| `WEB_PORT` | `8000` | Port for the FastAPI dashboard and WebSocket server. |
| `ENABLE_AUTO_BROWSER` | `true` | Automatically open Chrome/Edge to the dashboard on launch. |

---

## 7. Troubleshooting & Common Resolutions

* **Issue: `Tool choice is none, but model called a tool (400)`**
  * *Resolution:* Handled by the self-healing recovery in `groq_llm.py` and the multi-turn loop in `engine.py`.
* **Issue: `Cartesia 402 Insufficient credits`**
  * *Resolution:* Add additional backup Cartesia API keys into `CARTESIA_API_KEYS` in `.env` for automatic rotation.
* **Issue: Playwright browser tools not working**
  * *Resolution:* Run `playwright install chromium` inside your `.venv`.
* **Issue: Window snap shortcut not registering**
  * *Resolution:* `switch_to_window` includes a 150ms OS focus stabilization delay before `Win + Arrow` hotkeys are dispatched.

---

*VISION AI — Autonomous Multimodal AI Voice OS.*
