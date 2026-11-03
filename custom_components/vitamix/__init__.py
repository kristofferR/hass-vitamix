"""Vitamix BLE integration for Home Assistant."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import VitamixCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

SERVICE_CANCEL = "cancel"
SERVICE_LOAD_PROGRAM = "load_program"
SERVICE_SET_MOTOR_SPEED = "set_motor_speed"
SERVICE_START_MOTOR = "start_motor"
SERVICE_STOP_MOTOR = "stop_motor"
SERVICE_PLAY_MELODY = "play_melody"

ATTR_SLOT = "slot"
ATTR_SPEED = "speed"
ATTR_DURATION = "duration"
ATTR_NOTES = "notes"
ATTR_GAP = "gap"

# Saved-program slots are 1-indexed. Allow up to 16 to accommodate models
# with extended program tables; the firmware will reject out-of-range
# values via VitamixWriteRejectedError.
SCHEMA_LOAD_PROGRAM = vol.Schema(
    {
        vol.Required(ATTR_SLOT): vol.All(int, vol.Range(min=1, max=16)),
    },
    extra=vol.ALLOW_EXTRA,
)

# Speeds 0..10 (Vitamix variable-speed dial); duration in u16 seconds.
SCHEMA_SET_MOTOR_SPEED = vol.Schema(
    {
        vol.Required(ATTR_SPEED): vol.All(int, vol.Range(min=0, max=10)),
        vol.Optional(ATTR_DURATION, default=0xFFFF): vol.All(
            int, vol.Range(min=1, max=0xFFFF)
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_START_MOTOR = vol.Schema(
    {
        vol.Optional(ATTR_SPEED, default=5): vol.All(int, vol.Range(min=1, max=10)),
        vol.Optional(ATTR_DURATION, default=0xFFFF): vol.All(
            int, vol.Range(min=1, max=0xFFFF)
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

# Each note is {speed: 0..10, duration: float seconds}.
SCHEMA_NOTE = vol.Schema(
    {
        vol.Required(ATTR_SPEED): vol.All(int, vol.Range(min=0, max=10)),
        vol.Required(ATTR_DURATION): vol.All(
            vol.Coerce(float), vol.Range(min=0.05, max=60.0)
        ),
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

ALL_SERVICES = (
    SERVICE_CANCEL,
    SERVICE_LOAD_PROGRAM,
    SERVICE_SET_MOTOR_SPEED,
    SERVICE_START_MOTOR,
    SERVICE_STOP_MOTOR,
    SERVICE_PLAY_MELODY,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vitamix from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    coordinator = VitamixCoordinator(hass, entry, address)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass)

    # Poll in the background: an idle blender advertises rarely, so a BLE
    # connect (often through a proxy) can take over a minute and would otherwise
    # hold up HA startup. Entities stay unknown until the first poll, then go
    # unavailable on failure and recover on the regular interval.
    entry.async_create_background_task(
        hass, coordinator.async_refresh(), f"{DOMAIN} first refresh {address}"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data.get(DOMAIN):
        # Last entry gone — drop services so a future reinstall registers fresh.
        for svc in ALL_SERVICES:
            if hass.services.has_service(DOMAIN, svc):
                hass.services.async_remove(DOMAIN, svc)
    return unloaded


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the integration's services exactly once."""
    if hass.services.has_service(DOMAIN, SERVICE_CANCEL):
        return

    async def _resolve_coordinators(call: ServiceCall) -> list[VitamixCoordinator]:
        """Find the coordinators targeted by ``call`` (via target devices)."""
        device_ids: list[str] = call.data.get("device_id", []) or []
        if isinstance(device_ids, str):
            device_ids = [device_ids]

        device_reg = dr.async_get(hass)
        domain_data: dict[str, VitamixCoordinator] = hass.data.get(DOMAIN, {})

        if not device_ids:
            # No target — apply to every configured Vitamix.
            return list(domain_data.values())

        # Match on our device identifier rather than the device's config
        # entries: DeviceEntry.config_entries is deprecated since HA 2026.11,
        # and its replacement (config_entry_id) doesn't exist on older cores.
        identifiers: set[tuple[str, str]] = set()
        for device_id in device_ids:
            if (device := device_reg.async_get(device_id)) is not None:
                identifiers |= device.identifiers
        coordinators = [
            coordinator
            for coordinator in domain_data.values()
            if (DOMAIN, coordinator.address) in identifiers
        ]

        if not coordinators:
            raise HomeAssistantError(f"no Vitamix device matched targets {device_ids}")
        return coordinators

    async def _async_cancel(call: ServiceCall) -> None:
        for coordinator in await _resolve_coordinators(call):
            await coordinator.async_cancel_program()

    async def _async_load_program(call: ServiceCall) -> None:
        slot: int = call.data[ATTR_SLOT]
        for coordinator in await _resolve_coordinators(call):
            await coordinator.async_load_program(slot)

    async def _async_set_motor_speed(call: ServiceCall) -> None:
        speed: int = call.data[ATTR_SPEED]
        duration: int = call.data[ATTR_DURATION]
        for coordinator in await _resolve_coordinators(call):
            await coordinator.async_set_motor_speed(speed, duration_seconds=duration)

    async def _async_start_motor(call: ServiceCall) -> None:
        speed: int = call.data[ATTR_SPEED]
        duration: int = call.data[ATTR_DURATION]
        for coordinator in await _resolve_coordinators(call):
            await coordinator.async_start_motor(speed, duration_seconds=duration)

    async def _async_stop_motor(call: ServiceCall) -> None:
        for coordinator in await _resolve_coordinators(call):
            await coordinator.async_stop_motor()

    async def _async_play_melody(call: ServiceCall) -> None:
        notes_raw = call.data[ATTR_NOTES]
        gap: float = call.data[ATTR_GAP]
        notes: list[tuple[int, float]] = [
            (n[ATTR_SPEED], n[ATTR_DURATION]) for n in notes_raw
        ]
        for coordinator in await _resolve_coordinators(call):
            await coordinator.async_play_melody(notes, gap_seconds=gap)

    # We use device targets, not entity targets, so the schemas only
    # validate our own field; HA injects target keys (device_id /
    # entity_id / area_id) into call.data which we tolerate via
    # extra=vol.ALLOW_EXTRA.
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL,
        _async_cancel,
        schema=vol.Schema({}, extra=vol.ALLOW_EXTRA),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOAD_PROGRAM,
        _async_load_program,
        schema=SCHEMA_LOAD_PROGRAM,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MOTOR_SPEED,
        _async_set_motor_speed,
        schema=SCHEMA_SET_MOTOR_SPEED,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_MOTOR,
        _async_start_motor,
        schema=SCHEMA_START_MOTOR,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_MOTOR,
        _async_stop_motor,
        schema=vol.Schema({}, extra=vol.ALLOW_EXTRA),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_MELODY,
        _async_play_melody,
        schema=SCHEMA_PLAY_MELODY,
    )
