#!/usr/bin/env python3
"""
Voice Evals — Automated accuracy tests for Marimba's voice pipeline.

Sends realistic teacher phrases through the EXACT context + prompt used in
production, then checks two things:
  1. Action accuracy — does the returned JSON action match expectations?
  2. Fact accuracy   — does the SPOKEN reply state correct schedule facts?

Why this matters: a previous version of these evals built context with
``build_context`` (the priority prompt's full block) while production voice
actually used a stripped, today-only context. The eval was green while
production hallucinated — e.g. telling the teacher 7B met at 10:50am when it
really meets at 11:30am. To prevent that class of false-green, these evals now
call the SAME ``_build_voice_context`` the ``/api/voice`` endpoint uses, fed
the SAME real ``data/teacher_schedule.json``, with "today" pinned so tomorrow
is the day under test.

Usage:
    python -m tests.evals.run_voice_evals          # run all evals
    python -m tests.evals.run_voice_evals --verbose # show full Mistral responses
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Ensure backend module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Load .env so MISTRAL_API_KEY is available outside of FastAPI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

import context_builder
import main
from prompts.voice import call_voice_mistral

# ── Pin "today" so evals are deterministic ────────────────────────────────────
#
# We pin the rolling schedule day to 3, which makes the NEXT class day = Day 4.
# Day 4 is where 7B lives (11:30am–12:50pm) — the exact case the teacher hit.
# ``format_schedule_block`` reads ``get_current_schedule_day`` from BOTH the
# ``main`` and ``context_builder`` namespaces, plus ``main._get_current_time``,
# so we override all three to freeze the rotation.

PINNED_SCHEDULE_DAY = 3
PINNED_NOW = datetime(2026, 6, 2, 9, 0)  # Tuesday → tomorrow (Wed) is Day 4

main.get_current_schedule_day = lambda: PINNED_SCHEDULE_DAY
context_builder.get_current_schedule_day = lambda: PINNED_SCHEDULE_DAY
main._get_current_time = lambda: PINNED_NOW

# Use the REAL production schedule, not a fixture — so these evals catch real
# regressions in data/teacher_schedule.json the moment they appear.
with open(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "teacher_schedule.json"),
    encoding="utf-8",
) as _f:
    EVAL_SCHEDULE = json.load(_f)

EVAL_TASKS = [
    {"id": "task_design_cat_1", "title": "Design Cat 1 registration", "priority": "high"},
    {"id": "task_grade_projects", "title": "Grade 10A1 final projects", "priority": "medium"},
    {"id": "task_parent_meeting", "title": "Parent meeting about 8A1 student", "priority": "high"},
]

# Every group the teacher teaches — so the context lists which classes have NO
# session logged. With session_notes=None below, ALL of them are unlogged, which
# lets us assert Marimba admits "no record" instead of inventing a lesson.
ALL_GROUPS = list(dict.fromkeys(
    [(EVAL_SCHEDULE.get("homeroom") or {}).get("group")]
    + [p["group"] for d in EVAL_SCHEDULE.get("classes", []) for p in d.get("periods", [])]
))
ALL_GROUPS = [g for g in ALL_GROUPS if g]

# THE key line: build context through the production code path, not a parallel
# one. If _build_voice_context ever stops injecting the full schedule again,
# these fact evals go red.
EVAL_CONTEXT = main._build_voice_context(
    schedule_data=EVAL_SCHEDULE,
    all_tasks=EVAL_TASKS,
    weekly_data=None,
    session_notes=None,        # nothing logged → every class is "no record"
    all_groups=ALL_GROUPS,
)


# ── Test cases ────────────────────────────────────────────────────────────────
#
# Each case is a dict with:
#   - phrase: what the teacher says
#   - expected_action_type: the action.type we expect (or None for no action)
#   - expected_fields: optional dict of fields that must match in the action
#   - response_contains: substrings that MUST all appear in the spoken reply
#   - response_excludes: substrings that must NOT appear in the spoken reply
#   - description: human-readable explanation of the test

EVAL_CASES: list[dict] = [
    # ── open_class ────────────────────────────────────────────────────────
    {
        "phrase": "Can you open 9A1?",
        "expected_action_type": "open_class",
        "expected_fields": {"group": "9A1"},
        "description": "Direct request to open a class by group name",
    },
    {
        "phrase": "Show me 5B2",
        "expected_action_type": "open_class",
        "expected_fields": {"group": "5B2"},
        "description": "Shorthand request to open a class",
    },
    {
        "phrase": "Can you open my first class of today?",
        "expected_action_type": "open_class",
        "expected_fields": {"group": "9A2"},
        "description": "Relative reference — first class today (Day 3) is 9A2",
    },
    # ── add_task ──────────────────────────────────────────────────────────
    {
        "phrase": "Add task: grade 10A1 submissions",
        "expected_action_type": "add_task",
        "description": "Explicit add_task command",
    },
    {
        "phrase": "Remind me to print worksheets for 5B2",
        "expected_action_type": "add_task",
        "description": "Implicit task creation via 'remind me'",
    },
    # ── open_priority ─────────────────────────────────────────────────────
    {
        "phrase": "Open my top priority",
        "expected_action_type": "open_priority",
        "description": "Request to open the first priority card",
    },
    # ── close_all ─────────────────────────────────────────────────────────
    {
        "phrase": "Close everything",
        "expected_action_type": "close_all",
        "description": "Direct close_all command",
    },
    {
        "phrase": "Tidy up the workspace please",
        "expected_action_type": "close_all",
        "description": "Indirect close_all using 'tidy up'",
    },
    # ── Tier-A actions ────────────────────────────────────────────────────
    {
        "phrase": "Mark the Design Cat 1 registration task as done",
        "expected_action_type": "complete_task",
        "expected_fields": {"id": "task_design_cat_1"},
        "description": "Complete a named task — must echo its exact bracketed id",
    },
    {
        "phrase": "Show me tomorrow's schedule",
        "expected_action_type": "view_schedule_day",
        "expected_fields": {"offset": 1},
        "description": "Navigate the schedule view to tomorrow (offset +1)",
    },
    {
        "phrase": "Help me plan the lesson for 7B",
        "expected_action_type": "open_lesson_plan",
        "expected_fields": {"group": "7B"},
        "description": "Open the lesson-plan drawer for a group",
    },
    {
        "phrase": "Log 9A1: we finished the logo project and the pair work went well",
        "expected_action_type": "log_session",
        "expected_fields": {"group": "9A1"},
        "description": "Record a class session note for a group (explicit 'log')",
    },
    {
        "phrase": "In 7B today we visited the Microsoft headquarters and it went really well",
        "expected_action_type": "log_session",
        "expected_fields": {"group": "7B"},
        "description": "Narrated lesson with NO 'log' keyword must still fire log_session",
    },
    # ── No action (just conversation) ─────────────────────────────────────
    {
        "phrase": "Good morning Marimba",
        "expected_action_type": None,
        "description": "Greeting — no action should be triggered",
    },
    {
        "phrase": "What is the capital of France?",
        "expected_action_type": None,
        "description": "Off-topic question — definitely no UI action",
    },
    # ── FACT ACCURACY — the regression class these evals were blind to ────
    # These assert the SPOKEN reply, not just the action. They would have
    # caught the "7B at 10:50am" hallucination.
    {
        "phrase": "When is my next class with 7B?",
        "expected_action_type": None,
        "response_contains": ["11:30"],
        "response_excludes": ["10:50"],
        "description": "7B (Day 4) meets at 11:30am — must NOT say 10:50am",
    },
    {
        "phrase": "What time do I have 7B tomorrow?",
        "expected_action_type": None,
        "response_contains": ["11:30"],
        "response_excludes": ["10:50"],
        "description": "Tomorrow (Day 4) 7B is 11:30am — direct time question",
    },
    {
        "phrase": "Which groups do I teach tomorrow?",
        "expected_action_type": None,
        "response_contains": ["10A1", "6B2", "7B"],
        "description": "Tomorrow = Day 4: 10A1, 6B2, 7B (homeroom 9A2 optional)",
    },
    {
        "phrase": "What time is my last class today?",
        "expected_action_type": None,
        "response_contains": ["10:10"],
        "response_excludes": ["11:30am - 12:50pm"],
        "description": "Today = Day 3, last class is 8A1 at 10:10am",
    },
    {
        "phrase": "Do I have homeroom tomorrow?",
        "expected_action_type": None,
        "response_contains": ["7:30"],
        "description": "Day 4 has homeroom 9A2 at 7:30am — must confirm with time",
    },
    # ── Honesty about missing data (the 7B/Figma hallucination) ───────────
    {
        "phrase": "What did I do in my last class with 7B?",
        "expected_action_type": None,
        "response_contains_any": [
            "no record", "haven't logged", "don't have", "nothing logged",
            "no session", "not logged", "haven't got", "no log",
        ],
        "description": "No 7B session is logged — must admit it, never invent a lesson",
    },
]


# ── Runner ────────────────────────────────────────────────────────────────────


class EvalResult:
    """Result of a single eval case."""

    def __init__(
        self,
        case: dict,
        actual_action_type: str | None,
        actual_action: dict | None,
        response_text: str,
        raw_json: str,
        passed: bool,
        failure_reason: str = "",
    ):
        self.case = case
        self.actual_action_type = actual_action_type
        self.actual_action = actual_action
        self.response_text = response_text
        self.raw_json = raw_json
        self.passed = passed
        self.failure_reason = failure_reason


async def run_single_eval(case: dict) -> EvalResult:
    """Run a single eval case against the live Mistral API."""
    result = await call_voice_mistral(
        transcript=case["phrase"],
        context=EVAL_CONTEXT,
    )

    if result is None:
        return EvalResult(
            case=case,
            actual_action_type=None,
            actual_action=None,
            response_text="",
            raw_json="(no response from Mistral)",
            passed=False,
            failure_reason="Mistral returned None — check API key",
        )

    action = result.get("action")
    response_text = result.get("response", "") or ""
    raw_json = result.get("raw_json", "{}")
    actual_type = action.get("type") if action else None

    def fail(reason: str) -> EvalResult:
        return EvalResult(
            case=case,
            actual_action_type=actual_type,
            actual_action=action,
            response_text=response_text,
            raw_json=raw_json,
            passed=False,
            failure_reason=reason,
        )

    # 1. Action type
    if actual_type != case["expected_action_type"]:
        return fail(f"Expected action '{case['expected_action_type']}', got '{actual_type}'")

    # 2. Action fields (if any)
    for field, expected_value in case.get("expected_fields", {}).items():
        actual_value = action.get(field) if action else None
        if isinstance(expected_value, str) and isinstance(actual_value, str):
            if actual_value.upper() != expected_value.upper():
                return fail(f"Field '{field}': expected '{expected_value}', got '{actual_value}'")
        elif actual_value != expected_value:
            return fail(f"Field '{field}': expected '{expected_value}', got '{actual_value}'")

    # 3. Fact accuracy — the spoken reply must contain / exclude substrings
    lowered = response_text.lower()
    for needle in case.get("response_contains", []):
        if needle.lower() not in lowered:
            return fail(f"Reply missing required text '{needle}' — got: {response_text!r}")
    for forbidden in case.get("response_excludes", []):
        if forbidden.lower() in lowered:
            return fail(f"Reply contains forbidden text '{forbidden}' — got: {response_text!r}")
    any_of = case.get("response_contains_any", [])
    if any_of and not any(opt.lower() in lowered for opt in any_of):
        return fail(f"Reply missing any of {any_of} — got: {response_text!r}")

    return EvalResult(
        case=case,
        actual_action_type=actual_type,
        actual_action=action,
        response_text=response_text,
        raw_json=raw_json,
        passed=True,
    )


async def run_all_evals(verbose: bool = False) -> None:
    """Run all eval cases and print a summary report."""
    print("\n" + "=" * 70)
    print("🧪 MARIMBA VOICE EVALS")
    print("=" * 70)
    print(f"Running {len(EVAL_CASES)} test cases against Mistral Large...")
    print(f"(context pinned to schedule day {PINNED_SCHEDULE_DAY}, "
          f"production _build_voice_context path)\n")

    results: list[EvalResult] = []

    for i, case in enumerate(EVAL_CASES, 1):
        print(f'  [{i}/{len(EVAL_CASES)}] "{case["phrase"]}"', end=" ... ", flush=True)

        eval_result = await run_single_eval(case)
        results.append(eval_result)

        if eval_result.passed:
            print("✅ PASS")
        else:
            print(f"❌ FAIL — {eval_result.failure_reason}")

        if verbose:
            print(f"         Reply: {eval_result.response_text!r}")
            print()

    # ── Summary ───────────────────────────────────────────────────────────
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)
    accuracy = (passed / total * 100) if total else 0

    print("\n" + "=" * 70)
    print(f"📊 RESULTS: {passed}/{total} passed ({accuracy:.0f}% accuracy)")
    print("=" * 70)

    if failed > 0:
        print("\n❌ FAILURES:")
        for r in results:
            if not r.passed:
                print(f'  • "{r.case["phrase"]}"')
                print(f"    {r.case['description']}")
                print(f"    Reason: {r.failure_reason}")
                print()

    print()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    asyncio.run(run_all_evals(verbose=verbose))
