# YoLink Hub

A Home Assistant custom integration that monitors the **YoLink hub itself**: whether it is online, whether it is on AC power or its backup battery, its firmware, and its network connection.

The official YoLink integration shows the sensors connected through a hub but not the hub. This integration fills that gap and runs alongside the official one. A request to add hub support to the official integration is open at [home-assistant discussion #3141](https://github.com/orgs/home-assistant/discussions/3141).

## What it shows

Everything appears on one **hub device** page. State names match the YoLink app's wording.

| Entity | States | Source |
|---|---|---|
| Status | Online / Offline / YoLink cloud unreachable, hub reachable on LAN / … | Cloud + local ping combined |
| Online | Connected / Disconnected | YoLink cloud (`Hub.getState`) |
| Local network | Connected / Disconnected | Ping of the hub's LAN address |
| YoLink cloud | Connected / Disconnected | Whether Home Assistant can reach the YoLink API |
| DC | Connected / Disconnected | `other.power.dc` |
| Battery | Supply / Charging / Standby | `other.power.batteryState` 1 / 2 / 3 |
| Last cloud check *(diagnostic)* | When the YoLink cloud was last asked, with the reason as an attribute | |
| Firmware *(diagnostic)* | e.g. 1316 | `version` |
| Ethernet, Wi-Fi *(diagnostic)* | Connected / Not Connected, with IP, gateway and mask as attributes | `eth`, `wifi` |
| Needs review *(diagnostic)* | Problem / OK, with a `reasons` list | Anything the integration doesn't recognize yet |

### Telling outages apart

Pinging the hub on your LAN as well as asking the YoLink cloud separates the cases the YoLink app can't:

| YoLink cloud | Hub online (cloud) | Local ping | Status |
|---|---|---|---|
| reachable | yes | replies | Online |
| reachable | no | no reply | Offline |
| reachable | no | replies | Offline in cloud, reachable on LAN (the hub has lost its internet path) |
| unreachable | – | replies | YoLink cloud unreachable, hub reachable on LAN (internet or YoLink outage) |
| unreachable | – | no reply | YoLink cloud and hub both unreachable |

When the hub's state can't be read, DC, Battery, Firmware and network sensors go **unavailable** instead of showing old values.

### Needs review

Anything new or unexpected turns on **Needs review** and lists the reason, so it can be compared with the YoLink app and added here:

- battery state codes 0 and 4 (documented by YoLink, but the app's wording hasn't been confirmed yet) or any other unrecognized code
- an unexpected API response code
- a field the API hasn't returned before
- a value of the wrong type

## Installation

1. In HACS (the Marketplace), add `https://github.com/neilbrookins/yolink-hub` as a custom repository, category **Integration**, and download **YoLink Hub**.
2. Restart Home Assistant.
3. **Settings → Devices & services → Add integration → YoLink Hub.**

## Setup

1. In the YoLink app: **Settings → Account → Advanced Settings → User Access Credentials**. Tap **+** if none exist, then copy the **UAID** and **Secret Key**.
2. Enter them in Home Assistant. If the account has more than one hub, pick one.
3. Enter the hub's LAN IP address for the local check (suggested from what the hub reports; a DHCP reservation for the hub is recommended), how often to ping it (5–60 seconds, default 10), and how often to check the YoLink cloud (30–300 seconds, default 60).

These settings can be changed later under the integration's **Configure** button.

## Notes

- Polls the YoLink cloud API, reusing the access token until it is about to expire, so one check costs one API request.
- The ping runs on its own, faster timer. When the hub stops answering, the cloud is checked at once; when it starts answering again, 5 seconds later, giving the hub time to reconnect to YoLink. Either way, the cloud is asked again every 5 seconds until it agrees with the ping, for at most a minute.
- Uses its own User Access Credentials, separate from the official integration's login.
- "Update available" for hub firmware isn't possible yet: the API reports only the installed version.

## Tests

```
python3 tests/test_status.py     # parsing, against real Pro Hub (YS1613-UC) API captures
python3 tests/simulate_ha.py     # coordinator and entities with Home Assistant stubbed out
```
