#!/bin/bash
# Rongle Dev Environment Launcher
# Starts Backend and Frontend in parallel and tails logs.

# Ensure we are in the root
cd "$(dirname "$0")/.."

# Check for venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Cleanup on exit
trap 'kill $(jobs -p)' EXIT

echo "🦆 Starting Rongle Dev Environment..."

# Start Backend (Background)
echo "[Backend] Launching Operator..."
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"
python -m rng_operator.main --dry-run --software-estop &
BACKEND_PID=$!

# Wait a moment for backend to initialize
sleep 2

# Start Frontend (Background)
echo "[Frontend] Launching Vite..."
npm run dev -- --host &
FRONTEND_PID=$!

echo "---------------------------------------------------"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop."
echo "---------------------------------------------------"

# Wait for both
wait
