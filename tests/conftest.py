"""Shared fixtures for the Rongle test suite."""

import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a clean temporary directory."""
    return tmp_path


@pytest.fixture
def allowlist_path(tmp_path):
    """Write the default allowlist to a temp file and return the path."""
    allowlist = {
        "allowed_regions": [
            {"x_min": 0, "y_min": 0, "x_max": 1920, "y_max": 1080, "label": "full screen"}
        ],
        "blocked_keystroke_patterns": [
            r"rm\s+-rf",
            r":\(\)\{.*\|.*&.*\};:",
            r"dd\s+if=",
            r"mkfs\.",
            r"format\s+[a-z]:",
            r"> /dev/sd[a-z]",
            r"chmod\s+777",
            r"curl.*\|.*sh",
            r"wget.*\|.*sh",
            r"python\s+-c",
            r"powershell\s+-enc",
            r"net\s+user.*\/add",
        ],
        "allowed_keystroke_patterns": [],
        "max_commands_per_second": 50,
        "max_mouse_speed_px_per_s": 5000,
        "allow_all_regions": False,
        "blocked_key_combos": ["CTRL ALT DELETE"],
    }
    p = tmp_path / "allowlist.json"
    p.write_text(json.dumps(allowlist))
    return str(p)


@pytest.fixture
def audit_log_path(tmp_path):
    """Return a temp path for the audit log."""
    return str(tmp_path / "audit.jsonl")


@pytest.fixture
def restrictive_allowlist_path(tmp_path):
    """Allowlist with a small allowed region and more blocked combos."""
    allowlist = {
        "allowed_regions": [
            {"x_min": 100, "y_min": 100, "x_max": 500, "y_max": 400, "label": "safe zone"}
        ],
        "blocked_keystroke_patterns": [r"rm\s+-rf", r"sudo"],
        "allowed_keystroke_patterns": [],
        "max_commands_per_second": 5,
        "max_mouse_speed_px_per_s": 1000,
        "allow_all_regions": False,
        "blocked_key_combos": ["CTRL ALT DELETE", "ALT F4"],
    }
    p = tmp_path / "restrictive_allowlist.json"
    p.write_text(json.dumps(allowlist))
    return str(p)
