"""Google Contacts Agent — Google People API integration.

Handles searching for contacts by name to retrieve phone numbers.
Requires a credentials.json file in the root directory.
"""

import logging
import os
import pickle
import re
from typing import Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Scopes needed for both calendar and contacts to share the same token.pickle
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/contacts.readonly"
]


def _get_people_service():
    """Authenticates and returns the Google People API service."""
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
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
                
        if not creds:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    "Google Contacts credentials.json not found in the root directory. "
                    "Please create an OAuth Client ID in Google Cloud Console and save it as credentials.json."
                )
            
            # If token exists but scope is wrong, it will prompt to login again
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    return build("people", "v1", credentials=creds)


@function_tool
async def search_google_contact(name: str) -> str:
    """
    Searches the user's Google Contacts for a person by name and returns their phone number.
    Use this to look up a phone number before sending a WhatsApp message or SMS.
    
    Args:
        name: The name or partial name of the contact (e.g., 'Amma', 'John Doe').
    """
    logger.info(f"Searching Google Contacts for: {name}")
    try:
        service = _get_people_service()
        
        # We fetch all contacts and filter locally since searchDirectory isn't always reliable for personal contacts
        results = service.people().connections().list(
            resourceName='people/me',
            pageSize=1000,
            personFields='names,phoneNumbers'
        ).execute()
        
        connections = results.get('connections', [])
        
        if not connections:
            return "Your Google Contacts list is empty."
            
        # Try to find a match
        query = name.lower().strip()
        best_match = None
        
        for person in connections:
            names = person.get('names', [])
            if not names:
                continue
                
            display_name = names[0].get('displayName', '').lower()
            
            if query in display_name:
                phone_numbers = person.get('phoneNumbers', [])
                if phone_numbers:
                    number = phone_numbers[0].get('value', '')
                    best_match = {
                        "name": names[0].get('displayName', ''),
                        "number": number
                    }
                    # Exact match takes priority
                    if query == display_name:
                        break
                        
        if best_match:
            result = f"Found contact '{best_match['name']}' with phone number: {best_match['number']}"
            logger.info(result)
            return result
        else:
            result = f"Could not find any contact matching the name '{name}'."
            logger.info(result)
            return result
            
    except Exception as e:
        logger.error(f"search_google_contact error: {e}")
        return f"Failed to search Google Contacts: {e}. If it is a permission error, please delete token.pickle and restart JARVIS."


__all__ = ["search_google_contact"]
