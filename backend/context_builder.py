#!/usr/bin/env python3
"""
Context Builder — constructs the natural-language Mistral prompt.
"""

from datetime import datetime
from typing import List, Dict, Any

from schedule_day import get_current_schedule_day


def build_context(
    tasks: List[Dict[str, Any]],
    schedule_data: Dict[str, Any],
    current_time: datetime,
) -> str:
    """
    Build a natural-language prompt describing the teacher's context.

    Args:
        tasks: All pending tasks
        schedule_data: Teacher schedule data
        current_time: Current datetime

    Returns:
        str: Formatted prompt for Mistral
    """
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_name = day_names[current_time.weekday()]
    date_str = current_time.strftime("%Y-%m-%d")
    time_str = current_time.strftime("%H:%M")

    current_schedule_day = get_current_schedule_day()

    homeroom = schedule_data.get("homeroom", {})
    homeroom_line = (
        f"  - Homeroom: {homeroom.get('group', '')} at {homeroom.get('time', '')} in {homeroom.get('room', '')}"
        if homeroom else ""
    )

    periods_lines = []
    for day_schedule in schedule_data.get("classes", []):
        if day_schedule.get("day") == current_schedule_day:
            for p in day_schedule.get("periods", []):
                periods_lines.append(
                    f"  - {p.get('time', '')}: {p.get('subject', '')} — {p.get('group', '')} in {p.get('room', '')}"
                )
            break

    schedule_section = "\n".join(filter(None, [homeroom_line] + periods_lines)) or "  (no classes scheduled)"

    task_lines = []
    for task in tasks:
        task_lines.append(
            f"  - id={task.get('id')} | priority={task.get('priority')} | due={task.get('due_date')} | "
            f"class={task.get('related_class')} | subject={task.get('related_subject')} | "
            f"est={task.get('estimated_time')} | title={task.get('title')} | desc={task.get('description', '')}"
        )

    tasks_section = "\n".join(task_lines) or "  (no tasks)"

    prompt = f"""You are an AI assistant helping a teacher prioritize their day.

Today is {day_name}, {date_str} at {time_str}.

TODAY'S SCHEDULE (schedule day {current_schedule_day}):
{schedule_section}

PENDING TASKS:
{tasks_section}

Select the 3 most important tasks the teacher should focus on today, considering:
- Tasks due today or overdue are most urgent
- Tasks related to classes happening today are more relevant
- High priority tasks take precedence over low priority ones
- Shorter tasks are preferable when priority is equal

Respond ONLY with a JSON object in this exact format:
{{"task_ids": ["<id1>", "<id2>", "<id3>"]}}
"""
    return prompt
