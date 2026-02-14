"""Tests for PolicyGuardian Blocked Regions."""

import json
import pytest
from rng_operator.policy_engine.guardian import PolicyGuardian

@pytest.fixture
def blocked_regions_allowlist(tmp_path):
    policy = {
        "allowed_regions": [
            {"x_min": 0, "y_min": 0, "x_max": 1920, "y_max": 1080, "label": "screen"}
        ],
        "blocked_regions": [
            {"x_min": 100, "y_min": 100, "x_max": 200, "y_max": 200, "label": "restricted_button"}
        ],
        "max_commands_per_second": 100
    }
    p = tmp_path / "blocked_regions.json"
    p.write_text(json.dumps(policy))
    return str(p)

def test_click_in_blocked_region_is_denied(blocked_regions_allowlist):
    guardian = PolicyGuardian(blocked_regions_allowlist)
    # Click inside blocked region (100,100) -> (200,200)
    verdict = guardian.check_command("MOUSE_CLICK LEFT", 150, 150)
    assert verdict.allowed is False
    assert verdict.rule_name == "blocked_region"
    assert "restricted_button" in verdict.reason

def test_click_outside_blocked_region_is_allowed(blocked_regions_allowlist):
    guardian = PolicyGuardian(blocked_regions_allowlist)
    # Click outside blocked region but inside allowed region
    verdict = guardian.check_command("MOUSE_CLICK LEFT", 50, 50)
    assert verdict.allowed is True

def test_blocked_overrides_allowed(blocked_regions_allowlist):
    guardian = PolicyGuardian(blocked_regions_allowlist)
    # The blocked region is technically inside the allowed region (full screen)
    # It must still be blocked.
    verdict = guardian.check_command("MOUSE_CLICK LEFT", 150, 150)
    assert verdict.allowed is False
