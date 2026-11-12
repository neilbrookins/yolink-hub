"""Constants for the YoLink Hub integration."""

DOMAIN = "yolink_hub"

TOKEN_URL = "https://api.yosmart.com/open/yolink/token"
API_URL = "https://api.yosmart.com/open/yolink/v2/api"

CONF_UAID = "uaid"
CONF_SECRET_KEY = "secret_key"
CONF_HUB_ID = "hub_id"
CONF_HUB_TOKEN = "hub_token"
CONF_HUB_NAME = "hub_name"
CONF_HUB_TYPE = "hub_type"
CONF_HUB_MODEL = "hub_model"
CONF_LOCAL_HOST = "local_host"
CONF_SCAN_INTERVAL = "scan_interval"  # YoLink cloud check interval
CONF_PING_INTERVAL = "ping_interval"  # local ping interval

DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 300

DEFAULT_PING_INTERVAL = 10  # seconds
MIN_PING_INTERVAL = 5
MAX_PING_INTERVAL = 60

PING_COUNT = 3  # the hub counts as reachable if any of these is answered
PING_INTERVAL_WITHIN = 0.2  # seconds between the packets of one ping
PING_TIMEOUT = 1  # seconds to wait for each reply

# After the ping result changes, the cloud is checked until it agrees:
RECOVERY_FIRST_CHECK = 5  # seconds after the ping recovers (hub reconnecting)
FOLLOW_UP_EVERY = 5  # seconds between further checks while they disagree
FOLLOW_UP_WINDOW = 60  # give up after this many seconds; scheduled checks go on

MANUFACTURER = "YoSmart"
