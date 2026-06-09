"""
Phone call tool — LiveKit SIP outbound calls via Telnyx.
JARVIS can call any phone number and speak with the person.
"""

import asyncio
import logging
import os
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

SIP_TRUNK_ID  = os.getenv("LIVEKIT_SIP_TRUNK_ID", "")
LIVEKIT_ROOM  = os.getenv("LIVEKIT_ROOM_NAME", "jarvis-room")


@function_tool
async def make_phone_call(phone_number: str, greeting: str = "") -> str:
    """
    Calls a real phone number. JARVIS will speak with the person
    using its voice pipeline. The call joins the active JARVIS room.

    Args:
        phone_number: Number with country code, e.g. +919876543210
        greeting: Optional opening line JARVIS says when they pick up.
                  If empty, JARVIS will greet naturally.
    """
    if not SIP_TRUNK_ID:
        return (
            "SIP trunk not configured. "
            "Set LIVEKIT_SIP_TRUNK_ID in .env after creating a trunk "
            "in LiveKit Cloud dashboard."
        )

    try:
        from livekit import api
        from livekit.protocol import sip as sip_proto

        lk_api = api.LiveKitAPI(
            url=os.getenv("LIVEKIT_URL"),
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
        )

        # Clean up number — strip spaces and dashes
        clean_number = "".join(c for c in phone_number if c.isdigit() or c == "+")
        if not clean_number.startswith("+"):
            clean_number = "+91" + clean_number  # default India country code

        participant_identity = f"phone_{clean_number.replace('+', '')}"

        req = sip_proto.CreateSIPParticipantRequest(
            sip_trunk_id=SIP_TRUNK_ID,
            sip_call_to=clean_number,
            room_name=LIVEKIT_ROOM,
            participant_identity=participant_identity,
            participant_name=f"Call: {clean_number}",
            play_ringtone=True,
        )

        participant = await lk_api.sip.create_sip_participant(req)
        await lk_api.aclose()

        logger.info(f"SIP call initiated to {clean_number}, participant: {participant_identity}")

        if greeting:
            # Small delay to let the call connect, then say the greeting
            await asyncio.sleep(3)
            return (
                f"Calling {clean_number}... "
                f"When they answer, I'll say: '{greeting}'"
            )

        return f"Calling {clean_number}. Ringing now, sir."

    except Exception as e:
        logger.error(f"Phone call failed: {e}", exc_info=True)
        return f"Call failed: {e}"


@function_tool
async def end_phone_call(phone_number: str = "") -> str:
    """
    Ends an active phone call by removing the SIP participant from the room.

    Args:
        phone_number: The number that was called. If empty, ends all active calls.
    """
    try:
        from livekit import api

        lk_api = api.LiveKitAPI(
            url=os.getenv("LIVEKIT_URL"),
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
        )

        room_client = api.RoomService(lk_api)

        if phone_number:
            clean = "".join(c for c in phone_number if c.isdigit() or c == "+")
            identity = f"phone_{clean.replace('+', '')}"
            await room_client.remove_participant(
                api.RemoveParticipantRequest(
                    room=LIVEKIT_ROOM,
                    identity=identity,
                )
            )
            await lk_api.aclose()
            return f"Call with {phone_number} ended."
        else:
            # List participants and remove all SIP ones
            participants = await room_client.list_participants(
                api.ListParticipantsRequest(room=LIVEKIT_ROOM)
            )
            ended = []
            for p in participants.participants:
                if p.identity.startswith("phone_"):
                    await room_client.remove_participant(
                        api.RemoveParticipantRequest(
                            room=LIVEKIT_ROOM,
                            identity=p.identity,
                        )
                    )
                    ended.append(p.identity)
            await lk_api.aclose()
            return f"Ended {len(ended)} call(s)." if ended else "No active calls found."

    except Exception as e:
        return f"Failed to end call: {e}"


@function_tool
async def list_active_calls() -> str:
    """
    Lists all currently active phone calls in the JARVIS room.
    """
    try:
        from livekit import api

        lk_api = api.LiveKitAPI(
            url=os.getenv("LIVEKIT_URL"),
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
        )

        room_client = api.RoomService(lk_api)
        participants = await room_client.list_participants(
            api.ListParticipantsRequest(room=LIVEKIT_ROOM)
        )
        await lk_api.aclose()

        calls = [
            p for p in participants.participants
            if p.identity.startswith("phone_")
        ]

        if not calls:
            return "No active phone calls."

        lines = [f"Active calls ({len(calls)}):"]
        for c in calls:
            number = c.identity.replace("phone_", "+")
            lines.append(f"  {number} — joined {c.joined_at}")
        return "\n".join(lines)

    except Exception as e:
        return f"Failed to list calls: {e}"
