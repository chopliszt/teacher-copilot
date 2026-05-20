"""
Task Chat Prompt — Marimba's "chat to solve" mode.

Given a Top 3 task and a conversation history, Mistral acts as a focused
co-worker for that one task. It knows the teacher's profile, the task's
full context, and the teacher's ignore rules. Output is plain conversational
text — no JSON, no actions. Email-reply drafting is handled separately via
draft_email_reply() so the model has a tighter, single-purpose prompt for
the reply itself.
"""

import os
from typing import Any, Dict, List, Optional

from mistralai import Mistral

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_builder import TEACHER_PROFILE
from preferences import get_ignore_rules


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(task_context: str) -> str:
    ignore_rules = get_ignore_rules()
    ignore_block = (
        f"\n\nTeacher's personal ignore rules — anything matching these is "
        f"low value; respect them when advising:\n{ignore_rules}"
        if ignore_rules else ""
    )
    return f"""You are Marimba, the teacher's focused assistant working through ONE task.
{TEACHER_PROFILE}
{ignore_block}

The teacher has opened a chat to solve the task below. Help them resolve it
quickly. Be direct, conversational, and short. Reply in the language the
teacher writes to you in (Spanish or English). Do not make up information
the task context does not provide. If you don't know something, say so and
ask the teacher.

TASK CONTEXT (read carefully — this is what we're solving):
{task_context}
""".strip()


# ── Chat call ─────────────────────────────────────────────────────────────────

async def call_task_chat(
    task_context: str,
    messages: List[Dict[str, str]],
) -> Optional[str]:
    """
    Run one turn of conversation.

    Args:
        task_context: A natural-language block describing the task (subject,
                      sender, full email body, etc.).
        messages: List of {"role": "user"|"assistant", "content": str},
                  ordered oldest-first.

    Returns:
        The assistant's reply text, or None if Mistral is not configured /
        errored. Caller handles the None gracefully.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None

    system_prompt = _build_system_prompt(task_context)
    chat_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ] + [{"role": m["role"], "content": m["content"]} for m in messages]

    try:
        client = Mistral(api_key=api_key)
        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=chat_messages,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[TaskChat] Mistral error: {type(e).__name__}: {e}")
        return None


# ── Email reply drafter ───────────────────────────────────────────────────────

async def draft_email_reply(
    *,
    original_subject: str,
    original_sender: str,
    original_body: str,
    chat_history: List[Dict[str, str]],
) -> Optional[Dict[str, str]]:
    """
    Produce a ready-to-send reply draft, informed by what the teacher and
    Marimba discussed in the chat. The model returns a JSON object with the
    suggested subject and body so we can show it in an editable preview.

    Subject defaults to "Re: <original>" if the model leaves it blank.
    Reply language matches the original email's language.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None

    ignore_rules = get_ignore_rules()
    ignore_block = (
        f"\n\nThe teacher's personal ignore rules (just for tone calibration; "
        f"not for filtering): {ignore_rules}"
        if ignore_rules else ""
    )

    system_prompt = f"""You are drafting an email reply on behalf of a teacher.
{TEACHER_PROFILE}
{ignore_block}

Write a reply to the email below, taking into account the chat conversation
the teacher had with Marimba — that conversation tells you the teacher's
intent and tone. Match the language of the ORIGINAL email (Spanish or
English). Be courteous, clear, and concise. Sign off as "Profe" (or in
English, "Best, [Teacher]") — keep it warm but professional.

ORIGINAL EMAIL:
From: {original_sender}
Subject: {original_subject}
Body:
{original_body}

Respond ONLY with a JSON object in this exact format:
{{"subject": "<suggested subject — Re: ... is fine>", "body": "<the full plain-text reply>"}}
""".strip()

    chat_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ] + [{"role": m["role"], "content": m["content"]} for m in chat_history]
    chat_messages.append({
        "role": "user",
        "content": "Draft the reply now based on our conversation.",
    })

    try:
        import json
        client = Mistral(api_key=api_key)
        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=chat_messages,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)
        subject = str(parsed.get("subject") or f"Re: {original_subject}")
        body = str(parsed.get("body") or "")
        if not body:
            return None
        return {"subject": subject, "body": body}
    except Exception as e:
        print(f"[TaskChat] Draft reply error: {type(e).__name__}: {e}")
        return None
