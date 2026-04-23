"""
Meeting Summary Prompt — generates a Spanish email draft from a meeting transcript.

Called by POST /api/meetings/process after Voxtral transcribes the audio.
Returns a subject, email body, and extracted action items.
"""

import json
import os
from typing import Optional

from context_builder import TEACHER_PROFILE

MEETING_SUMMARY_SYSTEM_PROMPT = f"""You are Marimba, an AI assistant for a Digital Design teacher at Golden Valley School, Costa Rica.
{TEACHER_PROFILE}

Your task is to read a transcription of a school meeting and produce a JSON object with exactly these four keys:

- "summary": a single paragraph in Spanish (3–6 sentences) summarising the meeting.
- "action_items": a JSON array of plain strings — each string is one action item. NO objects, NO nested keys. Example: ["Entregar planillas antes del viernes", "Confirmar asistencia al acto del 15"]
- "suggested_subject": a single Spanish string starting with "Resumen reunión:" followed by the meeting topic.
- "email_body": the full email body text in Spanish, warm and professional, ready to send. Do not include salutation or signature.

CRITICAL: "action_items" MUST be an array of strings, never an array of objects.
Respond ONLY with a valid JSON object. No markdown, no code fences.
""".strip()


async def summarize_meeting(transcript: str) -> Optional[dict]:
    """
    Ask Mistral Large to summarize a meeting transcript in Spanish.

    Args:
        transcript: Full meeting transcription text (from Voxtral, in Spanish)

    Returns:
        Optional[dict]: {
            "summary": str,
            "action_items": list[str],
            "suggested_subject": str,
            "email_body": str,
        }
        Returns None if MISTRAL_API_KEY is missing or on any error.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None

    try:
        from mistralai import Mistral

        client = Mistral(api_key=api_key)

        user_content = f"Transcripción de la reunión:\n\n{transcript}"

        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[
                {"role": "system", "content": MEETING_SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        parsed = json.loads(content)

        summary = parsed.get("summary", "")
        raw_items = parsed.get("action_items", [])
        suggested_subject = parsed.get("suggested_subject", "Resumen de reunión")
        email_body = parsed.get("email_body", "")

        # Normalize action_items: Mistral sometimes returns objects instead of strings.
        # Convert any non-string item to a readable string so the schema never breaks.
        action_items: list[str] = []
        for item in raw_items if isinstance(raw_items, list) else []:
            if isinstance(item, str):
                action_items.append(item)
            elif isinstance(item, dict):
                # Common shapes: {"task": "..."} or {"description": "..."} or {"item": "..."}
                text = (
                    item.get("task")
                    or item.get("description")
                    or item.get("item")
                    or item.get("action")
                    or item.get("text")
                    or ", ".join(str(v) for v in item.values() if v)
                )
                if text:
                    action_items.append(str(text))
            elif item is not None:
                action_items.append(str(item))

        # If the model returned summary+action_items but no email_body, build one
        if not email_body and summary:
            email_body = summary
            if action_items:
                items_text = "\n".join(f"- {item}" for item in action_items)
                email_body += f"\n\nPuntos de acción:\n{items_text}"

        if not isinstance(summary, str) or not summary.strip():
            return None

        return {
            "summary": summary,
            "action_items": action_items if isinstance(action_items, list) else [],
            "suggested_subject": suggested_subject,
            "email_body": email_body,
        }

    except Exception as e:
        print(f"[MeetingSummary] Error: {e}")
        return None
