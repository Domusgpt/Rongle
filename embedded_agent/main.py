import asyncio
import websockets
import json
import sys
import os
import logging

# Add current directory to path so imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.actuator import HygienicActuator
from core.ledger import ImmutableLedger
from core.policy_engine import PolicyEngine

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HIAO-Server")

class AgentServer:
    def __init__(self):
        self.ledger = ImmutableLedger()
        self.policy = PolicyEngine()
        self.actuator = HygienicActuator()
        logger.info("Agent Modules Initialized")

    async def handler(self, websocket):
        client_info = websocket.remote_address
        logger.info(f"Client connected: {client_info}")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    command_type = data.get("type")

                    if command_type == "EXECUTE_SCRIPT":
                        script = data.get("script")
                        logger.info(f"Received script execution request from {client_info}")

                        # 1. Validate
                        is_allowed, reason = self.policy.validate_command(script)

                        if is_allowed:
                            # 2. Execute
                            logger.info("Policy Check: APPROVED. Executing...")
                            # Run in executor to avoid blocking the event loop
                            await asyncio.to_thread(self.actuator.execute_ducky_script, script)

                            # 3. Log
                            self.ledger.log_action("EXECUTION", script)

                            await websocket.send(json.dumps({
                                "type": "EXECUTION_RESULT",
                                "status": "SUCCESS",
                                "message": "Script executed successfully"
                            }))
                        else:
                            logger.warning(f"Policy Check: BLOCKED. Reason: {reason}")
                            self.ledger.log_action("BLOCKED", script, reason)

                            await websocket.send(json.dumps({
                                "type": "EXECUTION_RESULT",
                                "status": "BLOCKED",
                                "message": reason
                            }))

                    elif command_type == "PING":
                         await websocket.send(json.dumps({"type": "PONG"}))

                    else:
                        logger.warning(f"Unknown command type: {command_type}")
                        await websocket.send(json.dumps({
                            "type": "ERROR",
                            "message": "Unknown command type"
                        }))

                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
                    await websocket.send(json.dumps({"type": "ERROR", "message": "Invalid JSON"}))
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await websocket.send(json.dumps({"type": "ERROR", "message": str(e)}))

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_info}")

async def main():
    server_instance = AgentServer()
    port = 8000
    logger.info(f"Starting WebSocket Server on 0.0.0.0:{port}")

    async with websockets.serve(server_instance.handler, "0.0.0.0", port):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
