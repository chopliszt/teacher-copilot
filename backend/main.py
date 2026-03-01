#!/usr/bin/env python3
"""
TeacherPilot Backend - FastAPI Application

Core API server for the TeacherPilot application, providing endpoints
for priority management, classroom data, and AI-powered assistance.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="TeacherPilot API",
    description="Backend API for TeacherPilot - AI Command Center for Educators",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint - Health check and basic info
    
    Returns:
        dict: Basic application information
    """
    return {
        "name": "TeacherPilot API",
        "version": "0.1.0",
        "status": "healthy",
        "message": "Welcome to TeacherPilot - The AI Command Center for Educators"
    }


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint
    
    Returns:
        dict: Health status information
    """
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "api_version": "0.1.0"
    }


@app.get("/api/schedule")
async def get_teacher_schedule() -> dict:
    """
    Get teacher's schedule data
    
    Security Considerations (OWASP Top 10):
    - Input validation: No user input processed
    - Authentication: Should be protected in production
    - Sensitive data: No personal data exposed
    - Error handling: Basic error handling implemented
    
    Returns:
        dict: Teacher schedule data from JSON file
    """
    try:
        schedule_path = Path(__file__).parent / "data" / "teacher_schedule.json"
        with open(schedule_path, "r", encoding="utf-8") as f:
            schedule_data = json.load(f)
        return schedule_data
    except FileNotFoundError:
        return {"error": "Schedule data not found"}
    except json.JSONDecodeError:
        return {"error": "Invalid schedule data format"}
    except Exception:
        # Generic error handling to prevent information leakage (OWASP)
        return {"error": "Failed to load schedule data"}


def _load_priority_data() -> Optional[Dict[str, Any]]:
    """
    Load priority data from JSON file with error handling

    Security: File path constructed safely, no user input

    Returns:
        Optional[Dict]: Priority data or None if error occurs
    """
    try:
        priority_path = Path(__file__).parent / "data" / "mock_priorities.json"
        with open(priority_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return None


def _load_schedule_data() -> Optional[Dict[str, Any]]:
    """
    Load teacher schedule data from JSON file with error handling

    Security: File path constructed safely, no user input

    Returns:
        Optional[Dict]: Schedule data or None if error occurs
    """
    try:
        schedule_path = Path(__file__).parent / "data" / "teacher_schedule.json"
        with open(schedule_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return None


def _get_current_time() -> datetime:
    """
    Get current time for priority calculation
    
    Returns:
        datetime: Current datetime (mockable for testing)
    """
    return datetime.now()


def _calculate_priority_score(task: Dict[str, Any], current_time: datetime) -> int:
    """
    Calculate priority score for a task based on multiple factors
    
    Args:
        task: Task dictionary with priority information
        current_time: Current datetime for comparison
    
    Returns:
        int: Priority score (higher = more urgent)
    """
    score = 0
    
    # Priority level
    priority_map = {"high": 3, "medium": 2, "low": 1}
    score += priority_map.get(task.get("priority", "low"), 1) * 100
    
    # Time sensitivity
    try:
        due_date = datetime.fromisoformat(task.get("due_date", ""))
        time_diff = (due_date - current_time).total_seconds()
        if time_diff < 0:
            score += 500  # Overdue
        elif time_diff < 86400:  # Less than 24 hours
            score += 300
        elif time_diff < 172800:  # Less than 48 hours
            score += 150
    except (ValueError, TypeError):
        pass
    
    # Estimated time (shorter tasks get slight priority)
    try:
        estimated_minutes = _parse_estimated_time(task.get("estimated_time", ""))
        if estimated_minutes > 0:
            score += max(0, 50 - estimated_minutes)  # Max 50 points for quick tasks
    except (ValueError, TypeError):
        pass
    
    return score


def _parse_estimated_time(time_str: str) -> int:
    """
    Parse estimated time string to minutes
    
    Args:
        time_str: Time string like "2 hours" or "30 minutes"
    
    Returns:
        int: Time in minutes
    """
    if not time_str:
        return 0
    
    parts = time_str.split()
    if len(parts) != 2:
        return 0
    
    try:
        value = int(parts[0])
        unit = parts[1].lower()
        
        if unit.startswith("hour"):
            return value * 60
        elif unit.startswith("min"):
            return value
        return 0
    except (ValueError, IndexError):
        return 0


def _get_current_schedule_day() -> int:
    """
    Get current day in the 6-day rotating schedule (1-6)
    
    For now, we'll use a simple approach that assumes:
    - Day 1 = Monday
    - Day 2 = Tuesday
    - Day 3 = Wednesday
    - Day 4 = Thursday
    - Day 5 = Friday
    - Day 6 = Next Monday (start of rotation)
    
    Returns:
        int: Current schedule day (1-6)
    """
    # Get current weekday (0=Monday, 6=Sunday)
    current_weekday = _get_current_time().weekday()
    
    # Map to 6-day rotation (1-6)
    # Monday -> 1, Tuesday -> 2, Wednesday -> 3, Thursday -> 4, Friday -> 5, Next Monday -> 6
    if current_weekday < 5:  # Monday-Friday
        return current_weekday + 1
    else:  # Saturday or Sunday -> treat as day 6 (next Monday)
        return 6


def _filter_tasks_by_schedule(tasks: List[Dict[str, Any]], schedule_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Filter tasks by current/relevant classes from schedule
    
    Uses the 6-day rotating schedule system where:
    - Day 1 = Monday (Week 1)
    - Day 2 = Tuesday (Week 1)
    - Day 3 = Wednesday (Week 1)
    - Day 4 = Thursday (Week 1)
    - Day 5 = Friday (Week 1)
    - Day 6 = Monday (Week 2)
    
    Args:
        tasks: List of task dictionaries
        schedule_data: Teacher schedule data
    
    Returns:
        List[Dict]: Filtered tasks
    """
    current_schedule_day = _get_current_schedule_day()
    current_class_groups = set()
    
    # Find classes for current schedule day
    for day_schedule in schedule_data.get("classes", []):
        if day_schedule.get("day") == current_schedule_day:
            for period in day_schedule.get("periods", []):
                current_class_groups.add(period.get("group"))
            break
    
    # Always include homeroom class (homeroom happens every day)
    homeroom_group = schedule_data.get("homeroom", {}).get("group")
    if homeroom_group:
        current_class_groups.add(homeroom_group)
    
    # Filter tasks related to current classes or all classes
    filtered_tasks = []
    for task in tasks:
        related_class = task.get("related_class", "")
        if related_class in current_class_groups or related_class == "All":
            filtered_tasks.append(task)
    
    return filtered_tasks


