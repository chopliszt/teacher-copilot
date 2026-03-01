#!/usr/bin/env python3
"""
Schedule Day — rolling 6-day calculator with persistent state.

The school uses a 6-day rotating schedule. This module tracks which
schedule day it is today by counting school days since the last known
date, skipping weekends and holidays.

State is persisted to data/schedule_state.json so the calculation
survives server restarts.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import List

STATE_FILE = Path(__file__).parent / "data" / "schedule_state.json"

_DEFAULT_STATE: dict = {
    "last_date": "2026-02-28",
    "last_day": 3,
    "holidays": [],
}


def _load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULT_STATE)


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _count_school_days(start: date, end: date, holidays: List[str]) -> int:
    """Count school days from start (exclusive) to end (inclusive)."""
    holiday_set = set(holidays)
    count = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() < 5 and current.isoformat() not in holiday_set:
            count += 1
        current += timedelta(days=1)
    return count


def get_current_schedule_day() -> int:
    """
    Return today's schedule day (1–6) using a rolling calculator.

    Algorithm:
      1. Load persisted state (last known date + day).
      2. If last_date == today, return cached last_day immediately.
      3. Count school days between last_date (exclusive) and today
         (inclusive), skipping weekends and holidays.
      4. Advance last_day by that count (mod 6, 1-based).
      5. Persist new state and return new day.

    Returns:
        int: Schedule day in range [1, 6]
    """
    state = _load_state()
    today = date.today()
    today_str = today.isoformat()

    if state.get("last_date") == today_str:
        return state["last_day"]

    last_date = date.fromisoformat(state["last_date"])
    count = _count_school_days(last_date, today, state.get("holidays", []))

    new_day = ((state["last_day"] - 1 + count) % 6) + 1

    new_state = {
        "last_date": today_str,
        "last_day": new_day,
        "holidays": state.get("holidays", []),
    }
    _save_state(new_state)
    return new_day


def set_schedule_day(date_str: str, day: int) -> None:
    """
    Manual override — write a known date/day pair to the state file.

    Used when a holiday or school closure causes drift between the
    calculator and the real schedule.

    Args:
        date_str: ISO date string (YYYY-MM-DD)
        day: Schedule day to record (1–6)
    """
    state = _load_state()
    state["last_date"] = date_str
    state["last_day"] = day
    _save_state(state)
