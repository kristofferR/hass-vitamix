"""Coordinator that polls the Vitamix over BLE.

We re-resolve the :class:`BLEDevice` from Home Assistant's Bluetooth
integration on every poll so any registered scanner (USB adapter,
ESPHome Bluetooth Proxy, Shelly BLE Gateway, …) can be the one that
delivers the device to us. Vitamix blenders advertise sparingly while
idle, so we keep the connection short and rely on whichever proxy is
closest to wake the radio.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from vitamix_ble import VitamixClient, VitamixState
from vitamix_ble.client import VitamixError

from .const import DOMAIN, SCAN_INTERVAL_IDLE_S, SCAN_INTERVAL_RUNNING_S

_LOGGER = logging.getLogger(__name__)


class VitamixCoordinator(DataUpdateCoordinator[VitamixState]):
    """Poll a single Vitamix blender."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        address: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {address}",
            update_interval=timedelta(seconds=SCAN_INTERVAL_IDLE_S),
        )
        self.entry = entry
        self.address = address.upper()

    async def _async_update_data(self) -> VitamixState:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(f"no Bluetooth scanner has seen {self.address} recently")
        client = VitamixClient(ble_device)
        try:
            async with client as vmx:
                state = await vmx.read_state()
        except (TimeoutError, VitamixError, BleakError) as err:
            raise UpdateFailed(f"vitamix poll failed: {err}") from err

        # Speed up polling once the motor is running so live attributes
        # (motor on/off, recipe slot) update with low latency.
        new_interval = (
            SCAN_INTERVAL_RUNNING_S if state.motor_running else SCAN_INTERVAL_IDLE_S
        )
        new_td = timedelta(seconds=new_interval)
        if self.update_interval != new_td:
            self.update_interval = new_td

        return state

    async def _connected_client(self) -> VitamixClient:
        """Resolve a BLEDevice and return a *connected* :class:`VitamixClient`.

        Opens a fresh, short-lived connection. Caller is responsible for
        closing the client (use ``async with`` where possible).
        """
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(f"no Bluetooth scanner has seen {self.address} recently")
        return VitamixClient(ble_device)

    async def async_cancel_program(self) -> None:
        """Send the cancel-program packet to the blender.

        Equivalent to writing 0 to the recipe register. Triggers a
        refresh on success so HA picks up the new state quickly.
        """
        client = await self._connected_client()
        try:
            async with client as vmx:
                await vmx.cancel_program()
        except (TimeoutError, VitamixError, BleakError) as err:
            raise UpdateFailed(f"vitamix cancel failed: {err}") from err
        await self.async_request_refresh()

    async def async_load_program(self, slot: int) -> None:
        """Arm a saved program slot (Smoothie / Frozen Dessert / Spreads).

        Mirrors the final write of the official app's setBlenderProgram
        for built-in saved programs. Whether the motor also spins
        immediately depends on the panel "armed" flag (the dial
        position).
        """
        client = await self._connected_client()
        try:
            async with client as vmx:
                await vmx.load_program(slot)
        except (TimeoutError, VitamixError, BleakError) as err:
            raise UpdateFailed(f"vitamix load_program failed: {err}") from err
        await self.async_request_refresh()

    async def async_set_motor_speed(
        self, speed: int, duration_seconds: int = 0xFFFF
    ) -> None:
        """Set the motor to a fixed Variable-speed (0..10).

        Stages a 1-step custom program in the panel-2 scratch buffer
        (registers 0x0201..) and fires it via REG_PROGRAM_FLAG. Calling
        this while the motor is already running re-stages the buffer
        and effectively changes speed live.
        """
        client = await self._connected_client()
        try:
            async with client as vmx:
                await vmx.set_motor_speed(speed, duration_seconds=duration_seconds)
        except (TimeoutError, VitamixError, BleakError) as err:
            raise UpdateFailed(f"vitamix set_motor_speed failed: {err}") from err
        await self.async_request_refresh()

    async def async_start_motor(
        self, speed: int = 5, duration_seconds: int = 0xFFFF
    ) -> None:
        """Start the motor at ``speed`` (defaults to Variable-5)."""
        client = await self._connected_client()
        try:
            async with client as vmx:
                await vmx.start_motor(speed, duration_seconds=duration_seconds)
        except (TimeoutError, VitamixError, BleakError) as err:
            raise UpdateFailed(f"vitamix start_motor failed: {err}") from err
        await self.async_request_refresh()

    async def async_stop_motor(self) -> None:
        """Stop the motor (same wire packet as cancel_program)."""
        client = await self._connected_client()
        try:
            async with client as vmx:
                await vmx.stop_motor()
        except (TimeoutError, VitamixError, BleakError) as err:
            raise UpdateFailed(f"vitamix stop_motor failed: {err}") from err
        await self.async_request_refresh()

    async def async_play_melody(
        self,
        notes: list[tuple[int, float]],
        gap_seconds: float = 0.0,
    ) -> None:
        """Play a sequence of (speed, duration_seconds) "notes".

        We hold a single BLE connection open for the whole melody so
        re-staging the program for each note is fast (no reconnect
        between notes). The motor stops at the end.
        """
        client = await self._connected_client()
        try:
            async with client as vmx:
                await vmx.play_melody(notes, gap_seconds=gap_seconds)
        except (TimeoutError, VitamixError, BleakError) as err:
            raise UpdateFailed(f"vitamix play_melody failed: {err}") from err
        await self.async_request_refresh()
