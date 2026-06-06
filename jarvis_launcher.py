import sys
import os

# Fix for onnxruntime DLL loading in PyInstaller
if hasattr(sys, '_MEIPASS'):
    base_dir = sys._MEIPASS
    os.environ['PATH'] = base_dir + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(base_dir)
        capi_dir = os.path.join(base_dir, 'onnxruntime', 'capi')
        if os.path.exists(capi_dir):
            os.add_dll_directory(capi_dir)

    # Add the folder where the .exe lives to sys.path so it can find our manually copied onnxruntime
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir not in sys.path:
        sys.path.insert(0, exe_dir)

import subprocess
import uuid
import time
from dotenv import load_dotenv

def get_base_path():
    """Get the absolute path to the resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return base_path

def main():
    # If this is a child process, dispatch it
    if len(sys.argv) > 1:
        if sys.argv[1] == "agent":
            # Override sys.argv for the agent to parse
            sys.argv = [sys.argv[0], "connect", "--room", sys.argv[2]]
            import agent
            agent.agents.cli.run_app(
                agent.agents.WorkerOptions(
                    entrypoint_fnc=agent.entrypoint,
                    worker_type=agent.agents.WorkerType.ROOM,
                    agent_name="jarvis",
                )
            )
            return
        elif sys.argv[1] == "ui":
            # Set the room name in env so dynamic island picks it up
            os.environ["LIVEKIT_ROOM_NAME"] = sys.argv[2]
            # Override sys.argv for dynamic island to parse
            sys.argv = [sys.argv[0]]
            import dynamic_island
            dynamic_island.main()
            return
        elif sys.argv[1] == "telegram":
            import telegram_bot
            import asyncio
            asyncio.run(telegram_bot.main())
            return
        elif sys.argv[1] == "whatsapp":
            import whatsapp_webhook
            whatsapp_webhook.run_server()
            return

    # MAIN LAUNCHER LOGIC
    # Load env vars from the bundled .env
    env_path = os.path.join(get_base_path(), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    
    # Generate a unique room name for this session to prevent clashes
    room_name = f"jarvis-room-{uuid.uuid4().hex[:8]}"
    print(f"Starting JARVIS in room: {room_name}")

    # Determine the correct base command depending on if we are frozen (PyInstaller) or a raw python script
    if getattr(sys, 'frozen', False):
        cmd = [sys.executable]
    else:
        cmd = [sys.executable, sys.argv[0]]

    # Launch Agent
    agent_proc = subprocess.Popen(cmd + ["agent", room_name])
    
    # Wait a second for agent to initialize
    time.sleep(2)
    
    # Launch UI
    ui_proc = subprocess.Popen(cmd + ["ui", room_name])
    
    # Launch Telegram Bot (if token is configured)
    telegram_proc = None
    if os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
        print("Starting Telegram Bot...")
        telegram_proc = subprocess.Popen(cmd + ["telegram"])
    else:
        print("No TELEGRAM_BOT_TOKEN found, skipping Telegram bot.")
        
    # Launch WhatsApp Webhook Server (if enabled)
    whatsapp_proc = None
    if os.getenv("WHATSAPP_WEBHOOK_ENABLED", "false").lower() == "true":
        print("Starting WAHA Webhook Server...")
        whatsapp_proc = subprocess.Popen(cmd + ["whatsapp"])
    else:
        print("WHATSAPP_WEBHOOK_ENABLED is not true, skipping WAHA webhook server.")
    
    try:
        # Wait for UI to close
        ui_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        print("Shutting down JARVIS...")
        agent_proc.terminate()
        agent_proc.wait()
        if telegram_proc:
            telegram_proc.terminate()
            telegram_proc.wait()
        if whatsapp_proc:
            whatsapp_proc.terminate()
            whatsapp_proc.wait()

if __name__ == "__main__":
    # Windows multiprocessing/subprocess support for PyInstaller
    import multiprocessing
    multiprocessing.freeze_support()
    main()
