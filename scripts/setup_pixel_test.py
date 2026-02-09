#!/usr/bin/env python3
"""
Pixel Test Setup Wizard

Automates the configuration and launching of the Rongle environment for testing
with a Pixel phone (via IP Webcam) and a PC.

Usage:
    python3 scripts/setup_pixel_test.py
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

# ANSI colors
class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

def print_step(msg):
    print(f"\n{Color.CYAN}{Color.BOLD}>>> {msg}{Color.RESET}")

def print_success(msg):
    print(f"{Color.GREEN}✔ {msg}{Color.RESET}")

def print_warning(msg):
    print(f"{Color.YELLOW}⚠ {msg}{Color.RESET}")

def print_error(msg):
    print(f"{Color.RED}✖ {msg}{Color.RESET}")

def check_command(cmd, name=None):
    name = name or cmd
    if shutil.which(cmd) is None:
        print_error(f"{name} is not installed or not in PATH.")
        return False
    print_success(f"{name} found.")
    return True

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't need to be reachable
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def scan_for_ipwebcam(subnet_prefix):
    print_step(f"Scanning for IP Webcam on {subnet_prefix}.* (Port 8080)...")
    found = []

    # Fast parallel scan (conceptually) - strictly sequential here for simplicity/compatibility
    # For a robust scan we'd use nmap, but we want zero external dependencies if possible.
    # We'll just scan the local IP and a few likely neighbors or ask the user.

    # Actually, scanning a whole /24 sequentially is slow in Python.
    # Let's prompt the user first, with a default guess.
    return []

def main():
    print(f"{Color.BOLD}Rongle Pixel Test Wizard{Color.RESET}")
    print("========================")

    # 1. Check Prerequisites
    print_step("Checking Environment")
    if not check_command("node", "Node.js"):
        sys.exit(1)
    if not check_command("npm", "npm"):
        sys.exit(1)
    if not check_command("python3", "Python 3"):
        sys.exit(1)

    # 2. Configuration
    print_step("Configuration")
    local_ip = get_local_ip()
    print(f"Your PC IP: {Color.BOLD}{local_ip}{Color.RESET}")

    phone_ip = input(f"Enter Pixel Phone IP (from IP Webcam app) [e.g. 192.168.1.X]: ").strip()
    if not phone_ip:
        print_error("Phone IP is required.")
        sys.exit(1)

    video_url = f"http://{phone_ip}:8080/video"
    print(f"Video URL: {video_url}")

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        gemini_key = input("Enter Gemini API Key: ").strip()
        if not gemini_key:
            print_warning("No API key provided. Agent will fail to plan.")

    # Generate Settings
    settings_path = Path("rng_operator/config/settings.json")
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    settings = {
        "video_device": video_url,
        "screen_width": 1920,
        "screen_height": 1080,
        "vlm_model": "gemini-3.0-pro",
        "capture_fps": 15, # Lower FPS for network
        "humanizer_jitter_sigma": 1.5
    }

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    print_success(f"Generated {settings_path}")

    # 3. Install Backend Deps
    print_step("Installing Backend Dependencies")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "rng_operator/requirements.txt"])
    print_success("Backend dependencies installed.")

    # 4. Install Frontend Deps
    print_step("Installing Frontend Dependencies")
    subprocess.check_call(["npm", "install"], shell=True) # shell=True for windows compat
    print_success("Frontend dependencies installed.")

    print(f"\n{Color.CYAN}Tip: You can also build a standalone Android APK to run the frontend without this PC server.{Color.RESET}")
    print(f"     See: docs/android/BUILDING_APK.md\n")

    # 5. Launch
    print_step("Launching System")
    print(f"{Color.YELLOW}Press Ctrl+C to stop all services.{Color.RESET}")

    env = os.environ.copy()
    if gemini_key:
        env["GEMINI_API_KEY"] = gemini_key

    procs = []
    try:
        # Backend (Dry Run)
        print("Starting Backend (Dry Run)...")
        backend_cmd = [sys.executable, "-m", "rng_operator.main", "--dry-run", "--software-estop"]
        procs.append(subprocess.Popen(backend_cmd, env=env))

        # Frontend
        print("Starting Frontend...")
        frontend_cmd = ["npm", "run", "dev", "--", "--host"]
        procs.append(subprocess.Popen(frontend_cmd, shell=True)) # npm creates subshells

        # Wait
        while True:
            time.sleep(1)
            # Check if processes are alive
            if procs[0].poll() is not None:
                print_error("Backend crashed!")
                break

    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        for p in procs:
            p.terminate()
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
        print_success("Shutdown complete.")

if __name__ == "__main__":
    main()
