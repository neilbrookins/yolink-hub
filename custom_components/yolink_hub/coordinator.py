"""Pings the hub on the LAN often, and checks the YoLink cloud less often.

When the ping result changes (the hub stops or starts answering), the cloud is
checked again: at once when the ping fails, a few seconds later when it
recovers (the hub needs a moment to reconnect to the cloud), then every few
seconds until the cloud agrees with the ping, for at most a minute. So the
status settles within seconds without polling the cloud more often.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from icmplib import SocketPermissionError, async_ping

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import YoLinkApi, YoLinkAuthError, YoLinkCloudError
from .const import (
    CONF_HUB_ID,
    CONF_HUB_TOKEN,
    CONF_HUB_TYPE,
    CONF_LOCAL_HOST,
    CONF_PING_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_PING_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FOLLOW_UP_EVERY,
    FOLLOW_UP_WINDOW,
    PING_COUNT,
    PING_INTERVAL_WITHIN,
    RECOVERY_FIRST_CHECK,
    PING_TIMEOUT,
)
from .status import KNOWN_CODES, HubData, parse

_LOGGER = logging.getLogger(__name__)


class YoLinkHubCoordinator(DataUpdateCoordinator[HubData]):
    """Cloud checks on the update interval; pings on their own, faster timer."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: YoLinkApi) -> None:
        interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=int(interval)),
        )
        self.api = api
        self.hub_id: str = entry.data[CONF_HUB_ID]
        self.hub_type: str = entry.data[CONF_HUB_TYPE]
        self._hub_token: str = entry.data[CONF_HUB_TOKEN]
        self.local_host: str | None = (
            entry.options.get(CONF_LOCAL_HOST, entry.data.get(CONF_LOCAL_HOST)) or None
        )
        self.ping_interval = int(
            entry.options.get(CONF_PING_INTERVAL, DEFAULT_PING_INTERVAL)
        )
        self._cloud_was_down = False
        self._privileged_ping: bool | None = None
        self._local: bool | None = None  # latest ping result
        self._pinging = False
        self._reply: dict | None = None  # latest cloud reply (None = unreachable)
        self._extra: list[str] = []
        self._checked_at: datetime | None = None
        self._check_reason = "startup"
        self._next_reason = "startup"
        self._follow_up_task: asyncio.Task | None = None

    async def async_start_pinging(self) -> None:
        """First ping now, then on the ping interval until the entry unloads."""
        if not self.local_host:
            return
        self._local = await self._ping()
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass, self._ping_tick, timedelta(seconds=self.ping_interval)
            )
        )

    async def _ping_tick(self, _now: datetime) -> None:
        if self._pinging:  # the previous ping is still waiting for replies
            return
        self._pinging = True
        try:
            local = await self._ping()
        finally:
            self._pinging = False
        if local == self._local:
            return
        self._local = local
        _LOGGER.info(
            "Hub %s %s on the LAN; checking the YoLink cloud now",
            self.local_host,
            "answering" if local else "not answering",
        )
        if self.data is not None:
            self.async_set_updated_data(self._build())  # show the ping change at once
        if self._follow_up_task and not self._follow_up_task.done():
            self._follow_up_task.cancel()
        self._follow_up_task = self.config_entry.async_create_background_task(
            self.hass, self._follow_up(local), "yolink_hub cloud follow-up"
        )

    async def _follow_up(self, local: bool) -> None:
        """Ask the cloud until it agrees with the ping, for at most a minute."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + FOLLOW_UP_WINDOW
        reason = "ping recovered" if local else "ping failed"
        if local:
            await asyncio.sleep(RECOVERY_FIRST_CHECK)  # let the hub reconnect first
        while True:
            self._next_reason = reason
            await self.async_refresh()
            online = self.data.online if self.data else None
            if online is None or online == local or loop.time() >= deadline:
                return  # agrees, cloud unreachable, or out of time
            await asyncio.sleep(FOLLOW_UP_EVERY)
            reason = ("ping recovered" if local else "ping failed") + ", follow-up"

    async def _async_update_data(self) -> HubData:
        self._check_reason, self._next_reason = self._next_reason, "scheduled"
        self._reply, self._extra = await self._fetch_state()
        self._checked_at = dt_util.utcnow()
        data = self._build()
        self._update_device(data)
        return data

    def _build(self) -> HubData:
        data = parse(self._reply, self._local if self.local_host else None, self._extra)
        data.cloud_checked_at = self._checked_at
        data.cloud_check_reason = self._check_reason
        return data

    async def _fetch_state(self) -> tuple[dict | None, list[str]]:
        """Return (reply or None if the cloud is unreachable, extra review reasons)."""
        try:
            reply = await self.api.get_state(self.hub_type, self.hub_id, self._hub_token)
            if str(reply.get("code")) not in KNOWN_CODES:
                # Maybe the hub's token changed: renew both tokens and retry once.
                _LOGGER.debug("Unexpected reply %s, retrying with fresh tokens", reply)
                self.api.invalidate_token()
                await self._refresh_hub_token()
                reply = await self.api.get_state(
                    self.hub_type, self.hub_id, self._hub_token
                )
        except YoLinkAuthError as err:
            # The cloud answered, so it is reachable; flag this for review.
            _LOGGER.error("%s", err)
            self._log_cloud(True)
            return {
                "code": "credentials_rejected",
                "desc": "YoLink rejected the UAID / Secret Key; check User Access "
                "Credentials in the YoLink app and reconfigure the integration",
            }, []
        except YoLinkCloudError as err:
            self._log_cloud(False, err)
            return None, []
        self._log_cloud(True)
        return reply, []

    async def _refresh_hub_token(self) -> None:
        for dev in await self.api.device_list():
            if dev.get("deviceId") == self.hub_id and dev.get("token"):
                if dev["token"] != self._hub_token:
                    self._hub_token = dev["token"]
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={**self.config_entry.data, CONF_HUB_TOKEN: dev["token"]},
                    )
                return

    def _log_cloud(self, ok: bool, err: Exception | None = None) -> None:
        if not ok and not self._cloud_was_down:
            _LOGGER.warning("YoLink cloud unreachable: %s", err)
        elif ok and self._cloud_was_down:
            _LOGGER.info("YoLink cloud reachable again")
        self._cloud_was_down = not ok

    async def _ping(self) -> bool:
        """Ping the hub's LAN address; True if any reply comes back."""
        tries = [self._privileged_ping] if self._privileged_ping is not None else [False, True]
        for privileged in tries:
            try:
                host = await async_ping(
                    self.local_host,
                    count=PING_COUNT,
                    interval=PING_INTERVAL_WITHIN,
                    timeout=PING_TIMEOUT,
                    privileged=privileged,
                )
            except SocketPermissionError:
                continue
            except Exception as err:  # noqa: BLE001  name lookup or socket errors
                _LOGGER.debug("Ping to %s failed: %s", self.local_host, err)
                return False
            self._privileged_ping = privileged
            return host.is_alive
        _LOGGER.error("No permission to send ping packets")
        return False

    def _update_device(self, data: HubData) -> None:
        """Keep the device page's firmware version current."""
        if not data.version:
            return
        registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        ):
            if device.sw_version != data.version:
                registry.async_update_device(device.id, sw_version=data.version)
