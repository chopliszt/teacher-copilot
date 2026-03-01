"""
Database — SQLAlchemy setup for TeacherPilot.

Uses SQLite for simplicity. The DB file lives in data/ alongside
the other JSON data files. Swap DATABASE_URL for Postgres when ready.
"""

from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

DB_PATH = Path(__file__).parent / "data" / "teacher_pilot.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class ImportantEmailRecord(Base):
    """
    Emails that require action from the teacher.
    category: "action_required" | "weekly_schedule"
    """
    __tablename__ = "important_emails"

    id       = Column(String, primary_key=True, index=True)
    subject  = Column(String, nullable=False)
    sender   = Column(String, nullable=False)
    snippet  = Column(Text,   nullable=False)
    date     = Column(String, nullable=False)   # ISO-8601 UTC string
    category = Column(String, nullable=False, default="action_required")


class AbsenceRecord(Base):
    """
    Student absence notifications extracted from forwarded emails.
    Used to flag missing students in the class briefing chips.
    """
    __tablename__ = "absences"

    id           = Column(String, primary_key=True)  # source email id
    student_name = Column(String, nullable=False)
    group_name   = Column(String, nullable=False)     # e.g. "6B1"
    date         = Column(String, nullable=False)     # ISO-8601 UTC string
    raw_snippet  = Column(Text,   nullable=False)     # original text for reference


class WeeklyScheduleRecord(Base):
    """
    Extracted weekly schedule data from the "Anuncios Semanales" Google Doc.
    Only one row ever exists (id="current") — overwritten each week.

    data: JSON blob — {week_label, meetings, class_disruptions, action_items,
                        upcoming_dates, absences}
    """
    __tablename__ = "weekly_schedule"

    id         = Column(String, primary_key=True, default="current")
    week_label = Column(String, nullable=False, default="")
    data       = Column(Text,   nullable=False)   # full JSON from Mistral extraction
    created_at = Column(String, nullable=False)   # ISO date when last updated


class UserTaskRecord(Base):
    """
    Tasks added manually by the teacher (text or voice).
    These join the Mistral priority pool and compete with emails and newsletter items.
    """
    __tablename__ = "user_tasks"

    id           = Column(String, primary_key=True)   # UUID
    title        = Column(String, nullable=False)
    priority     = Column(String, nullable=False, default="medium")  # high/medium/low
    due_date     = Column(String, nullable=True)        # YYYY-MM-DD, optional
    created_at   = Column(String, nullable=False)


class ClassSessionRecord(Base):
    """
    Session log written by the teacher after each class.

    id format: "{group}_{YYYY-MM-DD}_{schedule_day}" — upserted on save.
    what_worked is nullable; Phase 5 will query WHERE what_worked IS NOT NULL
    to build cross-group suggestions.
    """
    __tablename__ = "class_sessions"

    id           = Column(String, primary_key=True)
    group        = Column(String, nullable=False, index=True)
    schedule_day = Column(Integer, nullable=False)
    date         = Column(String, nullable=False)   # YYYY-MM-DD
    notes        = Column(Text,   nullable=False)   # how the class went
    what_worked  = Column(Text,   nullable=True)    # optional — feeds Phase 5
    created_at   = Column(String, nullable=False)


def init_db() -> None:
    """Create all tables. Safe to call on every startup (no-op if they exist)."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
