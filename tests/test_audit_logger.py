"""Tests for AuditLogger — Merkle hash chain, verification, persistence."""

import hashlib
import json
import time

import pytest
from rongle_operator.immutable_ledger.audit_logger import AuditLogger, AuditEntry, _GENESIS_HASH


# ---------------------------------------------------------------------------
# Hash computation
# ---------------------------------------------------------------------------
class TestHashComputation:
    def test_genesis_hash_is_64_zeros(self):
        assert _GENESIS_HASH == "0" * 64
        assert len(_GENESIS_HASH) == 64

    def test_compute_hash_deterministic(self):
        h1 = AuditLogger.compute_hash(1000.0, "TEST", "abc123", "0" * 64)
        h2 = AuditLogger.compute_hash(1000.0, "TEST", "abc123", "0" * 64)
        assert h1 == h2

    def test_compute_hash_is_sha256_hex(self):
        h = AuditLogger.compute_hash(1000.0, "TEST", "abc", "0" * 64)
        assert len(h) == 64
        int(h, 16)  # should not raise — valid hex

    def test_compute_hash_format(self):
        """Verify the hash preimage format matches the documented formula."""
        ts = 1706000000.123456
        action = "CLICK"
        ss_hash = "a" * 64
        prev_hash = "b" * 64

        expected_preimage = f"{ts:.6f}||{action}||{ss_hash}||{prev_hash}"
        expected_hash = hashlib.sha256(expected_preimage.encode("utf-8")).hexdigest()

        actual = AuditLogger.compute_hash(ts, action, ss_hash, prev_hash)
        assert actual == expected_hash

    def test_different_inputs_different_hash(self):
        h1 = AuditLogger.compute_hash(1000.0, "ACTION_A", "x", "0" * 64)
        h2 = AuditLogger.compute_hash(1000.0, "ACTION_B", "x", "0" * 64)
        assert h1 != h2

    def test_chain_linkage(self):
        """Each hash depends on the previous entry's hash."""
        h1 = AuditLogger.compute_hash(1.0, "A", "x", _GENESIS_HASH)
        h2 = AuditLogger.compute_hash(2.0, "B", "y", h1)
        h3 = AuditLogger.compute_hash(3.0, "C", "z", h2)
        # Changing h1 would cascade
        h1_tampered = AuditLogger.compute_hash(1.0, "A_MODIFIED", "x", _GENESIS_HASH)
        assert h1_tampered != h1
        h2_from_tampered = AuditLogger.compute_hash(2.0, "B", "y", h1_tampered)
        assert h2_from_tampered != h2


