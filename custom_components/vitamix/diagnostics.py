"""Diagnostics for the Vitamix integration."""

from __future__ import annotations

import dataclasses
import time
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothReachabilityIntent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS, DOMAIN
from .coordinator import VitamixCoordinator

REDACTED = "**REDACTED**"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    address = entry.data[CONF_ADDRESS].upper()

    def redact(text: str | None) -> str | None:
        return text.replace(address, REDACTED) if text else text

    info = bluetooth.async_last_service_info(hass, address, connectable=True)
    advertisement = None
    if info is not None:
        advertisement = {
            # HA reports the address as the name when none was advertised.
            "name": redact(info.name),
            "rssi": info.rssi,
            "source": info.source,
            "age_s": round(time.monotonic() - info.time, 1),
            "service_uuids": info.service_uuids,
            "manufacturer_data": {k: v.hex() for k, v in info.manufacturer_data.items()},
        }
    reachability = bluetooth.async_address_reachability_diagnostics(
        hass, address, BluetoothReachabilityIntent.CONNECTION
    )
    result: dict[str, Any] = {
        "advertisement": advertisement,
        "reachability": redact(reachability),
    }
    # While setup is retrying there is no coordinator yet.
    coordinator: VitamixCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is not None:
        panel, state, success = coordinator.panel, coordinator.data, coordinator.last_success
        result |= {
            "panel": dataclasses.asdict(panel) if panel else None,
            "state": dataclasses.asdict(state) if state else None,
            "last_success": success.isoformat() if success else None,
            "last_error": redact(coordinator.last_error),
            "experimental": coordinator.experimental,
        }
    return result
