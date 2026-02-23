import time
import math
import random
import struct
import sys

class HygienicActuator:
    def __init__(self, keyboard_dev='/dev/hidg0', mouse_dev='/dev/hidg1'):
        self.keyboard_dev_path = keyboard_dev
        self.mouse_dev_path = mouse_dev
        self.current_x = 0
        self.current_y = 0
        self.screen_w = 1920
        self.screen_h = 1080

        # Verify access to HID gadgets (Simulation mode fallback)
        try:
            self.kb_fd = open(self.keyboard_dev_path, 'wb')
            self.mouse_fd = open(self.mouse_dev_path, 'wb')
            self.simulation_mode = False
        except IOError:
            print("[Actuator] HID gadgets not found. Running in SIMULATION mode.")
            self.simulation_mode = True

    def _bezier_curve(self, start, end, control1, control2, steps):
        """Generates points along a cubic bezier curve for mouse movement."""
        path = []
        for i in range(steps + 1):
            t = i / steps
            x = (1-t)**3 * start[0] + 3*(1-t)**2 * t * control1[0] + \
                3*(1-t) * t**2 * control2[0] + t**3 * end[0]
            y = (1-t)**3 * start[1] + 3*(1-t)**2 * t * control1[1] + \
                3*(1-t) * t**2 * control2[1] + t**3 * end[1]
            path.append((int(x), int(y)))
        return path

    def move_mouse_humanized(self, target_x, target_y, duration_sec=0.5):
        """
        Moves mouse to target using a human-like arc (Bezier curve)
        with variable speed to simulate hand mass/jitter.
        """
        start = (self.current_x, self.current_y)
        end = (target_x, target_y)

        # Randomize control points to create arcs/imperfections
        dist = math.hypot(end[0] - start[0], end[1] - start[1])
        offset = dist * 0.2  # Arc magnitude

        # Control points deviated from the straight line
        c1 = (start[0] + random.uniform(-offset, offset),
              start[1] + random.uniform(-offset, offset))
        c2 = (end[0] + random.uniform(-offset, offset),
              end[1] + random.uniform(-offset, offset))

        # Calculate steps based on 60Hz update rate
        steps = max(10, int(duration_sec * 60))
        points = self._bezier_curve(start, end, c1, c2, steps)

        for p in points:
            dx = p[0] - self.current_x
            dy = p[1] - self.current_y

            # Send relative movement packet
            self._send_mouse_report(buttons=0, x=dx, y=dy)
            self.current_x, self.current_y = p[0], p[1]

            # Non-uniform sleep to mimic nervous system processing (Motor noise)
            time.sleep(duration_sec / steps + random.uniform(-0.001, 0.001))

    def execute_ducky_script(self, script):
        """Parses high-level Ducky commands."""
        lines = script.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('REM'):
                continue

            parts = line.split(' ', 1)
            cmd = parts[0].upper()

            if cmd == 'DELAY':
                time.sleep(int(parts[1]) / 1000.0)
            elif cmd == 'STRING':
                self._type_string(parts[1])
            elif cmd == 'ENTER':
                self._press_key(40) # HID Usage ID for Enter
            elif cmd == 'GUI':
                # Simplified GUI key handling
                self._press_key(227) # GUI Modifier
            elif cmd == 'MOUSE_MOVE':
                try:
                    coords = parts[1].split(',')
                    self.move_mouse_humanized(int(coords[0]), int(coords[1]))
                except IndexError:
                    print("[Actuator] Error parsing MOUSE_MOVE")

    def _send_mouse_report(self, buttons, x, y):
        if self.simulation_mode:
            # print(f"[SIM] Mouse Move: dx={x}, dy={y}")
            return

        # Clamp values to signed byte range (-127 to 127)
        x = max(-127, min(127, x))
        y = max(-127, min(127, y))
        # Structure: Buttons, X, Y, Wheel
        try:
            report = struct.pack('BBbb', buttons, x, y, 0)
            self.mouse_fd.write(report)
            self.mouse_fd.flush()
        except Exception as e:
            print(f"[Actuator] HID Write Error: {e}")

    def _type_string(self, text):
        if self.simulation_mode:
            print(f"[SIM] Typing: {text}")
            return

        # Simplified placeholder for char-to-hid mapping
        for char in text:
            # self._send_key_report(...)
            time.sleep(random.uniform(0.02, 0.08)) # Fast typing jitter

    def _press_key(self, usage_id):
        if self.simulation_mode:
            print(f"[SIM] Key Press: {usage_id}")
            return
        # Implementation of key press/release report
        pass
