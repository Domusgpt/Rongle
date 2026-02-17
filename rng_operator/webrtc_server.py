"""
WebRTC Signaling Server — Lightweight HTTP server for SDP exchange.

Endpoints:
  POST /offer: Accepts JSON {sdp, type}, returns JSON {sdp, type}
  OPTIONS /offer: CORS handling
"""

from __future__ import annotations

import logging
from aiohttp import web

from .visual_cortex.webrtc_receiver import WebRTCReceiver

logger = logging.getLogger(__name__)


class WebRTCServer:
    def __init__(self, receiver: WebRTCReceiver, host: str = "0.0.0.0", port: int = 8080):
        self.receiver = receiver
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: web.AppRunner | None = None

        self.app.router.add_post("/offer", self.offer)
        self.app.router.add_options("/offer", self.options)

    async def offer(self, request: web.Request):
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
                "Access-Control-Allow-Headers": "Content-Type",
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