def _build_mistral_context(
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

    # Build today's schedule summary
    current_schedule_day = _get_current_schedule_day()
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

    # Build tasks section
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


async def _call_mistral_for_priorities(
    tasks: List[Dict[str, Any]],
    schedule_data: Dict[str, Any],
    current_time: datetime,
) -> Optional[List[str]]:
    """
    Ask Mistral to rank the top 3 task IDs.

    Returns None immediately if MISTRAL_API_KEY is not set or on any error,
    allowing the caller to fall back to the scoring algorithm.

    Args:
        tasks: All pending tasks
        schedule_data: Teacher schedule data
        current_time: Current datetime

    Returns:
        Optional[List[str]]: Ordered list of 3 task IDs, or None
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None

    try:
        from mistralai import Mistral

        client = Mistral(api_key=api_key)
        prompt = _build_mistral_context(tasks, schedule_data, current_time)

        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        parsed = json.loads(content)
        task_ids = parsed.get("task_ids", [])

        if isinstance(task_ids, list) and len(task_ids) == 3:
            return [str(tid) for tid in task_ids]

        return None

    except Exception:
        return None


@app.get("/api/priorities")
async def get_priorities() -> Dict[str, Any]:
    """
    Get top 3 priority tasks for the teacher
    
    Security Considerations (OWASP Top 10):
    - A03:2021: No user input processed
    - A01:2021: Generic error messages
    - A04:2021: No insecure deserialization
    - A05:2021: Proper error handling
    
    Returns:
        Dict: Top 3 priorities with metadata
    """
    try:
        # Load data
        priority_data = _load_priority_data()
        schedule_data = _load_schedule_data()

        if not priority_data or not schedule_data:
            return {"error": "Priority data not available"}

        # Combine all tasks
        all_tasks = (
            priority_data.get("urgent_tasks", []) +
            priority_data.get("important_tasks", []) +
            priority_data.get("routine_tasks", [])
        )

        current_time = _get_current_time()

        # Try Mistral-powered prioritization first
        mistral_ids = await _call_mistral_for_priorities(all_tasks, schedule_data, current_time)

        if mistral_ids:
            task_dict = {task["id"]: task for task in all_tasks}
            top_3_tasks = [task_dict[tid] for tid in mistral_ids if tid in task_dict]
        else:
            # Fallback: schedule-filter + scoring algorithm
            filtered_tasks = _filter_tasks_by_schedule(all_tasks, schedule_data)

            if not filtered_tasks:
                return {"priorities": [], "message": "No relevant tasks found"}

            scored_tasks = [
                {"task": task, "score": _calculate_priority_score(task, current_time)}
                for task in filtered_tasks
            ]
            scored_tasks.sort(key=lambda x: x["score"], reverse=True)
            top_3_tasks = [task["task"] for task in scored_tasks[:3]]

        # Format response (schema unchanged — frontend safe)
        response = {
            "priorities": [
                {
                    "id": task["id"],
                    "title": task["title"],
                    "priority": task["priority"],
                    "estimated_time": task.get("estimated_time", "Unknown"),
                    "due_date": task.get("due_date", ""),
                    "class": task.get("related_class", ""),
                    "subject": task.get("related_subject", "")
                }
                for task in top_3_tasks
            ],
            "generated_at": datetime.now().isoformat(),
            "count": len(top_3_tasks)
        }

        return response

    except Exception:
        # Generic error to prevent information leakage
        return {"error": "Failed to generate priorities"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )