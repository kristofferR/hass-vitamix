"""Vitamix BLE integration for Home Assistant."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ADDRESS,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_extract_config_entry_ids
from vitamix_ble import ProgramStep, VitamixClient

from .const import DOMAIN
from .coordinator import VitamixCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

# Entities whose meaning was wrong, or whose registers the official app never
# reads. Removed so they don't linger as unavailable.
REMOVED_ENTITIES: tuple[tuple[Platform, str], ...] = (
    (Platform.BINARY_SENSOR, "armed"),
    (Platform.SENSOR, "recipe_slot"),
    (Platform.SENSOR, "rated_power"),
    (Platform.SENSOR, "max_rpm"),
    (Platform.SENSOR, "rated_rpm"),
)

# Only a call with none of these reaches every blender; an explicitly empty
# target (e.g. a template that matched nothing) reaches none.
TARGET_KEYS = {ATTR_AREA_ID, ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_FLOOR_ID, ATTR_LABEL_ID}

SERVICE_CANCEL = "cancel"
SERVICE_UPLOAD_PROGRAM = "upload_program"
SERVICE_LOAD_PROGRAM = "load_program"
SERVICE_SET_MOTOR_SPEED = "set_motor_speed"
SERVICE_START_MOTOR = "start_motor"
SERVICE_STOP_MOTOR = "stop_motor"
SERVICE_PLAY_MELODY = "play_melody"

ATTR_STEPS = "steps"
ATTR_POWER = "power"
ATTR_SECONDS = "seconds"
ATTR_RAMP = "ramp"
ATTR_CONTAINER_ID = "container_id"
ATTR_SLOT = "slot"
ATTR_SPEED = "speed"
ATTR_DURATION = "duration"
ATTR_NOTES = "notes"
ATTR_GAP = "gap"

# Services take device targets; HA injects target keys (device_id, ...)
# into call.data, which every schema tolerates via extra=vol.ALLOW_EXTRA.
SCHEMA_TARGET_ONLY = vol.Schema({}, extra=vol.ALLOW_EXTRA)

SCHEMA_STEP = vol.Schema(
    {
        vol.Required(ATTR_POWER): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        vol.Required(ATTR_SECONDS): vol.All(vol.Coerce(int), vol.Range(min=1, max=960)),
        vol.Optional(ATTR_RAMP, default=1.0): vol.All(
            vol.Coerce(float), vol.Range(min=0.0625, max=60)
        ),
    }
)

SCHEMA_UPLOAD_PROGRAM = vol.Schema(
    {
        vol.Required(ATTR_STEPS): vol.All([SCHEMA_STEP], vol.Length(min=1, max=4)),
        vol.Optional(ATTR_CONTAINER_ID): vol.All(int, vol.Range(min=1, max=5)),
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_LOAD_PROGRAM = vol.Schema(
    {vol.Required(ATTR_SLOT): vol.All(int, vol.Range(min=1, max=16))},
    extra=vol.ALLOW_EXTRA,
)

# Legacy speeds 0..10 (dial scale); duration in u16 seconds.
SCHEMA_SET_MOTOR_SPEED = vol.Schema(
    {
        vol.Required(ATTR_SPEED): vol.All(int, vol.Range(min=0, max=10)),
        vol.Optional(ATTR_DURATION, default=0xFFFF): vol.All(int, vol.Range(min=1, max=0xFFFF)),
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_START_MOTOR = vol.Schema(
    {
        vol.Optional(ATTR_SPEED, default=5): vol.All(int, vol.Range(min=1, max=10)),
        vol.Optional(ATTR_DURATION, default=0xFFFF): vol.All(int, vol.Range(min=1, max=0xFFFF)),
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_NOTE = vol.Schema(
    {
        vol.Required(ATTR_SPEED): vol.All(int, vol.Range(min=0, max=10)),
        vol.Required(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0.05, max=60.0)),
    }
)

SCHEMA_PLAY_MELODY = vol.Schema(
    {
        vol.Required(ATTR_NOTES): vol.All([SCHEMA_NOTE], vol.Length(min=1, max=64)),
        vol.Optional(ATTR_GAP, default=0.0): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=5.0)
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

Action = Callable[[ServiceCall], Callable[[VitamixClient], Awaitable[object]]]


def _upload(call: ServiceCall) -> Callable[[VitamixClient], Awaitable[object]]:
    steps = [
        ProgramStep(s[ATTR_POWER] / 100, s[ATTR_SECONDS], s[ATTR_RAMP])
        for s in call.data[ATTR_STEPS]
    ]
    container_id: int | None = call.data.get(ATTR_CONTAINER_ID)
    return lambda vmx: vmx.upload_program(steps, container_id=container_id)


def _play(call: ServiceCall) -> Callable[[VitamixClient], Awaitable[object]]:
    notes = [(n[ATTR_SPEED], n[ATTR_DURATION]) for n in call.data[ATTR_NOTES]]
    return lambda vmx: vmx.play_melody(notes, gap_seconds=call.data[ATTR_GAP])


# name -> (schema, action builder)
SERVICES: dict[str, tuple[vol.Schema, Action]] = {
    SERVICE_CANCEL: (
        SCHEMA_TARGET_ONLY,
        lambda _call: lambda vmx: vmx.cancel_program(),
    ),
    SERVICE_UPLOAD_PROGRAM: (SCHEMA_UPLOAD_PROGRAM, _upload),
}

# Only registered while some entry enables the experimental option.
EXPERIMENTAL_SERVICES: dict[str, tuple[vol.Schema, Action]] = {
    SERVICE_LOAD_PROGRAM: (
        SCHEMA_LOAD_PROGRAM,
        lambda call: lambda vmx: vmx.load_program(call.data[ATTR_SLOT]),
    ),
    SERVICE_SET_MOTOR_SPEED: (
        SCHEMA_SET_MOTOR_SPEED,
        lambda call: (
            lambda vmx: vmx.set_motor_speed(
                call.data[ATTR_SPEED], duration_seconds=call.data[ATTR_DURATION]
            )
        ),
    ),
    SERVICE_START_MOTOR: (
        SCHEMA_START_MOTOR,
        lambda call: (
            lambda vmx: vmx.start_motor(
                call.data[ATTR_SPEED], duration_seconds=call.data[ATTR_DURATION]
            )
        ),
    ),
    SERVICE_STOP_MOTOR: (
        SCHEMA_TARGET_ONLY,
        lambda _call: lambda vmx: vmx.stop_motor(),
    ),
    SERVICE_PLAY_MELODY: (SCHEMA_PLAY_MELODY, _play),
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vitamix from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    registry = er.async_get(hass)
    for platform, key in REMOVED_ENTITIES:
        if entity_id := registry.async_get_entity_id(platform, DOMAIN, f"{address}_{key}"):
            registry.async_remove(entity_id)

    coordinator = VitamixCoordinator(hass, entry, address)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    _async_sync_services(hass)
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _async_sync_services(hass)
    return unloaded


def _async_sync_services(hass: HomeAssistant) -> None:
    """Register the services the loaded entries need and remove the rest."""
    coordinators: dict[str, VitamixCoordinator] = hass.data.get(DOMAIN, {})
    wanted: dict[str, tuple[vol.Schema, Action]] = {}
    if coordinators:
        wanted |= SERVICES
    if any(c.experimental for c in coordinators.values()):
        wanted |= EXPERIMENTAL_SERVICES

    for name in (SERVICES | EXPERIMENTAL_SERVICES).keys() - wanted.keys():
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)

    for name, (schema, build) in wanted.items():
        if hass.services.has_service(DOMAIN, name):
            continue

        async def _handle(call: ServiceCall, name: str = name, build: Action = build) -> None:
            targets = await _resolve_coordinators(hass, call)
            if name in EXPERIMENTAL_SERVICES and (
                blocked := [c.entry.title for c in targets if not c.experimental]
            ):
                raise HomeAssistantError(
                    f"{name} is experimental; enable it in the options of {', '.join(blocked)}"
                )
            for coordinator in targets:
                await coordinator.async_command(name, build(call))

        hass.services.async_register(DOMAIN, name, _handle, schema=schema)


async def _resolve_coordinators(hass: HomeAssistant, call: ServiceCall) -> list[VitamixCoordinator]:
    """Find the coordinators targeted by ``call``; all of them without a target."""
    domain_data: dict[str, VitamixCoordinator] = hass.data.get(DOMAIN, {})
    if not TARGET_KEYS & call.data.keys():
        return list(domain_data.values())
    # Resolves device, entity, area, floor and label targets alike.
    entry_ids = await async_extract_config_entry_ids(call)
    coordinators = [c for entry_id, c in domain_data.items() if entry_id in entry_ids]
    if not coordinators:
        raise HomeAssistantError("no Vitamix device matched the service target")
    return coordinators
