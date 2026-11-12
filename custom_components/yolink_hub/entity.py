"""Base entity: every entity belongs to the one hub device."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HUB_MODEL, CONF_HUB_NAME, DOMAIN, MANUFACTURER
from .coordinator import YoLinkHubCoordinator


class YoLinkHubEntity(CoordinatorEntity[YoLinkHubCoordinator]):
    """Shared device info and unique IDs."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: YoLinkHubCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{coordinator.hub_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.hub_id)},
            name=entry.data.get(CONF_HUB_NAME, "YoLink Hub"),
            manufacturer=MANUFACTURER,
            model=entry.data.get(CONF_HUB_MODEL),
            sw_version=coordinator.data.version if coordinator.data else None,
        )
