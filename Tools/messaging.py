"""Messaging tool — Discord Webhook / Bot API."""

import logging
import os
from typing import Optional

import requests
from Tools.function_tool import function_tool

logger = logging.getLogger(__name__)

# ── Discord ───────────────────────────────────────────────────────────────────
DISCORD_BOT_TOKEN   = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")   # fallback (single channel)
DISCORD_API         = "https://discord.com/api/v10"


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
