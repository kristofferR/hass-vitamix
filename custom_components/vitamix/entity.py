"""Shared base entity for the Vitamix integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import VitamixCoordinator


class VitamixEntity(CoordinatorEntity[VitamixCoordinator]):
    """Base class shared by all Vitamix entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VitamixCoordinator) -> None:
        super().__init__(coordinator)
        self._address = coordinator.address

    @property
    def device_info(self) -> DeviceInfo:
        # No model here: entities register before the first poll, and an
        # explicit model=None would clear it. The coordinator sets it instead.
        return DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            connections={(CONNECTION_BLUETOOTH, self._address)},
            manufacturer=MANUFACTURER,
            name=self.coordinator.entry.title,
        )
