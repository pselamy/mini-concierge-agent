# app/session.py
from google.adk.sessions import DatabaseSessionService
from google.adk.apps.app import App, EventsCompactionConfig

import os
from google.adk.apps.app import ResumabilityConfig
from google.adk.runners import Runner
from app.agents import coordinator

DB_DIR = "data"
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "sessions.db")
db_url = f"sqlite+aiosqlite:///{DB_PATH}"

session_service = DatabaseSessionService(db_url=db_url)

app = App(
    name="mini_concierge",
    root_agent=coordinator,
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=3,
        overlap_size=1,
    ),
    resumability_config=ResumabilityConfig(is_resumable=True),
)


def get_runner() -> Runner:
    return Runner(app=app, session_service=session_service, auto_create_session=True)
