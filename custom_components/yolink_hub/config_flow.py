"""UI setup: credentials, pick the hub, local address and polling interval."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import YoLinkApi, YoLinkAuthError, YoLinkCloudError
from .const import (
    CONF_HUB_ID,
    CONF_HUB_MODEL,
    CONF_HUB_NAME,
    CONF_HUB_TOKEN,
    CONF_HUB_TYPE,
    CONF_LOCAL_HOST,
    CONF_SCAN_INTERVAL,
    CONF_SECRET_KEY,
    CONF_UAID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _is_hub(dev: dict[str, Any]) -> bool:
    return "hub" in str(dev.get("type", "")).lower()


def _interval_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL,
            max=MAX_SCAN_INTERVAL,
            step=10,
            unit_of_measurement="seconds",
            mode=NumberSelectorMode.BOX,
        )
    )


class YoLinkHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a YoLink hub."""

    VERSION = 1

    def __init__(self) -> None:
        self._creds: dict[str, str] = {}
        self._hubs: list[dict[str, Any]] = []
        self._hub: dict[str, Any] = {}
        self._api: YoLinkApi | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the YoLink User Access Credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            uaid = user_input[CONF_UAID].strip()
            secret = user_input[CONF_SECRET_KEY].strip()
            api = YoLinkApi(async_get_clientsession(self.hass), uaid, secret)
            try:
                devices = await api.device_list()
            except YoLinkAuthError:
                errors["base"] = "invalid_auth"
            except YoLinkCloudError as err:
                _LOGGER.warning("YoLink cloud error during setup: %s", err)
                errors["base"] = "cannot_connect"
            else:
                self._hubs = [d for d in devices if _is_hub(d)]
                if not self._hubs:
                    errors["base"] = "no_hubs"
                else:
                    self._creds = {CONF_UAID: uaid, CONF_SECRET_KEY: secret}
                    self._api = api
                    if len(self._hubs) == 1:
                        return await self._select_hub(self._hubs[0])
                    return await self.async_step_hub()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UAID): TextSelector(),
                    vol.Required(CONF_SECRET_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_hub(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick the hub when the account has more than one."""
        if user_input is not None:
            hub = next(h for h in self._hubs if h["deviceId"] == user_input[CONF_HUB_ID])
            return await self._select_hub(hub)
        options = [
            SelectOptionDict(
                value=h["deviceId"], label=f"{h.get('name')} ({h.get('modelName')})"
            )
            for h in self._hubs
        ]
        return self.async_show_form(
            step_id="hub",
            data_schema=vol.Schema(
                {vol.Required(CONF_HUB_ID): SelectSelector(SelectSelectorConfig(options=options))}
            ),
        )

    async def _select_hub(self, hub: dict[str, Any]) -> ConfigFlowResult:
        await self.async_set_unique_id(hub["deviceId"])
        self._abort_if_unique_id_configured()
        self._hub = hub
        return await self.async_step_local()

    async def async_step_local(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Local address to ping, and how often to poll."""
        if user_input is not None:
            hub = self._hub
            return self.async_create_entry(
                title=hub.get("name") or "YoLink Hub",
                data={
                    **self._creds,
                    CONF_HUB_ID: hub["deviceId"],
                    CONF_HUB_TOKEN: hub["token"],
                    CONF_HUB_TYPE: hub["type"],
                    CONF_HUB_NAME: hub.get("name") or "YoLink Hub",
                    CONF_HUB_MODEL: hub.get("modelName"),
                },
                options={
                    CONF_LOCAL_HOST: (user_input.get(CONF_LOCAL_HOST) or "").strip(),
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                },
            )

        # Suggest the address the hub reports for itself.
        suggested = ""
        try:
            reply = await self._api.get_state(
                self._hub["type"], self._hub["deviceId"], self._hub["token"]
            )
            data = reply.get("data") or {}
            for link in ("eth", "wifi"):
                part = data.get(link) or {}
                if part.get("enable") and part.get("ip"):
                    suggested = part["ip"]
                    break
        except (YoLinkCloudError, YoLinkAuthError):
            pass

        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LOCAL_HOST, description={"suggested_value": suggested}
                    ): TextSelector(),
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): _interval_selector(),
                }
            ),
            description_placeholders={"hub": self._hub.get("name", "")},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return YoLinkHubOptionsFlow()


class YoLinkHubOptionsFlow(OptionsFlow):
    """Change the local address or polling interval later."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_LOCAL_HOST: (user_input.get(CONF_LOCAL_HOST) or "").strip(),
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                }
            )
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LOCAL_HOST,
                        description={"suggested_value": opts.get(CONF_LOCAL_HOST, "")},
                    ): TextSelector(),
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): _interval_selector(),
                }
            ),
        )
