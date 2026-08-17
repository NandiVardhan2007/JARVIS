"""
Autonomous Communication & Notification Sub-Agent for VISION.
Drafts and dispatches emails, WhatsApp messages, notifications, and clipboard sharing.
"""

from typing import Dict, Any, Optional
from vision.cognitive.agents.base_agent import BaseAgent
from vision.config import config


COMMUNICATION_AGENT_SYSTEM_PROMPT = """You are the VISION Communication & Dispatch Agent.
Your mission is to compose and send emails, send WhatsApp notifications, and communicate findings or alerts to the user.

CAPABILITIES:
- Use `send_email` to send emails to recipients.
- Use `send_whatsapp_message` to dispatch WhatsApp texts to contacts or phone numbers.
- Use `write_to_clipboard` to copy critical links or results directly to the user's system clipboard.

RULES:
1. Keep communications polite, concise, professional, and directly addressed.
2. If given text from a prior research or file step, summarize the essence clearly before sending.
3. Confirm the recipient and send status in your response.
"""


class CommunicationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CommunicationAgent",
            agent_type="communication",
            dedicated_api_key=getattr(config, "EMAIL_AGENT_LLM_API", None),
            allowed_tools=[
                "send_email", "send_whatsapp_message",
                "save_whatsapp_contact_alias", "write_to_clipboard"
            ]
        )

    def get_system_prompt(self) -> str:
        return COMMUNICATION_AGENT_SYSTEM_PROMPT
