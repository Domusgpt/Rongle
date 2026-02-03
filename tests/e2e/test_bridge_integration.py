import asyncio
import websockets
import json
import pytest
import subprocess
import time
import sys
import os

# Path to the backend server script
BACKEND_SCRIPT = os.path.join(os.path.dirname(__file__), '../../embedded_agent/main.py')

@pytest.fixture(scope="module")
def agent_server():
    # Start the backend server in a separate process
    proc = subprocess.Popen(
        [sys.executable, BACKEND_SCRIPT],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for the server to start (simple sleep for now)
    time.sleep(2)

    yield proc

    # Teardown: Kill the server
    proc.terminate()
    proc.wait()

@pytest.mark.asyncio
async def test_bridge_execution(agent_server):
    uri = "ws://localhost:8000"

    async with websockets.connect(uri) as websocket:
        # Test PING
        await websocket.send(json.dumps({"type": "PING"}))
        response = await websocket.recv()
        data = json.loads(response)
        assert data["type"] == "PONG"

        # Test EXECUTE_SCRIPT (Simulation Mode)
        script = "DELAY 100\nSTRING Hello World"
        await websocket.send(json.dumps({
            "type": "EXECUTE_SCRIPT",
            "script": script
        }))

        response = await websocket.recv()
        data = json.loads(response)

        assert data["type"] == "EXECUTION_RESULT"
        # Since we haven't mocked the policy engine to fail, it should succeed
        # (Assuming simulation mode handles it without error)
        assert data["status"] == "SUCCESS"
