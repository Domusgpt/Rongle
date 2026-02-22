#!/usr/bin/env python3
"""
Rongle Audit Log Visualizer

Reads an audit.jsonl file and generates a simple HTML report visualizing:
- Confidence scores over time
- Action types distribution
- Policy verdict timeline
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

# HTML Template
REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Rongle Audit Report</title>
    <style>
        body { font-family: monospace; background: #0f1115; color: #e2e8f0; padding: 20px; }
        .card { background: #161b22; padding: 20px; margin-bottom: 20px; border-radius: 8px; border: 1px solid #2d3848; }
        h1 { color: #00ff41; }
        h2 { color: #00ccff; margin-top: 0; }
        .metric { font-size: 2em; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #2d3848; }
        th { color: #718096; }
        tr:hover { background: #1a202c; }
        .allowed { color: #22c55e; }
        .blocked { color: #ef4444; }
    </style>
</head>
<body>
    <h1>Rongle Audit Report</h1>
    <div class="card">
        <h2>Summary</h2>
        <div style="display: flex; gap: 40px;">
            <div>
                <div class="metric">{total_entries}</div>
                <div>Total Actions</div>
            </div>
            <div>
                <div class="metric">{blocked_count}</div>
                <div>Policy Blocks</div>
            </div>
            <div>
                <div class="metric">{duration:.1f}s</div>
                <div>Session Duration</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>Action Log</h2>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Action</th>
                    <th>Detail</th>
                    <th>Verdict</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

def generate_report(log_path: Path):
    if not log_path.exists():
        print(f"Error: Log file {log_path} not found.")
        sys.exit(1)

    entries = []
    with open(log_path, "r") as f:
        for line in f:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not entries:
        print("Error: Log file is empty or invalid.")
        sys.exit(1)

    # Analytics
    start_time = entries[0]["timestamp"]
    end_time = entries[-1]["timestamp"]
    duration = end_time - start_time

    blocked = [e for e in entries if e.get("policy_verdict") == "blocked"]

    # Table rows
    rows = ""
    for e in entries:
        verdict_class = "allowed"
        if e.get("policy_verdict") == "blocked":
            verdict_class = "blocked"

        ts_str = datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S")
        rows += f"""
        <tr>
            <td>{ts_str}</td>
            <td>{e.get("action", "")}</td>
            <td>{e.get("action_detail", "")}</td>
            <td class="{verdict_class}">{e.get("policy_verdict", "INFO")}</td>
        </tr>
        """

    html = REPORT_TEMPLATE.format(
        total_entries=len(entries),
        blocked_count=len(blocked),
        duration=duration,
        table_rows=rows
    )

    output_path = log_path.with_suffix(".html")
    with open(output_path, "w") as f:
        f.write(html)

    print(f"Report generated: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file", help="Path to audit.jsonl")
    args = parser.parse_args()
    generate_report(Path(args.log_file))
