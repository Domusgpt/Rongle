"""
AuthManager — Handles API key management and token rotation for the PortalClient.

Responsible for:
- Storing the long-lived Device API Key.
- (Future) Negotiating short-lived JWT access tokens.
- Handling 401 Unauthorized errors by triggering re-authentication.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AuthConfig:
    device_id: str
    api_key: str
    token: str | None = None
    token_expires_at: float = 0.0


class AuthManager:
    """
    Manages authentication state for the Portal Client.
    """

    def __init__(self, device_id: str, api_key: str) -> None:
        self.config = AuthConfig(device_id=device_id, api_key=api_key)

    def get_headers(self) -> dict[str, str]:
        """Return headers for HTTP requests."""
        # Currently we use the raw API key.
        # Future: Check if self.config.token is valid, if not, refresh.
        return {
            "X-Device-Key": self.config.api_key,
            # "Authorization": f"Bearer {self.config.token}"  # Future
        }

    async def handle_401(self) -> bool:
        """
        Called when a request returns 401 Unauthorized.
        Returns True if auth was successfully refreshed, False if fatal.
        """
        logger.warning("Authentication failed (401). Device Key might be revoked.")
        # In a JWT flow, we would try to use the refresh token here.
        # With static keys, a 401 is usually fatal unless it was a rotation race condition.
        return False
