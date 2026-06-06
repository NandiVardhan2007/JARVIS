"""Messaging tool — Telegram Bot API + Discord Webhook / Bot API."""

import logging
import os
from typing import Literal, Optional

import requests
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API       = "https://api.telegram.org/bot{token}/{method}"

# ── Discord ───────────────────────────────────────────────────────────────────
DISCORD_BOT_TOKEN   = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")   # fallback (single channel)
DISCORD_API         = "https://discord.com/api/v10"


# ── Telegram helpers ──────────────────────────────────────────────────────────

def _tg(method: str, **kwargs) -> dict:
    url  = TELEGRAM_API.format(token=TELEGRAM_BOT_TOKEN, method=method)
    resp = requests.post(url, json=kwargs, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _resolve_telegram_chat_id(contact: str) -> str:
    """
    Accepts a numeric chat_id string, @username, or a display name matched
    against recent /getUpdates messages.
    Returns a chat_id string or raises ValueError.
    """
    # Already numeric
    if contact.lstrip("-").isdigit():
        return contact

    # @username → look it up in recent updates (offset=-100 keeps only the latest 100 and drops older backlog)
    updates = _tg("getUpdates", offset=-100, limit=100, allowed_updates=["message"])
    for update in reversed(updates.get("result", [])):
        msg  = update.get("message", {})
        chat = msg.get("chat", {})
        user = msg.get("from", {})

        # Match @username
        if contact.startswith("@"):
            if chat.get("username", "").lower() == contact.lstrip("@").lower():
                return str(chat["id"])
            if user.get("username", "").lower() == contact.lstrip("@").lower():
                return str(chat["id"])

        # Match display name (first + last, case-insensitive)
        full_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip().lower()
        chat_name = chat.get("title", "").lower()
        if contact.lower() in (full_name, chat_name):
            return str(chat["id"])

    raise ValueError(
        f"Could not resolve Telegram contact '{contact}'. "
        "Use the numeric chat_id, @username, or make sure the contact has sent "
        "a message to your bot recently."
    )


# ── Discord helpers ───────────────────────────────────────────────────────────

def _discord_headers() -> dict:
    return {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}


def _resolve_discord_channel(channel: str) -> str:
    """
    Accepts a numeric channel_id or a #channel-name.
    For named channels, searches the guilds the bot is in.
    Returns a channel_id string or raises ValueError.
    """
    if channel.lstrip("#").isdigit():
        return channel.lstrip("#")

    name = channel.lstrip("#").lower()
    guilds = requests.get(
        f"{DISCORD_API}/users/@me/guilds", headers=_discord_headers(), timeout=10
    ).json()

    for guild in guilds:
        channels = requests.get(
            f"{DISCORD_API}/guilds/{guild['id']}/channels",
            headers=_discord_headers(), timeout=10,
        ).json()
        for ch in channels:
            if ch.get("type") == 0 and ch.get("name", "").lower() == name:
                return str(ch["id"])

    raise ValueError(
        f"Discord channel '{channel}' not found. "
        "Use the numeric channel ID or #exact-channel-name."
    )


# ── Public tools ──────────────────────────────────────────────────────────────

@function_tool
async def send_telegram_message(
    contact: str,
    message: str,
    parse_mode: Literal["plain", "markdown", "html"] = "plain",
) -> str:
    """
    Sends a Telegram message via your configured Telegram Bot.

    Setup: Create a bot via @BotFather, get the token, set TELEGRAM_BOT_TOKEN in .env.
    The recipient must have started a conversation with your bot first.

    Args:
        contact: Recipient — numeric chat_id, @username, or display name
                 (e.g. "12345678", "@john_doe", "John Doe").
        message: Text to send. Supports Markdown or HTML based on parse_mode.
        parse_mode: "plain" (default), "markdown", or "html" formatting.
    """
    logger.info(f"Telegram send → {contact}")

    if not TELEGRAM_BOT_TOKEN:
        return (
            "Telegram bot token not configured. "
            "Set TELEGRAM_BOT_TOKEN in your .env file. "
            "Create a bot at https://t.me/BotFather."
        )
    if not message.strip():
        return "Message cannot be empty."

    try:
        chat_id = _resolve_telegram_chat_id(contact)

        kwargs: dict = {"chat_id": chat_id, "text": message}
        if parse_mode == "markdown":
            kwargs["parse_mode"] = "MarkdownV2"
        elif parse_mode == "html":
            kwargs["parse_mode"] = "HTML"

        result = _tg("sendMessage", **kwargs)
        if result.get("ok"):
            msg_id = result["result"]["message_id"]
            return f"Telegram message sent to '{contact}' (message ID: {msg_id})."
        return f"Telegram API error: {result.get('description', 'Unknown error')}"

    except requests.HTTPError as e:
        return f"Telegram request failed (HTTP {e.response.status_code}): {e}"
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Telegram send failed: {e}"


@function_tool
async def get_telegram_messages(
    contact: Optional[str] = None,
    limit: int = 5,
) -> str:
    """
    Retrieves recent messages from your Telegram bot inbox.

    Args:
        contact: Optional — filter messages from a specific contact (name or @username).
                 If omitted, returns the latest messages from any chat.
        limit: Number of recent messages to retrieve (1–20, default 5).
    """
    logger.info(f"Telegram fetch — contact: {contact}, limit: {limit}")

    if not TELEGRAM_BOT_TOKEN:
        return "Telegram bot token not configured. Set TELEGRAM_BOT_TOKEN in .env."

    limit = max(1, min(limit, 20))

    try:
        # Use offset=-100 to instantly flush old buffers and only get the latest 100 messages
        updates = _tg("getUpdates", offset=-100, limit=100, allowed_updates=["message"])
        results = updates.get("result", [])
        if not results:
            return "No messages in bot inbox yet."

        messages = []
        for update in reversed(results):
            msg  = update.get("message", {})
            if not msg:
                continue
            chat = msg.get("chat", {})
            user = msg.get("from", {})
            text = msg.get("text", "[non-text content]")

            sender = (
                user.get("username")
                or f"{user.get('first_name','')} {user.get('last_name','')}".strip()
                or chat.get("title", "Unknown")
            )

            if contact:
                name_match = contact.lower() in sender.lower()
                user_match = (
                    contact.lstrip("@").lower() == user.get("username", "").lower()
                )
                if not (name_match or user_match):
                    continue

            messages.append(f"• {sender}: {text}")
            if len(messages) >= limit:
                break

        if not messages:
            return (
                f"No messages from '{contact}'."
                if contact else "No messages found."
            )

        header = (
            f"Last {len(messages)} message(s)"
            + (f" from '{contact}'" if contact else "")
            + ":"
        )
        return header + "\n" + "\n".join(messages)

    except Exception as e:
        return f"Failed to fetch Telegram messages: {e}"


@function_tool
async def send_discord_message(
    channel: str,
    message: str,
    username_override: Optional[str] = None,
) -> str:
    """
    Sends a message to a Discord channel.

    Two modes (auto-detected from .env):
      - Webhook mode: Set DISCORD_WEBHOOK_URL for a single fixed channel.
        'channel' param is ignored — message always goes to webhook channel.
      - Bot mode: Set DISCORD_BOT_TOKEN for full multi-channel/guild support.
        'channel' must be a channel_id or #channel-name.

    Args:
        channel: Target channel — numeric ID (e.g. "123456789") or name (e.g. "#general").
                 Ignored in webhook mode.
        message: Message text to send. Supports Discord markdown.
        username_override: Display name for the message sender (webhook mode only).
    """
    logger.info(f"Discord send → {channel}")

    if not DISCORD_BOT_TOKEN and not DISCORD_WEBHOOK_URL:
        return (
            "Discord not configured. Set DISCORD_BOT_TOKEN or DISCORD_WEBHOOK_URL in .env.\n"
            "Bot token: https://discord.com/developers/applications\n"
            "Webhook: Server Settings → Integrations → Webhooks"
        )
    if not message.strip():
        return "Message cannot be empty."

    # Webhook mode (simpler — no bot token needed)
    if DISCORD_WEBHOOK_URL and not DISCORD_BOT_TOKEN:
        try:
            payload: dict = {"content": message}
            if username_override:
                payload["username"] = username_override
            resp = requests.post(
                DISCORD_WEBHOOK_URL, json=payload, timeout=10
            )
            if resp.status_code in (200, 204):
                return "Discord message sent via webhook."
            return f"Webhook failed (HTTP {resp.status_code}): {resp.text[:200]}"
        except Exception as e:
            return f"Discord webhook failed: {e}"

    # Bot mode — full API
    try:
        channel_id = _resolve_discord_channel(channel)
        resp = requests.post(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers=_discord_headers(),
            json={"content": message},
            timeout=10,
        )
        if resp.status_code == 200:
            msg_id = resp.json().get("id", "?")
            return f"Discord message sent to {channel} (ID: {msg_id})."
        return f"Discord API error (HTTP {resp.status_code}): {resp.text[:200]}"

    except requests.HTTPError as e:
        code = e.response.status_code
        if code == 403:
            return f"Bot lacks permission to send in '{channel}'. Check bot role permissions."
        if code == 404:
            return f"Channel '{channel}' not found."
        return f"Discord request failed (HTTP {code}): {e}"
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Discord send failed: {e}"


@function_tool
async def get_discord_messages(
    channel: str,
    limit: int = 5,
) -> str:
    """
    Fetches recent messages from a Discord channel (bot mode only).

    Args:
        channel: Channel ID or #channel-name to read from.
        limit: Number of recent messages to fetch (1–20, default 5).
    """
    logger.info(f"Discord fetch — channel: {channel}, limit: {limit}")

    if not DISCORD_BOT_TOKEN:
        return "Discord bot token required to read messages. Set DISCORD_BOT_TOKEN in .env."

    limit = max(1, min(limit, 20))

    try:
        channel_id = _resolve_discord_channel(channel)
        resp = requests.get(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers=_discord_headers(),
            params={"limit": limit},
            timeout=10,
        )
        if resp.status_code != 200:
            return f"Discord API error (HTTP {resp.status_code}): {resp.text[:200]}"

        msgs = resp.json()
        if not msgs:
            return f"No messages found in '{channel}'."

        lines = [
            f"• {m['author']['username']}: {m['content'] or '[embed/attachment]'}"
            for m in msgs
        ]
        return f"Last {len(lines)} message(s) in {channel}:\n" + "\n".join(lines)

    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Failed to fetch Discord messages: {e}"
