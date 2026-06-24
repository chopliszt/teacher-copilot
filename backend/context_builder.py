#!/usr/bin/env python3
"""
Context Builder — constructs the natural-language Mistral prompt.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from schedule_day import get_current_schedule_day

# Shared teacher identity — used in both the priority prompt and the voice prompt
TEACHER_PROFILE = (
    "The teacher's name is T. Teacher. He teaches Digital Design / Diseño Digital "
    "at Golden Valley School, Costa Rica. The teacher is male — use masculine agreement "
    "in Spanish (e.g. \"atento\", not \"atenta\"). "
    "Address them as \"profe\" — never by name. "
    "They teach 13 groups (4A, 4B, 5B1, 5B2, 6B1, 6B2, 7A1, 7B, 8A1, 9A1, 9A2, 10A1, 10A2) "
    "across grades 4–10 only (not grades 11–12), approximately 272 students total. "
    "The teacher has ADHD — keep responses and summaries short and decisive. "
    "Key people: Fabiola Jiménez (fabiola.jimenez@goldenvalley.ed.cr) is the substitute "
    "coordinator — any request from her to cover a class is always urgent. "
    "Carolina Marín (carolina.marin@goldenvalley.ed.cr) and "
    "Kimberly Fonseca (kimberly.fonseca@goldenvalley.ed.cr) are school directors — "
    "their direct requests are always high priority."
)


def _next_weekday(date: datetime) -> datetime:
    """Return the next weekday after `date`, skipping Sat/Sun. Holidays
    are not modelled here — the rotating-day system handles those at the
    state level; this is just for the "what day is tomorrow" hint."""
    nxt = date + timedelta(days=1)
    while nxt.weekday() >= 5:  # 5=Sat, 6=Sun
        nxt += timedelta(days=1)
    return nxt


def _format_day_periods(
    day_schedule: Dict[str, Any],
    homeroom: Dict[str, Any],
) -> str:
    """One-line compact period list for a schedule day, e.g.:
    "07:30 Homeroom 9A2, 11:30 9A1 (Diseño Digital), 13:30 5B1"
    The homeroom only renders on days where it actually meets — that
    metadata lives on the homeroom block, NOT on each day's periods."""
    day_num = day_schedule.get("day")
    parts: List[str] = []
    if homeroom and day_num in (homeroom.get("days") or []):
        parts.append(f"{homeroom.get('time', '')} Homeroom {homeroom.get('group', '')}")
    for p in day_schedule.get("periods", []):
        time = p.get("time", "")
        group = p.get("group", "")
        subject = p.get("subject", "")
        # Keep subject short — Marimba doesn't need "Diseño Digital" on
        # every line, but include it once per period for unambiguity.
        parts.append(f"{time} {group}" + (f" ({subject})" if subject else ""))
    return ", ".join(parts) if parts else "(no classes)"


