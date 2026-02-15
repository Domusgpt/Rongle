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
class TimeWindowRule:
    """Allowed time window for operation (24h format)."""
    start_hour: int = 0
    end_hour: int = 24

    def is_allowed(self) -> bool:
        """Check if current time is within the allowed window."""
        current_hour = time.localtime().tm_hour
        if self.start_hour <= self.end_hour:
            return self.start_hour <= current_hour < self.end_hour
        else:
            # Window crosses midnight (e.g. 22 to 06)
            return current_hour >= self.start_hour or current_hour < self.end_hour


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
    blocked_regions: list[ClickRegion] = field(default_factory=list)
    blocked_keystroke_patterns: list[re.Pattern] = field(default_factory=list)
    allowed_keystroke_patterns: list[re.Pattern] = field(default_factory=list)
    max_commands_per_second: float = 50.0
    max_mouse_speed_px_per_s: float = 5000.0
    allow_all_regions: bool = False
    blocked_key_combos: list[str] = field(default_factory=list)
    time_window: TimeWindowRule | None = None
    blocked_sequences: list[list[str]] = field(default_factory=list)
    semantic_safety_check: bool = False


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
    """

    def __init__(self, allowlist_path: str | Path = "rongle_operator/config/allowlist.json") -> None:
        self.allowlist_path = Path(allowlist_path)
        self._config = PolicyConfig()
        self._command_timestamps: list[float] = []
        self._command_history: list[str] = []  # Last N commands for sequence checking
        self._history_len = 5
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
        blocked_regions = [
            ClickRegion(**r) for r in raw.get("blocked_regions", [])
        ]
        blocked_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in raw.get("blocked_keystroke_patterns", [])
        ]
        allowed_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in raw.get("allowed_keystroke_patterns", [])
        ]

        time_window = None
        if "time_window" in raw:
            time_window = TimeWindowRule(
                start_hour=raw["time_window"].get("start_hour", 0),
                end_hour=raw["time_window"].get("end_hour", 24),
            )

        self._config = PolicyConfig(
            allowed_regions=regions,
            blocked_regions=blocked_regions,
            blocked_keystroke_patterns=blocked_patterns,
            allowed_keystroke_patterns=allowed_patterns,
            max_commands_per_second=raw.get("max_commands_per_second", 50.0),
            max_mouse_speed_px_per_s=raw.get("max_mouse_speed_px_per_s", 5000.0),
            allow_all_regions=raw.get("allow_all_regions", False),
            blocked_key_combos=raw.get("blocked_key_combos", []),
            time_window=time_window,
            blocked_sequences=raw.get("blocked_sequences", []),
            semantic_safety_check=raw.get("semantic_safety_check", False),
        )

        # Determine max sequence length to keep relevant history size
        max_seq_len = 0
        for seq in self._config.blocked_sequences:
            if len(seq) > max_seq_len:
                max_seq_len = len(seq)
        if max_seq_len > 0:
            self._history_len = max_seq_len

        logger.info(
            "Policy loaded: %d regions, %d blocked patterns, time_window=%s",
            len(regions), len(blocked_patterns),
            f"{time_window.start_hour}-{time_window.end_hour}" if time_window else "None",
        )

    # ------------------------------------------------------------------
    # Validation checks
    # ------------------------------------------------------------------
    def check_keyboard(self, raw_line: str) -> PolicyVerdict:
        """
        Validate a keyboard/string command line.
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
        """
        rate_verdict = self._check_rate_limit()
        if not rate_verdict.allowed:
            return rate_verdict

        # Check explicitly blocked regions first (Blocklist overrides Allowlist)
        for region in self._config.blocked_regions:
            if region.contains(x, y):
                return PolicyVerdict(
                    allowed=False,
                    reason=f"Click at ({x}, {y}) inside explicitly blocked region '{region.label}'",
                    rule_name="blocked_region",
                )

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
        """
        # Global checks

        # 1. Time Window
        if self._config.time_window and not self._config.time_window.is_allowed():
            return PolicyVerdict(
                allowed=False,
                reason="Operation blocked outside allowed time window",
                rule_name="time_window"
            )

        # 2. Sequence Checking
        # We need to normalize the command slightly to match broad patterns if needed,
        # but for now we'll do exact string prefix matching or similar.
        # We check if [history + current] ends with a blocked sequence.

        # Simplification: treat the command line as the token
        # This is primitive but satisfies the requirement for "sequence of commands"

        potential_history = self._command_history + [raw_line.strip()]
        for blocked_seq in self._config.blocked_sequences:
            # blocked_seq is e.g. ["STRING sudo", "STRING rm"]
            # Check if potential_history ends with blocked_seq
            if len(potential_history) >= len(blocked_seq):
                sub_history = potential_history[-len(blocked_seq):]
                # Compare fuzzy or exact? Let's do startsWith for now to be generous
                match = True
                for i, token in enumerate(blocked_seq):
                    # Check if the history item starts with the blocked token (ignoring case)
                    if not sub_history[i].upper().startswith(token.upper()):
                        match = False
                        break
                if match:
                    return PolicyVerdict(
                        allowed=False,
                        reason=f"Blocked command sequence detected: {blocked_seq}",
                        rule_name="blocked_sequence"
                    )

        # Dispatch to specific checkers
        upper = raw_line.upper().strip()
        verdict = PolicyVerdict(allowed=True)

        if upper.startswith("MOUSE_CLICK"):
            verdict = self.check_mouse_click(cursor_x, cursor_y)
        elif upper.startswith("MOUSE_MOVE"):
            parts = raw_line.split()
            if len(parts) >= 3:
                try:
                    tx, ty = int(parts[1]), int(parts[2])
                    verdict = self.check_mouse_move(tx, ty)
                except ValueError:
                    verdict = self.check_keyboard(raw_line)
            else:
                verdict = self.check_keyboard(raw_line)
        elif upper.startswith("DELAY"):
             verdict = PolicyVerdict(allowed=True)
        else:
            verdict = self.check_keyboard(raw_line)

        # Update history if allowed
        if verdict.allowed:
            self._command_history.append(raw_line.strip())
            if len(self._command_history) > self._history_len:
                self._command_history.pop(0)

        return verdict

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
