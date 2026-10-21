"""DataUpdateCoordinator for a single Vitamix blender."""

from __future__ import annotations

import logging
from asyncio import Lock
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import TypeVar

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothReachabilityIntent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from vitamix_ble import (
    BlenderState,
    DeviceInfo,
    VitamixClient,
    VitamixError,
    VitamixState,
    VitamixUnsupportedError,
)

from .const import (
    CONF_EXPERIMENTAL,
    DOMAIN,
    SCAN_INTERVAL_IDLE_S,
    SCAN_INTERVAL_RUNNING_S,
)

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")


class VitamixCoordinator(DataUpdateCoordinator[VitamixState]):
    """Poll a single Vitamix blender.

    Polls and service calls each open a short-lived connection, serialized by
    one lock because the blender accepts a single connection. The panel is
    identified once and reused for later connections.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        address: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {address}",
            update_interval=timedelta(seconds=SCAN_INTERVAL_IDLE_S),
        )
        self.entry = entry
        self.address = address.upper()
        self.panel: DeviceInfo | None = None
        self.last_success: datetime | None = None
        self.last_error: str | None = None
        self._lock = Lock()

    @property
    def experimental(self) -> bool:
        return bool(self.entry.options.get(CONF_EXPERIMENTAL, False))

    def reachability(self) -> str:
        return bluetooth.async_address_reachability_diagnostics(
            self.hass, self.address, BluetoothReachabilityIntent.CONNECTION
        )

    def _ble_device(self) -> BLEDevice | None:
        return bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)

    async def _session(self, action: Callable[[VitamixClient], Awaitable[_T]]) -> _T:
        """Run ``action`` on a fresh connection; raises UpdateFailed if unreachable."""
        async with self._lock:
            if (ble_device := self._ble_device()) is None:
                self.last_error = "unreachable"
                raise UpdateFailed(f"cannot reach {self.address}: {self.reachability()}")
            client = VitamixClient(
                ble_device,
                device_info=self.panel,
                experimental=self.experimental,
            )
            try:
                async with client as vmx:
                    result = await action(vmx)
            except (TimeoutError, VitamixError, BleakError) as err:
                self.last_error = f"{type(err).__name__}: {err}"
                raise
            finally:
                # Keep only usable results so a bad identification is retried.
                if (info := client.device_info) is not None and info.supported:
                    self.panel = info
            self.last_success = dt_util.utcnow()
            self.last_error = None
            return result

    async def _async_update_data(self) -> VitamixState:
        try:
            state = await self._session(lambda vmx: vmx.read_state())
        except (TimeoutError, VitamixError, BleakError) as err:
            raise UpdateFailed(f"vitamix poll failed: {err}") from err

        # Poll faster while the motor runs so state updates with low latency.
        running = state.state is BlenderState.RUNNING
        interval = timedelta(seconds=SCAN_INTERVAL_RUNNING_S if running else SCAN_INTERVAL_IDLE_S)
        if self.update_interval != interval:
            self.update_interval = interval
        return state

    async def async_command(
        self, name: str, action: Callable[[VitamixClient], Awaitable[object]]
    ) -> None:
        """Run a service action, translate errors, then refresh state."""
        try:
            await self._session(action)
        except (ValueError, VitamixUnsupportedError) as err:
            raise ServiceValidationError(f"vitamix {name}: {err}") from err
        except (TimeoutError, VitamixError, BleakError) as err:
            raise HomeAssistantError(f"vitamix {name} failed: {err}") from err
        await self.async_request_refresh()
