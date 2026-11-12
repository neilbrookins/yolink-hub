# Changelog

Each version's notes. A release on GitHub is made from its section here
by running the Release workflow (Actions tab): see .github/workflows/release.yml.

## 0.1.6

### Changed
- **Several hubs work better together.** Add the integration once per hub;
  the same UAID and Secret Key work for every hub on the account. The hub
  list now leaves out hubs already set up (and says so when all are), hubs
  on the same account share one access token, and a token replaced by a
  newer one is renewed and the request retried instead of showing the cloud
  as unreachable.
- **Hubs without a battery or "online" field** (SpeakerHub, per YoLink's
  docs): a successful reply counts as online, and the SpeakerHub's
  documented speaker options no longer trigger Needs review. Not yet tested
  on real hardware other than the Pro Hub.

## 0.1.5

### Added
- **Battery state since**: when the battery's current state (Supply,
  Charging, Standby, ...) began, which Home Assistant shows as "12 minutes
  ago". The API gives no charge percentage, so this honest duration stands
  in for one: on Supply, it is how long the hub has been on battery. It
  restarts only when the battery state changes, not when the hub drops
  offline and returns in the same state, nor across Home Assistant
  restarts. Its attribute exact_start is false when the change wasn't seen
  as it happened (first setup, or a change while Home Assistant was stopped
  or the hub couldn't be read); the time is then when it was first seen.

## 0.1.4

### Changed
- **After the ping result changes, the cloud is asked until it agrees.**
  When the ping fails the cloud is checked at once; when it recovers, 5
  seconds later (the hub needs a moment to reconnect to YoLink). If the
  cloud still disagrees with the ping, it is asked again every 5 seconds,
  for at most a minute, before falling back to the scheduled checks. In
  testing, the cloud reported the hub back online about a minute late,
  because the only check after the ping recovered came before the hub had
  reconnected.
- **Faster ping:** 1-second reply timeout (was 2) and 0.2 seconds between
  its three packets, so an unplugged hub is noticed within about 1.5
  seconds of a ping. The hub still counts as reachable if any of the
  three is answered.

## 0.1.3

### Changed
- **The local ping and the YoLink cloud check have separate intervals.**
  The ping is cheap, so it runs often (default every 10 seconds, 5–60); the
  cloud check stays considerate of YoLink's servers (default every 60
  seconds, 30–300). Your existing interval is kept as the cloud interval.
- **When the ping result changes, the cloud is checked right away**, so
  Status settles within seconds of the hub dropping off (or coming back on)
  the LAN, without polling the cloud more often.

### Added
- **Last cloud check** (diagnostic): when the YoLink cloud was last asked,
  with the reason (scheduled, ping failed, ping recovered, startup) as an
  attribute. Comparing it with Online shows how quickly the cloud notices
  the hub going offline.

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
