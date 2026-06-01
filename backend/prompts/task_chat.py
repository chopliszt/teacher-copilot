"""
Task Chat Prompt — Marimba's "chat to solve" mode.

Given a Top 3 task and a conversation history, Mistral acts as a focused
co-worker for that one task. It knows the teacher's profile, the task's
full context, and the teacher's ignore rules. Output is plain conversational
text — no JSON, no actions. Email-reply drafting is handled separately via
draft_email_reply() so the model has a tighter, single-purpose prompt for
the reply itself.
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from mistralai import Mistral

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_builder import TEACHER_PROFILE
from preferences import get_ignore_rules, get_personal_context


# ── Output formatting rules (shared across chat + draft) ──────────────────────

# ── Tools (Mistral function calling) ──────────────────────────────────────────
#
# Marimba can pull context from Gmail when the conversation needs it. The
# model decides when to call these; we execute and feed results back.
# Search scope is always the last 90 days — fast and covers the vast
# majority of "what did I say about X" cases.

TOOLS_SPEC: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_sent_emails",
            "description": (
                "Search the teacher's SENT Gmail from the last 90 days. Returns "
                "up to N matching messages with subject, recipient, date, and "
                "body. Use this when the teacher asks you to find something "
                "they've sent (e.g. 'find what I told parents about the trip')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Gmail free-text search (e.g. 'Microsoft visit', 'gira', 'reunion 8A').",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of results to return (1-10). Default 5.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_inbox",
            "description": (
                "Search the teacher's INBOX (received emails) from the last 90 "
                "days. Use when looking for messages the teacher has been sent — "
                "for example to summarize what a parent has asked previously."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_full_email",
            "description": (
                "Fetch the full body of one specific email by its id. Use this "
                "after a search if you need the complete content of a specific "
                "match (e.g. to copy logistics verbatim)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                },
                "required": ["message_id"],
            },
        },
    },
]


def _dispatch_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute one tool call. Returns a JSON-serializable dict that becomes the
    tool message content fed back to Mistral. Errors come back as
    {"error": "..."} so the model can recover gracefully (apologize, try
    a different query) instead of getting a 500.
    """
    try:
        from connectors.gmail import (
            search_sent_emails,
            search_inbox_emails,
            get_full_email,
        )

        if name == "search_sent_emails":
            limit = int(arguments.get("limit") or 5)
            results = search_sent_emails(str(arguments.get("query", "")), limit=limit)
            return {"results": results, "count": len(results)}

        if name == "search_inbox":
            limit = int(arguments.get("limit") or 5)
            results = search_inbox_emails(str(arguments.get("query", "")), limit=limit)
            return {"results": results, "count": len(results)}

        if name == "get_full_email":
            email = get_full_email(str(arguments.get("message_id", "")))
            if email is None:
                return {"error": "Email not found or Gmail not configured."}
            return email

        return {"error": f"Unknown tool: {name}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# Convenience type the API endpoint uses to summarize tool calls to the UI.
ToolCallSummary = Dict[str, Any]  # {"name": str, "args": {...}, "result_count": int|None, "error"?: str}


_FORMATTING_RULES = """
Output formatting rules:
- Match the language the teacher writes in (Spanish or English).
- Keep replies short and direct. The teacher has ADHD — long walls of text
  are noise. Use bullets only when listing multiple parallel items.
- You can use markdown (bold, italics, lists, tables) — the UI renders it.

- When you DRAFT AN EMAIL the teacher wants to send (a NEW email — a
  forward, a freeform message, sending the same content to a different
  address), wrap it in a fenced block tagged `email` with this EXACT
  structure (no extra prose inside the block):

    ```email
    To: someone@example.com
    Subject: <one-line subject>
    Body:
    <multi-line plain-text body, including the signoff>
    ```

  CRITICAL — email body MUST be PLAIN TEXT ONLY:
  - No **bold** or *italics* (asterisks will appear literally in the inbox)
  - No ### headers (hash symbols will appear literally)
  - No --- dividers
  - No bullet points with asterisks (*) — use a plain dash (-) if needed
  - Use CAPS sparingly for emphasis; use blank lines to separate sections
  Email clients do not render markdown. Write as you would in a real email.

  The UI parses this into an editable composer (To / Subject / Body
  fields + Send button + optional attachments). If you're not sure who
  it goes to, put a placeholder like `To: <fill in>` — the teacher will
  edit before sending.

  Use this format for NEW emails ONLY. For replying to the SAME email
  this task is about, tell the teacher to use the "Draft a reply" button
  instead (it threads into the original Gmail conversation).

- For OTHER copyable artifacts, use the matching fence tag — but do NOT
  use the To/Subject/Body structure:
    ```prompt   for a prompt to paste into another AI tool
    ```handout  for a handout
    ```draft    for a draft text (non-email)

- Plain conversational text MUST stay outside code fences.
""".strip()


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(
    task_context: str,
    schedule_block: str = "",
) -> str:
    ignore_rules = get_ignore_rules()
    personal_context = get_personal_context()

    personal_block = (
        f"\nABOUT THE TEACHER / HOW THEY LIKE TO WORK (always honour this when "
        f"producing slides, handouts, prompts, drafts):\n{personal_context}\n"
        if personal_context else ""
    )
    ignore_block = (
        f"\nIGNORE RULES — things the teacher treats as low value:\n{ignore_rules}\n"
        if ignore_rules else ""
    )
    schedule_section = f"\n{schedule_block}\n" if schedule_block else ""

    return f"""You are Marimba, the teacher's focused assistant working through ONE task.
{TEACHER_PROFILE}
{personal_block}{ignore_block}{schedule_section}
{_FORMATTING_RULES}

The teacher has opened a chat to solve the task below. Help them resolve it
quickly. Do not make up information the task context does not provide — if
you don't know something, say so and ask. When the teacher asks about
"today" (classes, meetings, etc.), use the SCHEDULE section above as the
source of truth — never guess from the task title alone.

TOOLS YOU CAN CALL (use them silently — don't ask permission first):
- search_sent_emails(query, limit=5): search the teacher's sent Gmail from
  the last 90 days. Use when the teacher asks you to find / reuse / adapt
  something they've already sent.
- search_inbox(query, limit=5): same scope for received emails.
- get_full_email(message_id): pull the complete body of one specific
  match after a search, when you need verbatim content.

HOW TO SEARCH WELL — this is the most common place you fail. Read carefully:

1. Gmail full-text search treats spaces as AND. Every word you include
   MUST appear in the email or it returns nothing. So broader = better.
   Start with ONE keyword. Add a second only if the first returns too many
   irrelevant matches. Examples:
     GOOD:  "Microsoft"           "gira"            "concurso"
     BAD:   "Microsoft visit May 25"  ← almost guaranteed to return 0

2. The school is in Costa Rica. Emails are typically in SPANISH or mixed
   Spanish/English. ALWAYS try Spanish keywords first or in parallel — do
   not wait for the teacher to remind you. Common Spanish keywords by
   topic:
     trips / excursions  → "gira", "visita", "salida", "viaje", "excursión"
     events / workshops  → "evento", "actividad", "taller", "concurso"
     meetings            → "reunión", "junta", "convocatoria"
     announcements       → "anuncio", "comunicado", "circular"
   For English-named brands (Microsoft, Google, etc.), use the brand name
   directly — it's the same in both languages.

3. NEVER include a raw date (e.g. "May 25", "25 de mayo", "2026") in the
   query. Dates rarely appear verbatim in subjects/bodies, and the 90-day
   scope is already applied automatically. Search by topic, not date.

4. If a search returns 0 matches: BROADEN by removing words. Don't add
   "OR" alternatives — that often makes things worse. Drop adjectives,
   try the most distinctive keyword alone.

5. If a search returns matches: look at them carefully before deciding
   they're irrelevant. Use get_full_email if a subject looks promising
   but the snippet is unclear. Never tell the teacher "nothing was found"
   when the tool returned matches — at minimum, list what you saw.

6. After tool calls: synthesize, don't dump raw JSON. Mention which
   email you're drawing on ("based on your email from May 3 to parents…")
   so the teacher can verify.

FIRST-TURN OPENER (when the teacher just opened the drawer and there
are no prior messages, your reply IS the opener — match the rules below):

If TASK CONTEXT starts with "Type: incoming email" → skip this section.
The reply draft is handled by a separate "Draft a reply" button; just
greet briefly and offer to help refine.

Otherwise, look at the Title. Decide which case it falls into:

  A) COMMUNICATION TO A PERSON — verbs like enviar, escribir, mandar,
     responder, contestar, avisar, comunicar, send, write, email, reply,
     message, AND a target audience (padres, parent, director, colega,
     maestro, profe, alumno, estudiante, etc.):
     → Open with a SHORT intro line ("Te dejo un borrador, ajustalo:")
       followed by an ```email``` fenced block. To: <fill in> if you
       don't know the address. Subject: concrete and short. Body:
       plain-text, warm but professional, signed off as Profe. The UI
       turns the block into an editable composer the teacher can send
       directly from chat.

  B) NON-EMAIL WRITING — drafting a prompt, handout, message that
     isn't an email (e.g. "redactar prompt para ChatGPT", "preparar
     reflexión para alumno", "crear plantilla de…"):
     → Open with a short intro and the appropriate fenced block:
       ```prompt for a prompt to paste into another AI tool,
       ```handout for a student handout,
       ```draft  for any other copyable text.

  C) VAGUE OR NON-WRITING TASK — anything else ("revisar planilla",
     "hablar con X", "buscar material", etc.):
     → Don't draft anything. Open with ONE concrete clarifying question
       that helps the teacher decide what to do next ("¿Lo querés hacer
       hoy o pasarlo al jueves?", "¿Qué decisión necesitás antes de
       hablar con ella?").

CRITICAL ANTI-FABRICATION RULE (applies to A and B):
Before drafting, check: does the Title actually give you the FACTS
you'd need to write meaningful content? Specifically:
  - For a "reflexión" or behaviour message: what did the student DO?
    What's the specific situation?
  - For a request/announcement: what's the request, the date, the ask?
  - For any communication: what are the 2-3 things the reader needs
    to know?

If the Title names a person or situation but gives NO FACTS (e.g.
"Enviar reflexión a Daniel 7A1", "Escribir nota a padres de María",
"Avisar al director sobre la salida"), DO NOT INVENT details to fill
the body. Do not assume the student did well, did poorly, did anything
specific — you have zero evidence.

→ Fall through to case C: ask ONE short, concrete question that
  surfaces the missing facts. Example openers:
    "Antes de redactar: ¿qué pasó con Daniel y qué querés que sepan
     los padres / Maria? Con eso te armo el borrador."
    "¿Qué necesitás avisar al director y cuándo es la salida?"

Once the teacher answers with the facts, draft in the next turn.
Inventing content erodes the teacher's trust in your drafts — better
one extra turn than a hallucinated email they have to rewrite.

Also CRITICAL — never emit an empty/placeholder draft just to fill
space. If you're unsure which case applies, fall back to case C and
ASK.

TASK CONTEXT (read carefully — this is what we're solving):
{task_context}
""".strip()


# ── Chat call ─────────────────────────────────────────────────────────────────

MAX_TOOL_ITERATIONS = 3  # safety net so a buggy model can't loop forever


async def call_task_chat(
    task_context: str,
    messages: List[Dict[str, str]],
    schedule_block: str = "",
) -> Tuple[Optional[str], List[ToolCallSummary]]:
    """
    Run one turn of conversation, possibly with tool calls.

    Marimba can call Gmail search tools to pull context she doesn't already
    have (e.g. "find what I told parents about the trip"). We execute each
    tool call, append the result back into the conversation, and re-ask
    Mistral for the next step. Capped at MAX_TOOL_ITERATIONS so a buggy or
    confused model can't infinite-loop.

    Args:
        task_context: A natural-language block describing the task (subject,
                      sender, full email body, etc.).
        messages: List of {"role": "user"|"assistant", "content": str},
                  ordered oldest-first.
        schedule_block: Today's schedule + meetings + disruptions, so the
                        chat doesn't contradict the UI when asked "what class
                        is at 11:30?".

    Returns:
        (reply, tool_calls_summary):
          - reply: the assistant's final text, or None on error / no API key
          - tool_calls_summary: list of {"name", "args", "result_count"|"error"}
            describing every tool Marimba called this turn. Empty list if she
            answered directly. The UI uses this to render "Searched sent
            emails — 2 matches" style chips above the message.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None, []

    system_prompt = _build_system_prompt(task_context, schedule_block=schedule_block)
    chat_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ] + [{"role": m["role"], "content": m["content"]} for m in messages]

    # First-turn nudge — synthetic user message that gives Mistral a clear
    # "respond now" signal and points it at the opener guidance. Without
    # this, a system-only conversation often returns empty or boilerplate.
    # Skipped for email-source tasks because the dedicated Draft-a-reply
    # button handles their opener.
    if not messages and not task_context.startswith("Type: incoming email"):
        chat_messages.append({
            "role": "user",
            "content": (
                "(Sistema: el profe acaba de abrir el chat para esta tarea. "
                "Aplicá la sección FIRST-TURN OPENER del system prompt: "
                "proponé un borrador concreto si la tarea lo amerita, o "
                "hacé una pregunta corta si es vaga. No respondas con un "
                "saludo genérico.)"
            ),
        })

    tool_summary: List[ToolCallSummary] = []

    try:
        client = Mistral(api_key=api_key)

        for _ in range(MAX_TOOL_ITERATIONS + 1):
            response = await client.chat.complete_async(
                model="mistral-large-latest",
                messages=chat_messages,
                tools=TOOLS_SPEC,
                tool_choice="auto",
            )
            msg = response.choices[0].message

            tool_calls = getattr(msg, "tool_calls", None) or []
            if not tool_calls:
                # Final answer — return whatever text we got.
                return (getattr(msg, "content", None) or ""), tool_summary

            if len(tool_summary) >= MAX_TOOL_ITERATIONS:
                # We've exhausted the loop — force a text answer next time
                # by stripping tools. Append a synthetic note so the model
                # doesn't try to call again.
                chat_messages.append({
                    "role": "user",
                    "content": (
                        "You've already used the tool budget for this turn. "
                        "Please answer with what you have."
                    ),
                })
                final = await client.chat.complete_async(
                    model="mistral-large-latest",
                    messages=chat_messages,
                )
                return (final.choices[0].message.content or ""), tool_summary

            # Append the assistant's tool-call message so Mistral keeps state.
            # The SDK returns these as objects; we re-serialize a minimal dict.
            chat_messages.append({
                "role": "assistant",
                "content": getattr(msg, "content", None) or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            })

            # Execute each tool, feed results back as tool messages.
            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                result = _dispatch_tool(tc.function.name, args)
                summary: ToolCallSummary = {
                    "name": tc.function.name,
                    "args": args,
                }
                if isinstance(result, dict) and "error" in result:
                    summary["error"] = str(result["error"])
                    print(f"[TaskChat tool] {tc.function.name}({args}) → ERROR: {result['error']}")
                else:
                    count: Optional[int] = None
                    matches_preview: List[Dict[str, str]] = []
                    if isinstance(result, dict) and "count" in result:
                        count = result.get("count")
                        for r in (result.get("results") or [])[:5]:
                            matches_preview.append({
                                "id": str(r.get("id", "")),
                                "subject": str(r.get("subject", ""))[:120],
                                "from": str(r.get("from", ""))[:120],
                                "date": str(r.get("date", ""))[:25],
                            })
                    summary["result_count"] = count
                    if matches_preview:
                        summary["matches"] = matches_preview
                    # Backend log so we can debug from the terminal when a
                    # search behaves unexpectedly. Subjects only — bodies
                    # would flood the log.
                    log_subjects = ", ".join(
                        f'"{m["subject"]}"' for m in matches_preview
                    ) or "(none)"
                    print(
                        f"[TaskChat tool] {tc.function.name}({args}) → "
                        f"{count} match(es): {log_subjects}"
                    )
                tool_summary.append(summary)
                chat_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        # Loop fell through without a final text answer — shouldn't happen
        # but guard anyway.
        return (
            "I had trouble pulling the information together. Could you rephrase?",
            tool_summary,
        )

    except Exception as e:
        print(f"[TaskChat] Mistral error: {type(e).__name__}: {e}")
        return None, tool_summary


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
    personal_context = get_personal_context()
    personal_block = (
        f"\n\nABOUT THE TEACHER / HOW THEY LIKE TO WRITE:\n{personal_context}"
        if personal_context else ""
    )
    ignore_block = (
        f"\n\nThe teacher's personal ignore rules (just for tone calibration; "
        f"not for filtering): {ignore_rules}"
        if ignore_rules else ""
    )

    system_prompt = f"""You are drafting an email reply on behalf of a teacher.
{TEACHER_PROFILE}
{personal_block}{ignore_block}

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

CRITICAL: The body field must be PLAIN TEXT ONLY — no **bold**, no *italics*,
no ### headers, no --- dividers, no asterisk bullets. Email clients do not
render markdown; those characters will show up literally in the inbox.
Use blank lines to separate paragraphs, plain dashes (-) for lists, and CAPS
sparingly for emphasis.

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
