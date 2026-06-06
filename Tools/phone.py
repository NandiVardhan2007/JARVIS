import os
import logging
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

@function_tool
async def make_phone_call(phone_number: str, sip_trunk_id: str = "") -> str:
    """
    Make a phone call using LiveKit SIP trunking.
    This dials the target phone number and brings them into the active JARVIS room.
    
    Args:
        phone_number: The phone number to dial, including country code (e.g. +1234567890).
        sip_trunk_id: Optional SIP trunk ID. If not provided, it will use the default SIP trunk configured in LiveKit.
    """
    try:
        from livekit.api import LiveKitAPI
        from livekit.protocol import sip
        
        # Ensure LiveKit API credentials are set
        if not os.getenv("LIVEKIT_API_KEY") or not os.getenv("LIVEKIT_API_SECRET") or not os.getenv("LIVEKIT_URL"):
            return "LiveKit API credentials (LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL) are not set. Cannot make phone call."
            
        # The room JARVIS is currently in
        room_name = os.getenv("LIVEKIT_ROOM", "jarvis-room")
        
        api = LiveKitAPI()
        
        # Dial the participant
        req = sip.CreateSIPParticipantRequest(
            sip_trunk_id=sip_trunk_id,
            sip_call_to=phone_number,
            room_name=room_name,
            participant_identity=f"phone_{phone_number.replace('+', '')}"
        )
        participant = await api.sip.create_sip_participant(req)
        
        await api.aclose()
        return f"Successfully dialing {phone_number}... They will join the room '{room_name}' shortly."
    except Exception as e:
        logger.error(f"Failed to make phone call: {e}", exc_info=True)
        return f"Failed to make phone call: {str(e)}"
