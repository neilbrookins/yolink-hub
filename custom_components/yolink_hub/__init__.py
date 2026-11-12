"""YoLink Hub: hub status (online, DC power, battery, firmware) plus a local ping."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import YoLinkApi
from .const import CONF_SECRET_KEY, CONF_UAID
from .coordinator import YoLinkHubCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = YoLinkApi(
        async_get_clientsession(hass), entry.data[CONF_UAID], entry.data[CONF_SECRET_KEY]
    )
    coordinator = YoLinkHubCoordinator(hass, entry, api)
    await coordinator.async_start_pinging()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
