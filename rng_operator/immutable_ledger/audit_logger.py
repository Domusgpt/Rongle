"""
AuditLogger — Tamper-evident logging with Merkle (hash) chain.

Every action is recorded as an entry whose hash incorporates:
  - Timestamp
  - Action description
  - Screenshot hash (SHA-256 of the frame at time of action)
  - Previous entry's hash

This creates a cryptographic chain: if any entry is modified or deleted,
all subsequent hashes break, making tampering detectable even if the
device is physically seized.

The log is persisted to a secure partition as append-only JSONL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Genesis hash — the "previous hash" for the very first entry
_GENESIS_HASH = "0" * 64


@dataclass
class AuditEntry:
    """A single immutable log entry in the Merkle chain."""
    sequence: int
    timestamp: float
    timestamp_iso: str
    action: str
    action_detail: str
    screenshot_hash: str        # SHA-256 hex of the frame at time of action
    previous_hash: str          # hash of entry N-1
    entry_hash: str             # SHA-256(timestamp + action + screenshot_hash + previous_hash)
    policy_verdict: str = ""    # "allowed" | "blocked" | ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


class AuditLogger:
    """
    Append-only, hash-chained audit logger.

    Usage::

        audit = AuditLogger("/mnt/secure/audit.jsonl")
        audit.log("MOUSE_CLICK LEFT", screenshot_hash="abc123...")
        audit.verify_chain()  # raises if tampered

    Parameters
    ----------
    log_path : str | Path
        Path to the JSONL log file (append-only).
    sync_interval : int
        Flush to disk every N entries (0 = flush every entry).
    """

    def __init__(
        self,
        log_path: str | Path = "/mnt/secure/audit.jsonl",
        sync_interval: int = 0,
    ) -> None:
        self.log_path = Path(log_path)
        self.sync_interval = sync_interval
        self._lock = threading.Lock()
        self._sequence = 0
        self._last_hash = _GENESIS_HASH
        self._buffer: list[AuditEntry] = []
        self._fd = None

        self._init_log_file()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
    def _init_log_file(self) -> None:
        """Open or resume the log file. Replay existing entries to restore chain state."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        if self.log_path.exists() and self.log_path.stat().st_size > 0:
            self._replay_existing()

        self._fd = open(self.log_path, "a")
        logger.info(
            "AuditLogger initialized: %s (seq=%d, last_hash=%s…)",
            self.log_path, self._sequence, self._last_hash[:16],
        )

    def _replay_existing(self) -> None:
        """Read existing log to restore sequence counter and chain head hash."""
        with open(self.log_path, "r") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self._sequence = data["sequence"]
                    self._last_hash = data["entry_hash"]
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.error("Corrupt log entry at line %d: %s", line_no, exc)
                    raise RuntimeError(
                        f"Audit log corrupted at line {line_no}. "
                        "Chain integrity cannot be guaranteed."
                    ) from exc

        logger.info("Replayed %d existing audit entries", self._sequence)

    # ------------------------------------------------------------------
    # Core hashing
    # ------------------------------------------------------------------
    @staticmethod
    def compute_hash(
        timestamp: float,
        action: str,
        screenshot_hash: str,
        previous_hash: str,
    ) -> str:
        """
        Compute the Merkle chain hash for an entry.

        ``hash_N = SHA256(timestamp || action || screenshot_hash || hash_{N-1})``
        """
        preimage = f"{timestamp:.6f}|{action}|{screenshot_hash}|{previous_hash}"
        return hashlib.sha256(preimage.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def log(
        self,
        action: str,
        screenshot_hash: str = "",
        action_detail: str = "",
        policy_verdict: str = "",
        metadata: dict | None = None,
    ) -> AuditEntry:
        """
        Record an action in the tamper-evident log.

        Parameters
        ----------
        action : str
            Short action identifier (e.g., "STRING hello", "MOUSE_CLICK LEFT").
        screenshot_hash : str
            SHA-256 hex digest of the screenshot at time of action.
        action_detail : str
            Optional extended description.
        policy_verdict : str
            "allowed", "blocked", or empty.
        metadata : dict
            Arbitrary metadata to attach.

        Returns
        -------
        AuditEntry
            The newly created log entry.
        """
        screenshot_hash = screenshot_hash or ("0" * 64)
        with self._lock:
            self._sequence += 1
            ts = round(time.time(), 6)

            entry_hash = self.compute_hash(
                ts, action, screenshot_hash, self._last_hash
            )

            entry = AuditEntry(
                sequence=self._sequence,
                timestamp=ts,
                timestamp_iso=time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.gmtime(ts)
                ) + f".{int((ts % 1) * 1000):03d}Z",
                action=action,
                action_detail=action_detail,
                screenshot_hash=screenshot_hash,
                previous_hash=self._last_hash,
                entry_hash=entry_hash,
                policy_verdict=policy_verdict,
                metadata=metadata or {},
            )

            self._last_hash = entry_hash
            self._write_entry(entry)

        return entry

    def _write_entry(self, entry: AuditEntry) -> None:
        """Append entry to the log file."""
        if self._fd is None:
            return
        self._fd.write(entry.to_json() + "\n")
        self._buffer.append(entry)

        if self.sync_interval == 0 or len(self._buffer) >= self.sync_interval:
            self._fd.flush()
            os.fsync(self._fd.fileno())
            self._buffer.clear()

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    def verify_chain(self) -> bool:
        """
        Verify the entire Merkle chain from genesis to HEAD.

        Returns True if the chain is intact.  Raises ``RuntimeError``
        with details if any entry has been tampered with.
        """
        prev_hash = _GENESIS_HASH

        with open(self.log_path, "r") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                data = json.loads(line)
                expected_hash = self.compute_hash(
                    data["timestamp"],
                    data["action"],
                    data["screenshot_hash"],
                    data["previous_hash"],
                )

                # Verify previous_hash linkage
                if data["previous_hash"] != prev_hash:
                    raise RuntimeError(
                        f"Chain broken at entry {line_no}: "
                        f"previous_hash mismatch "
                        f"(expected {prev_hash[:16]}…, got {data['previous_hash'][:16]}…)"
                    )

                # Verify entry_hash integrity
                if data["entry_hash"] != expected_hash:
                    raise RuntimeError(
                        f"Tampered entry at line {line_no}: "
                        f"hash mismatch "
                        f"(expected {expected_hash[:16]}…, got {data['entry_hash'][:16]}…)"
                    )

                prev_hash = data["entry_hash"]

        logger.info("Chain verification PASSED (%d entries)", line_no)
        return True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def close(self) -> None:
        """Flush and close the log file."""
        if self._fd is not None:
            self._fd.flush()
            os.fsync(self._fd.fileno())
            self._fd.close()
            self._fd = None

    def __enter__(self) -> AuditLogger:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def chain_head(self) -> str:
        """Current chain HEAD hash."""
        return self._last_hash

    @property
    def entry_count(self) -> int:
        """Total entries logged in this session."""
        return self._sequence
