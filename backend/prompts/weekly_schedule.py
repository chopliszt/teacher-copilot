"""
Weekly Schedule Prompt — extracts structured agenda items from the
"Anuncios Semanales" Google Doc content.

Paste the plain text from the weekly Google Doc into POST /api/weekly-schedule.
This module reads it with Mistral and returns structured JSON.

Edit EXTRACTION_RULES freely to add or remove output fields.
"""

import json
import os
import re
from datetime import time as _time
from pathlib import Path

from mistralai import Mistral

# ── Prompt ────────────────────────────────────────────────────────────────────

TEACHER_CONTEXT = """
The teacher's name is T. Teacher. They teach Digital Design / Diseño Digital
at Golden Valley School, Costa Rica. Their exact class schedule is:

  Day 1: 9A1 (11:30am–12:50pm), 5B1 (1:30pm–2:50pm)
  Day 2: 8A1 (7:50am–9:10am), 5B2 (10:50am–12:10pm), 6B1 (1:30pm–2:50pm)
  Day 3: 9A2 (7:50am–9:10am), 10A2 (9:10am–9:50am), 8A1 (10:10am–11:30am)
  Day 4: Homeroom 9A2 (7:30–7:50am), 10A1 (7:50am–8:30am), 6B2 (10:10am–11:30am), 7B (11:30am–12:50pm)
  Day 5: Homeroom 9A2 (7:30–7:50am), 9A2 (8:30am–9:50am), 9A1 (10:10am–11:30am), 7A1 (11:30am–12:50pm)
  Day 6: Homeroom 9A2 (7:30–7:50am) — no classes this day
""".strip()

EXTRACTION_RULES = """
You are reading the weekly school announcements document for a bilingual school
in Costa Rica. Extract information relevant to the teacher described below.

{teacher_context}

From the document, extract and return a JSON object with these fields:

  week_label        (string) e.g. "Semana #6 - Del 2 al 6 de marzo"

  meetings          (array) Events or meetings the teacher must attend.
                    Each item: {{ description, day, schedule_day (1-6 or null),
                                  time, location, mandatory (true/false) }}

  class_disruptions (array) Events that could disrupt classes for this teacher's groups.
                    Include any event that involves a group this teacher teaches,
                    on the schedule day the teacher has them.
                    Each item: {{ description, day, schedule_day (1-6 or null),
                                  time, groups_affected (array of group names
                                  or ["all"] if school-wide) }}

  action_items      (array of strings) Things the teacher needs to do,
                    remind students about, or prepare.

  upcoming_dates    (array) Important future dates (even outside this week).
                    Each item: {{ date (YYYY-MM-DD or best estimate),
                                  description }}

  absences          (array) Any students mentioned as absent this week.
                    Each item: {{ student_name, group, day }}

Return ONLY the JSON object. No explanation.

Document:
{document_text}
""".strip()


# ── Time-overlap filter (Python handles the deterministic math) ────────────────

def _parse_single_time(s: str) -> _time | None:
    """Parse '7:50am', '9:10 AM', '1:30pm', '12:10md' → time object."""
    s = s.strip().lower().replace('\u00a0', '').replace(' ', '')
    s = s.replace('md', 'pm')   # Spanish mediodía = noon
    m = re.match(r'^(\d{1,2}):(\d{2})(am|pm)?$', s)
    if not m:
        return None
    h, mins, mer = int(m.group(1)), int(m.group(2)), m.group(3)
    if mer == 'pm' and h != 12:
        h += 12
    elif mer == 'am' and h == 12:
        h = 0
    elif mer is None and 1 <= h <= 6:
        h += 12   # no suffix + 1–6 → assume afternoon (school context)
    return _time(h, mins) if 0 <= h <= 23 and 0 <= mins <= 59 else None


def _parse_time_range(s: str) -> tuple[_time, _time] | None:
    """Parse '7:50am–9:10am', '10:10am - 11:30am', '11:00am', etc."""
    parts = re.split(r'\s*[–—\-]\s*', s.strip(), maxsplit=1)
    if len(parts) == 2:
        start = _parse_single_time(parts[0])
        end   = _parse_single_time(parts[1])
        if start and end:
            return start, end
    # Single time — give it a 90-minute window (one school period)
    start = _parse_single_time(s.strip())
    if start:
        return start, _time(min(start.hour + 1, 23), min(start.minute + 30, 59))
    return None


def _overlaps(r1: tuple[_time, _time], r2: tuple[_time, _time]) -> bool:
    return r1[0] < r2[1] and r2[0] < r1[1]


def _load_schedule() -> dict:
    path = Path(__file__).parent.parent / "data" / "teacher_schedule.json"
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _filter_disruptions(disruptions: list[dict], schedule: dict) -> list[dict]:
    """
    Post-process Mistral's class_disruptions to only keep entries where:
      1. The teacher actually has that group on that schedule day.
      2. The disruption time overlaps with the teacher's class time for that group.
    Entries that pass neither check are dropped entirely.
    """
    day_groups: dict[int, dict[str, str]] = {
        day["day"]: {p["group"]: p["time"] for p in day.get("periods", [])}
        for day in schedule.get("classes", [])
    }

    result = []
    for d in disruptions:
        sday = d.get("schedule_day")

        # No schedule day → can't filter, keep as-is
        if sday is None or sday not in day_groups:
            result.append(d)
            continue

        teacher_today = day_groups[sday]         # {group: "HH:MMam–HH:MMpm"}
        raw_groups = d.get("groups_affected", [])

        # Expand "all" → every group the teacher has today
        if any(g.lower() == "all" for g in raw_groups):
            raw_groups = list(teacher_today.keys())

        d_range = _parse_time_range(d.get("time", ""))

        affected = []
        for group in raw_groups:
            if group not in teacher_today:
                continue                          # teacher doesn't teach this group today
            if d_range is None:
                affected.append(group)            # can't parse time → include conservatively
                continue
            c_range = _parse_time_range(teacher_today[group])
            if c_range is None or _overlaps(d_range, c_range):
                affected.append(group)

        if affected:
            result.append({**d, "groups_affected": affected})
        # Otherwise the event doesn't actually hit any of this teacher's classes → drop

    return result


# ── Mistral call ───────────────────────────────────────────────────────────────

async def extract_weekly_schedule(document_text: str) -> dict:
    """
    Extract structured agenda items from the weekly announcements doc.

    Returns:
        Parsed dict with keys: week_label, meetings, class_disruptions,
        action_items, upcoming_dates, absences.
        Returns empty dict on error or missing API key.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return {}

    prompt = EXTRACTION_RULES.format(
        teacher_context=TEACHER_CONTEXT,
        document_text=document_text,
    )

    try:
        client = Mistral(api_key=api_key)
        response = await client.chat.complete_async(
            model="mistral-small-latest",
            messages=[
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)

        # Python post-processing: enforce time-overlap filter deterministically
        schedule = _load_schedule()
        result["class_disruptions"] = _filter_disruptions(
            result.get("class_disruptions", []), schedule
        )

        return result

    except Exception:
        return {}
