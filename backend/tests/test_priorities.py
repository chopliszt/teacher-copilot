#!/usr/bin/env python3
"""
Test suite for TeacherPilot priorities functionality

Comprehensive tests for the priority generation algorithm and API endpoint.
"""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
from fastapi.testclient import TestClient

# Import the functions to test
from main import (
    _calculate_priority_score,
    _parse_estimated_time,
    _filter_tasks_by_schedule,
    _load_priority_data,
    _load_schedule_data,
)
from mistral_client import call_mistral as _call_mistral_for_priorities  # alias for legacy tests


# Create a test client for the FastAPI app
from main import app
client = TestClient(app)


class TestPriorityScoring:
    """Test the priority scoring algorithm"""
    
    def test_high_priority_task_scoring(self):
        """Test scoring for high priority tasks"""
        task = {
            "priority": "high",
            "due_date": (datetime.now() + timedelta(hours=2)).isoformat(),
            "estimated_time": "30 minutes"
        }
        current_time = datetime.now()
        score = _calculate_priority_score(task, current_time)
        assert score > 400  # High priority + due soon + quick task
        
    def test_low_priority_task_scoring(self):
        """Test scoring for low priority tasks"""
        task = {
            "priority": "low",
            "due_date": (datetime.now() + timedelta(days=7)).isoformat(),
            "estimated_time": "2 hours"
        }
        current_time = datetime.now()
        score = _calculate_priority_score(task, current_time)
        assert score < 200  # Low priority + far due date + longer task
        
    def test_overdue_task_scoring(self):
        """Test scoring for overdue tasks"""
        task = {
            "priority": "medium",
            "due_date": (datetime.now() - timedelta(days=1)).isoformat(),
            "estimated_time": "1 hour"
        }
        current_time = datetime.now()
        score = _calculate_priority_score(task, current_time)
        assert score > 400  # Medium priority + overdue


class TestTimeParsing:
    """Test time parsing functionality"""
    
    def test_parse_hours(self):
        """Test parsing hours to minutes"""
        assert _parse_estimated_time("2 hours") == 120
        assert _parse_estimated_time("1 hour") == 60
        
    def test_parse_minutes(self):
        """Test parsing minutes"""
        assert _parse_estimated_time("30 minutes") == 30
        assert _parse_estimated_time("15 minutes") == 15
        
    def test_parse_invalid_formats(self):
        """Test handling of invalid time formats"""
        assert _parse_estimated_time("") == 0
        assert _parse_estimated_time("invalid") == 0
        assert _parse_estimated_time("5") == 0
        assert _parse_estimated_time("hours 2") == 0


class TestScheduleFiltering:
    """Test schedule-based task filtering"""
    
    def test_filter_current_day_classes(self):
        """Test filtering tasks for current day's classes"""
        # Mock schedule data for Monday (day 1)
        schedule_data = {
            "homeroom": {
                "group": "9A2"
            },
            "classes": [
                {
                    "day": 1,  # Monday
                    "periods": [
                        {"group": "8A1", "subject": "Digital Design"},
                        {"group": "9A1", "subject": "Diseño Digital"}
                    ]
                }
            ]
        }
        
        tasks = [
            {"related_class": "8A1", "title": "Task for 8A1"},
            {"related_class": "9A1", "title": "Task for 9A1"},
            {"related_class": "10A1", "title": "Task for 10A1"},
            {"related_class": "All", "title": "Task for all"}
        ]
        
        # Mock current schedule day as day 1 (Monday)
        import main
        original_get_current_schedule_day = main.get_current_schedule_day
        main.get_current_schedule_day = lambda: 1  # Force day 1

        try:
            filtered = _filter_tasks_by_schedule(tasks, schedule_data)
            filtered_titles = [task["title"] for task in filtered]

            assert "Task for 8A1" in filtered_titles
            assert "Task for 9A1" in filtered_titles
            assert "Task for all" in filtered_titles
            assert "Task for 10A1" not in filtered_titles

        finally:
            main.get_current_schedule_day = original_get_current_schedule_day


class TestDataLoading:
    """Test data loading functionality"""
    
    def test_load_valid_priority_data(self):
        """Test loading valid priority data"""
        # This test assumes the mock_priorities.json file exists and is valid
        data = _load_priority_data()
        assert data is not None
        assert "urgent_tasks" in data
        assert "important_tasks" in data
        assert "routine_tasks" in data
        
    def test_load_missing_file(self, monkeypatch):
        """Test handling of missing priority data file"""
        # Mock file not found error
        def mock_open(*args, **kwargs):
            raise FileNotFoundError()
        
        monkeypatch.setattr("builtins.open", mock_open)
        data = _load_priority_data()
        assert data is None


