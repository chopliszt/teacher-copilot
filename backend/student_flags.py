"""
Student flags loader.

Reads data/student_flags.json — a per-group list of students who need
academic or behavioural accommodation. Used to inject "watch out for"
context into the lesson-plan prompt so Marimba can suggest specific
supports (extra time, modified rubric, 1-on-1 check-in, etc.).

The file format is:
    {
      "8A1": [
        { "name": "Sofía M.", "notes": "Necesita apoyo en todas las materias" },
        ...
      ],
      ...
    }

Missing groups return an empty list — Marimba handles "no flags" gracefully.
"""

import json
from pathlib import Path
from typing import Dict, List

_PATH = Path(__file__).parent / "data" / "student_flags.json"


def get_flags_for_group(group: str) -> List[Dict[str, str]]:
    """Return the list of {name, notes} entries for `group`, or [] if none."""
    if not _PATH.exists():
        return []
    try:
        with _PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return list(data.get(group, []))
    except Exception as e:
        print(f"[StudentFlags] Could not read {_PATH}: {e}")
        return []


def format_flags_block(group: str) -> str:
    """
    Natural-language block describing students who need support.
    Empty string if the group has no flagged students.
    """
    flags = get_flags_for_group(group)
    if not flags:
        return ""
    lines = []
    for f in flags:
        note = f.get("notes", "").strip()
        if note:
            lines.append(f"  - {f['name']} — {note}")
        else:
            lines.append(f"  - {f['name']}")
    return f"STUDENTS IN {group} WHO NEED ACADEMIC SUPPORT:\n" + "\n".join(lines)
