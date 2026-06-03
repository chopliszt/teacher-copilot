"""
Lesson Plan Prompt — Marimba's "plan lesson" drawer.

One entry point: `call_lesson_plan_chat()`. It handles three flows
based on the conversation state:

1. WARM FIRST TURN (history exists): propose 3 distinct lesson approaches,
   each <100 words, on different pedagogical axes. End with "¿Cuál te gusta?"

2. COLD FIRST TURN (no class_sessions, no lesson_plans for this group):
   open Socratically — ask the teacher what happened last class OR what
   they have in mind, since a proposal in the dark would be noise.

3. REFINEMENT TURNS: the teacher picked an option / proposed their own.
   Marimba elaborates it into a full timed plan wrapped in a ```lesson
   fenced block, which the frontend renders as a copyable artifact.

A separate helper, `call_assignment_description()`, takes a finalized
plan and produces a ```assignment block (one-line title, learning
objective, deliverable, evaluation criteria, due date) for the teacher
to paste into Toddle.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mistralai.client import Mistral

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_builder import TEACHER_PROFILE
from preferences import get_ignore_rules, get_personal_context
from student_flags import format_flags_block


# ── Tools (Mistral function calling) ──────────────────────────────────────────
#
# Marimba has exactly ONE tool in the lesson-plan drawer: writing a past class
# session to the DB. The teacher tells her what they did last class, she
# confirms ("¿lo guardo?"), and on yes she calls log_class_session — the same
# write path the manual "Log this session" button on the briefing card uses.
# This closes the loop the teacher hit before, where Marimba seemed smart
# enough to remember the conversation but couldn't actually persist anything.

TOOLS_SPEC: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "log_class_session",
            "description": (
                "Persist what happened in a past class to the teacher's history "
                "(class_sessions table). Use this AFTER you have confirmed with "
                "the teacher (e.g. they said 'sí guardalo' or 'log it'). The "
                "tool writes one record keyed by (group, date) — calling it "
                "twice for the same date overwrites the previous note. Returns "
                "{saved: true} on success or {error: '...'} otherwise."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "group": {
                        "type": "string",
                        "description": "Class group exactly as it appears in the schedule (e.g. '10A2', '8A1', '7B').",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date of the class being logged, in YYYY-MM-DD. If the teacher didn't specify, ask before calling — never guess.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "What happened — what was taught, what students engaged with, anything noteworthy.",
                    },
                    "what_worked": {
                        "type": "string",
                        "description": "Optional. What specifically worked well — feeds future lesson-plan suggestions.",
                    },
                },
                "required": ["group", "date", "notes"],
            },
        },
    },
]


def _dispatch_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute one tool call. Sync — opens a fresh DB session so we don't have
    to thread the request's session through the async tool loop. Returns a
    dict that becomes the tool message content fed back to Mistral.
    """
    if name != "log_class_session":
        return {"error": f"Unknown tool: {name}"}

    group = str(arguments.get("group", "")).strip()
    date = str(arguments.get("date", "")).strip()
    notes = str(arguments.get("notes", "")).strip()
    what_worked = arguments.get("what_worked")
    what_worked = str(what_worked).strip() if what_worked else None

    if not group or not date or not notes:
        return {"error": "group, date, and notes are all required"}

    try:
        from database import SessionLocal, ClassSessionRecord
        from schedule_day import get_current_schedule_day
    except Exception as e:
        return {"error": f"could not load DB: {type(e).__name__}: {e}"}

    db = SessionLocal()
    try:
        sday = get_current_schedule_day()
        record_id = f"{group}_{date}_{sday}"
        now_str = datetime.now(timezone.utc).isoformat()

        existing = db.get(ClassSessionRecord, record_id)
        if existing:
            existing.notes = notes
            existing.what_worked = what_worked
            existing.created_at = now_str
        else:
            db.add(
                ClassSessionRecord(
                    id=record_id,
                    group=group,
                    schedule_day=sday,
                    date=date,
                    notes=notes,
                    what_worked=what_worked,
                    created_at=now_str,
                )
            )
        db.commit()
        return {"saved": True, "id": record_id, "group": group, "date": date}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        db.close()


# A summary the API echoes back to the frontend so the UI can show a small
# "Marimba just logged your last 10A2 session" chip above the message.
ToolCallSummary = Dict[str, Any]
MAX_TOOL_ITERATIONS = 2


