"""
Settings — Centralized configuration for the Agentic Operator.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """All operator configuration in one place."""

    # Screen / capture
    screen_width: int = 1920
    screen_height: int = 1080
    video_device: str = "/dev/video0"
    capture_fps: int = 30

    # HID gadget paths
    hid_keyboard_dev: str = "/dev/hidg0"
    hid_mouse_dev: str = "/dev/hidg1"

    # Humanizer tuning
    humanizer_jitter_sigma: float = 1.5
    humanizer_overshoot: float = 0.25

    # Visual Cortex
    cursor_templates_dir: str = "assets/cursors"
    vlm_model: str = "gemini-3.0-pro"
    local_vlm_model: str = "HuggingFaceTB/SmolVLM-256M-Instruct"

    # Policy
    allowlist_path: str = "rng_operator/config/allowlist.json"

    # Audit
    audit_log_path: str = "/mnt/secure/audit.jsonl"

    # Emergency stop
    estop_gpio_line: int = 17

    # Agent
    max_iterations: int = 100
    confidence_threshold: float = 0.5

    @classmethod
    def load(cls, path: str | Path = "rng_operator/config/settings.json") -> Settings:
        """Load settings from a JSON file, falling back to defaults."""
        p = Path(path)
        if not p.exists():
            logger.info("Settings file not found (%s), using defaults", p)
            return cls()

        with open(p, "r") as f:
            data = json.load(f)

        # Only override fields that exist in the dataclass
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered)

    def save(self, path: str | Path = "rng_operator/config/settings.json") -> None:
        """Persist current settings to JSON."""
        import dataclasses
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(dataclasses.asdict(self), f, indent=2)
