"""Shared base entity for the Vitamix integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from vitamix_ble import PanelType

from .const import DOMAIN, MANUFACTURER
from .coordinator import VitamixCoordinator

PANEL_NAMES = {PanelType.C: "C-panel", PanelType.B: "B-panel", PanelType.OLD_B: "Old B-panel"}


class VitamixEntity(CoordinatorEntity[VitamixCoordinator]):
    """Base class shared by all Vitamix entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VitamixCoordinator) -> None:
        super().__init__(coordinator)
        self._address = coordinator.address

    @property
    def device_info(self) -> DeviceInfo:
        panel = self.coordinator.panel
        return DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            connections={(CONNECTION_BLUETOOTH, self._address)},
            manufacturer=MANUFACTURER,
            name=self.coordinator.entry.title,
            model=panel.model if panel else None,
            hw_version=PANEL_NAMES[panel.panel] if panel else None,
        )
