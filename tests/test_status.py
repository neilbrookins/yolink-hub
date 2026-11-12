"""Tests for status.py against real Pro Hub (YS1613-UC) captures.

Run with:  python3 -m pytest tests  (or: python3 tests/test_status.py)
"""

import copy
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = pathlib.Path(__file__).resolve().parent / "fixtures"

# Load status.py directly so Home Assistant isn't needed for these tests.
_spec = importlib.util.spec_from_file_location(
    "status", ROOT / "custom_components" / "yolink_hub" / "status.py"
)
status = importlib.util.module_from_spec(_spec)
sys.modules["status"] = status
_spec.loader.exec_module(status)


def load(name):
    return json.loads((FIX / f"{name}.json").read_text())


def test_normal():
    hub = status.parse(load("normal"), True)
    assert hub.status == status.STATUS_ONLINE
    assert hub.online is True and hub.dc is True
    assert hub.battery_state == "standby" and hub.battery_code == 3
    assert hub.version == "1316"
    assert hub.eth_connected is True and hub.eth["ip"] == "192.168.0.250"
    assert hub.wifi_connected is False
    assert hub.review_reasons == []


def test_ac_unplugged():
    hub = status.parse(load("ac_unplugged"), True)
    assert hub.dc is False and hub.battery_state == "supply"
    assert hub.status == status.STATUS_ONLINE
    assert hub.review_reasons == []


def test_ac_restored():
    hub = status.parse(load("ac_restored"), True)
    assert hub.dc is True and hub.battery_state == "charging"
    assert hub.review_reasons == []


def test_ethernet_unplugged():
    hub = status.parse(load("ethernet_unplugged"), False)
    assert hub.cloud_reachable is True
    assert hub.online is False and hub.has_state is False
    assert hub.status == status.STATUS_OFFLINE
    assert hub.dc is None and hub.battery_state is None  # no stale values
    assert hub.review_reasons == []


def test_offline_but_lan_ok():
    hub = status.parse(load("ethernet_unplugged"), True)
    assert hub.status == status.STATUS_OFFLINE_LAN_OK


def test_cloud_down():
    assert status.parse(None, True).status == status.STATUS_CLOUD_DOWN_LAN_OK
    assert status.parse(None, False).status == status.STATUS_CLOUD_DOWN_LAN_DOWN
    assert status.parse(None, None).status == status.STATUS_CLOUD_DOWN
    hub = status.parse(None, True)
    assert hub.online is None and hub.review_reasons == []


def test_online_no_ping():
    hub = status.parse(load("normal"), False)
    assert hub.status == status.STATUS_ONLINE_NO_PING


def test_no_local_address():
    hub = status.parse(load("normal"), None)
    assert hub.status == status.STATUS_ONLINE


def _with_battery(code):
    resp = copy.deepcopy(load("normal"))
    resp["data"]["other"]["power"]["batteryState"] = code
    return resp


def test_documented_battery_codes_flagged():
    for code, state in ((0, "code_0"), (4, "code_4")):
        hub = status.parse(_with_battery(code), True)
        assert hub.battery_state == state and hub.battery_code == code
        assert len(hub.review_reasons) == 1
        assert f"code {code}" in hub.review_reasons[0]


def test_unrecognized_battery_code_flagged():
    hub = status.parse(_with_battery(7), True)
    assert hub.battery_state == status.BATTERY_UNRECOGNIZED
    assert hub.review_reasons == ["Unrecognized battery state code 7"]


def test_unexpected_api_code_flagged():
    resp = {"code": "010104", "desc": "Token is expired", "data": {}}
    hub = status.parse(resp, True)
    assert hub.status == status.STATUS_UNEXPECTED and hub.online is None
    assert "010104" in hub.review_reasons[0]


def test_new_field_flagged():
    resp = copy.deepcopy(load("normal"))
    resp["data"]["other"]["power"]["batteryLevel"] = 80
    hub = status.parse(resp, True)
    assert hub.review_reasons == [
        "New field from YoLink API: other.power.batteryLevel = 80"
    ]


def test_no_battery_flagged():
    resp = copy.deepcopy(load("normal"))
    resp["data"]["other"]["power"]["battery"] = False
    hub = status.parse(resp, True)
    assert any("no battery" in r for r in hub.review_reasons)


def test_odd_dc_value_flagged():
    resp = copy.deepcopy(load("normal"))
    resp["data"]["other"]["power"]["dc"] = "yes"
    hub = status.parse(resp, True)
    assert hub.dc is None
    assert any("other.power.dc" in r for r in hub.review_reasons)


def test_speakerhub_documented_fields_not_flagged():
    # Shape from YoLink's SpeakerHub.getState docs (no hardware tested):
    # no power section, plus speaker options.
    resp = {"code": "000000", "desc": "Success", "data": {
        "version": "0402",  # docs list no "online" field
        "wifi": {"enable": True, "ssid": "home", "ip": "192.168.1.20",
                 "gateway": "192.168.1.1", "mask": "255.255.255.0"},
        "eth": {"enable": False},
        "options": {"volume": 8, "enableBeep": True, "mute": False}}}
    hub = status.parse(resp, True)
    assert hub.review_reasons == []
    assert hub.status == status.STATUS_ONLINE
    assert hub.dc is None and hub.battery_state is None  # no battery: those stay unavailable
    assert hub.wifi_connected is True and hub.eth_connected is False


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