def format_schedule_block(
    schedule_data: Dict[str, Any],
    current_time: datetime,
    weekly_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Return the natural-language block that describes the teacher's schedule
    rotation and today's specific events. Renders ALL 6 schedule days so
    Marimba can answer questions about future days ("what about Thursday?")
    without hallucinating — previously only today's day was injected, which
    led her to guess wrong groups for tomorrow's meetings.
    """
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_name = day_names[current_time.weekday()]
    date_str = current_time.strftime("%Y-%m-%d")
    time_str = current_time.strftime("%H:%M")
    current_schedule_day = get_current_schedule_day()

    # Next class day — the schedule day always advances by one weekday,
    # wrapping 6→1. Use weekday math for the date, modular arithmetic for
    # the schedule day. Holidays could break this, but they're rare and
    # the get_current_schedule_day call handles them on the actual day.
    next_date = _next_weekday(current_time)
    next_schedule_day = (current_schedule_day % 6) + 1
    next_day_name = day_names[next_date.weekday()]
    next_date_str = next_date.strftime("%Y-%m-%d")

    homeroom = schedule_data.get("homeroom", {}) or {}

    # Full 6-day rotation — compact one-line-per-day format. Today and
    # tomorrow are marked so Marimba doesn't need to do the math herself.
    rotation_lines: List[str] = []
    for day_schedule in sorted(
        schedule_data.get("classes", []),
        key=lambda d: d.get("day", 0),
    ):
        day_num = day_schedule.get("day")
        marker = ""
        if day_num == current_schedule_day:
            marker = " ← TODAY"
        elif day_num == next_schedule_day:
            marker = f" ← NEXT CLASS DAY ({next_day_name} {next_date_str})"
        rotation_lines.append(
            f"  Day {day_num}{marker}: {_format_day_periods(day_schedule, homeroom)}"
        )
    rotation_section = "\n".join(rotation_lines) or "  (no rotation data)"

    disruptions_section = ""
    if weekly_data:
        disruptions = [
            d for d in weekly_data.get("class_disruptions", [])
            if d.get("schedule_day") == current_schedule_day
        ]
        if disruptions:
            lines = []
            for d in disruptions:
                groups = ", ".join(d.get("groups_affected", []))
                lines.append(f"  - {groups} ({d.get('time', '')}): {d.get('description', '')}")
            disruptions_section = (
                f"\nTODAY'S DISRUPTIONS (schedule day {current_schedule_day}):\n"
                + "\n".join(lines)
            )

    meetings_section = ""
    if weekly_data:
        meetings = [
            m for m in weekly_data.get("meetings", [])
            if m.get("schedule_day") == current_schedule_day
        ]
        if meetings:
            lines = []
            for m in meetings:
                mandatory_tag = " [MANDATORY]" if m.get("mandatory") else ""
                location = f" — {m['location']}" if m.get("location") else ""
                lines.append(
                    f"  - {m.get('description', '')} — {m.get('time', '')}"
                    f"{location}{mandatory_tag}"
                )
            meetings_section = "\nTODAY'S MEETINGS:\n" + "\n".join(lines)

    return (
        f"Today is {day_name}, {date_str} at {time_str}. "
        f"Schedule day TODAY = {current_schedule_day}. "
        f"Schedule day on the next class day "
        f"({next_day_name} {next_date_str}) = {next_schedule_day}.\n\n"
        f"6-DAY CLASS ROTATION — the school's schedule is a 6-day rotation "
        f"(NOT Mon–Sat); each weekday advances by one, wrapping 6→1. "
        f"Use this when reasoning about ANY date — never guess what groups "
        f"meet on a given day:\n"
        f"{rotation_section}"
        f"{disruptions_section}"
        f"{meetings_section}"
    )


def build_context(
    tasks: List[Dict[str, Any]],
    schedule_data: Dict[str, Any],
    current_time: datetime,
    weekly_data: Optional[Dict[str, Any]] = None,
    ignore_rules: Optional[str] = None,
) -> str:
    """
    Build a natural-language prompt describing the teacher's context.

    Args:
        tasks: All pending tasks
        schedule_data: Teacher schedule data
        current_time: Current datetime
        weekly_data: Extracted weekly schedule (meetings, disruptions, action items)

    Returns:
        str: Formatted prompt for Mistral
    """
    schedule_block = format_schedule_block(schedule_data, current_time, weekly_data)

    task_lines = []
    for task in tasks:
        age_str = ""
        created_at = task.get("created_at", "")
        if created_at:
            try:
                created = datetime.fromisoformat(created_at)
                age_days = (current_time - created.replace(tzinfo=None)).days
                if age_days >= 2:
                    age_str = f" | waiting={age_days}d"
            except (ValueError, TypeError):
                pass
        task_lines.append(
            f"  - id={task.get('id')} | priority={task.get('priority')} | due={task.get('due_date')}"
            f"{age_str} | class={task.get('related_class')} | subject={task.get('related_subject')} | "
            f"est={task.get('estimated_time')} | title={task.get('title')} | desc={task.get('description', '')}"
        )

    tasks_section = "\n".join(task_lines) or "  (no tasks)"

    ignore_section = ""
    if ignore_rules and ignore_rules.strip():
        ignore_section = (
            "\nTEACHER'S IGNORE RULES (treat tasks matching any of these as low value "
            "— do NOT put them in the Top 3 unless nothing else competes):\n"
            f"{ignore_rules.strip()}\n"
        )

    prompt = f"""You are an AI assistant helping a teacher prioritize their day.
{TEACHER_PROFILE}

{schedule_block}
{ignore_section}
PENDING TASKS:
{tasks_section}

Select the most important tasks the teacher should focus on today (up to 3 — return fewer if the pool is small). Consider:
- Mandatory meetings today MUST be included
- Disrupted classes need prep or adjustment — raise tasks related to those groups
- Tasks due today or overdue are most urgent; priority="high" already accounts for this
- Tasks with waiting=Nd have been sitting untouched — if they have been waiting 4+ days and nothing more urgent competes, elevate them
- High priority beats medium beats low when urgency is equal
- Shorter tasks are preferable when priority is equal (quick wins)
- Respect the teacher's ignore rules above when applicable

Respond ONLY with a JSON object in this exact format:
{{"priorities": [{{"id": "<id1>", "reason": "<why this task is critical today>"}}, {{"id": "<id2>", "reason": "<why>"}}, {{"id": "<id3>", "reason": "<why>"}}]}}
"""
    return prompt
