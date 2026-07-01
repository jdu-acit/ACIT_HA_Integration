"""Constants for the ACIT ThermACEC integration."""
from typing import Final

# Integration domain
DOMAIN: Final = "acit"

# Default configuration
DEFAULT_NAME: Final = "ACIT ThermACEC"
DEFAULT_PORT: Final = 80
DEFAULT_SCAN_INTERVAL: Final = 30

# mDNS/Zeroconf
MDNS_SERVICE_TYPE: Final = "_acit._tcp.local."
MDNS_HOSTNAME_PREFIX: Final = "acit-thermacec-"

# HTTP RPC
RPC_ENDPOINT: Final = "/rpc"
RPC_TIMEOUT: Final = 10

# WebSocket
WS_ENDPOINT: Final = "/ws"
WS_RECONNECT_DELAY: Final = 5
WS_PING_INTERVAL: Final = 30

# JSON-RPC Methods
RPC_METHOD_GET_STATUS: Final = "Thermostat.GetStatus"
RPC_METHOD_GET_CONFIG: Final = "Thermostat.GetConfig"
RPC_METHOD_SET_TARGET_TEMP: Final = "Thermostat.SetTargetTemp"
RPC_METHOD_SET_MODE: Final = "Thermostat.SetMode"
RPC_METHOD_SYSTEM_REBOOT: Final = "System.Reboot"
RPC_METHOD_REQUEST_TOKEN: Final = "System.RequestToken"

# JSON-RPC Methods - OTA
RPC_METHOD_CHECK_UPDATE: Final = "System.CheckUpdate"
RPC_METHOD_START_OTA: Final = "System.StartOTA"
RPC_METHOD_GET_OTA_STATUS: Final = "System.GetOTAStatus"

# WebSocket Notifications
WS_NOTIFY_STATUS: Final = "NotifyStatus"

# Temperature limits
MIN_TEMP: Final = 5.0
MAX_TEMP: Final = 35.0
TEMP_STEP: Final = 0.1

# Modes HVAC
HVAC_MODE_OFF: Final = "off"
HVAC_MODE_HEAT: Final = "heat"
HVAC_MODE_COOL: Final = "cool"
HVAC_MODE_AUTO: Final = "auto"

# Update interval (seconds) - used as fallback if WebSocket fails
UPDATE_INTERVAL: Final = 30

# Availability timeout (seconds)
AVAILABILITY_TIMEOUT: Final = 60
