"""Shared fixtures: a fake VitamixClient and patched Bluetooth lookups."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from bleak.backends.device import BLEDevice
from vitamix_ble import BlenderState, DeviceInfo, PanelType, VitamixState

ADDRESS = "C1:37:8F:47:E3:47"
PANEL = DeviceInfo(PanelType.C, "Ascent A3500", 0, {"thread": (1, 3, 0)}, (9, 0))
STATE = VitamixState(BlenderState.IDLE, False, True, 1, None, False, None)


class FakeClient:
    """Stands in for VitamixClient; records what the coordinator asks for."""

    identifies = 0
    calls: list[tuple[str, Any]] = []
    experimental: list[bool] = []

    def __init__(
        self,
        _ble_device: BLEDevice,
        *,
        device_info: DeviceInfo | None = None,
        **kwargs: Any,
    ) -> None:
        self.device_info = device_info
        FakeClient.experimental.append(kwargs["experimental"])

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        pass

    async def read_state(self) -> VitamixState:
        if self.device_info is None:
            FakeClient.identifies += 1
            self.device_info = PANEL
        return STATE

    async def upload_program(self, steps: Any, *, container_id: int | None = None) -> None:
        FakeClient.calls.append(("upload_program", (steps, container_id)))

    async def cancel_program(self) -> None:
        FakeClient.calls.append(("cancel_program", None))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


@pytest.fixture
def ble_device() -> BLEDevice:
    return BLEDevice(ADDRESS, "Vitamix_2.0", None)


@pytest.fixture
def fake_client(ble_device: BLEDevice) -> Generator[type[FakeClient]]:
    FakeClient.identifies = 0
    FakeClient.calls = []
    FakeClient.experimental = []
    base = "custom_components.vitamix.coordinator"
    with (
        patch(f"{base}.VitamixClient", FakeClient),
        patch(f"{base}.bluetooth.async_ble_device_from_address", return_value=ble_device),
        patch(
            f"{base}.bluetooth.async_address_reachability_diagnostics",
            return_value=f"{ADDRESS} was last seen by proxy-kitchen",
        ),
    ):
        yield FakeClient
