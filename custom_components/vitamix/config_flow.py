"""Config flow for the Vitamix integration.

The blender is discovered automatically via the bluetooth platform
by its local name (`Vitamix_2.0`) or service UUID. Manual entry by
MAC address is also offered for setups where the blender is only
reachable via a remote scanner that hasn't surfaced an advertisement
to Home Assistant yet.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import format_mac

from .const import ADV_LOCAL_NAME, DEFAULT_DEVICE_NAME, DOMAIN, SERVICE_UUID


class VitamixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the Vitamix integration."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_address: str | None = None
        self._discovered_name: str | None = None
        self._discovered: dict[str, str] = {}  # address -> name

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a BLE advertisement that matches our manifest filter."""
        address = format_mac(discovery_info.address).upper()
        await self.async_set_unique_id(address, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        self._discovered_address = address
        self._discovered_name = discovery_info.name or DEFAULT_DEVICE_NAME
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a single discovered device."""
        assert self._discovered_address is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_name or DEFAULT_DEVICE_NAME,
                data={CONF_ADDRESS: self._discovered_address},
            )
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovered_name or DEFAULT_DEVICE_NAME,
                "address": self._discovered_address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick from currently-discovered Vitamix devices, or fall through to manual entry."""
        self._discovered = {}
        for info in async_discovered_service_info(self.hass):
            if not (
                (info.name or "").startswith(ADV_LOCAL_NAME)
                or SERVICE_UUID in info.service_uuids
            ):
                continue
            address = format_mac(info.address).upper()
            if address in self._async_current_ids():
                continue
            # HA reports the address as the name when none was advertised.
            name = info.name if info.name and info.name != info.address else None
            self._discovered[address] = f"{name or DEFAULT_DEVICE_NAME} ({address})"

        if not self._discovered:
            return await self.async_step_manual()

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered.get(address, DEFAULT_DEVICE_NAME),
                data={CONF_ADDRESS: address},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered)}
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Fall-back manual entry by MAC address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = format_mac(user_input[CONF_ADDRESS]).upper()
            if not _looks_like_mac(address):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_DEVICE_NAME,
                    data={CONF_ADDRESS: address},
                )
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors=errors,
        )


def _looks_like_mac(value: str) -> bool:
    parts = value.split(":")
    if len(parts) != 6:
        return False
    return all(
        len(p) == 2 and all(c in "0123456789ABCDEFabcdef" for c in p) for p in parts
    )
