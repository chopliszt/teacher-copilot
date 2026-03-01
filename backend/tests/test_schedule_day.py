#!/usr/bin/env python3
"""
Test suite for schedule_day — rolling 6-day calculator.
"""

import json
import pytest
from datetime import date, timedelta
from pathlib import Path

import schedule_day


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_state(state_file: Path, last_date: str, last_day: int, holidays=None):
    state_file.write_text(json.dumps({
        "last_date": last_date,
        "last_day": last_day,
        "holidays": holidays or [],
    }))


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    """Redirect STATE_FILE to a temp path for each test."""
    path = tmp_path / "schedule_state.json"
    monkeypatch.setattr("schedule_day.STATE_FILE", path)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScheduleDay:

    def test_same_day_returns_cached(self, state_file, monkeypatch):
        """If last_date == today, return cached last_day without any math."""
        today = date.today().isoformat()
        write_state(state_file, today, 4)

        result = schedule_day.get_current_schedule_day()

        assert result == 4
        # State file should be unchanged (no write needed)
        saved = json.loads(state_file.read_text())
        assert saved["last_day"] == 4
        assert saved["last_date"] == today

    def test_advances_by_weekdays(self, state_file, monkeypatch):
        """5 consecutive weekdays forward → day increments by 5."""
        # Pick a Monday 5 weekdays ago as the base so today (any weekday) works
        today = date.today()
        # Use a fixed past date: 5 school days before today assuming no weekends
        # To keep the test deterministic, set last_date to exactly 5 weekdays ago
        base = today - timedelta(days=7)  # Go back a full week (5 weekdays)
        # Count real weekdays between base and today to set expected result
        count = schedule_day._count_school_days(base, today, [])
        start_day = 1
        expected = ((start_day - 1 + count) % 6) + 1

        write_state(state_file, base.isoformat(), start_day)
        result = schedule_day.get_current_schedule_day()

        assert result == expected

    def test_skips_weekends(self, state_file):
        """Friday → next Monday counts as exactly 1 school day."""
        # Find the most recent Friday
        today = date.today()
        days_since_friday = (today.weekday() - 4) % 7
        friday = today - timedelta(days=days_since_friday)
        monday = friday + timedelta(days=3)

        write_state(state_file, friday.isoformat(), 3)

        count = schedule_day._count_school_days(friday, monday, [])
        assert count == 1  # Saturday and Sunday are skipped

        expected = ((3 - 1 + 1) % 6) + 1  # day 3 + 1 = day 4
        assert expected == 4

    def test_skips_holidays(self, state_file):
        """A holiday between two school days is not counted."""
        today = date.today()
        # Use a Monday two weeks ago as base, mark all days in between as holidays
        base = today - timedelta(days=14)
        # Mark every weekday between base and today as a holiday
        holidays = []
        cursor = base + timedelta(days=1)
        while cursor <= today:
            if cursor.weekday() < 5:
                holidays.append(cursor.isoformat())
            cursor += timedelta(days=1)

        write_state(state_file, base.isoformat(), 2, holidays=holidays)
        result = schedule_day.get_current_schedule_day()

        # 0 school days → day should not change
        assert result == 2

    def test_wraps_from_6_to_1(self, state_file):
        """Day 6 + 1 school day wraps to day 1."""
        today = date.today()
        # Find the most recent weekday to use as today's anchor
        if today.weekday() >= 5:
            # It's a weekend; shift to last Friday
            friday = today - timedelta(days=today.weekday() - 4)
            yesterday = friday - timedelta(days=1)  # Thursday
        else:
            yesterday = today - timedelta(days=1)
            if yesterday.weekday() >= 5:  # yesterday was weekend
                yesterday = today - timedelta(days=today.weekday() + 1)

        # Make sure yesterday is a weekday
        while yesterday.weekday() >= 5:
            yesterday -= timedelta(days=1)

        write_state(state_file, yesterday.isoformat(), 6)

        count = schedule_day._count_school_days(yesterday, today, [])
        expected = ((6 - 1 + count) % 6) + 1

        result = schedule_day.get_current_schedule_day()
        assert result == expected

    def test_set_schedule_day_persists(self, state_file):
        """set_schedule_day writes the override to the state file."""
        write_state(state_file, "2026-01-01", 1)

        schedule_day.set_schedule_day("2026-03-03", 4)

        saved = json.loads(state_file.read_text())
        assert saved["last_date"] == "2026-03-03"
        assert saved["last_day"] == 4

    def test_missing_state_file_uses_default(self, state_file, monkeypatch):
        """When state file is absent, defaults are used without crashing."""
        # state_file fixture points to a non-existent path; don't write anything
        monkeypatch.setattr(
            "schedule_day._DEFAULT_STATE",
            {"last_date": date.today().isoformat(), "last_day": 2, "holidays": []},
        )
        result = schedule_day.get_current_schedule_day()
        assert result == 2
