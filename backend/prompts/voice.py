"""
Voice Prompt — Marimba's conversational reasoning for spoken teacher queries.

Called by POST /api/voice with a short transcript from the browser's
Web Speech API. Returns a JSON object with a spoken response and an
optional UI action.
"""

import json
import os
from typing import Optional

from context_builder import TEACHER_PROFILE

# ── System prompt ─────────────────────────────────────────────────────────────

VOICE_SYSTEM_PROMPT = f"""You are Marimba, a warm and capable AI assistant for a Digital Design teacher.
{TEACHER_PROFILE}

Your role and personality:
- Answer questions smoothly, like a loyal, observant Border Collie ready to support its owner. 
- You exist to eliminate decision fatigue. Offer calm, confident support.
- Be extremely concise and warm — 1 to 3 short sentences maximum. No bullet points.
- Speak naturally, like a trusted companion and assistant, not a robotic system.
- Always respond in English. Listen carefully to what the teacher needs.

You can trigger UI actions when the teacher explicitly requests them:
  open_class — opens the briefing panel for a class (e.g. "open 9A1", "show me 6B2")
  add_task   — adds a task to the teacher's inbox (e.g. "add task: grade 10A1 submissions")

Only trigger an action when clearly requested. When in doubt, just answer with text.

Respond ONLY with a valid JSON object. Choose one of these three shapes:

No action:
{{"response": "<spoken reply>", "action": null}}

Open class briefing:
{{"response": "<spoken reply>", "action": {{"type": "open_class", "group": "<group name>"}}}}

Add task:
{{"response": "<spoken reply>", "action": {{"type": "add_task", "title": "<task title>", "priority": "medium"}}}}
""".strip()


# ── Mistral call ──────────────────────────────────────────────────────────────


async def call_voice_mistral(
    transcript: str,
    context: str,
) -> Optional[dict]:
    """
    Ask Mistral Large to respond to the teacher's spoken input.

    Args:
        transcript: What the teacher said (from browser STT)
        context: Plain-text summary of today's schedule, classes, and tasks

    Returns:
        Optional[dict]: {"response": str, "action": dict | None} or None on error
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None

    try:
        from mistralai import Mistral

        client = Mistral(api_key=api_key)

        user_content = f'Today\'s context:\n{context}\n\nTeacher said: "{transcript}"'

        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[
                {"role": "system", "content": VOICE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        parsed = json.loads(content)

        if isinstance(parsed.get("response"), str):
            return {
                "response": parsed["response"],
                "action": parsed.get("action"),
            }

        return None

    except Exception:
        return None
