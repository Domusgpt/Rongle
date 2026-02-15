#!/usr/bin/env python3
"""
Rongle Hardware Certification Tool
-----------------------------------
Validates that the host hardware (Pi, Android, etc.) meets the requirements
for stable operation. Specifically tests:
1. USB Gadget API (/dev/hidg*) availability and write latency.
2. Camera (/dev/video*) availability, resolution, and FPS.
3. System Load (CPU/RAM) during stress.

Usage:
    sudo python3 scripts/certify_hardware.py
"""

import os
import sys
import time
import json
import logging
import platform
import subprocess
import cv2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("hardware_cert")

REPORT_FILE = "hardware_report.json"

def check_hid_gadgets():
    """Check existence and write performance of HID gadgets."""
    gadgets = ["/dev/hidg0", "/dev/hidg1"]
    results = {}

    for g in gadgets:
        if not os.path.exists(g):
            logger.error(f"Missing HID gadget: {g}")
            results[g] = {"available": False}
            continue

        logger.info(f"Testing write performance on {g}...")
        try:
            # Open in binary write mode
            # Using non-blocking might be safer but we want to test stability
            with open(g, "wb") as f:
                start_time = time.time()
                # Send 100 null reports
                count = 100
                for _ in range(count):
                    # Standard keyboard report is 8 bytes
                    f.write(b'\x00' * 8)
                    f.flush()
                duration = time.time() - start_time
                avg_latency = (duration / count) * 1000 # ms

                logger.info(f"{g}: {count} writes in {duration:.4f}s (Avg: {avg_latency:.2f}ms)")
                results[g] = {
                    "available": True,
                    "avg_write_latency_ms": avg_latency,
                    "status": "PASS" if avg_latency < 10 else "WARN" # <10ms is good
                }
        except Exception as e:
            logger.error(f"Write failed on {g}: {e}")
            results[g] = {
                "available": True,
                "write_error": str(e),
                "status": "FAIL"
            }

    return results

def check_camera():
    """Check camera availability and performance."""
    results = {}
    # Try typical indexes
    for idx in range(4):
        dev_path = f"/dev/video{idx}"
        if not os.path.exists(dev_path):
            continue

        logger.info(f"Testing camera at {dev_path}...")
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            logger.warning(f"Could not open {dev_path}")
            results[dev_path] = {"available": True, "openable": False}
            continue

        # Check default resolution
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps_prop = cap.get(cv2.CAP_PROP_FPS)

        # Capture performance test
        start_time = time.time()
        frames = 30
        captured = 0
        for _ in range(frames):
            ret, frame = cap.read()
            if ret:
                captured += 1
        duration = time.time() - start_time
        actual_fps = captured / duration if duration > 0 else 0

        cap.release()

        logger.info(f"{dev_path}: {w}x{h} @ {actual_fps:.2f} FPS (Prop: {fps_prop})")
        results[dev_path] = {
            "available": True,
            "openable": True,
            "resolution": f"{int(w)}x{int(h)}",
            "actual_fps": actual_fps,
            "status": "PASS" if actual_fps > 10 else "WARN"
        }

    if not results:
        logger.error("No video devices found in /dev/video[0-3]")

    return results

def check_system_resources():
    """Check RAM and CPU info."""
    info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version()
    }

    try:
        # Memory
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if "MemTotal" in line:
                    info["mem_total_kb"] = int(line.split()[1])
                if "MemAvailable" in line:
                    info["mem_available_kb"] = int(line.split()[1])
                    break
    except FileNotFoundError:
        pass

    return info

def main():
    logger.info("Starting Hardware Certification...")

    report = {
        "timestamp": time.time(),
        "system": check_system_resources(),
        "hid_gadgets": check_hid_gadgets(),
        "camera": check_camera()
    }

    # Analyze overall status
    passed = True
    for g, res in report["hid_gadgets"].items():
        if res.get("status") == "FAIL" or not res.get("available"):
            passed = False

    # Camera checks (soft fail if none, strictly speaking we need one)
    if not report["camera"]:
        passed = False # Fail if no camera? Or just warn?
        report["camera_status"] = "FAIL: No cameras found"
    else:
        # Check if at least one passed
        if not any(c.get("status") == "PASS" for c in report["camera"].values()):
             passed = False
             report["camera_status"] = "FAIL: No suitable camera"
        else:
             report["camera_status"] = "PASS"

    report["certification_result"] = "PASS" if passed else "FAIL"

    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Report generated: {REPORT_FILE}")
    logger.info(f"Certification Result: {report['certification_result']}")

    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
