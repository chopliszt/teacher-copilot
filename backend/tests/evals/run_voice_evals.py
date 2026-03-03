#!/usr/bin/env python3
"""
Voice Evals — Automated accuracy tests for Marimba's voice action pipeline.

Sends realistic teacher phrases through the exact same Mistral prompt used in production,
then checks whether the returned JSON action matches expectations.

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

from context_builder import build_context
from prompts.voice import call_voice_mistral

# ── Fake context for deterministic evals ──────────────────────────────────────

EVAL_SCHEDULE = {
    "homeroom": {"time": "7:30 - 7:50am", "room": "C203", "group": "9A2"},
    "classes": [
        {
            "day": 2,
            "periods": [
                {
                    "time": "7:50am",
                    "subject": "Diseño Digital",
                    "room": "Codingspace",
                    "group": "9A2",
                },
                {
                    "time": "8:30am",
                    "subject": "Digital Design",
                    "room": "Codingspace",
                    "group": "5B2",
                },
                {
                    "time": "10:30am",
                    "subject": "Digital Design",
                    "room": "Codingspace",
                    "group": "8A1",
                },
                {
                    "time": "1:00pm",
                    "subject": "Diseño Digital",
                    "room": "Codingspace",
                    "group": "9A1",
                },
            ],
        }
    ],
}

EVAL_TASKS = [
    {
        "id": "task_design_cat_1",
        "title": "Design Cat 1 registration",
        "description": "Open registration form for Design Cat 1",
        "priority": "high",
        "due_date": "2026-03-03",
        "estimated_time": "15 minutes",
        "related_class": "9A2",
        "related_subject": "Diseño Digital",
    },
    {
        "id": "task_grade_projects",
        "title": "Grade 10A1 final projects",
        "description": "Grade the final projects for 10A1",
        "priority": "medium",
        "due_date": "2026-03-05",
        "estimated_time": "2 hours",
        "related_class": "10A1",
        "related_subject": "Digital Design",
    },
    {
        "id": "task_parent_meeting",
        "title": "Parent meeting about student progress",
        "description": "Meeting with parent of student in 8A1",
        "priority": "high",
        "due_date": "2026-03-03",
        "estimated_time": "30 minutes",
        "related_class": "8A1",
        "related_subject": "Digital Design",
    },
]

EVAL_CONTEXT = build_context(
    tasks=EVAL_TASKS,
    schedule_data=EVAL_SCHEDULE,
    current_time=datetime(2026, 3, 3, 7, 15),
    weekly_data=None,
)


# ── Test cases ────────────────────────────────────────────────────────────────

# Each test case is a dict with:
#   - phrase: what the teacher says
#   - expected_action_type: the action.type we expect (or None for no action)
#   - expected_fields: optional dict of fields that must match in the action
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
        "description": "Relative reference — first class should resolve to 9A2",
    },
    {
        "phrase": "Open the card of 9A1 so I can log what we did",
        "expected_action_type": "open_class",
        "expected_fields": {"group": "9A1"},
        "description": "Long sentence with intent to log — should still open the class",
    },
    # ── add_task ──────────────────────────────────────────────────────────
    {
        "phrase": "Add task: grade 10A1 submissions",
        "expected_action_type": "add_task",
        "expected_fields": {},
        "description": "Explicit add_task command",
    },
    {
        "phrase": "Remind me to print worksheets for 5B2",
        "expected_action_type": "add_task",
        "expected_fields": {},
        "description": "Implicit task creation via 'remind me'",
    },
    # ── open_priority ─────────────────────────────────────────────────────
    {
        "phrase": "Open my top priority",
        "expected_action_type": "open_priority",
        "expected_fields": {},
        "description": "Request to open the first priority card",
    },
    {
        "phrase": "What are the details of my main priority? Open it for me",
        "expected_action_type": "open_priority",
        "expected_fields": {},
        "description": "Request for details with explicit open",
    },
    # ── close_all ─────────────────────────────────────────────────────────
    {
        "phrase": "Close everything",
        "expected_action_type": "close_all",
        "expected_fields": {},
        "description": "Direct close_all command",
    },
    {
        "phrase": "Tidy up the workspace please",
        "expected_action_type": "close_all",
        "expected_fields": {},
        "description": "Indirect close_all using 'tidy up'",
    },
    {
        "phrase": "Can you close all the panels?",
        "expected_action_type": "close_all",
        "expected_fields": {},
        "description": "Explicit close all panels",
    },
    # ── No action (just conversation) ─────────────────────────────────────
    {
        "phrase": "Good morning Marimba",
        "expected_action_type": None,
        "expected_fields": {},
        "description": "Greeting — no action should be triggered",
    },
    {
        "phrase": "How many classes do I have today?",
        "expected_action_type": None,
        "expected_fields": {},
        "description": "Information question — should answer with text only",
    },
    {
        "phrase": "What is the capital of France?",
        "expected_action_type": None,
        "expected_fields": {},
        "description": "Off-topic question — definitely no UI action",
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
        raw_json: str,
        passed: bool,
        failure_reason: str = "",
    ):
        self.case = case
        self.actual_action_type = actual_action_type
        self.actual_action = actual_action
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
            raw_json="(no response from Mistral)",
            passed=False,
            failure_reason="Mistral returned None — check API key",
        )

    action = result.get("action")
    raw_json = result.get("raw_json", "{}")
    actual_type = action.get("type") if action else None

    # Check action type
    if actual_type != case["expected_action_type"]:
        return EvalResult(
            case=case,
            actual_action_type=actual_type,
            actual_action=action,
            raw_json=raw_json,
            passed=False,
            failure_reason=f"Expected action '{case['expected_action_type']}', got '{actual_type}'",
        )

    # Check expected fields (if any)
    for field, expected_value in case.get("expected_fields", {}).items():
        actual_value = action.get(field) if action else None
        # Case-insensitive comparison for group names
        if isinstance(expected_value, str) and isinstance(actual_value, str):
            if actual_value.upper() != expected_value.upper():
                return EvalResult(
                    case=case,
                    actual_action_type=actual_type,
                    actual_action=action,
                    raw_json=raw_json,
                    passed=False,
                    failure_reason=f"Field '{field}': expected '{expected_value}', got '{actual_value}'",
                )
        elif actual_value != expected_value:
            return EvalResult(
                case=case,
                actual_action_type=actual_type,
                actual_action=action,
                raw_json=raw_json,
                passed=False,
                failure_reason=f"Field '{field}': expected '{expected_value}', got '{actual_value}'",
            )

    return EvalResult(
        case=case,
        actual_action_type=actual_type,
        actual_action=action,
        raw_json=raw_json,
        passed=True,
    )


async def run_all_evals(verbose: bool = False) -> None:
    """Run all eval cases and print a summary report."""
    print("\n" + "=" * 70)
    print("🧪 MARIMBA VOICE EVALS")
    print("=" * 70)
    print(f"Running {len(EVAL_CASES)} test cases against Mistral Large...\n")

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
            print(f"         Raw JSON: {eval_result.raw_json[:200]}")
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
                if r.actual_action:
                    print(f"    Got: {json.dumps(r.actual_action)}")
                print()

    # Accuracy by action type
    action_types = set(c["expected_action_type"] for c in EVAL_CASES)
    print("\n📈 ACCURACY BY ACTION TYPE:")
    for action_type in sorted(action_types, key=lambda x: x or "zzz"):
        type_results = [
            r for r in results if r.case["expected_action_type"] == action_type
        ]
        type_passed = sum(1 for r in type_results if r.passed)
        type_total = len(type_results)
        label = action_type or "no_action (conversation)"
        bar = "█" * type_passed + "░" * (type_total - type_passed)
        print(f"  {label:30s} {bar}  {type_passed}/{type_total}")

    print()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    asyncio.run(run_all_evals(verbose=verbose))
