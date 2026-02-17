#!/usr/bin/env python3
"""
Rongle Hardware Certification Tool

Validates that the host device meets the requirements to run the Rongle Operator.
Checks for USB Gadget capabilities, Camera access, and Compute performance.
"""

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

# ANSI colors
class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

def check_usb_gadget():
    print(f"{Color.BOLD}Checking USB HID Gadget...{Color.RESET}")
    hidg0 = Path("/dev/hidg0")
    hidg1 = Path("/dev/hidg1")

    if hidg0.exists() and hidg1.exists():
        print(f"{Color.GREEN}✔ USB Gadgets found.{Color.RESET}")
        return True
    else:
        print(f"{Color.RED}✖ USB Gadgets missing.{Color.RESET}")
        print("  Ensure 'dwc2' and 'libcomposite' are loaded and ConfigFS is set up.")
        return False

def check_camera():
    print(f"{Color.BOLD}Checking Camera...{Color.RESET}")
    try:
        import cv2
    except ImportError:
        print(f"{Color.RED}✖ OpenCV not installed.{Color.RESET}")
        return False

    # Check V4L2 devices
    devices = list(Path("/dev").glob("video*"))
    if not devices:
        print(f"{Color.YELLOW}⚠ No local /dev/video devices found.{Color.RESET}")
        print("  (This is fine if using Network Stream)")
        return True # Soft pass

    # Try opening the first one
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            h, w = frame.shape[:2]
            print(f"{Color.GREEN}✔ Camera 0 is working ({w}x{h}).{Color.RESET}")
            cap.release()
            return True

    print(f"{Color.RED}✖ Failed to capture frame from Camera 0.{Color.RESET}")
    return False

def check_compute():
    print(f"{Color.BOLD}Checking Compute Performance...{Color.RESET}")
    start = time.time()
    # Simple CPU stress: 1 million squares
    _ = [x**2 for x in range(1_000_000)]
    duration = time.time() - start

    score = 1.0 / duration
    print(f"  Benchmark Score: {score:.2f}")

    if score > 5.0:
        print(f"{Color.GREEN}✔ CPU is adequate.{Color.RESET}")
        return True
    else:
        print(f"{Color.YELLOW}⚠ CPU might be slow for local CNN inference.{Color.RESET}")
        return True # Soft pass

def main():
    print(f"{Color.BOLD}Rongle Hardware Certification{Color.RESET}")
    print("=============================")

    report = {
        "timestamp": time.time(),
        "platform": platform.uname()._asdict(),
        "usb_gadget": check_usb_gadget(),
        "camera": check_camera(),
        "compute": check_compute(),
    }

    # Save report
    with open("hardware_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\nReport saved to hardware_report.json")

    if report["usb_gadget"]:
        print(f"\n{Color.GREEN}Result: HARDWARE CERTIFIED{Color.RESET}")
        sys.exit(0)
    else:
        print(f"\n{Color.YELLOW}Result: SOFTWARE ONLY (Simulation Mode){Color.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
