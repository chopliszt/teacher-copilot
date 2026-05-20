"""
User preferences — single editable text field with personal ignore rules,
injected into the priority prompt and email-triage prompt so Mistral knows
what the teacher considers noise.

Stored as plain JSON on disk so it survives backend restarts without a DB
migration. The file lives next to schedule_state.json under data/.
"""

import json
from pathlib import Path
from typing import Any, Dict

_PREFS_PATH = Path(__file__).parent / "data" / "user_preferences.json"


def _read_prefs() -> Dict[str, Any]:
    try:
        return json.loads(_PREFS_PATH.read_text())
    except Exception:
        return {}


def get_ignore_rules() -> str:
    return str(_read_prefs().get("ignore_rules", "") or "")


def set_ignore_rules(rules: str) -> str:
    prefs = _read_prefs()
    prefs["ignore_rules"] = rules.strip()
    _PREFS_PATH.write_text(json.dumps(prefs, indent=2))
    return prefs["ignore_rules"]
