"""Binary sensors: hub online, LAN reachable, YoLink cloud reachable, needs review."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import YoLinkHubCoordinator
from .entity import YoLinkHubEntity
from .status import HubData


@dataclass(frozen=True, kw_only=True)
class HubBinaryDescription(BinarySensorEntityDescription):
    """How to read one binary sensor from HubData."""

    is_on_fn: Callable[[HubData], bool | None]
    available_fn: Callable[[HubData], bool] = lambda d: True
    attrs_fn: Callable[[HubData], dict[str, Any]] | None = None
    needs_local_host: bool = False


DESCRIPTIONS: tuple[HubBinaryDescription, ...] = (
    HubBinaryDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda d: d.online,
        available_fn=lambda d: d.online is not None,
    ),
    HubBinaryDescription(
        key="local_network",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda d: d.local_reachable,
        available_fn=lambda d: d.local_reachable is not None,
        needs_local_host=True,
    ),
    HubBinaryDescription(
        key="yolink_cloud",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda d: d.cloud_reachable,
    ),
    HubBinaryDescription(
        key="needs_review",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: bool(d.review_reasons),
        attrs_fn=lambda d: {"reasons": list(d.review_reasons)},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: YoLinkHubCoordinator = entry.runtime_data
    async_add_entities(
        HubBinarySensor(coordinator, desc)
        for desc in DESCRIPTIONS
        if coordinator.local_host or not desc.needs_local_host
    )


class HubBinarySensor(YoLinkHubEntity, BinarySensorEntity):
    """One binary sensor of the hub."""

    entity_description: HubBinaryDescription

    def __init__(self, coordinator: YoLinkHubCoordinator, desc: HubBinaryDescription) -> None:
        super().__init__(coordinator, desc.key)
        self.entity_description = desc

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.available_fn(self.coordinator.data)
        )

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data) if fn and self.coordinator.data else None