class TestAPIEndpoints:
    """Test API endpoints"""
    
    def test_schedule_endpoint(self):
        """Test the schedule endpoint"""
        response = client.get("/api/schedule")
        assert response.status_code == 200
        data = response.json()
        assert "school" in data
        assert "classes" in data
        
    def test_priorities_endpoint(self):
        """Test the priorities endpoint"""
        response = client.get("/api/priorities")
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "priorities" in data
        assert "generated_at" in data
        assert "count" in data
        
        # Check that we get 3 or fewer priorities
        assert len(data["priorities"]) <= 3
        
        # Check priority structure
        if data["priorities"]:
            priority = data["priorities"][0]
            assert "id" in priority
            assert "title" in priority
            assert "priority" in priority
            assert "estimated_time" in priority
            assert "due_date" in priority
            assert "class" in priority
            assert "subject" in priority
    
    def test_health_endpoint(self):
        """Test the health endpoint"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "environment" in data
        assert "api_version" in data


class TestErrorHandling:
    """Test error handling"""

    def test_priorities_error_handling(self, monkeypatch):
        """Schedule data unavailable → endpoint returns empty priorities (not 500)."""
        monkeypatch.setattr("main._load_schedule_data", lambda: None)

        response = client.get("/api/priorities")
        assert response.status_code == 200  # graceful degradation, not a 500
        data = response.json()
        assert data["priorities"] == []
        assert "generated_at" in data
        assert data["count"] == 0


class TestMistralIntegration:
    """Test Mistral-powered prioritization and fallback behaviour"""

    _SAMPLE_TASKS = [
        {
            "id": "urgent_1",
            "title": "Grade projects",
            "description": "Grade final projects",
            "priority": "high",
            "due_date": "2026-01-15",
            "estimated_time": "2 hours",
            "related_class": "9A2",
            "related_subject": "Diseño Digital",
        },
        {
            "id": "urgent_2",
            "title": "Parent meeting",
            "description": "Meeting with parent",
            "priority": "high",
            "due_date": "2026-01-16",
            "estimated_time": "30 minutes",
            "related_class": "8A1",
            "related_subject": "Digital Design",
        },
        {
            "id": "important_1",
            "title": "Prepare lesson plan",
            "description": "Create lesson",
            "priority": "medium",
            "due_date": "2026-01-18",
            "estimated_time": "1 hour",
            "related_class": "10A1",
            "related_subject": "Diseño Digital",
        },
    ]

    _SAMPLE_SCHEDULE = {
        "homeroom": {"time": "7:30 - 7:50am", "room": "C203", "group": "9A2"},
        "classes": [
            {
                "day": 1,
                "periods": [
                    {"time": "7:50am", "subject": "Digital Design", "room": "Codingspace", "group": "8A1"},
                ],
            }
        ],
    }

    def test_mistral_path_returns_correct_structure(self, monkeypatch):
        """Mistral-driven path: endpoint returns correct schema when Mistral provides 3 items"""
        async def mock_mistral(tasks, schedule, current_time, weekly_data=None):
            return [
                {"id": "urgent_1", "reason": "Most urgent grading deadline today"},
                {"id": "urgent_2", "reason": "Parent meeting cannot be rescheduled"},
                {"id": "important_1", "reason": "Lesson plan due before class"},
            ]

        monkeypatch.setattr("mistral_client.call_mistral", mock_mistral)

        response = client.get("/api/priorities")
        assert response.status_code == 200
        data = response.json()

        assert "priorities" in data
        assert "generated_at" in data
        assert "count" in data
        assert data["count"] == 3

        # Verify schema of each priority item including marimba_note
        for item in data["priorities"]:
            assert "id" in item
            assert "title" in item
            assert "priority" in item
            assert "estimated_time" in item
            assert "due_date" in item
            assert "class" in item
            assert "subject" in item
            assert "marimba_note" in item
            assert isinstance(item["marimba_note"], str)
            assert len(item["marimba_note"]) > 0

    def test_fallback_when_mistral_returns_none(self, monkeypatch):
        """Fallback path: scoring algorithm kicks in when Mistral returns None"""
        async def mock_mistral_none(tasks, schedule, current_time):
            return None

        monkeypatch.setattr("mistral_client.call_mistral", mock_mistral_none)

        response = client.get("/api/priorities")
        assert response.status_code == 200
        data = response.json()

        # Response structure must be identical regardless of path
        assert "priorities" in data
        assert "generated_at" in data
        assert "count" in data

    def test_call_mistral_returns_none_without_api_key(self, monkeypatch):
        """_call_mistral_for_priorities returns None when MISTRAL_API_KEY is unset"""
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            _call_mistral_for_priorities(
                self._SAMPLE_TASKS,
                self._SAMPLE_SCHEDULE,
                datetime.now(),
                weekly_data=None,
            )
        )
        assert result is None

    def test_load_schedule_data(self):
        """_load_schedule_data returns valid schedule with required keys"""
        data = _load_schedule_data()
        assert data is not None
        assert "homeroom" in data
        assert "classes" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])