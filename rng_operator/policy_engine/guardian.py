"""
PolicyGuardian — Intercepts every command before execution.

Validates Ducky Script commands against a configurable allowlist that
specifies permitted click regions, blocked keystroke patterns, and
rate limits.  Any command that violates policy is rejected before it
reaches the HID gadget.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy types
# ---------------------------------------------------------------------------
@dataclass
class ClickRegion:
    """Allowed rectangular region for mouse clicks."""
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    label: str = ""

    def contains(self, x: int, y: int) -> bool:
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max


@dataclass
class PolicyVerdict:
    """Result of a policy check."""
    allowed: bool
    reason: str = ""
    rule_name: str = ""


@dataclass
class PolicyConfig:
    """Parsed representation of the allowlist.json policy file."""
    allowed_regions: list[ClickRegion] = field(default_factory=list)
    blocked_keystroke_patterns: list[re.Pattern] = field(default_factory=list)
    allowed_keystroke_patterns: list[re.Pattern] = field(default_factory=list)
    max_commands_per_second: float = 50.0
    max_mouse_speed_px_per_s: float = 5000.0
    allow_all_regions: bool = False
    blocked_key_combos: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# PolicyGuardian
# ---------------------------------------------------------------------------
class PolicyGuardian:
    """
    Intercepts and validates every command against the policy allowlist.

    Usage::

        guardian = PolicyGuardian("config/allowlist.json")
        verdict = guardian.check_keyboard("STRING rm -rf /")
        if not verdict.allowed:
            print(f"BLOCKED: {verdict.reason}")

    The allowlist.json schema::

        {
            "allowed_regions": [
                {"x_min": 0, "y_min": 0, "x_max": 1920, "y_max": 1080, "label": "full screen"}
            ],
            "blocked_keystroke_patterns": [
                "rm\\\\s+-rf",
                ":(){ :|:& };:",
                "dd\\\\s+if=",
                "mkfs\\\\.",
                "format\\\\s+[a-z]:",
                "> /dev/sd[a-z]",
                "chmod\\\\s+777",
                "curl.*\\\\|.*sh",
                "wget.*\\\\|.*sh"
            ],
            "allowed_keystroke_patterns": [],
            "max_commands_per_second": 50,
            "max_mouse_speed_px_per_s": 5000,
            "allow_all_regions": false,
            "blocked_key_combos": [
                "CTRL ALT DELETE",
                "ALT F4"
            ]
        }
    """

    def __init__(self, allowlist_path: str | Path = "config/allowlist.json") -> None:
        self.allowlist_path = Path(allowlist_path)
        self._config = PolicyConfig()
        self._command_timestamps: list[float] = []
        self.load()

    # ------------------------------------------------------------------
    # Configuration loading
    # ------------------------------------------------------------------
    def load(self) -> None:
        """Load or reload the policy allowlist from disk."""
        if not self.allowlist_path.exists():
            logger.warning(
                "Allowlist not found at %s — using permissive defaults",
                self.allowlist_path,
            )
            self._config = PolicyConfig(allow_all_regions=True)
            return

        with open(self.allowlist_path, "r") as f:
            raw: dict[str, Any] = json.load(f)

        regions = [
            ClickRegion(**r) for r in raw.get("allowed_regions", [])
        ]
        blocked_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in raw.get("blocked_keystroke_patterns", [])
        ]
        allowed_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in raw.get("allowed_keystroke_patterns", [])
        ]

        self._config = PolicyConfig(
            allowed_regions=regions,
            blocked_keystroke_patterns=blocked_patterns,
            allowed_keystroke_patterns=allowed_patterns,
            max_commands_per_second=raw.get("max_commands_per_second", 50.0),
            max_mouse_speed_px_per_s=raw.get("max_mouse_speed_px_per_s", 5000.0),
            allow_all_regions=raw.get("allow_all_regions", False),
            blocked_key_combos=raw.get("blocked_key_combos", []),
        )
        logger.info(
            "Policy loaded: %d regions, %d blocked patterns, %d blocked combos",
            len(regions), len(blocked_patterns), len(self._config.blocked_key_combos),
        )

    # ------------------------------------------------------------------
    # Validation checks
    # ------------------------------------------------------------------
    def check_keyboard(self, raw_line: str) -> PolicyVerdict:
        """
        Validate a keyboard/string command line.

        Checks:
          1. Rate limiting
          2. Blocked keystroke patterns (e.g., 'rm -rf')
          3. Blocked key combos (e.g., 'CTRL ALT DELETE')
        """
        # Rate limit
        rate_verdict = self._check_rate_limit()
        if not rate_verdict.allowed:
            return rate_verdict

        # Extract the typed content from STRING commands
        content = raw_line
        string_match = re.match(r"^STRINGLN?\s+(.+)$", raw_line, re.IGNORECASE)
        if string_match:
            content = string_match.group(1)

        # Check blocked patterns
        for pattern in self._config.blocked_keystroke_patterns:
            if pattern.search(content):
                return PolicyVerdict(
                    allowed=False,
                    reason=f"Blocked keystroke pattern matched: {pattern.pattern}",
                    rule_name="blocked_keystroke_pattern",
                )

        # Check blocked key combos
        upper_line = raw_line.upper().strip()
        for combo in self._config.blocked_key_combos:
            if combo.upper() == upper_line:
                return PolicyVerdict(
                    allowed=False,
                    reason=f"Blocked key combo: {combo}",
                    rule_name="blocked_key_combo",
                )

        return PolicyVerdict(allowed=True)

    def check_mouse_click(self, x: int, y: int) -> PolicyVerdict:
        """
        Validate a mouse click at (x, y).

        The click must fall within at least one allowed region.
        """
        rate_verdict = self._check_rate_limit()
        if not rate_verdict.allowed:
            return rate_verdict

        if self._config.allow_all_regions:
            return PolicyVerdict(allowed=True)

        if not self._config.allowed_regions:
            return PolicyVerdict(
                allowed=False,
                reason="No allowed click regions defined",
                rule_name="no_regions",
            )

        for region in self._config.allowed_regions:
            if region.contains(x, y):
                return PolicyVerdict(allowed=True)

        return PolicyVerdict(
            allowed=False,
            reason=f"Click at ({x}, {y}) outside all allowed regions",
            rule_name="region_violation",
        )

    def check_mouse_move(self, target_x: int, target_y: int) -> PolicyVerdict:
        """Validate a mouse movement target (lighter check than click)."""
        return self._check_rate_limit()

    def check_command(self, raw_line: str, cursor_x: int = 0, cursor_y: int = 0) -> PolicyVerdict:
        """
        Unified check for any Ducky Script command line.

        Dispatches to the appropriate specific checker based on command type.
        """
        upper = raw_line.upper().strip()

        if upper.startswith("MOUSE_CLICK"):
            return self.check_mouse_click(cursor_x, cursor_y)

        if upper.startswith("MOUSE_MOVE"):
            parts = raw_line.split()
            if len(parts) >= 3:
                try:
                    tx, ty = int(parts[1]), int(parts[2])
                    return self.check_mouse_move(tx, ty)
                except ValueError:
                    pass

        if upper.startswith("DELAY"):
            return PolicyVerdict(allowed=True)

        # All other commands (STRING, key combos, etc.)
        return self.check_keyboard(raw_line)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    def _check_rate_limit(self) -> PolicyVerdict:
        """Enforce per-second command rate limit."""
        now = time.time()
        window = 1.0  # 1-second sliding window

        # Prune old timestamps
        self._command_timestamps = [
            ts for ts in self._command_timestamps if now - ts < window
        ]

        if len(self._command_timestamps) >= self._config.max_commands_per_second:
            return PolicyVerdict(
                allowed=False,
                reason=f"Rate limit exceeded: {self._config.max_commands_per_second} cmd/s",
                rule_name="rate_limit",
            )

        self._command_timestamps.append(now)
        return PolicyVerdict(allowed=True)
