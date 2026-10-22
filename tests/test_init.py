"""Setup, polling, services and diagnostics."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from vitamix_ble import ProgramStep

from custom_components.vitamix.const import CONF_EXPERIMENTAL, DOMAIN

from .conftest import ADDRESS, FakeClient


async def setup_entry(hass: HomeAssistant, **options: bool) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Vitamix_2.0",
        data={"address": ADDRESS},
        unique_id=ADDRESS,
        options=options,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_panel_is_identified_once(hass: HomeAssistant, fake_client: type[FakeClient]) -> None:
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    assert fake_client.identifies == 1
    assert hass.states.get("sensor.vitamix_2_0_state").state == "idle"


async def test_stale_entities_are_removed(
    hass: HomeAssistant, fake_client: type[FakeClient]
) -> None:
    registry = er.async_get(hass)
    registry.async_get_or_create("binary_sensor", DOMAIN, f"{ADDRESS}_armed")
    registry.async_get_or_create("sensor", DOMAIN, f"{ADDRESS}_container")
    await setup_entry(hass)
    assert registry.async_get_entity_id("binary_sensor", DOMAIN, f"{ADDRESS}_armed") is None
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{ADDRESS}_container") is not None


async def test_unreachable_retry_explains_why(
    hass: HomeAssistant, fake_client: type[FakeClient]
) -> None:
    with patch(
        "custom_components.vitamix.coordinator.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert "proxy-kitchen" in (entry.reason or "")


async def test_diagnostics_while_setup_retries(
    hass: HomeAssistant, hass_client, fake_client: type[FakeClient]
) -> None:  # type: ignore[no-untyped-def]
    with patch(
        "custom_components.vitamix.coordinator.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        entry = await setup_entry(hass)
    with patch(
        "custom_components.vitamix.diagnostics.bluetooth.async_address_reachability_diagnostics",
        return_value=f"{ADDRESS} was last seen by proxy-kitchen",
    ):
        diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert "proxy-kitchen" in diagnostics["reachability"]
    assert ADDRESS not in str(diagnostics)


async def test_experimental_services_need_the_option(
    hass: HomeAssistant, fake_client: type[FakeClient]
) -> None:
    entry = await setup_entry(hass)
    assert hass.services.has_service(DOMAIN, "cancel")
    assert not hass.services.has_service(DOMAIN, "start_motor")

    hass.config_entries.async_update_entry(entry, options={CONF_EXPERIMENTAL: True})
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "start_motor")
    assert fake_client.experimental[-1] is True


async def test_upload_program_service(hass: HomeAssistant, fake_client: type[FakeClient]) -> None:
    await setup_entry(hass)
    await hass.services.async_call(
        DOMAIN,
        "upload_program",
        {"steps": [{"power": 50, "seconds": 60}], "container_id": 3},
        blocking=True,
    )
    assert ("upload_program", ([ProgramStep(0.5, 60, 1.0)], 3)) in fake_client.calls


async def test_entity_target_only_hits_that_blender(
    hass: HomeAssistant, fake_client: type[FakeClient]
) -> None:
    await setup_entry(hass)
    other = MockConfigEntry(domain=DOMAIN, data={"address": "AA:BB:CC:DD:EE:FF"})
    other.add_to_hass(hass)
    hass.data[DOMAIN][other.entry_id] = object()  # must never be called
    await hass.services.async_call(
        DOMAIN, "cancel", {"entity_id": "sensor.vitamix_2_0_state"}, blocking=True
    )
    assert fake_client.calls == [("cancel_program", None)]


async def test_empty_target_hits_no_blender(
    hass: HomeAssistant, fake_client: type[FakeClient]
) -> None:
    await setup_entry(hass)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "cancel", {"entity_id": []}, blocking=True)
    assert fake_client.calls == []


async def test_diagnostics_redact_address(
    hass: HomeAssistant, hass_client, fake_client: type[FakeClient]
) -> None:  # type: ignore[no-untyped-def]
    entry = await setup_entry(hass)
    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diagnostics["panel"]["model"] == "Ascent A3500"
    assert diagnostics["state"]["state"] == "idle"
    assert ADDRESS not in str(diagnostics)
