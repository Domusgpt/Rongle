import hashlib
import json
import time
import os

class ImmutableLedger:
    def __init__(self, log_dir='logs', log_file='audit_chain.log'):
        self.log_dir = log_dir
        self.log_path = os.path.join(log_dir, log_file)
        self._ensure_log_dir()
        self.prev_hash = self._get_last_hash()

    def _ensure_log_dir(self):
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def _get_last_hash(self):
        """Retrieves the hash of the last entry from the file to maintain the chain."""
        if not os.path.exists(self.log_path):
            return "0" * 64 # Genesis hash
        
        try:
            with open(self.log_path, 'r') as f:
                lines = f.readlines()
                if not lines: return "0" * 64
                # Parse the last line to get its hash
                last_entry = json.loads(lines[-1])
                return last_entry.get('current_hash', "0" * 64)
        except Exception:
            return "ERROR_READING_CHAIN"

    def log_action(self, action_type, command, screenshot_hash="N/A"):
        timestamp = time.time()
        
        # 1. Construct the payload for hashing
        # Structure: Previous Hash + Timestamp + Action Details + Evidence Hash
        # This creates the dependency on the previous state.
        payload = f"{self.prev_hash}{timestamp}{action_type}{command}{screenshot_hash}"
        
        # 2. Generate SHA-256 Hash
        current_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        
        entry = {
            "index": self._get_index(),
            "timestamp": timestamp,
            "prev_hash": self.prev_hash,
            "action_type": action_type,
            "command": command,
            "screenshot_hash": screenshot_hash,
            "current_hash": current_hash
        }
        
        # 3. Atomic append to file
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(entry) + "\n")
            
        print(f"[Ledger] Recorded: {action_type} | Hash: {current_hash[:8]}...")
        
        # 4. Update memory state for next entry
        self.prev_hash = current_hash
        return current_hash

    def _get_index(self):
        if not os.path.exists(self.log_path): return 0
        with open(self.log_path, 'r') as f:
            return sum(1 for _ in f)
