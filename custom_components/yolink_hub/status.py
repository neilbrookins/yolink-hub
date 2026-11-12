"""Turn a YoLink Hub.getState response and a local ping result into hub status.

This module has no Home Assistant imports so it can be tested on its own.

Anything the YoLink API returns that we have not seen and matched to the
YoLink app's wording is listed in ``review_reasons``. The integration shows
those through its "Needs review" sensor so the new value can be compared with
the YoLink app and added here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CODE_SUCCESS = "000000"
CODE_DEVICE_OFFLINE = "000201"  # "Cannot connect to the device"
KNOWN_CODES = frozenset({CODE_SUCCESS, CODE_DEVICE_OFFLINE})

# batteryState codes, with the words the YoLink app shows for them.
# Confirmed by comparing the API with the app on a Pro Hub (YS1613-UC):
BATTERY_CONFIRMED: dict[int, str] = {
    1: "supply",  # app: "Supply" (battery powering the hub)
    2: "charging",  # app: "Charging"
    3: "standby",  # app: "Standby"
}
# Documented by YoLink (CellularHub docs) but not yet seen in the app:
BATTERY_DOCUMENTED: dict[int, str] = {
    0: "code_0",  # YoLink docs: no battery connected
    4: "code_4",  # YoLink docs: battery under maintenance
}
BATTERY_UNRECOGNIZED = "unrecognized"
BATTERY_DOC_MEANING = {
    0: "no battery connected",
    4: "battery under maintenance",
}

# Fields seen from the Pro Hub, plus the ones YoLink documents for hubs.
# A field outside this list is reported for review.
KNOWN_PATHS = frozenset(
    {
        "online",
        "version",
        "wifi.enable",
        "wifi.ssid",
        "wifi.ip",
        "wifi.gateway",
        "wifi.mask",
        "eth.enable",
        "eth.ip",
        "eth.gateway",
        "eth.mask",
        "other.supportNRP",
        "other.power.dc",
        "other.power.battery",
        "other.power.batteryState",
        "cellular.enable",
        "cellular.iccid",
        "cellular.module.enable",
        "cellular.module.ver",
        "cellular.module.imei",
        # SpeakerHub (YoLink docs)
        "options.volume",
        "options.enableBeep",
        "options.mute",
    }
)

# Overall status values (shown with friendly names via translations).
STATUS_ONLINE = "online"
STATUS_ONLINE_NO_PING = "online_no_ping"
STATUS_OFFLINE = "offline"
STATUS_OFFLINE_LAN_OK = "offline_cloud_lan_ok"
STATUS_CLOUD_DOWN_LAN_OK = "cloud_down_lan_ok"
STATUS_CLOUD_DOWN_LAN_DOWN = "cloud_down_lan_down"
STATUS_CLOUD_DOWN = "cloud_down"
STATUS_UNEXPECTED = "unexpected_response"
STATUSES = [
    STATUS_ONLINE,
    STATUS_ONLINE_NO_PING,
    STATUS_OFFLINE,
    STATUS_OFFLINE_LAN_OK,
    STATUS_CLOUD_DOWN_LAN_OK,
    STATUS_CLOUD_DOWN_LAN_DOWN,
    STATUS_CLOUD_DOWN,
    STATUS_UNEXPECTED,
]


@dataclass
class HubData:
    """Everything the entities show, from one poll."""

    cloud_reachable: bool
    local_reachable: bool | None  # None = no local address configured
    status: str
    api_code: str | None = None
    api_desc: str | None = None
    online: bool | None = None  # None = unknown (cloud unreachable or odd reply)
    has_state: bool = False  # True when the reply carried the hub's state
    version: str | None = None
    dc: bool | None = None
    battery_present: bool | None = None
    battery_code: int | None = None
    battery_state: str | None = None
    eth_connected: bool | None = None
    eth: dict[str, Any] = field(default_factory=dict)
    wifi_connected: bool | None = None
    wifi: dict[str, Any] = field(default_factory=dict)
    review_reasons: list[str] = field(default_factory=list)
    cloud_checked_at: Any = None  # when the cloud was last asked (set by the coordinator)
    cloud_check_reason: str | None = None  # scheduled / ping failed / ping recovered / startup


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    """Return {"a.b.c": leaf} for every leaf in nested dicts."""
    if isinstance(value, dict) and value:
        out: dict[str, Any] = {}
        for key, sub in value.items():
            out.update(_flatten(sub, f"{prefix}.{key}" if prefix else str(key)))
        return out
    return {prefix: value} if prefix else {}


def _bool(value: Any, path: str, reasons: list[str]) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    reasons.append(f"Unexpected value for {path}: {value!r} (expected true/false)")
    return None


def parse(
    response: dict[str, Any] | None,
    local_reachable: bool | None,
    extra_reasons: list[str] | None = None,
) -> HubData:
    """Build HubData from a Hub.getState reply (None = cloud unreachable)."""
    reasons: list[str] = list(extra_reasons or [])

    if response is None:
        if local_reachable is True:
            status = STATUS_CLOUD_DOWN_LAN_OK
        elif local_reachable is False:
            status = STATUS_CLOUD_DOWN_LAN_DOWN
        else:
            status = STATUS_CLOUD_DOWN
        return HubData(
            cloud_reachable=False,
            local_reachable=local_reachable,
            status=status,
            review_reasons=reasons,
        )

    code = str(response.get("code", ""))
    desc = response.get("desc")
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    hub = HubData(
        cloud_reachable=True,
        local_reachable=local_reachable,
        status=STATUS_UNEXPECTED,
        api_code=code,
        api_desc=desc,
    )

    if code not in KNOWN_CODES:
        reasons.append(f"Unexpected YoLink API response code {code}: {desc}")
        hub.review_reasons = reasons
        return hub

    if code == CODE_DEVICE_OFFLINE:
        hub.online = False
    else:
        hub.has_state = True
        for path, leaf in sorted(_flatten(data).items()):
            if path not in KNOWN_PATHS:
                reasons.append(f"New field from YoLink API: {path} = {leaf!r}")

        # YoLink's docs for some hubs don't list "online"; a successful reply
        # means the cloud reached the hub (an offline hub gives 000201).
        hub.online = _bool(data.get("online", True), "online", reasons)

        version = data.get("version")
        hub.version = str(version) if version is not None else None

        eth = data.get("eth") if isinstance(data.get("eth"), dict) else {}
        hub.eth = eth
        hub.eth_connected = _bool(eth.get("enable"), "eth.enable", reasons)
        wifi = data.get("wifi") if isinstance(data.get("wifi"), dict) else {}
        hub.wifi = wifi
        hub.wifi_connected = _bool(wifi.get("enable"), "wifi.enable", reasons)

        other = data.get("other") if isinstance(data.get("other"), dict) else {}
        power = other.get("power") if isinstance(other.get("power"), dict) else {}
        hub.dc = _bool(power.get("dc"), "other.power.dc", reasons)
        hub.battery_present = _bool(
            power.get("battery"), "other.power.battery", reasons
        )
        if hub.battery_present is False:
            reasons.append(
                "YoLink API reports no battery connected (other.power.battery = false)"
            )

        if "batteryState" in power:
            raw = power.get("batteryState")
            if isinstance(raw, bool) or not isinstance(raw, int):
                reasons.append(f"Unexpected battery state value: {raw!r}")
                hub.battery_state = BATTERY_UNRECOGNIZED
            else:
                hub.battery_code = raw
                if raw in BATTERY_CONFIRMED:
                    hub.battery_state = BATTERY_CONFIRMED[raw]
                elif raw in BATTERY_DOCUMENTED:
                    hub.battery_state = BATTERY_DOCUMENTED[raw]
                    reasons.append(
                        f"Battery state code {raw} seen (YoLink docs: "
                        f"{BATTERY_DOC_MEANING[raw]}); check the YoLink app's wording"
                    )
                else:
                    hub.battery_state = BATTERY_UNRECOGNIZED
                    reasons.append(f"Unrecognized battery state code {raw}")

    if hub.online is True:
        hub.status = (
            STATUS_ONLINE_NO_PING if local_reachable is False else STATUS_ONLINE
        )
    elif hub.online is False:
        hub.status = STATUS_OFFLINE_LAN_OK if local_reachable else STATUS_OFFLINE

    hub.review_reasons = reasons
    return hub
