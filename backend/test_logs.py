from database import init_db, get_db, VoiceLogRecord
from sqlalchemy import select

# This initializes the database, adding the new table if it doesn't exist
init_db()

print("Database initialized, VoiceLog table ready!")
