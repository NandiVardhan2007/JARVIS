import asyncio
import psutil
import logging
from livekit.agents.llm import ChatMessage

logger = logging.getLogger(__name__)

async def start_proactive_monitor(session, get_active_app_fn):
    """
    Background monitor that periodically checks system state and active window.
    Injects context into the session if significant events occur and the room is silent.
    """
    last_app = get_active_app_fn()
    battery_alert_triggered = False
    cpu_alert_triggered = False
    
    while True:
        await asyncio.sleep(5)
        
        try:
            # Check if agent is currently speaking or user is speaking (simple heuristic: if agent is speaking, don't interrupt)
            # Since LiveKit VAD updates session, we try to ensure silence.
            # We'll just wait if the agent's TTS is active.
            if hasattr(session, 'agent') and session.agent.tts.is_playing:
                continue

            current_app = get_active_app_fn()
            
            messages_to_inject = []
            
            # 1. Context Shift (Active Window)
            if current_app != last_app and current_app not in ["Unknown", "None", ""]:
                # To avoid spamming, only inject if it's a known 'productive' app or significant switch
                if any(x in current_app.lower() for x in ['code', 'studio', 'spotify', 'chrome', 'youtube', 'docs']):
                    messages_to_inject.append(f"The user just switched their active window to: {current_app}. If it seems relevant (e.g. coding, watching a video), you may proactively offer assistance or comment. Keep it very brief.")
                last_app = current_app
                
            # 2. Battery Monitor
            if hasattr(psutil, 'sensors_battery'):
                batt = psutil.sensors_battery()
                if batt and batt.percent < 20 and not batt.power_plugged and not battery_alert_triggered:
                    messages_to_inject.append(f"URGENT SYSTEM ALERT: The laptop battery is at {batt.percent}%. Warn the user proactively.")
                    battery_alert_triggered = True
                elif batt and batt.power_plugged:
                    battery_alert_triggered = False

            # 3. CPU Monitor
            cpu = psutil.cpu_percent(interval=None)
            if cpu > 90 and not cpu_alert_triggered:
                messages_to_inject.append(f"SYSTEM ALERT: CPU usage has spiked to {cpu}%. Warn the user proactively.")
                cpu_alert_triggered = True
            elif cpu < 70:
                cpu_alert_triggered = False
                
            if messages_to_inject:
                for msg in messages_to_inject:
                    session.chat_ctx._items.append(ChatMessage(role="system", content=msg))
                # Trigger LLM explicitly since it's proactive
                asyncio.create_task(session.generate_reply())
                
        except Exception as e:
            logger.error(f"Proactive monitor error: {e}")
