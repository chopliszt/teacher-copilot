"""
Connector: Google Calendar
Status: stub — not yet implemented
n8n setup: Google Calendar OAuth2 credential + event-list webhook
"""
from typing import List, Dict, Any


def is_configured() -> bool:
    """Returns True when required env vars / webhook URL are set."""
    return False


def get_tasks() -> List[Dict[str, Any]]:
    """Fetch tasks/items from this source. Returns [] until implemented."""
    return []
