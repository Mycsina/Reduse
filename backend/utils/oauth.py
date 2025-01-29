"""OAuth token management utilities."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Protocol, cast

import httpx


class TokenProvider(Protocol):
    """Protocol for OAuth token providers."""

    async def get_token(self) -> str:
        """Get a valid OAuth token."""
        ...


class OAuthError(Exception):
    """Base exception for OAuth-related errors."""

    pass


class TokenError(OAuthError):
    """Error raised when token retrieval fails."""

    pass


class OAuthManager:
    """OAuth token manager with caching and automatic refresh."""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str,
        safety_margin: int = 300,
    ):
        """Initialize the OAuth manager.

        Args:
            token_url: OAuth token endpoint URL
            client_id: OAuth client ID
            client_secret: OAuth client secret
            scope: OAuth scope(s)
            safety_margin: Number of seconds before token expiry to refresh (default: 300)
        """
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.safety_margin = safety_margin
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self.client: Optional[httpx.AsyncClient] = None
        self.logger = logging.getLogger(__name__)
        self._lock = asyncio.Lock()

    async def _ensure_client(self) -> None:
        """Ensure httpx client exists."""
        if self.client is None:
            self.client = httpx.AsyncClient()
            if not self.client:
                raise RuntimeError("Failed to create httpx client")

    async def _fetch_new_token(self) -> Dict[str, Any]:
        """Fetch a new OAuth token from the server.

        Returns:
            Dict containing token response data

        Raises:
            RuntimeError: If client creation fails
            TokenError: If token retrieval fails
        """
        await self._ensure_client()
        if not self.client:
            raise RuntimeError("Failed to create client")

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope,
        }

        try:
            response = await self.client.post(
                self.token_url, headers=headers, data=data
            )
            if response.status_code != 200:
                raise TokenError(f"Failed to get access token: {response.text}")
            result = response.json()
            if not isinstance(result, dict):
                raise TokenError("Invalid response format")
            return result
        except httpx.RequestError as e:
            raise TokenError(f"Network error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error fetching new token: {str(e)}")
            raise TokenError(str(e))

    async def get_token(self) -> str:
        """Get a valid OAuth token, refreshing if necessary.

        Returns:
            str: A valid OAuth access token

        Raises:
            TokenError: If token retrieval fails
        """
        async with self._lock:  # Prevent multiple simultaneous token refreshes
            now = datetime.now()

            # Return existing token if still valid
            if self._access_token and self._token_expiry and self._token_expiry > now:
                return self._access_token

            # Get new token
            try:
                result = await self._fetch_new_token()
                token = cast(str, result.get("access_token"))
                if not token:
                    raise TokenError("No access token in response")

                self._access_token = token
                expires_in = int(result.get("expires_in", 3600))  # Default to 1 hour
                self._token_expiry = now + timedelta(
                    seconds=expires_in - self.safety_margin
                )
                self.logger.debug(
                    f"Got new token, expires in {expires_in} seconds "
                    f"(with {self.safety_margin}s safety margin)"
                )
                return token

            except TokenError:
                raise
            except Exception as e:
                self.logger.error(f"Error getting access token: {str(e)}")
                raise TokenError(str(e))

    async def close(self) -> None:
        """Close the client and clean up resources."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def __aenter__(self) -> "OAuthManager":
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
