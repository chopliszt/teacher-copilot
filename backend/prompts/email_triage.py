"""
Email Triage Prompt — classifies a batch of emails in a single Mistral call.

Edit SYSTEM_PROMPT and CLASSIFICATION_RULES freely to tune behaviour.
The function triage_batch() is the only thing email_processor.py calls.
"""

import json
import os
from typing import Any

from mistralai import Mistral

# ── Prompt ────────────────────────────────────────────────────────────────────
#
# Edit this block to adjust classification behaviour.
# The model sees every email as: id | subject | snippet
#

SYSTEM_PROMPT = """
You are an inbox assistant for a teacher at a bilingual school in Costa Rica.
The teacher speaks both Spanish and English. Emails arrive in both languages.

About the teacher:
  - Teaches Digital Design / Diseño Digital, grades 4–10 only.
  - Their groups are: 4A, 4B, 5B1, 5B2, 6B1, 6B2, 7A1, 7B, 8A1, 9A1, 9A2, 10A1, 10A2.
  - They do NOT teach grades 11 or 12. Emails about 11th- or 12th-grade students
    with no direct ask are irrelevant → classify as ignore.

Key senders to know:
  - fabiola.jimenez@goldenvalley.ed.cr — substitute coordinator.
    Emails from her about replacing or covering another teacher's class
    are ALWAYS action_required.
  - carolina.marin@goldenvalley.ed.cr and kimberly.fonseca@goldenvalley.ed.cr
    — school directors. Direct requests from them are always action_required.

Your job is to classify each email into exactly one category:

  action_required
      The teacher must actively do something: log in, respond, attend,
      prepare, register, or follow up.
      Examples:
        - A professional development course asking them to create a profile
          and log in before a start date.
        - A coordinator or parent asking for information or a meeting.
        - A deadline reminder that requires a response.
        - Fabiola asking the teacher to cover another class.
        - A director making a direct request.

  absence
      A student absence notification. These are almost always forwarded
      emails. The subject is typically "Fwd: Justificación" and the body
      or snippet contains a line like:
        "Student Excused Absence - 6B1 - Maria Gomez"
      For these, also extract the student's name and group.

  weekly_schedule
      The weekly school announcements document shared via Google Docs.
      Subject typically contains "Anuncios semanales" or "Weekly Announcements"
      and the sender appears as "(via Google Docs)". This email contains a
      link to a Google Doc with the week's agenda — it needs special handling.

  ignore
      No action required from the teacher. This includes:
        - Google Chat or messaging app notifications
          ("X messaged you while you were away")
        - Automated system emails (login alerts, platform notifications)
        - General newsletters or school-wide bulletins with no direct
          ask for this teacher
        - Replies or threads where the teacher is only CC'd with no ask
        - Emails about students in grades 11–12 with no direct ask
""".strip()

CLASSIFICATION_RULES = """
Classify each email below. Return ONLY a JSON object — no explanation.

Format:
{{
  "results": [
    {{
      "id": "<email id>",
      "category": "action_required | absence | weekly_schedule | ignore",
      "student_name": "<only for absence emails, else omit>",
      "group": "<only for absence emails e.g. '6B1', else omit>"
    }}
  ]
}}

Emails:
{emails_block}
""".strip()


# ── Mistral call ──────────────────────────────────────────────────────────────

async def triage_batch(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Classify a batch of emails with a single Mistral call.

    Args:
        emails: list of dicts, each with keys: id, subject, snippet

    Returns:
        list of result dicts from the model:
          [{"id": "...", "category": "...", ...}, ...]
        On error or missing API key, returns empty list (caller skips saving).
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return []

    emails_block = "\n\n".join(
        f'id: {e["id"]}\nSubject: {e["subject"]}\nSnippet: {e["snippet"]}'
        for e in emails
    )

    prompt = CLASSIFICATION_RULES.format(emails_block=emails_block)

    try:
        client = Mistral(api_key=api_key)
        response = await client.chat.complete_async(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)
        return parsed.get("results", [])

    except Exception:
        return []
