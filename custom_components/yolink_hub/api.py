"""Small client for the YoLink Open API (User Access Credentials)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from .const import API_URL, TOKEN_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)
TOKEN_MARGIN = 300  # renew the token this many seconds before it expires


class YoLinkCloudError(Exception):
    """The YoLink cloud could not be reached or sent an unusable reply."""


class YoLinkAuthError(Exception):
    """YoLink rejected the UAID / Secret Key."""


class YoLinkApi:
    """Calls the YoLink cloud, reusing the access token until it nears expiry."""

    def __init__(self, session: aiohttp.ClientSession, uaid: str, secret: str) -> None:
        self._session = session
        self._uaid = uaid
        self._secret = secret
        self._token: str | None = None
        self._token_expires = 0.0
        self._lock = asyncio.Lock()

    def invalidate_token(self) -> None:
        """Force a new token on the next call."""
        self._token = None

    async def _get_token(self) -> str:
        async with self._lock:
            if self._token and time.monotonic() < self._token_expires - TOKEN_MARGIN:
                return self._token
            try:
                async with self._session.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._uaid,
                        "client_secret": self._secret,
                    },
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    status = resp.status
                    body = await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
                raise YoLinkCloudError(f"Token request failed: {err}") from err
            token = body.get("access_token") if isinstance(body, dict) else None
            if not token:
                if status < 500:
                    raise YoLinkAuthError(f"Token request rejected (HTTP {status})")
                raise YoLinkCloudError(f"Token request failed (HTTP {status})")
            self._token = token
            self._token_expires = time.monotonic() + float(body.get("expires_in", 7200))
            _LOGGER.debug("Got a new YoLink access token")
            return token

    async def call(self, method: str, **extra: Any) -> dict[str, Any]:
        """Send one API request and return the JSON reply (any 'code')."""
        token = await self._get_token()
        payload = {"method": method, "time": int(time.time() * 1000), **extra}
        try:
            async with self._session.post(
                API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    self.invalidate_token()
                    raise YoLinkCloudError("Access token rejected (HTTP 401)")
                if resp.status >= 400:
                    raise YoLinkCloudError(f"{method} failed (HTTP {resp.status})")
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise YoLinkCloudError(f"{method} failed: {err}") from err
        if not isinstance(body, dict) or "code" not in body:
            raise YoLinkCloudError(f"{method} returned an unexpected reply")
        return body

    async def device_list(self) -> list[dict[str, Any]]:
        """Return the account's devices (deviceId, name, token, type, modelName)."""
        body = await self.call("Home.getDeviceList")
        devices = (body.get("data") or {}).get("devices")
        if body.get("code") != "000000" or not isinstance(devices, list):
            raise YoLinkCloudError(
                f"Home.getDeviceList returned {body.get('code')}: {body.get('desc')}"
            )
        return devices

    async def get_state(self, dev_type: str, dev_id: str, dev_token: str) -> dict[str, Any]:
        """Call <type>.getState for one device and return the full reply."""
        return await self.call(
            f"{dev_type}.getState", targetDevice=dev_id, token=dev_token
        )
