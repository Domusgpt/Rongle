# Engineering Improvement Proposals

This document proposes technical solutions for the issues identified in `ENGINEERING_CRITIQUE.md`.

## 1. Reliability: Persistent Session Manager

**Target:** `rongle_operator/session_manager.py`

Implement a `SessionManager` class to persist agent state.

```python
import sqlite3
from dataclasses import dataclass

@dataclass
class AgentSession:
    goal: str
    step_index: int
    context_history: list[str]
    last_active: float

class SessionManager:
    def __init__(self, db_path="state.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS session (
                key TEXT PRIMARY KEY,
                goal TEXT,
                step_index INTEGER,
                context_history TEXT,
                last_active REAL
            )
        """)

    def save_session(self, session: AgentSession):
        # ... logic to upsert session ...
        pass

    def load_session(self) -> AgentSession | None:
        # ... logic to load ...
        pass
```

**Integration:** Update `main.py` to check `SessionManager.load_session()` on startup.

## 2. Scalability: Batch Telemetry Upload

**Target:** `rongle_operator/portal_client.py`

Modify `sync_audit` to use a buffer.

```python
class PortalClient:
    def __init__(self, ...):
        self._audit_buffer = []
        self._flush_threshold = 10

    async def log_audit(self, entry: dict):
        self._audit_buffer.append(entry)
        if len(self._audit_buffer) >= self._flush_threshold:
            await self.flush_audit()

    async def flush_audit(self):
        if not self._audit_buffer: return
        try:
            await self._post("/api/audit/sync", {"entries": self._audit_buffer})
            self._audit_buffer = []
        except Exception:
            # logic to keep buffer and retry later
            pass
```

## 3. Security: Environment Validation

**Target:** `rongle_operator/main.py` (Pre-flight check)

```python
def check_environment(settings: Settings):
    required_paths = [
        settings.video_device,
        settings.hid_keyboard_dev,
        Path(settings.audit_log_path).parent
    ]
    for p in required_paths:
        if not Path(p).exists():
            raise RuntimeError(f"Critical path missing: {p}")
```

## 4. Vision: ONNX Runtime Integration

**Target:** `rongle_operator/visual_cortex/fast_detector.py`

Replace stub with `onnxruntime`.

```python
import onnxruntime as ort

class FastDetector:
    def __init__(self, model_path: str):
        self.session = ort.InferenceSession(model_path)

    def detect(self, frame: np.ndarray):
        # Preprocess: resize to 300x300, normalize
        # Run inference
        # Postprocess: NMS
        pass
```

---
[Back to Documentation Index](INDEX.md)
