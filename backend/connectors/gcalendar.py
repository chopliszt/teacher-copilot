"""
Connector: Google Calendar
Status: Active — uses the same token.json as the Gmail connector.
Scope required: https://www.googleapis.com/auth/calendar.events
Run auth_gmail.py to grant this scope (it's included in the SCOPES list there).
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.json")
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# Costa Rica is UTC-6, no DST
TIMEZONE = "America/Costa_Rica"


def is_configured() -> bool:
    return os.path.exists(TOKEN_FILE)


def _get_calendar_service():
    if not is_configured():
        return None
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        print(f"[Calendar] Error building service: {e}")
        return None


def create_event(
    summary: str,
    start_dt: datetime,
    end_dt: datetime,
    description: str = "",
    attendees: Optional[List[str]] = None,
    calendar_id: str = "primary",
) -> Optional[Dict[str, Any]]:
    """
    Create a Google Calendar event.

    Args:
        summary: Event title
        start_dt: Start datetime (timezone-aware preferred; naive = Costa Rica local)
        end_dt: End datetime
        description: Optional event description / meeting notes
        attendees: List of email addresses to invite
        calendar_id: Calendar to add the event to (default: "primary")

    Returns:
        The created event dict (includes 'id' and 'htmlLink'), or None on error.
    """
    service = _get_calendar_service()
    if not service:
        return None

    def _fmt(dt: datetime) -> str:
        if dt.tzinfo is None:
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        return dt.isoformat()

    event_body: Dict[str, Any] = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": _fmt(start_dt), "timeZone": TIMEZONE},
        "end": {"dateTime": _fmt(end_dt), "timeZone": TIMEZONE},
    }

    if attendees:
        event_body["attendees"] = [{"email": addr} for addr in attendees]

    try:
        event = (
            service.events()
            .insert(calendarId=calendar_id, body=event_body)
            .execute()
        )
        print(f"[Calendar] Event created: {event.get('htmlLink')}")
        return event
    except HttpError as e:
        print(f"[Calendar] Error creating event: {e}")
        return None


def list_upcoming_events(
    max_results: int = 10,
    calendar_id: str = "primary",
) -> List[Dict[str, Any]]:
    """
    Returns up to max_results upcoming events from now, ordered by start time.
    """
    service = _get_calendar_service()
    if not service:
        return []

    now = datetime.now(timezone.utc).isoformat()

    try:
        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return result.get("items", [])
    except HttpError as e:
        print(f"[Calendar] Error listing events: {e}")
        return []


if __name__ == "__main__":
    if not is_configured():
        print("❌ token.json not found. Run auth_gmail.py first.")
    else:
        events = list_upcoming_events(5)
        if events:
            print(f"✅ Next {len(events)} events:")
            for ev in events:
                start = ev["start"].get("dateTime", ev["start"].get("date"))
                print(f"  - {start}: {ev['summary']}")
        else:
            print("✅ Calendar connected. No upcoming events found.")
