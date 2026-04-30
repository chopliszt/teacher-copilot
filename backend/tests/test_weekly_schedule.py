"""
Tests for the weekly schedule extractor.

Uses sample_weekly_doc.txt — the real Semana #6 Google Doc content.
Mistral is always mocked so these tests run without an API key.
"""

import asyncio
import json
from pathlib import Path

import pytest

from prompts.weekly_schedule import extract_weekly_schedule

FIXTURES_DIR = Path(__file__).parent / "fixtures"

SAMPLE_DOC = (FIXTURES_DIR / "sample_weekly_doc.txt").read_text(encoding="utf-8")

# Representative Mistral response for Semana #6 — matches the real doc content
MOCK_EXTRACTION = {
    "week_label": "Semana #6 - Del 2 al 6 de marzo",
    "meetings": [
        {
            "description": "Capacitación IA Secundaria",
            "day": "Miércoles 4 de marzo",
            "schedule_day": 3,
            "time": "3:00 pm",
            "location": None,
            "mandatory": True,
        },
        {
            "description": "Professional Development PD",
            "day": "Viernes 6 de marzo",
            "schedule_day": 5,
            "time": "1:15 pm",
            "location": None,
            "mandatory": True,
        },
    ],
    "class_disruptions": [
        {
            "description": "Charla Prevención Vapeadores Dr. [Name 3]",
            "day": "Lunes 2 de marzo",
            "schedule_day": 1,
            "time": "7:50 am - 2:10 pm (grupos rotativos)",
            "groups_affected": ["all"],
        },
        {
            "description": "Charla Prevención Vapeadores Dr. [Name 3]",
            "day": "Martes 3 de marzo",
            "schedule_day": 2,
            "time": "7:50 am - 2:10 pm (grupos rotativos)",
            "groups_affected": ["all"],
        },
        {
            "description": "Asamblea Día de la Mujer",
            "day": "Viernes 6 de marzo",
            "schedule_day": 5,
            "time": "11:00 am",
            "groups_affected": ["all"],
        },
    ],
    "action_items": [
        "Remind students to bring university merchandise for March Madness on Monday March 9 at 8:30 am",
        "Reinforce school uniform expectations and notify parents of transgressions via email",
    ],
    "upcoming_dates": [
        {"date": "2026-03-09", "description": "March Madness 8:30 am — students bring university gear"},
        {"date": "2026-03-12", "description": "STEAM Showcase"},
        {"date": "2026-03-13", "description": "Pi Day activities 9:20–10:00 am (Secundaria)"},
        {"date": "2026-03-19", "description": "Día de usar medias — campaña inclusión"},
    ],
    "absences": [],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_mistral_class(response_json: str):
    """Return a minimal Mistral client mock that returns `response_json`."""
    class FakeMessage:
        content = response_json

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeChat:
        async def complete_async(self, **kwargs):
            return FakeResponse()

    class FakeMistral:
        def __init__(self, api_key):
            self.chat = FakeChat()

    return FakeMistral


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestExtractWeeklySchedule:

    def test_returns_empty_dict_without_api_key(self, monkeypatch):
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        result = asyncio.run(
            extract_weekly_schedule(SAMPLE_DOC)
        )
        assert result == {}

    def test_returns_parsed_dict_with_mocked_mistral(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
        monkeypatch.setattr(
            "prompts.weekly_schedule.Mistral",
            _mock_mistral_class(json.dumps(MOCK_EXTRACTION)),
        )
        result = asyncio.run(
            extract_weekly_schedule(SAMPLE_DOC)
        )
        assert result["week_label"] == "Semana #6 - Del 2 al 6 de marzo"

    def test_meetings_extracted(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
        monkeypatch.setattr(
            "prompts.weekly_schedule.Mistral",
            _mock_mistral_class(json.dumps(MOCK_EXTRACTION)),
        )
        result = asyncio.run(
            extract_weekly_schedule(SAMPLE_DOC)
        )
        assert len(result["meetings"]) == 2
        descriptions = [m["description"] for m in result["meetings"]]
        assert any("IA" in d for d in descriptions)      # Capacitación IA
        assert any("Development" in d for d in descriptions)  # PD Friday

    def test_class_disruptions_extracted(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
        monkeypatch.setattr(
            "prompts.weekly_schedule.Mistral",
            _mock_mistral_class(json.dumps(MOCK_EXTRACTION)),
        )
        result = asyncio.run(
            extract_weekly_schedule(SAMPLE_DOC)
        )
        assert len(result["class_disruptions"]) >= 2
        # Vaping talk disrupts both Day 1 and Day 2
        days = [d["schedule_day"] for d in result["class_disruptions"]]
        assert 1 in days
        assert 2 in days

    def test_upcoming_dates_extracted(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
        monkeypatch.setattr(
            "prompts.weekly_schedule.Mistral",
            _mock_mistral_class(json.dumps(MOCK_EXTRACTION)),
        )
        result = asyncio.run(
            extract_weekly_schedule(SAMPLE_DOC)
        )
        dates = [d["date"] for d in result["upcoming_dates"]]
        assert "2026-03-12" in dates   # STEAM Showcase
        assert "2026-03-09" in dates   # March Madness

    def test_returns_empty_dict_on_mistral_error(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

        class BrokenMistral:
            def __init__(self, api_key):
                pass
            @property
            def chat(self):
                raise RuntimeError("Mistral exploded")

        monkeypatch.setattr("prompts.weekly_schedule.Mistral", BrokenMistral)
        result = asyncio.run(
            extract_weekly_schedule(SAMPLE_DOC)
        )
        assert result == {}
