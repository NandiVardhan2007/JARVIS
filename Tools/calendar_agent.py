"""Calendar Agent — Google Calendar API integration.

Handles listing, creating, and deleting events. Uses OAuth2 for authentication.
Requires a credentials.json file in the root directory.
"""

import datetime
import logging
import os
import pickle
from typing import Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Scopes needed for both calendar and contacts to share the same token.pickle
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/contacts.readonly"
]


def _get_calendar_service():
    """Authenticates and returns the Google Calendar service."""
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    token_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.pickle")
    credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")

    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    "Google Calendar credentials.json not found in the root directory. "
                    "Please create an OAuth Client ID in Google Cloud Console and save it as credentials.json."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    return build("calendar", "v3", credentials=creds)


def _format_event(event: dict) -> str:
    """Formats a Google Calendar event dictionary into a readable string."""
    start = event["start"].get("dateTime", event["start"].get("date"))
    end = event["end"].get("dateTime", event["end"].get("date"))
    
    # Clean up the datetime string for readability if it's a dateTime
    if "T" in start:
        start_dt = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.datetime.fromisoformat(end.replace("Z", "+00:00"))
        start_str = start_dt.strftime("%b %d, %I:%M %p")
        end_str = end_dt.strftime("%I:%M %p")
        time_str = f"{start_str} to {end_str}"
    else:
        # It's an all-day event
        time_str = f"{start} (All Day)"
        
    event_id = event.get("id", "unknown")
    summary = event.get("summary", "No Title")
    return f"[ID: {event_id}] {time_str} - {summary}"


@function_tool
async def get_today_schedule() -> str:
    """
    Retrieves all calendar events scheduled for today.
    """
    logger.info("Fetching today's schedule")
    try:
        service = _get_calendar_service()

        now = datetime.datetime.utcnow().isoformat() + "Z"
        end_of_day = (datetime.datetime.utcnow().replace(hour=23, minute=59, second=59)).isoformat() + "Z"
        
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            timeMax=end_of_day,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        
        events = events_result.get("items", [])

        if not events:
            return "No upcoming events found for today."

        lines = ["Today's Schedule:"]
        for event in events:
            lines.append(_format_event(event))
            
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_today_schedule error: {e}")
        return f"Failed to retrieve today's schedule: {e}"


@function_tool
async def list_upcoming_events(days: int = 7) -> str:
    """
    Retrieves upcoming calendar events for the next N days.
    
    Args:
        days: Number of days to look ahead (default 7).
    """
    logger.info(f"Fetching upcoming events for {days} days")
    try:
        service = _get_calendar_service()

        now = datetime.datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + datetime.timedelta(days=days)).isoformat() + "Z"

        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=20,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        
        events = events_result.get("items", [])

        if not events:
            return f"No upcoming events found in the next {days} days."

        lines = [f"Upcoming events (next {days} days):"]
        for event in events:
            lines.append(_format_event(event))
            
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"list_upcoming_events error: {e}")
        return f"Failed to retrieve upcoming events: {e}"


@function_tool
async def create_event(
    title: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = ""
) -> str:
    """
    Creates a new calendar event.
    
    Args:
        title: The title or summary of the event.
        start_time: Start time in ISO 8601 format (e.g., '2023-10-27T10:00:00').
        end_time: End time in ISO 8601 format (e.g., '2023-10-27T11:00:00').
        description: Optional description of the event.
        location: Optional location of the event.
    """
    logger.info(f"Creating event: {title} from {start_time} to {end_time}")
    try:
        service = _get_calendar_service()
        
        # Ensure proper formatting if timezone info is missing (assume local)
        if not start_time.endswith("Z") and "+" not in start_time:
            # We'll let Google handle it, but it needs timezone formatting to be robust in real apps
            # For simplicity in this demo, we'll append the user's local tz offset or assume it's valid
            pass
            
        event = {
            "summary": title,
            "description": description,
            "location": location,
            "start": {
                "dateTime": start_time,
                # "timeZone": "America/New_York", # Optional, defaults to primary calendar tz
            },
            "end": {
                "dateTime": end_time,
            },
        }

        created_event = service.events().insert(calendarId="primary", body=event).execute()
        
        return f"Event created successfully: {created_event.get('htmlLink')}"
    except Exception as e:
        logger.error(f"create_event error: {e}")
        return f"Failed to create event: {e}"


@function_tool
async def find_free_slot(date_str: str, duration_minutes: int = 60) -> str:
    """
    Finds available time slots on a given date.
    
    Args:
        date_str: The date to search in 'YYYY-MM-DD' format.
        duration_minutes: Required free duration in minutes (default 60).
    """
    logger.info(f"Finding {duration_minutes}m free slot on {date_str}")
    try:
        service = _get_calendar_service()
        
        try:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return "Invalid date format. Please use YYYY-MM-DD."
            
        # We look from 9 AM to 5 PM on the target date (local time approximation)
        start_of_day = target_date.replace(hour=9, minute=0, second=0).isoformat() + "Z"
        end_of_day = target_date.replace(hour=17, minute=0, second=0).isoformat() + "Z"
        
        body = {
            "timeMin": start_of_day,
            "timeMax": end_of_day,
            "timeZone": "UTC",
            "items": [{"id": "primary"}]
        }
        
        freebusy_result = service.freebusy().query(body=body).execute()
        busy_slots = freebusy_result["calendars"]["primary"]["busy"]
        
        # Simple slot finding logic
        # For a real implementation, you'd want to handle timezone conversions accurately
        if not busy_slots:
            return f"The whole day (9AM-5PM) appears free on {date_str}."
            
        return f"Busy slots found on {date_str}: {busy_slots}. Finding an exact free slot requires more complex timezone handling in this simplified tool, but you can infer availability from these busy blocks."
        
    except Exception as e:
        logger.error(f"find_free_slot error: {e}")
        return f"Failed to find free slot: {e}"


@function_tool
async def delete_event(event_id: str) -> str:
    """
    Deletes a calendar event by its ID.
    
    Args:
        event_id: The ID of the event to delete.
    """
    logger.info(f"Deleting event ID: {event_id}")
    try:
        service = _get_calendar_service()
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return f"Event {event_id} deleted successfully."
    except Exception as e:
        logger.error(f"delete_event error: {e}")
        return f"Failed to delete event: {e}"


__all__ = ["get_today_schedule", "list_upcoming_events", "create_event", "find_free_slot", "delete_event"]
