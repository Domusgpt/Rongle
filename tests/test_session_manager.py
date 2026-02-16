import sqlite3
import time
from pathlib import Path
import pytest
from rongle_operator.session_manager import AgentSession, SessionManager

def test_session_serialization():
    """Verify AgentSession.to_json() and from_row() methods."""
    session = AgentSession(
        session_id="test-123",
        goal="Test goal",
        step_index=5,
        context_history=["step 1", "step 2"],
        last_active=time.time(),
        is_active=True
    )

    # Test to_json
    json_str = session.to_json()
    assert "test-123" in json_str
    assert "Test goal" in json_str
    assert "step 1" in json_str

    # Test from_row
    # row format is (session_id, data_json)
    row = ("test-123", json_str)
    restored = AgentSession.from_row(row)

    assert restored.session_id == session.session_id
    assert restored.goal == session.goal
    assert restored.step_index == session.step_index
    assert restored.context_history == session.context_history
    assert restored.is_active == session.is_active

def test_session_manager_init(tmp_path):
    """Verify DB initialization and table creation."""
    db_path = tmp_path / "test.db"
    manager = SessionManager(db_path)

    assert db_path.exists()

    # Check if table exists
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
        assert cursor.fetchone() is not None

def test_save_and_load_session(tmp_path):
    """Save a session and load it back."""
    db_path = tmp_path / "test.db"
    manager = SessionManager(db_path)

    session = AgentSession(
        session_id="s1",
        goal="Do something",
        step_index=0
    )

    manager.save_session(session)

    loaded = manager.load_active_session()
    assert loaded is not None
    assert loaded.session_id == "s1"
    assert loaded.goal == "Do something"
    assert loaded.is_active is True

def test_update_session(tmp_path):
    """Verify that save_session correctly updates (upserts) an existing session."""
    db_path = tmp_path / "test.db"
    manager = SessionManager(db_path)

    session = AgentSession(session_id="s1", goal="Goal 1", step_index=0)
    manager.save_session(session)

    # Update goal and index
    session.goal = "Goal 2"
    session.step_index = 1
    manager.save_session(session)

    loaded = manager.load_active_session()
    assert loaded.session_id == "s1"
    assert loaded.goal == "Goal 2"
    assert loaded.step_index == 1

def test_load_active_session_empty(tmp_path):
    """Verify that load_active_session returns None when no sessions are present."""
    db_path = tmp_path / "test.db"
    manager = SessionManager(db_path)

    assert manager.load_active_session() is None

def test_clear_session(tmp_path):
    """Verify marking a session as inactive works."""
    db_path = tmp_path / "test.db"
    manager = SessionManager(db_path)

    session = AgentSession(session_id="s1", goal="Goal 1", step_index=0)
    manager.save_session(session)

    # Verify it is active
    assert manager.load_active_session() is not None

    # Clear it
    manager.clear_session("s1")

    # Now it should be None because is_active is False
    assert manager.load_active_session() is None

    # Verify it still exists in DB but is_active=False
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT data FROM sessions WHERE session_id='s1'")
        row = cursor.fetchone()
        assert row is not None
        import json
        data = json.loads(row[0])
        assert data["is_active"] is False

def test_load_most_recent_active(tmp_path):
    """Verify load_active_session loads the MOST RECENT active session."""
    db_path = tmp_path / "test.db"
    manager = SessionManager(db_path)

    s1 = AgentSession(session_id="s1", goal="Goal 1", step_index=0)
    manager.save_session(s1)

    time.sleep(0.1) # Ensure different timestamp

    s2 = AgentSession(session_id="s2", goal="Goal 2", step_index=0)
    manager.save_session(s2)

    loaded = manager.load_active_session()
    assert loaded.session_id == "s2"

    # Now update s1
    time.sleep(0.1)
    s1.step_index = 5
    manager.save_session(s1)

    loaded = manager.load_active_session()
    assert loaded.session_id == "s1"
    assert loaded.step_index == 5
