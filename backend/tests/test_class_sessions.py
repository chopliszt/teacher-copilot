#!/usr/bin/env python3
"""
Test suite for the class session log feature (Phase 4).

Covers:
  - POST /api/class/{group}/session — create and upsert
  - GET /api/class/{group}/last-session — returns most recent or null
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db, ClassSessionRecord

# ── In-memory DB fixture ───────────────────────────────────────────────────────

@pytest.fixture()
def test_db():
    """
    Provide a fresh in-memory SQLite DB for each test.

    StaticPool is required so that every SQLAlchemy connection (including the
    one used inside the endpoint) shares the SAME in-memory database instance.
    Without it, each new connection gets a completely empty database and the
    tables created by create_all() would not be visible to the session.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


class TestLogSession:
    """POST /api/class/{group}/session"""

    def test_create_session(self, test_db):
        """Creates a new session log and returns the saved record."""
        response = client.post(
            "/api/class/9A1/session",
            json={"notes": "Good energy today", "what_worked": "Pair work really clicked"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["group"] == "9A1"
        assert data["notes"] == "Good energy today"
        assert data["what_worked"] == "Pair work really clicked"
        assert "id" in data
        assert "date" in data
        assert "schedule_day" in data
        assert "created_at" in data

    def test_create_session_without_what_worked(self, test_db):
        """what_worked is optional — should default to null."""
        response = client.post(
            "/api/class/8A1/session",
            json={"notes": "Quiet class, focused"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["group"] == "8A1"
        assert data["notes"] == "Quiet class, focused"
        assert data["what_worked"] is None

    def test_upsert_session(self, test_db):
        """Posting twice for the same group+date+day updates the existing record."""
        client.post(
            "/api/class/9A1/session",
            json={"notes": "First attempt", "what_worked": "Nothing yet"},
        )
        response = client.post(
            "/api/class/9A1/session",
            json={"notes": "Updated notes", "what_worked": "Gallery walk worked great"},
        )
        assert response.status_code == 200
        data = response.json()

        # Should reflect the updated content, not a new record
        assert data["notes"] == "Updated notes"
        assert data["what_worked"] == "Gallery walk worked great"


class TestGetLastSession:
    """GET /api/class/{group}/last-session"""

    def test_returns_null_when_no_session(self, test_db):
        """Returns null (HTTP 200) when no session has been logged for the group."""
        response = client.get("/api/class/10A2/last-session")
        assert response.status_code == 200
        assert response.json() is None

    def test_returns_last_session_after_logging(self, test_db):
        """Returns the session that was just logged."""
        client.post(
            "/api/class/7B/session",
            json={"notes": "Great participation today"},
        )
        response = client.get("/api/class/7B/last-session")
        assert response.status_code == 200
        data = response.json()

        assert data is not None
        assert data["group"] == "7B"
        assert data["notes"] == "Great participation today"

    def test_last_session_reflects_latest_upsert(self, test_db):
        """last-session endpoint returns the upserted (most recent) notes."""
        client.post("/api/class/6B1/session", json={"notes": "Older session"})
        client.post("/api/class/6B1/session", json={"notes": "Newer session overwrite"})

        response = client.get("/api/class/6B1/last-session")
        assert response.status_code == 200
        data = response.json()
        # Upsert means same key — most recent upsert wins
        assert data["notes"] == "Newer session overwrite"

    def test_sessions_are_isolated_by_group(self, test_db):
        """A session logged for group A does not appear under group B."""
        client.post("/api/class/9A1/session", json={"notes": "Only for 9A1"})

        response = client.get("/api/class/5B1/last-session")
        assert response.status_code == 200
        assert response.json() is None
