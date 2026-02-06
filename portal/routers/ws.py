"""
WebSocket router — real-time device telemetry and command channel.

Supports two connection modes:
  1. Device connects with API key → sends telemetry, receives commands
  2. User connects with JWT → receives live telemetry stream for their devices
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from ..database import async_session
from ..models import Device

logger = logging.getLogger(__name__)
router = APIRouter()

# Active connections indexed by device_id
_device_connections: dict[str, WebSocket] = {}
_user_connections: dict[str, list[WebSocket]] = defaultdict(list)


@router.websocket("/ws/device/{device_id}")
async def device_telemetry_ws(
    websocket: WebSocket,
    device_id: str,
    api_key: str = Query(..., alias="key"),
):
    """
    WebSocket for a device to stream telemetry and receive commands.

    Connect: ws://host/ws/device/{device_id}?key={api_key}
    """
    # Authenticate device
    async with async_session() as db:
        result = await db.execute(
            select(Device).where(Device.id == device_id, Device.api_key == api_key)
        )
        device = result.scalar_one_or_none()
        if device is None:
            await websocket.close(code=4001, reason="Invalid device credentials")
            return

    await websocket.accept()
    _device_connections[device_id] = websocket
    logger.info("Device %s connected via WebSocket", device_id)

    try:
        while True:
            data = await websocket.receive_text()
            telemetry = json.loads(data)

            # Broadcast to all user connections watching this device
            user_sockets = _user_connections.get(device_id, [])
            dead: list[WebSocket] = []
            for ws in user_sockets:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                user_sockets.remove(ws)

    except WebSocketDisconnect:
        logger.info("Device %s disconnected", device_id)
    except Exception as exc:
        logger.error("Device WS error: %s", exc)
    finally:
        _device_connections.pop(device_id, None)


@router.websocket("/ws/watch/{device_id}")
async def user_watch_ws(
    websocket: WebSocket,
    device_id: str,
    token: str = Query(...),
):
    """
    WebSocket for a user to watch live telemetry from their device.

    Connect: ws://host/ws/watch/{device_id}?token={jwt_token}
    """
    from ..auth import decode_token

    user_id = decode_token(token, expected_type="access")
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Verify device ownership
    async with async_session() as db:
        result = await db.execute(
            select(Device).where(Device.id == device_id, Device.user_id == user_id)
        )
        if result.scalar_one_or_none() is None:
            await websocket.close(code=4003, reason="Device not found")
            return

    await websocket.accept()
    _user_connections[device_id].append(websocket)
    logger.info("User %s watching device %s", user_id, device_id)

    try:
        while True:
            # Users can send commands to the device
            data = await websocket.receive_text()
            device_ws = _device_connections.get(device_id)
            if device_ws:
                await device_ws.send_text(data)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("User WS error: %s", exc)
    finally:
        conns = _user_connections.get(device_id, [])
        if websocket in conns:
            conns.remove(websocket)
