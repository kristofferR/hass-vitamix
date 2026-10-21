"""Constants for the Vitamix custom component."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "vitamix"

# How often to poll while the motor is idle / running.
SCAN_INTERVAL_IDLE_S: Final = 60.0
SCAN_INTERVAL_RUNNING_S: Final = 5.0

# When we lose contact, how long to wait before declaring the device unavailable.
AVAILABILITY_GRACE_S: Final = 300.0

# Discovery: the official app matches the service UUID, but some proxies only
# relay the local name (the UUID may be in the scan response), so match both.
ADV_LOCAL_NAME: Final = "Vitamix_2.0"
SERVICE_UUID: Final = "4a310001-cf3c-4cb9-bed6-2ea871b8d070"

# Default device name shown in the HA UI before users rename it.
DEFAULT_DEVICE_NAME: Final = "Vitamix"

# Manufacturer label.
MANUFACTURER: Final = "Vitamix"

# Config-entry data keys.
CONF_ADDRESS: Final = "address"
