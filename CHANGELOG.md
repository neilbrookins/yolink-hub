# Changelog

Each version's notes. A release on GitHub is made from its section here
by running the Release workflow (Actions tab): see .github/workflows/release.yml.

## 0.1.2

### Fixed
- Keeping the device page's firmware version current no longer uses a
  device-registry call Home Assistant has deprecated (it would stop working
  in Home Assistant 2027.8).

## 0.1.1

### Added
- **Icon** for the Marketplace and the integrations page: "YoLink HUB" on a
  dark tile, so it isn't confused with the official YoLink integration.
- Automatic checks on every push: the tests, HACS validation and hassfest.

## 0.1.0

### Added
- **The YoLink hub as a device** in Home Assistant, with Status, Online,
  Local network, YoLink cloud, DC, Battery, Firmware, Ethernet, Wi-Fi and
  Needs review. State names match the YoLink app (DC Connected /
  Disconnected; Battery Supply / Charging / Standby).
- **Local ping plus cloud check**, so Status tells a hub outage from an
  internet or YoLink cloud outage.
- **Needs review** turns on, with the reason, for anything not yet matched
  to the YoLink app: battery codes 0 and 4, other new codes, unexpected
  API replies and new fields.
- Set up and changed from the UI: User Access Credentials, the hub's LAN
  address, and how often to check (30–300 seconds).
