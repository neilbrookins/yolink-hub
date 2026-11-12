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
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 300

PING_COUNT = 3
PING_TIMEOUT = 2  # seconds per reply

MANUFACTURER = "YoSmart"
