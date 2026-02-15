"""
SessionManager — Persists agent state (goal, history) to withstand process restarts.

Uses a local SQLite database to store the current session state.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AgentSession:
    """The state of the current agent session."""
    session_id: str
    goal: str
    step_index: int
    context_history: list[str] = field(default_factory=list)
    last_active: float = 0.0
    is_active: bool = True

    def to_json(self) -> str:
        return json.dumps({
            "session_id": self.session_id,
            "goal": self.goal,
            "step_index": self.step_index,
            "context_history": self.context_history,
            "last_active": self.last_active,
            "is_active": self.is_active,
        })

    @classmethod
    def from_row(cls, row: tuple) -> AgentSession:
        """Parse a SQLite row (session_id, data_json)."""
        data = json.loads(row[1])
        return cls(**data)


class SessionManager:
    """
    Manages persistence of AgentSession to a local SQLite file.
    """

    def __init__(self, db_path: str | Path = "state.db") -> None:
        self.db_path = str(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT,
                    updated_at REAL
                )
            """)
            conn.commit()

    def save_session(self, session: AgentSession) -> None:
        """Upsert the session state."""
        session.last_active = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, data, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    data = excluded.data,
                    updated_at = excluded.updated_at
                """,
                (session.session_id, session.to_json(), session.last_active),
            )
            conn.commit()

    def load_active_session(self) -> AgentSession | None:
        """Load the most recent active session, if any."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT session_id, data FROM sessions ORDER BY updated_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                session = AgentSession.from_row(row)
                if session.is_active:
                    return session
        return None

    def clear_session(self, session_id: str) -> None:
        """Mark a session as inactive."""
        session = self.load_active_session()
        if session and session.session_id == session_id:
            session.is_active = False
            self.save_session(session)
