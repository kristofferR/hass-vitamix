"""Binary sensors for the Vitamix integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from vitamix_ble import VitamixState

from .const import DOMAIN
from .coordinator import VitamixCoordinator
from .entity import VitamixEntity


@dataclass(frozen=True, kw_only=True)
class VitamixBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[VitamixState], bool | None]


BINARY_SENSORS: tuple[VitamixBinarySensorDescription, ...] = (
    VitamixBinarySensorDescription(
        key="motor_running",
        translation_key="motor_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda s: s.motor_running,
    ),
    VitamixBinarySensorDescription(
        key="sleeping",
        translation_key="sleeping",
        value_fn=lambda s: s.sleeping,
    ),
    VitamixBinarySensorDescription(
        key="container_attached",
        translation_key="container_attached",
        device_class=BinarySensorDeviceClass.PRESENCE,
        value_fn=lambda s: s.container_present,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VitamixCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        VitamixBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class VitamixBinarySensor(VitamixEntity, BinarySensorEntity):
    entity_description: VitamixBinarySensorDescription

    def __init__(
        self,
        coordinator: VitamixCoordinator,
        description: VitamixBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
