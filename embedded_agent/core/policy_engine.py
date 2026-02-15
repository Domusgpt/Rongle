import json
import os

class PolicyEngine:
    def __init__(self, config_path='config/allowlist.json'):
        self.config_path = config_path
        self.blocked_keywords = []
        self.allowed_regions = []
        self._load_policy()

    def _load_policy(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.blocked_keywords = data.get('blocked_keywords', [])
                    self.allowed_regions = data.get('allowed_regions', [])
            except json.JSONDecodeError:
                print("[Policy] Error parsing allowlist.json. Using defaults.")
                self.blocked_keywords = ["rm -rf", "format", "mkfs"]
        else:
            # Default safe policy
            print("[Policy] No allowlist found. Using default safe mode.")
            self.blocked_keywords = ["rm -rf", "mkfs", "dd if=", "> /dev/sda"]
            self.allowed_regions = [] # Empty means all allowed if not restricted

    def validate_command(self, cmd_line):
        """
        Returns (bool, reason)
        """
        # 1. Keyword Scanning (Basic DLP)
        for keyword in self.blocked_keywords:
            if keyword in cmd_line:
                return False, f"Blocked keyword detected: '{keyword}'"
        
        # 2. Geometric Constraints (Geo-fencing for Mouse)
        if cmd_line.startswith("MOUSE_MOVE"):
            try:
                parts = cmd_line.split(' ')
                coords = parts[1].split(',')
                x, y = int(coords[0]), int(coords[1])
                
                # If regions are defined, movement MUST be within one of them
                if self.allowed_regions:
                    in_region = False
                    for r in self.allowed_regions:
                        # Assuming r has x, y, w, h
                        if (r['x'] <= x <= r['x'] + r['w']) and (r['y'] <= y <= r['y'] + r['h']):
                            in_region = True
                            break
                    if not in_region:
                        return False, f"Movement to ({x},{y}) is outside allowed regions."
            except (IndexError, ValueError):
                return False, "Invalid MOUSE_MOVE format"

        return True, "Allowed"