# ---------------------------------------------------------------------------
# Logging entries
# ---------------------------------------------------------------------------
class TestLogging:
    def test_log_returns_entry(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        entry = audit.log("TEST_ACTION", screenshot_hash="abc123")
        assert isinstance(entry, AuditEntry)
        assert entry.sequence == 1
        assert entry.action == "TEST_ACTION"
        assert entry.screenshot_hash == "abc123"
        audit.close()

    def test_sequence_increments(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        e1 = audit.log("A")
        e2 = audit.log("B")
        e3 = audit.log("C")
        assert e1.sequence == 1
        assert e2.sequence == 2
        assert e3.sequence == 3
        audit.close()

    def test_chain_head_updates(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        assert audit.chain_head == _GENESIS_HASH
        e1 = audit.log("A")
        assert audit.chain_head == e1.entry_hash
        e2 = audit.log("B")
        assert audit.chain_head == e2.entry_hash
        audit.close()

    def test_previous_hash_linkage(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        e1 = audit.log("A")
        e2 = audit.log("B")
        assert e1.previous_hash == _GENESIS_HASH
        assert e2.previous_hash == e1.entry_hash
        audit.close()

    def test_entry_count(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        assert audit.entry_count == 0
        audit.log("A")
        audit.log("B")
        assert audit.entry_count == 2
        audit.close()

    def test_empty_screenshot_hash_defaults(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        entry = audit.log("TEST")
        assert entry.screenshot_hash == "0" * 64
        audit.close()

    def test_metadata_stored(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        entry = audit.log("TEST", metadata={"key": "value"})
        assert entry.metadata == {"key": "value"}
        audit.close()

    def test_policy_verdict_stored(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        entry = audit.log("TEST", policy_verdict="allowed")
        assert entry.policy_verdict == "allowed"
        audit.close()


# ---------------------------------------------------------------------------
# Persistence (JSONL file)
# ---------------------------------------------------------------------------
class TestPersistence:
    def test_file_created(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        audit.log("TEST")
        audit.close()
        from pathlib import Path
        assert Path(audit_log_path).exists()

    def test_entries_in_jsonl(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        audit.log("A")
        audit.log("B")
        audit.close()

        from pathlib import Path
        lines = Path(audit_log_path).read_text().strip().splitlines()
        assert len(lines) == 2
        data1 = json.loads(lines[0])
        data2 = json.loads(lines[1])
        assert data1["action"] == "A"
        assert data2["action"] == "B"
        assert data1["sequence"] == 1
        assert data2["sequence"] == 2


# ---------------------------------------------------------------------------
# Chain verification
# ---------------------------------------------------------------------------
class TestChainVerification:
    def test_valid_chain_passes(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        for i in range(10):
            audit.log(f"ACTION_{i}", screenshot_hash=f"hash_{i}")
        audit.close()

        # Re-open to verify
        audit2 = AuditLogger(audit_log_path)
        assert audit2.verify_chain() is True
        audit2.close()

    def test_tampered_entry_fails(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        for i in range(5):
            audit.log(f"ACTION_{i}")
        audit.close()

        # Tamper with the file: modify the action in entry 3
        from pathlib import Path
        lines = Path(audit_log_path).read_text().strip().splitlines()
        tampered = json.loads(lines[2])
        tampered["action"] = "TAMPERED_ACTION"
        lines[2] = json.dumps(tampered, separators=(",", ":"))
        Path(audit_log_path).write_text("\n".join(lines) + "\n")

        audit2 = AuditLogger.__new__(AuditLogger)
        audit2.log_path = Path(audit_log_path)
        with pytest.raises(RuntimeError, match="hash mismatch|Tampered"):
            audit2.verify_chain()

    def test_deleted_entry_fails(self, audit_log_path):
        audit = AuditLogger(audit_log_path)
        for i in range(5):
            audit.log(f"ACTION_{i}")
        audit.close()

        # Delete entry 2 (middle of chain)
        from pathlib import Path
        lines = Path(audit_log_path).read_text().strip().splitlines()
        del lines[2]
        Path(audit_log_path).write_text("\n".join(lines) + "\n")

        audit2 = AuditLogger.__new__(AuditLogger)
        audit2.log_path = Path(audit_log_path)
        with pytest.raises(RuntimeError):
            audit2.verify_chain()


# ---------------------------------------------------------------------------
# Resume after restart
# ---------------------------------------------------------------------------
class TestResume:
    def test_resume_continues_sequence(self, audit_log_path):
        audit1 = AuditLogger(audit_log_path)
        audit1.log("A")
        audit1.log("B")
        last_hash = audit1.chain_head
        audit1.close()

        # Resume
        audit2 = AuditLogger(audit_log_path)
        assert audit2.entry_count == 2
        assert audit2.chain_head == last_hash
        e3 = audit2.log("C")
        assert e3.sequence == 3
        assert e3.previous_hash == last_hash
        audit2.close()

    def test_resume_chain_still_valid(self, audit_log_path):
        audit1 = AuditLogger(audit_log_path)
        audit1.log("A")
        audit1.log("B")
        audit1.close()

        audit2 = AuditLogger(audit_log_path)
        audit2.log("C")
        audit2.log("D")
        assert audit2.verify_chain() is True
        audit2.close()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------
class TestContextManager:
    def test_context_manager_closes(self, audit_log_path):
        with AuditLogger(audit_log_path) as audit:
            audit.log("TEST")
        # File should be closed — verify by reading
        from pathlib import Path
        content = Path(audit_log_path).read_text()
        assert "TEST" in content


# ---------------------------------------------------------------------------
# AuditEntry serialization
# ---------------------------------------------------------------------------
class TestAuditEntry:
    def test_to_dict(self):
        entry = AuditEntry(
            sequence=1, timestamp=1000.0, timestamp_iso="2024-01-01T00:00:00.000Z",
            action="TEST", action_detail="detail", screenshot_hash="abc",
            previous_hash="0" * 64, entry_hash="def",
        )
        d = entry.to_dict()
        assert d["sequence"] == 1
        assert d["action"] == "TEST"

    def test_to_json_parseable(self):
        entry = AuditEntry(
            sequence=1, timestamp=1000.0, timestamp_iso="2024-01-01T00:00:00.000Z",
            action="TEST", action_detail="", screenshot_hash="abc",
            previous_hash="0" * 64, entry_hash="def",
        )
        j = entry.to_json()
        parsed = json.loads(j)
        assert parsed["sequence"] == 1
