"""Sensors: status, DC, battery, firmware, Ethernet, Wi-Fi (words match the YoLink app)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    async_add_entities(HubSensor(coordinator, desc) for desc in DESCRIPTIONS)


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
