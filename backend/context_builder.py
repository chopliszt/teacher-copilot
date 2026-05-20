#!/usr/bin/env python3
"""
Context Builder — constructs the natural-language Mistral prompt.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from schedule_day import get_current_schedule_day

# Shared teacher identity — used in both the priority prompt and the voice prompt
TEACHER_PROFILE = (
    "The teacher's name is T. Teacher. They teach Digital Design / Diseño Digital "
    "at Golden Valley School, Costa Rica. "
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


def format_schedule_block(
    schedule_data: Dict[str, Any],
    current_time: datetime,
    weekly_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Return the natural-language block that describes today's schedule,
    meetings, and disruptions. Shared between the priority prompt and the
    task-chat prompt so both Mistral calls see the same "what's today"
    picture and never contradict the UI.
    """
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_name = day_names[current_time.weekday()]
    date_str = current_time.strftime("%Y-%m-%d")
    time_str = current_time.strftime("%H:%M")
    current_schedule_day = get_current_schedule_day()

    homeroom = schedule_data.get("homeroom", {})
    homeroom_line = (
        f"  - Homeroom: {homeroom.get('group', '')} at {homeroom.get('time', '')} "
        f"in {homeroom.get('room', '')}"
        if homeroom else ""
    )

    periods_lines = []
    for day_schedule in schedule_data.get("classes", []):
        if day_schedule.get("day") == current_schedule_day:
            for p in day_schedule.get("periods", []):
                periods_lines.append(
                    f"  - {p.get('time', '')}: {p.get('subject', '')} — "
                    f"{p.get('group', '')} in {p.get('room', '')}"
                )
            break

    schedule_section = "\n".join(filter(None, [homeroom_line] + periods_lines)) or "  (no classes scheduled)"

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
        f"Today is {day_name}, {date_str} at {time_str}.\n\n"
        f"TODAY'S SCHEDULE (schedule day {current_schedule_day}):\n"
        f"{schedule_section}"
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
        task_lines.append(
            f"  - id={task.get('id')} | priority={task.get('priority')} | due={task.get('due_date')} | "
            f"class={task.get('related_class')} | subject={task.get('related_subject')} | "
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

Select the 3 most important tasks the teacher should focus on today, considering:
- Mandatory meetings today MUST be in the Top 3
- Disrupted classes need prep or adjustment — raise tasks related to those groups
- Tasks due today or overdue are most urgent
- High priority tasks take precedence over low priority ones
- Shorter tasks are preferable when priority is equal (quick wins)
- Respect the teacher's ignore rules above when applicable

Respond ONLY with a JSON object in this exact format:
{{"priorities": [{{"id": "<id1>", "reason": "<why this task is critical today>"}}, {{"id": "<id2>", "reason": "<why>"}}, {{"id": "<id3>", "reason": "<why>"}}]}}
"""
    return prompt
