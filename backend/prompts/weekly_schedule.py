"""
Weekly Schedule Prompt — extracts structured agenda items from the
"Anuncios Semanales" Google Doc content.

n8n fetches the Google Doc text and POSTs it to POST /api/weekly-schedule.
This module reads it with Mistral and returns structured JSON.

Edit EXTRACTION_RULES freely to add or remove output fields.
"""

import json
import os

from mistralai import Mistral

# ── Prompt ────────────────────────────────────────────────────────────────────
#
# The school uses a 6-day rotating schedule (Day 1–6).
# Days of the week in the document map to schedule days.
#
# Edit TEACHER_CONTEXT to match the real schedule when connectors are live.
# For now it uses the known schedule from teacher_schedule.json.
#

TEACHER_CONTEXT = """
The teacher's name is C. Infante. They teach Digital Design / Diseño Digital
at Golden Valley School, Costa Rica. Their class groups are:
  Day 1: 8A1 (×2), 9A1, 5B1  — homeroom: 9A2
  Day 2: 9A2, 5B2, 6B1        — homeroom: 9A2
  Day 3: 9A2, 10A2, 6B2, 7B   — homeroom: 9A2
  Day 4: 10A1, 4B, 9A1, 4A, 7A1 — homeroom: 9A2
  Day 5: (no classes)          — homeroom: 9A2
  Day 6: (no classes)          — homeroom: 9A2
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

  class_disruptions (array) Events that interrupt normal class time.
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


# ── Mistral call ──────────────────────────────────────────────────────────────

async def extract_weekly_schedule(document_text: str) -> dict:
    """
    Extract structured agenda items from the weekly announcements doc.

    Args:
        document_text: Full plain text of the Google Doc

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
        return json.loads(response.choices[0].message.content)

    except Exception:
        return {}
