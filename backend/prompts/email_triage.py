"""
Email Triage Prompt — classifies a batch of emails in a single Mistral call.

Edit SYSTEM_PROMPT and CLASSIFICATION_RULES freely to tune behaviour.
The function triage_batch() is the only thing email_processor.py calls.
"""

import json
import os
from typing import Any

from mistralai import Mistral

from preferences import get_ignore_rules, get_personal_context

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

HOW TO DECIDE — addressee first, then ask:
  The single question that matters is: **is this email asking ME,
  specifically, to do or say something?** Decide it in two ordered steps.

  STEP 1 — Is it addressed to me personally?
    The teacher is Camilo Infante (profesor Infante / "profe").
    ADDRESSED-TO-ME signals:
      - The greeting names me: "Hola Camilo", "Camilo,", "@Camilo",
        "profe", "profesor Infante".
      - I am the primary recipient — my name/address is in the To line,
        not merely one of many and not only on Cc.
    BROADCAST / NOT-TO-ME signals (do NOT treat as personal):
      - I am only on the Cc line.
      - To is a large list or a group alias (e.g. "Personal Docente",
        "staff@...", "todos@...").
      - The greeting or the To line addresses someone else and I'm copied.

  STEP 2 — Only if it IS addressed to me: does it expect something back?
    Either of these counts as a yes:
      - An imperative directed at me (escalar, enviar, confirmar, llenar,
        revisar, responder, adjuntar, coordinar, programar, asistir,
        ayudar, pasar, mandar, pagar, traer, etc.).
      - A QUESTION I'm expected to answer — even with NO command verb:
        "¿Cómo sería la reestructuración del comité?", "¿Me confirmás?",
        "¿Qué te parece?", "¿Cuándo podrías?". A direct question to me
        IS an ask.

  If BOTH steps are yes → action_required, regardless of who sent it.

  IMPORTANT — do not flag on a question alone. A question in a school-wide
  bulletin, or a question aimed at someone else in a thread I'm only copied
  on, is NOT my ask → ignore. The gate is "addressed to me"; the question
  only matters after that gate passes.

  When it IS addressed to me and you are genuinely unsure whether it needs a
  reply, lean toward action_required — a missed personal ask costs more than
  one card the teacher can dismiss in a tap. This lean applies ONLY to mail
  addressed to me, never to broadcast or Cc-only mail.

  Pure pleasantries addressed to me with no ask ("Gracias Camilo", "Feliz
  fin de semana", an FYI that says "no need to reply") → ignore.

If the teacher's personal context (provided below) names specific
collaborators or describes ongoing initiatives they are organizing,
treat emails from those people OR about those initiatives as
action_required by default.
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

    # Surface From/To/Cc so the model can gate on "addressed to me" vs
    # broadcast/Cc-only, plus a body excerpt (first 800 chars) so direct
    # mentions buried in thread replies are visible — snippets miss those.
    def _fmt(e: dict[str, Any]) -> str:
        lines = [
            f'id: {e["id"]}',
            f'From: {e.get("sender", "")}',
            f'To: {e.get("to", "")}',
        ]
        cc = (e.get("cc") or "").strip()
        if cc:
            lines.append(f'Cc: {cc}')
        lines.append(f'Subject: {e["subject"]}')
        lines.append(f'Snippet: {e["snippet"]}')
        body = (e.get("body") or "").strip()
        if body:
            body_excerpt = body[:800].replace("\n", " ")
            lines.append(f'Body excerpt: {body_excerpt}')
        return "\n".join(lines)

    emails_block = "\n\n".join(_fmt(e) for e in emails)

    prompt = CLASSIFICATION_RULES.format(emails_block=emails_block)

    system_prompt = SYSTEM_PROMPT

    # Inject the teacher's "About me / How I work" block — names their roles,
    # direct collaborators, and ongoing initiatives. This is the single biggest
    # lift for triage accuracy.
    personal_context = get_personal_context()
    if personal_context:
        system_prompt = (
            system_prompt
            + "\n\nTeacher's personal context — use this to identify priority "
              "senders, ongoing initiatives, and roles:\n"
            + personal_context.strip()
        )

    ignore_rules = get_ignore_rules()
    if ignore_rules:
        system_prompt = (
            system_prompt
            + "\n\nTeacher's personal ignore rules — anything matching these "
              "should be classified as `ignore` unless it contains a direct ask:\n"
            + ignore_rules.strip()
        )

    try:
        client = Mistral(api_key=api_key)
        response = await client.chat.complete_async(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)
        return parsed.get("results", [])

    except Exception:
        return []
