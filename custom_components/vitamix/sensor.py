"""Sensors for the Vitamix integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from vitamix_ble import BlenderState, VitamixState

from .const import DOMAIN
from .coordinator import VitamixCoordinator
from .entity import VitamixEntity


@dataclass(frozen=True, kw_only=True)
class VitamixSensorDescription(SensorEntityDescription):
    value_fn: Callable[[VitamixState], int | str | None]


SENSORS: tuple[VitamixSensorDescription, ...] = (
    VitamixSensorDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in BlenderState],
        value_fn=lambda s: s.state.value,
    ),
    VitamixSensorDescription(
        key="container",
        translation_key="container",
        value_fn=lambda s: s.container.short_name if s.container else None,
    ),
    VitamixSensorDescription(
        key="container_name",
        translation_key="container_name",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.container.name if s.container else None,
    ),
    VitamixSensorDescription(
        key="container_hardware_id",
        translation_key="container_hardware_id",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.container_id,
    ),
    VitamixSensorDescription(
        key="container_max_runtime",
        translation_key="container_max_runtime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.container.max_runtime_s if s.container else None,
    ),
    VitamixSensorDescription(
        key="recipe_state",
        translation_key="recipe_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.recipe_state,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VitamixCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(VitamixSensor(coordinator, description) for description in SENSORS)


class VitamixSensor(VitamixEntity, SensorEntity):
    entity_description: VitamixSensorDescription

    def __init__(
        self,
        coordinator: VitamixCoordinator,
        description: VitamixSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

    @property
    def native_value(self) -> int | str | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
