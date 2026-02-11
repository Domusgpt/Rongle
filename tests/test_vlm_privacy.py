"""Tests for VLM Reasoner Privacy Routing."""

import numpy as np
from unittest.mock import Mock
from rng_operator.visual_cortex.vlm_reasoner import VLMReasoner, VLMBackend, VLMResponse

def test_routes_to_primary_by_default():
    primary = Mock(spec=VLMBackend)
    primary.query.return_value = VLMResponse(elements=[])
    local = Mock(spec=VLMBackend)

    reasoner = VLMReasoner(backend=primary, local_backend=local)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    reasoner.find_element(frame, "find button")

    primary.query.assert_called_once()
    local.query.assert_not_called()

def test_routes_to_local_when_privacy_required():
    primary = Mock(spec=VLMBackend)
    local = Mock(spec=VLMBackend)
    local.query.return_value = VLMResponse(elements=[])

    reasoner = VLMReasoner(backend=primary, local_backend=local)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    reasoner.find_element(frame, "find sensitive data", require_privacy=True)

    local.query.assert_called_once()
    primary.query.assert_not_called()

def test_falls_back_to_primary_if_local_missing():
    primary = Mock(spec=VLMBackend)
    primary.query.return_value = VLMResponse(elements=[])

    reasoner = VLMReasoner(backend=primary, local_backend=None)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Should log warning but proceed with primary
    reasoner.find_element(frame, "find sensitive data", require_privacy=True)

    primary.query.assert_called_once()
