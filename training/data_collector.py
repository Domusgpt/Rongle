#!/usr/bin/env python3
"""
Data Collection Utility for Rongle

Captures frames from the configured video device and saves them to disk
along with metadata. Use this to build datasets for training local CNN models.

Usage:
    python -m training.data_collector -o ./my_dataset -d /dev/video0 -i 1.0
"""
import argparse
import time
import json
import logging
from pathlib import Path
import cv2

# Import from rongle_operator (assumes running from repo root as module)
try:
    from rongle_operator.visual_cortex.frame_grabber import FrameGrabber
except ImportError:
    # If running directly, adjust path
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from rongle_operator.visual_cortex.frame_grabber import FrameGrabber

logger = logging.getLogger("collector")

def main():
    parser = argparse.ArgumentParser(description="Rongle Data Collector")
    parser.add_argument("--output", "-o", type=str, default="training/data/raw", help="Output directory")
    parser.add_argument("--device", "-d", type=str, default="/dev/video0", help="Video device path (default: /dev/video0)")
    parser.add_argument("--width", type=int, default=1920, help="Capture width")
    parser.add_argument("--height", type=int, default=1080, help="Capture height")
    parser.add_argument("--interval", "-i", type=float, default=2.0, help="Capture interval in seconds")
    parser.add_argument("--count", "-n", type=int, default=0, help="Max frames to capture (0=infinite)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting capture from {args.device} to {out_dir}")

    try:
        grabber = FrameGrabber(device=args.device, width=args.width, height=args.height)
        grabber.open()
    except Exception as e:
        logger.error(f"Failed to open device: {e}")
        logger.info("Ensure you are running on a device with a camera or mock device.")
        return

    captured = 0
    try:
        while True:
            if args.count > 0 and captured >= args.count:
                break

            try:
                frame = grabber.grab()
            except RuntimeError as e:
                logger.error(f"Capture error: {e}")
                time.sleep(1.0)
                continue

            timestamp = int(time.time() * 1000)
            filename = f"frame_{timestamp}.jpg"
            filepath = out_dir / filename

            # Save image
            cv2.imwrite(str(filepath), frame.image)

            # Save metadata
            meta = {
                "timestamp": timestamp,
                "sequence": frame.sequence,
                "sha256": frame.sha256,
                "width": args.width,
                "height": args.height,
                "device": args.device
            }
            with open(out_dir / f"frame_{timestamp}.json", "w") as f:
                json.dump(meta, f, indent=2)

            captured += 1
            logger.info(f"Captured {filename} ({captured})")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("Stopped by user")
    finally:
        grabber.close()
        logger.info(f"Finished. Total captured: {captured}")

if __name__ == "__main__":
    main()
