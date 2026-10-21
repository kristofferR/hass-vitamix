"""Discovery matches the service UUID as well as the local name."""

from __future__ import annotations

from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.vitamix.const import DOMAIN, SERVICE_UUID

from .conftest import ADDRESS


def service_info(name: str, address: str, uuids: list[str]) -> BluetoothServiceInfoBleak:
    return BluetoothServiceInfoBleak.from_scan(
        source="proxy",
        device=BLEDevice(address, name, None),
        advertisement_data=AdvertisementData(
            local_name=name,
            manufacturer_data={},
            service_data={},
            service_uuids=uuids,
            tx_power=None,
            rssi=-80,
            platform_data=(),
        ),
        monotonic_time=0.0,
        connectable=True,
    )


async def test_user_step_matches_service_uuid(hass: HomeAssistant) -> None:
    infos = [
        service_info("", ADDRESS, [SERVICE_UUID]),
        service_info("Vitamix_2.0", "AA:BB:CC:DD:EE:01", []),
        service_info("Toothbrush", "AA:BB:CC:DD:EE:02", []),
    ]
    with patch(
        "custom_components.vitamix.config_flow.async_discovered_service_info",
        return_value=infos,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    options = result["data_schema"].schema["address"].container
    assert set(options) == {ADDRESS, "AA:BB:CC:DD:EE:01"}