# ── Shared formatting rules for both flows ────────────────────────────────────

_FORMATTING_RULES = """
Output formatting rules:
- Always respond in the language the teacher writes in (Spanish or English).
  Default to Spanish — the teacher is at a bilingual school in Costa Rica.
- Keep prose short and direct. The teacher has ADHD — no walls of text.
- When you write a FULL TIMED PLAN, wrap it in a fenced block tagged `lesson`
  with bullet items in this shape (the UI renders it as a copyable artifact):

    ```lesson
    Grupo: 8A1 — Digital Design (80 min)

    0–10  · Repaso breve de la última clase
    10–30 · Introducción al tema X
    30–55 · Actividad guiada
    55–75 · Trabajo en parejas + feedback
    75–80 · Cierre / próxima tarea

    Diferenciación: [si aplica, mencionar accommodations específicas
    por estudiante usando los flags del grupo]

    Próxima tarea / tarea de cierre: [opcional]
    ```

- Three-option proposals are NOT wrapped in a code block — they are plain
  prose so the teacher can read them at a glance.
- Plain conversational text stays outside code fences.
""".strip()


def _build_system_prompt(group: str, context_block: str, has_history: bool) -> str:
    personal_context = get_personal_context()
    ignore_rules = get_ignore_rules()

    personal_section = (
        f"\nABOUT THE TEACHER / HOW THEY LIKE TO WORK:\n{personal_context}\n"
        if personal_context else ""
    )
    ignore_section = (
        f"\nIGNORE RULES (low-priority topics the teacher doesn't want to dwell on):\n{ignore_rules}\n"
        if ignore_rules else ""
    )

    if has_history:
        flow_instructions = f"""
ON YOUR VERY FIRST TURN of this conversation:
Propose THREE distinct lesson approaches for today's class with {group}.

Constraints for the proposals:
- Each one MUST take a different pedagogical angle (e.g. hands-on/making vs.
  analysis/theory-led vs. peer-driven; structured vs. exploratory; whole-class
  vs. 1-on-1 differentiation focus). Three flavours of the same idea = wrong.
- Each one builds naturally on the last session (see CONTEXT below).
- Each one MUST address the flagged students (see STUDENT FLAGS) appropriately.
- Each one MUST be under 100 words.
- Give each a short, evocative title in bold (2–3 words).
- Number them 1, 2, 3.

After the three options, end with exactly:
    "¿Cuál te gusta más, o querés proponer otra dirección?"

DO NOT wrap the proposals in a code block. Plain markdown with bold titles
is what the UI expects.

ON LATER TURNS — once the teacher picks an option (e.g. "2", "option 1 pero
más corto") or proposes their own direction:
- Elaborate the chosen direction into a FULL TIMED PLAN.
- Wrap the timed plan in a ```lesson fenced block per the formatting rules.
- After the block, briefly explain (1–2 sentences) why the structure works
  for THIS group on THIS day — referencing what worked last time, the unit,
  or specific flagged students.
- If the teacher asks for changes ("agregá 10 min de feedback"), update the
  ```lesson block — produce the FULL revised plan, not a diff.
""".strip()
    else:
        flow_instructions = f"""
COLD START — there is no recorded history for {group} yet (no past sessions,
no past lesson plans). Proposing options in the dark would be a waste of
the teacher's time.

ON YOUR VERY FIRST TURN, open Socratically. Ask the teacher one short
question that leaves both doors open:

  "Aún no tengo historial de {group}. Para que la propuesta valga la pena,
  contame una de dos cosas:
  1. ¿Qué hicieron la última clase? (con eso te propongo 3 enfoques)
  2. ¿Ya tenés algo en mente para hoy? (te ayudo a aterrizarlo)"

Then wait for the teacher's reply.

ON THE TEACHER'S REPLY:
- If they describe what happened last class → propose 3 distinct options
  per the warm-start rules. At the end of that turn add a single line:
  "¿Querés guardar lo de la última clase con el botón \"Log this session\"
  del briefing? Así lo recuerdo para la próxima."
- If they describe a half-formed idea → DO NOT propose 3 options. Go
  Socratic: ask 1–2 clarifying questions (objetivo, tiempo, evaluación),
  then propose a SINGLE elaborated plan in a ```lesson block.
""".strip()

    return f"""You are Marimba, the teacher's lesson-planning collaborator.
{TEACHER_PROFILE}
{personal_section}{ignore_section}
{context_block}

{flow_instructions}

GUIDING PRINCIPLES (apply on every turn):
- You PROPOSE — the teacher decides. Frame outputs as "propuesta", never
  as "the plan". The teacher is the master.
- Reference specific evidence from the context when you can ("Como en la
  última clase terminaron los mood boards, hoy es buen momento para…").
- If a flagged student needs accommodation, mention it concretely — not
  generically ("apartá 2 min al inicio con Sofía sobre las tareas
  atrasadas" beats "considerá differentiation").
- Avoid pedagogical jargon. Speak like a colleague, not a textbook.
- Keep proposals concrete and time-bound. No fluff like "promover el
  pensamiento crítico" without saying HOW in this class.

YOUR ONE WRITE TOOL — log_class_session:
You have exactly one tool that can write to storage: `log_class_session`.
It saves what happened in a past class to the teacher's history
(class_sessions table), keyed by (group, date).

WHEN to use it:
  - The teacher describes what they did in a past class, with enough
    detail to be useful (at least a sentence about what happened).

HOW to use it — ALWAYS confirm first:
  1. Restate what you understood briefly: "Entonces el viernes en {group}
     terminaron mood boards, Sofía no participó mucho — ¿lo guardo así?"
  2. Wait for an explicit yes ("sí", "guardalo", "log it", "dale").
  3. Then call log_class_session with the structured fields.
  4. After the tool returns, confirm in ONE short line:
     "✓ Listo, lo guardé. Ahora ¿pensamos en hoy?"
  5. If the date is unclear, ASK — never guess a date.

WHAT YOU CAN'T DO:
  - You CAN'T save lesson plans — that's what the teacher's "Save plan"
    button in this drawer is for.
  - You CAN'T save anything other than class_sessions via this tool.
  - You CAN'T remember conversations across drawer sessions; only the
    rows saved via tools or buttons persist.

Don't promise anything beyond log_class_session. If a teacher asks
you to "save the plan" or "remember to do X next week", redirect:
"La propuesta de hoy se guarda con el botón 'Save plan' ahí abajo —
no la puedo guardar yo."

{_FORMATTING_RULES}
""".strip()


