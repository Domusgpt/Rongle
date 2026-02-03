"""
PortalClient — Device-side client for communicating with the Rongle Portal.

Responsibilities:
  1. Fetch device settings and policy on startup
  2. Proxy VLM queries through the portal (so the device never holds the API key)
  3. Sync audit log entries to the portal
  4. Stream real-time telemetry over WebSocket
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class PortalClient:
    """
    Async HTTP + WebSocket client for device-to-portal communication.

    Usage::

        client = PortalClient(
            portal_url="https://portal.rongle.io",
            device_id="abc123",
            api_key="rng_xxx...",
        )
        await client.connect()
        settings = await client.fetch_settings()
        result = await client.vlm_query("Find the OK button", image_b64="...")
        await client.sync_audit([entry1, entry2, ...])
    """

    def __init__(
        self,
        portal_url: str,
        device_id: str,
        api_key: str,
        connect_timeout: float = 10.0,
        request_timeout: float = 30.0,
    ) -> None:
        self.portal_url = portal_url.rstrip("/")
        self.device_id = device_id
        self.api_key = api_key
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self._http = None
        self._ws = None
        self._ws_task: asyncio.Task | None = None

        # Batch buffer
        self._audit_buffer: list[dict] = []
        self._flush_threshold = 10
        self._last_flush = time.time()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    async def _ensure_http(self):
        if self._http is None:
            import httpx
            self._http = httpx.AsyncClient(
                base_url=self.portal_url,
                timeout=self.request_timeout,
                headers={"X-Device-Key": self.api_key},
            )

    async def _get(self, path: str) -> dict:
        await self._ensure_http()
        resp = await self._http.get(path)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, data: dict) -> dict:
        await self._ensure_http()
        resp = await self._http.post(path, json=data)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Settings & Policy
    # ------------------------------------------------------------------
    async def fetch_settings(self) -> dict:
        """Download the device's operator settings from the portal."""
        try:
            result = await self._get(f"/api/devices/{self.device_id}")
            settings_str = result.get("settings_json", "{}")
            return json.loads(settings_str) if isinstance(settings_str, str) else settings_str
        except Exception as exc:
            logger.warning("Failed to fetch settings from portal: %s", exc)
            return {}

    async def fetch_policy(self) -> dict:
        """Download the device's policy allowlist from the portal."""
        try:
            result = await self._get(f"/api/devices/{self.device_id}/policy")
            return result.get("policy", {})
        except Exception as exc:
            logger.warning("Failed to fetch policy from portal: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # LLM Proxy
    # ------------------------------------------------------------------
    async def vlm_query(
        self,
        prompt: str,
        image_base64: str | None = None,
        model: str | None = None,
    ) -> dict:
        """
        Proxy a VLM query through the portal.

        Returns the parsed VLM response dict.
        """
        payload: dict[str, Any] = {
            "device_id": self.device_id,
            "prompt": prompt,
        }
        if image_base64:
            payload["image_base64"] = image_base64
        if model:
            payload["model"] = model

        return await self._post("/api/llm/query", payload)

    # ------------------------------------------------------------------
    # Audit Sync (Batched)
    # ------------------------------------------------------------------
    async def log_audit_entry(self, entry: dict) -> None:
        """Queue an audit entry for batched upload."""
        self._audit_buffer.append(entry)
        if len(self._audit_buffer) >= self._flush_threshold:
            await self.flush_audit()

    async def flush_audit(self) -> None:
        """Force upload of buffered audit entries."""
        if not self._audit_buffer:
            return

        chunk = self._audit_buffer[:]
        self._audit_buffer.clear()

        try:
            await self._post("/api/audit/sync", {
                "device_api_key": self.api_key,
                "entries": chunk,
            })
            self._last_flush = time.time()
        except Exception as exc:
            logger.error("Failed to sync audit buffer: %s", exc)
            # Re-queue entries on failure (simple retry)
            # Note: infinite growth risk if portal down long-term.
            # In prod, use a persistent local queue (SessionManager DB).
            if len(self._audit_buffer) < 1000:
                self._audit_buffer = chunk + self._audit_buffer

    async def sync_audit(self, entries: list[dict]) -> dict:
        """Direct upload (legacy compatibility)."""
        return await self._post("/api/audit/sync", {
            "device_api_key": self.api_key,
            "entries": entries,
        })

    # ------------------------------------------------------------------
    # WebSocket Telemetry
    # ------------------------------------------------------------------
    async def connect_telemetry(self) -> None:
        """Establish persistent WebSocket for telemetry streaming."""
        try:
            import websockets
            ws_url = self.portal_url.replace("http", "ws")
            self._ws = await websockets.connect(
                f"{ws_url}/ws/device/{self.device_id}?key={self.api_key}",
                open_timeout=self.connect_timeout,
            )
            logger.info("WebSocket telemetry connected")
        except Exception as exc:
            logger.warning("WebSocket connection failed: %s", exc)
            self._ws = None

    async def send_telemetry(self, telemetry: dict) -> None:
        """Send a telemetry update over the WebSocket."""
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps(telemetry))
        except Exception as exc:
            logger.warning("Telemetry send failed: %s", exc)
            self._ws = None

    async def receive_command(self) -> dict | None:
        """Non-blocking check for commands from the portal."""
        if self._ws is None:
            return None
        try:
            msg = await asyncio.wait_for(self._ws.recv(), timeout=0.01)
            return json.loads(msg)
        except (asyncio.TimeoutError, Exception):
            return None

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------
    async def heartbeat(self) -> None:
        """Send a heartbeat to keep the device marked as online."""
        try:
            await self._post(f"/api/devices/{self.device_id}/heartbeat", {})
        except Exception as exc:
            logger.debug("Heartbeat failed: %s", exc)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def close(self) -> None:
        """Clean up connections."""
        await self.flush_audit()
        if self._ws:
            await self._ws.close()
        if self._http:
            await self._http.aclose()
