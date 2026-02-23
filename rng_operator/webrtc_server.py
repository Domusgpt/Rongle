"""
WebRTC Signaling Server — Lightweight HTTP server for SDP exchange.

Endpoints:
  POST /offer: Accepts JSON {sdp, type}, returns JSON {sdp, type}
  OPTIONS /offer: CORS handling
"""

from __future__ import annotations

import logging
import secrets
from aiohttp import web

from .visual_cortex.webrtc_receiver import WebRTCReceiver

logger = logging.getLogger(__name__)


class WebRTCServer:
    def __init__(self, receiver: WebRTCReceiver, host: str = "0.0.0.0", port: int = 8080, api_key: str | None = None):
        self.receiver = receiver
        self.host = host
        self.port = port
        self.api_key = api_key
        self.app = web.Application()
        self.runner: web.AppRunner | None = None

        self.app.router.add_post("/offer", self.offer)
        self.app.router.add_options("/offer", self.options)

    async def offer(self, request: web.Request):
        # Authentication check
        if self.api_key:
            auth_header = request.headers.get("X-Device-Key")
            if not auth_header or not secrets.compare_digest(auth_header, self.api_key):
                logger.warning("Unauthorized WebRTC offer attempt from %s", request.remote)
                return web.json_response(
                    {"error": "Unauthorized"},
                    status=401,
                    headers={"Access-Control-Allow-Origin": "*"}
                )

        params = await request.json()
        logger.info("Received SDP offer")

        try:
            answer = await self.receiver.handle_offer(params)
            return web.json_response(answer)
        except Exception as e:
            logger.error("Failed to handle offer: %s", e)
            return web.Response(status=500, text=str(e))

    async def options(self, request: web.Request):
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-Device-Key",
            },
        )

    async def start(self):
        logger.info("Starting WebRTC Signaling Server on %s:%d", self.host, self.port)
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
