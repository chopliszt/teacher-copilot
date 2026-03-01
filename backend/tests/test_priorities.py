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
    _load_priority_data
)


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
        original_get_current_schedule_day = main._get_current_schedule_day
        main._get_current_schedule_day = lambda: 1  # Force day 1
        
        try:
            filtered = _filter_tasks_by_schedule(tasks, schedule_data)
            filtered_titles = [task["title"] for task in filtered]
            
            assert "Task for 8A1" in filtered_titles
            assert "Task for 9A1" in filtered_titles
            assert "Task for all" in filtered_titles
            assert "Task for 10A1" not in filtered_titles
            
        finally:
            main._get_current_schedule_day = original_get_current_schedule_day


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
        """Test error handling in priorities endpoint"""
        # Mock data loading to return None
        def mock_load_data():
            return None
        
        monkeypatch.setattr("main._load_priority_data", mock_load_data)
        
        response = client.get("/api/priorities")
        assert response.status_code == 200  # Still returns 200 with error message
        data = response.json()
        assert "error" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])