# ── Chat call ─────────────────────────────────────────────────────────────────

async def call_lesson_plan_chat(
    group: str,
    messages: List[Dict[str, str]],
    context_block: str,
    has_history: bool,
) -> tuple[Optional[str], List[ToolCallSummary]]:
    """
    One conversational turn. Returns (reply_text, tool_calls_summary).
    tool_calls_summary is a list — usually empty, occasionally one entry
    when Marimba logged a class session this turn. The frontend can render
    a small "✓ Marimba logged your 10A2 session (May 21)" chip from it.

    Args:
        group: e.g. "8A1"
        messages: ordered chat history [{role: 'user'|'assistant', content: str}]
                  Empty list = first turn → Marimba opens.
        context_block: pre-built natural-language block with last sessions,
                       unit, schedule slot, student flags, recent plans.
        has_history: True if class_sessions OR lesson_plans exist for `group`.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None, []

    system_prompt = _build_system_prompt(group, context_block, has_history)

    chat_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ] + [{"role": m["role"], "content": m["content"]} for m in messages]

    # If this is the first turn, nudge the model to actually open the
    # conversation rather than waiting for a user message.
    if not messages:
        chat_messages.append({
            "role": "user",
            "content": (
                "(Sistema: el profe acaba de abrir el drawer para planificar "
                f"la clase de {group}. Iniciá vos la conversación según las "
                "reglas de tu prompt — sin saludo largo.)"
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
                return (getattr(msg, "content", None) or ""), tool_summary

            if len(tool_summary) >= MAX_TOOL_ITERATIONS:
                # Bound the loop — force a text answer next time around.
                chat_messages.append({
                    "role": "user",
                    "content": (
                        "Ya usaste el budget de herramientas para este turno. "
                        "Cerrá con texto ahora."
                    ),
                })
                final = await client.chat.complete_async(
                    model="mistral-large-latest",
                    messages=chat_messages,
                )
                return (final.choices[0].message.content or ""), tool_summary

            # Append the assistant's tool-call message so the next turn keeps
            # the trail intact.
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

            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                result = _dispatch_tool(tc.function.name, args)
                summary: ToolCallSummary = {"name": tc.function.name, "args": args}
                if isinstance(result, dict) and result.get("error"):
                    summary["error"] = str(result["error"])
                else:
                    summary["saved"] = bool(result.get("saved"))
                    summary["group"] = result.get("group")
                    summary["date"] = result.get("date")
                tool_summary.append(summary)
                print(
                    f"[LessonPlan tool] {tc.function.name}({args}) → {result}"
                )
                chat_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return (
            "Tuve un problema procesando esto. Probá de nuevo en un momento.",
            tool_summary,
        )
    except Exception as e:
        print(f"[LessonPlan] Mistral error: {type(e).__name__}: {e}")
        return None, tool_summary


# ── Assignment description generator ──────────────────────────────────────────

async def call_assignment_description(
    plan_text: str,
    group: str,
    context_block: str,
) -> Optional[str]:
    """
    Generate a copyable assignment description tied to the lesson plan,
    formatted as a ```assignment fenced block ready for Toddle.

    Returns the full assistant reply (the ```assignment block + a short
    explanatory line). None on error.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None

    personal_context = get_personal_context()
    personal_section = (
        f"\nABOUT THE TEACHER:\n{personal_context}\n"
        if personal_context else ""
    )

    system_prompt = f"""You are Marimba, generating a concise, Toddle-ready
assignment description that ties to today's lesson plan for {group}.
{TEACHER_PROFILE}
{personal_section}
{context_block}

LESSON PLAN (already agreed with the teacher):
{plan_text}

Produce a single ```assignment fenced block with this exact structure
(plain text inside — NO markdown formatting like **bold** or ### headers):

    ```assignment
    Título: <one-line title>
    Objetivo de aprendizaje: <one sentence — what students will be able to do>
    Entregable: <what students hand in>
    Criterios de evaluación: <2–4 short bullets, each on its own line,
      starting with a plain dash "- ">
    Fecha de entrega: <when, or "fin de clase" if in-class>
    Tipo: formativa | sumativa
    ```

After the block, add ONE short sentence explaining why this format works
for this lesson (e.g. "Es formativa porque…" or "Es sumativa porque…").

Match the language of the lesson plan above (Spanish if it's Spanish).
""".strip()

    try:
        client = Mistral(api_key=api_key)
        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Generá la descripción del entregable."},
            ],
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        print(f"[LessonPlan/Assignment] Mistral error: {type(e).__name__}: {e}")
        return None


