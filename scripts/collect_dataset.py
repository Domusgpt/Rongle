#!/usr/bin/env python3
"""
Rongle Dataset Collector

Tool to capture training images for the CNN "Reflex Cortex".
Supports local V4L2 capture or remote IP Webcam streams.
"""

import argparse
import os
import sys
import time
import cv2
import json
from pathlib import Path
from datetime import datetime

# ANSI colors
class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

def main():
    parser = argparse.ArgumentParser(description="Capture frames for training")
    parser.add_argument("--device", type=str, default="/dev/video0", help="V4L2 device or URL")
    parser.add_argument("--output", type=str, default="rng_operator/training/datasets/raw", help="Output directory")
    parser.add_argument("--interval", type=float, default=0, help="Auto-capture interval (0=manual)")
    args = parser.parse_args()

    # Determine backend
    device = args.device
    backend = cv2.CAP_ANY
    if str(device).startswith("/dev/"):
        backend = cv2.CAP_V4L2
    elif "://" in str(device):
        backend = cv2.CAP_FFMPEG

    print(f"{Color.CYAN}Opening capture device: {device}...{Color.RESET}")
    cap = cv2.VideoCapture(device, backend)

    if not cap.isOpened():
        print(f"{Color.RED}Failed to open device.{Color.RESET}")
        sys.exit(1)

    # Set resolution (try 1080p)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    # Prepare output dir
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = out_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # Metadata file (simple JSON list)
    meta_path = out_dir / "metadata.json"
    metadata = []
    if meta_path.exists():
        with open(meta_path, "r") as f:
            try:
                metadata = json.load(f)
            except:
                pass

    print(f"{Color.GREEN}Ready to capture!{Color.RESET}")
    print(f"  Directory: {out_dir}")
    if args.interval > 0:
        print(f"  Mode: Auto-capture every {args.interval}s (Press Ctrl+C to stop)")
    else:
        print(f"  Mode: Manual (Press ENTER to capture, 'q' to quit)")

    last_capture = 0
    count = len(metadata)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print(f"{Color.RED}Frame read failed.{Color.RESET}")
                time.sleep(1)
                continue

            # Display preview
            # cv2.imshow("Collector Preview", frame)
            # key = cv2.waitKey(1) & 0xFF

            # Since we might be running headless via SSH, we can't rely on cv2.imshow
            # Instead we rely on console input for manual mode

            capture_now = False

            if args.interval > 0:
                if time.time() - last_capture > args.interval:
                    capture_now = True
            else:
                # Non-blocking input is hard in Python without curses/termios magic
                # For simplicity in this script, manual mode blocks on input() if we don't show GUI
                # BUT we need to drain the camera buffer.
                # So we just grab frames in loop.
                # Interactive mode is tricky headless.
                # Let's assume we run this locally OR use a simple select on stdin.
                import select
                if select.select([sys.stdin], [], [], 0.01)[0]:
                    line = sys.stdin.readline()
                    if line.strip() == 'q':
                        break
                    capture_now = True

            if capture_now:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"capture_{ts}.jpg"
                filepath = images_dir / filename

                cv2.imwrite(str(filepath), frame)

                entry = {
                    "filename": filename,
                    "timestamp": time.time(),
                    "width": frame.shape[1],
                    "height": frame.shape[0]
                }
                metadata.append(entry)
                count += 1
                last_capture = time.time()

                print(f"{Color.GREEN}[{count}] Saved {filename}{Color.RESET}")

                # Auto-save metadata periodically
                with open(meta_path, "w") as f:
                    json.dump(metadata, f, indent=2)

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        # cv2.destroyAllWindows()
        print(f"\n{Color.CYAN}Capture complete. {count} images saved.{Color.RESET}")

if __name__ == "__main__":
    main()
