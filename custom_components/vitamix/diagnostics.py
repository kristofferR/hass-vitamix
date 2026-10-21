"""Diagnostics for the Vitamix integration."""

from __future__ import annotations

import dataclasses
import time
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import VitamixCoordinator

REDACTED = "**REDACTED**"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: VitamixCoordinator = hass.data[DOMAIN][entry.entry_id]
    address = coordinator.address
    info = bluetooth.async_last_service_info(hass, address, connectable=True)
    advertisement = None
    if info is not None:
        advertisement = {
            "name": info.name,
            "rssi": info.rssi,
            "source": info.source,
            "age_s": round(time.monotonic() - info.time, 1),
            "service_uuids": info.service_uuids,
            "manufacturer_data": {k: v.hex() for k, v in info.manufacturer_data.items()},
        }
    panel = coordinator.panel
    state = coordinator.data
    return {
        "panel": dataclasses.asdict(panel) if panel else None,
        "state": dataclasses.asdict(state) if state else None,
        "last_success": coordinator.last_success.isoformat() if coordinator.last_success else None,
        "last_error": (coordinator.last_error or "").replace(address, REDACTED) or None,
        "experimental": coordinator.experimental,
        "advertisement": advertisement,
        "reachability": coordinator.reachability().replace(address, REDACTED),
    }
