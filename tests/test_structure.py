import pytest
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_imports():
    """Verify that key modules can be imported, ensuring structure integrity."""
    try:
        from rng_operator.core.actuator import HygienicActuator
        from rng_operator.core.policy_engine import PolicyEngine
        from rng_operator.core.ledger import ImmutableLedger
    except ImportError as e:
        pytest.fail(f"Failed to import core modules: {e}")

def test_manifest_existence():
    """Verify documentation manifest exists."""
    assert os.path.exists("docs/manifest.md")
    assert os.path.exists("docs/api_reference.md")
    assert os.path.exists("docs/USER_GUIDE.md")
    assert os.path.exists("docs/OPERATOR_MANUAL.md")
    assert os.path.exists("docs/MONETIZATION_STRATEGY.md")
