"""Constants for the Daze Wallbox integration."""

from homeassistant.const import Platform

DOMAIN = "daze"

# Config entry keys
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_TOKEN_EXPIRY = "token_expiry"
CONF_EMAIL = "email"
CONF_NETWORK_UID = "network_uid"
CONF_NETWORK_NAME = "network_name"
CONF_EVSE_NAME = "evse_name"
CONF_SERIAL_NUMBER = "serial_number"
CONF_DEVICE_PROFILE = "device_profile"
CONF_FIRMWARE_VERSION = "firmware_version"
CONF_SOFTWARE_VERSION = "software_version"
CONF_POLL_INTERVAL = "poll_interval"
CONF_AUTH_METHOD = "auth_method"
CONF_PASSWORD = "password"

# Auth method constants
AUTH_METHOD_TOKEN = "token"
AUTH_METHOD_CREDENTIALS = "credentials"

# Coordinator defaults
DEFAULT_POLL_INTERVAL = 30  # seconds

# Platform list
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
]

# Service names
SERVICE_START_CHARGE = "start_charge"
SERVICE_STOP_CHARGE = "stop_charge"
SERVICE_SET_CHARGING_CURRENT = "set_charging_current"
