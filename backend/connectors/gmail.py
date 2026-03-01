"""
Connector: Gmail
Status: stub — not yet implemented
n8n setup: Gmail OAuth2 credential + Watch trigger webhook
"""
from typing import List, Dict, Any


def is_configured() -> bool:
    """Returns True when required env vars / webhook URL are set."""
    return False


def get_tasks() -> List[Dict[str, Any]]:
    """Fetch tasks/items from this source. Returns [] until implemented."""
    return []
