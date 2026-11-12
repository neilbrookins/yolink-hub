"""Sensors: status, DC, battery (and since when), firmware, Ethernet, Wi-Fi.

State words match the YoLink app.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .coordinator import YoLinkHubCoordinator
from .entity import YoLinkHubEntity
from .status import (
    BATTERY_CONFIRMED,
    BATTERY_DOCUMENTED,
    BATTERY_UNRECOGNIZED,
    STATUSES,
    HubData,
)


def _connected(value: bool | None) -> str | None:
    if value is None:
        return None
    return "connected" if value else "not_connected"


@dataclass(frozen=True, kw_only=True)
class HubSensorDescription(SensorEntityDescription):
    """How to read one sensor from HubData."""

    value_fn: Callable[[HubData], Any]
    needs_state: bool = True  # unavailable unless the hub's state came back
    attrs_fn: Callable[[HubData], dict[str, Any]] | None = None


DESCRIPTIONS: tuple[HubSensorDescription, ...] = (
    HubSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUSES,
        value_fn=lambda d: d.status,
        needs_state=False,
        attrs_fn=lambda d: {"api_code": d.api_code, "api_desc": d.api_desc},
    ),
    HubSensorDescription(
        key="dc",
        device_class=SensorDeviceClass.ENUM,
        options=["connected", "disconnected"],
        value_fn=lambda d: None if d.dc is None else ("connected" if d.dc else "disconnected"),
    ),
    HubSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.ENUM,
        options=[
            *BATTERY_CONFIRMED.values(),
            *BATTERY_DOCUMENTED.values(),
            BATTERY_UNRECOGNIZED,
        ],
        value_fn=lambda d: d.battery_state,
        attrs_fn=lambda d: {"battery_state_code": d.battery_code},
    ),
    HubSensorDescription(
        key="last_cloud_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.cloud_checked_at,
        needs_state=False,
        attrs_fn=lambda d: {"reason": d.cloud_check_reason, "api_code": d.api_code},
    ),
    HubSensorDescription(
        key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.version,
    ),
    HubSensorDescription(
        key="ethernet",
        device_class=SensorDeviceClass.ENUM,
        options=["connected", "not_connected"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _connected(d.eth_connected),
        attrs_fn=lambda d: {
            "ip_address": d.eth.get("ip"),
            "gateway": d.eth.get("gateway"),
            "network_mask": d.eth.get("mask"),
        },
    ),
    HubSensorDescription(
        key="wifi",
        device_class=SensorDeviceClass.ENUM,
        options=["connected", "not_connected"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _connected(d.wifi_connected),
        attrs_fn=lambda d: {
            "ssid": d.wifi.get("ssid") or None,
            "ip_address": d.wifi.get("ip"),
            "gateway": d.wifi.get("gateway"),
            "network_mask": d.wifi.get("mask"),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: YoLinkHubCoordinator = entry.runtime_data
    async_add_entities(
        [*(HubSensor(coordinator, desc) for desc in DESCRIPTIONS), BatterySinceSensor(coordinator)]
    )


class HubSensor(YoLinkHubEntity, SensorEntity):
    """One sensor of the hub."""

    entity_description: HubSensorDescription

    def __init__(self, coordinator: YoLinkHubCoordinator, desc: HubSensorDescription) -> None:
        super().__init__(coordinator, desc.key)
        self.entity_description = desc

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        if not super().available or data is None:
            return False
        if self.entity_description.needs_state and not data.has_state:
            return False  # never show stale values when the hub can't be read
        return self.entity_description.value_fn(data) is not None

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data) if fn and self.coordinator.data else None


class BatterySinceSensor(YoLinkHubEntity, RestoreEntity, SensorEntity):
    """When the Battery sensor's current state began (Supply, Charging, ...).

    Home Assistant shows a timestamp as "12 minutes ago", so this reads as how
    long the battery has been in its current state. It restarts only when the
    battery state changes: not when the hub drops offline and comes back in
    the same state, and not across Home Assistant restarts. If the state
    changed while nobody was looking (at first setup, while Home Assistant was
    stopped, or while the hub couldn't be read), the time is when the new
    state was first seen, and the attribute exact_start is false.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: YoLinkHubCoordinator) -> None:
        super().__init__(coordinator, "battery_since")
        self._for_state: str | None = None
        self._since: datetime | None = None
        self._exact = False
        self._seen_live = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.attributes.get("battery_state"):
            since = dt_util.parse_datetime(last.state) if last.state else None
            if since is not None:
                self._for_state = last.attributes["battery_state"]
                self._since = since
                self._exact = bool(last.attributes.get("exact_start"))
        self._track(self.coordinator.data)

    def _track(self, data) -> None:
        current = data.battery_state if data is not None and data.has_state else None
        if current is None:
            self._seen_live = False  # a change during this gap has no exact time
            return
        if current != self._for_state:
            # Exact only if we were watching the previous state up to now;
            # otherwise (first setup, after a restart or an offline gap) it is
            # the time the new state was first seen.
            self._exact = self._seen_live
            self._for_state = current
            self._since = dt_util.utcnow()
        self._seen_live = True

    @callback
    def _handle_coordinator_update(self) -> None:
        self._track(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        return (
            super().available
            and data is not None
            and data.has_state
            and data.battery_state is not None
            and self._since is not None
        )

    @property
    def native_value(self) -> datetime | None:
        return self._since

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"battery_state": self._for_state, "exact_start": self._exact}
