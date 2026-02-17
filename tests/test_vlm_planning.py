
import unittest
from unittest.mock import MagicMock
import numpy as np
from rng_operator.visual_cortex.vlm_reasoner import VLMReasoner, VLMBackend

class TestVLMPlanning(unittest.TestCase):
    def test_plan_action_routing(self):
        primary = MagicMock(spec=VLMBackend)
        local = MagicMock(spec=VLMBackend)

        reasoner = VLMReasoner(backend=primary, local_backend=local)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        # Test routing to primary
        reasoner.plan_action(frame, "goal", [])
        primary.generate_plan.assert_called_once()
        local.generate_plan.assert_not_called()

        primary.reset_mock()
        local.reset_mock()

        # Test routing to local
        reasoner.plan_action(frame, "goal", [], require_privacy=True)
        local.generate_plan.assert_called_once()
        primary.generate_plan.assert_not_called()

if __name__ == "__main__":
    unittest.main()
