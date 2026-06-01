import sys
from pathlib import Path

# Add the backend directory to sys.path so `import main` works
sys.path.insert(0, str(Path(__file__).parent.parent))

# TestClient does not trigger FastAPI's lifespan handler, so the live on-disk
# SQLite at data/teacher_pilot.db never gets migrated when the test suite
# runs. Run init_db() once here so any new columns are added before tests
# that query the existing DB (e.g. the priorities endpoint).
from database import init_db  # noqa: E402

init_db()
