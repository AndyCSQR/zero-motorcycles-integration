"""Constants for zero_motorcycles_integration."""
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

# we keep these constants, these shouldn't change anyway
DOMAIN = "zero_motorcycles_integration"

# Zero API configuration (from decompiled APK v2.13.0)
BASE_URL = "https://api-eu-cypherstore-prod.zeromotorcycles.com"
ENCRYPTION_KEY = "8FA043AADEC92367108D0E25D2C6064F"
SOURCE = "zero"
APP_VERSION = "2.13.0"
APP_CODE = "5.10.2"
LANG = "en-us"

# Config keys for stored tokens
CONF_TOKEN = "token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_SID = "sid"