# ── Context formatting helper ────────────────────────────────────────────────

def format_lesson_context(
    *,
    group: str,
    subject: str,
    duration_min: int,
    time_label: str,
    last_sessions: List[Dict[str, str]],
    recent_plans: List[Dict[str, str]],
) -> str:
    """
    Assemble the natural-language context block fed to the system prompt.
    `last_sessions` and `recent_plans` are short dicts pulled from the DB.
    Student flags are loaded from the JSON file via student_flags helper.
    """
    flags_block = format_flags_block(group)

    sessions_lines: List[str] = []
    for s in last_sessions:
        notes = (s.get("notes") or "").strip()
        worked = (s.get("what_worked") or "").strip()
        date = s.get("date", "")
        line = f"  - {date}: {notes}"
        if worked:
            line += f" (lo que funcionó: {worked})"
        sessions_lines.append(line)
    sessions_section = (
        "RECENT SESSIONS (most recent first):\n" + "\n".join(sessions_lines)
        if sessions_lines else "RECENT SESSIONS: (none recorded)"
    )

    plans_lines: List[str] = []
    for p in recent_plans:
        date = p.get("date", "")
        # Include the full plan text — Marimba needs to be able to reference
        # what she proposed before ("Last time we agreed on X, want to build
        # on that or pivot?"). A 140-char preview is too thin for that.
        plan_text = (p.get("plan_text") or "").strip()
        plans_lines.append(f"  --- {date} ---\n{plan_text}")
    plans_section = (
        "RECENT LESSON PLANS (most recent first):\n" + "\n\n".join(plans_lines)
        if plans_lines else "RECENT LESSON PLANS: (none saved yet)"
    )

    parts = [
        f"PLANNING CONTEXT FOR {group}:",
        f"  - Subject: {subject}",
        f"  - Today's slot: {time_label} ({duration_min} min)",
        "",
        sessions_section,
        "",
        plans_section,
    ]
    if flags_block:
        parts.extend(["", flags_block])

    return "\n".join(parts)
