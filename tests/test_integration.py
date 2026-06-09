"""Home Assistant config-flow and setup tests for PaceKeeper.

These require the Home Assistant test harness:

    pip install pytest-homeassistant-custom-component
    pytest tests/test_integration.py
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import (  # noqa: E402
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import CONF_ADDRESS  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,
)

from custom_components.pacekeeper.const import DOMAIN, SERVICE_PAD_UUID  # noqa: E402
from custom_components.pacekeeper.pacekeeper import PaceKeeperTreadmill  # noqa: E402
from custom_components.pacekeeper.protocol import Status, TreadmillData  # noqa: E402

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load the custom integration in these tests."""
    yield


class _FakeServiceInfo:
    """Minimal duck-typed stand-in for BluetoothServiceInfoBleak."""

    def __init__(self, address: str, name: str, service_uuids: list[str]) -> None:
        self.address = address
        self.name = name
        self.service_uuids = service_uuids


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """A discovered treadmill can be added through the user flow."""
    info = _FakeServiceInfo(ADDRESS, "PitPat-T01", [SERVICE_PAD_UUID])
    with (
        patch(
            "custom_components.pacekeeper.config_flow.async_discovered_service_info",
            return_value=[info],
        ),
        patch(
            "custom_components.pacekeeper.async_setup_entry", return_value=True
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "PitPat-T01"
    assert result2["data"] == {CONF_ADDRESS: ADDRESS}
    assert result2["result"].unique_id == ADDRESS
    assert len(mock_setup.mock_calls) >= 1


async def test_user_flow_aborts_without_devices(hass: HomeAssistant) -> None:
    """The user flow aborts cleanly when nothing is discovered."""
    with patch(
        "custom_components.pacekeeper.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_setup_creates_entities_and_unloads(hass: HomeAssistant) -> None:
    """The integration sets up entities and unloads cleanly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        title="PaceKeeper Treadmill",
        data={CONF_ADDRESS: ADDRESS},
    )
    entry.add_to_hass(hass)

    fake_device = MagicMock()
    fake_device.address = ADDRESS
    fake_device.name = "PitPat-T01"

    async def fake_connect(self: PaceKeeperTreadmill) -> None:
        self._connected = True
        self._client = MagicMock(is_connected=True)
        self._data = TreadmillData(
            status=Status.RUNNING,
            speed_feedback=2.5,
            speed_cmd=3.0,
            distance_km=1.2,
            duration_sec=60,
            calories=10,
            fw_version=7,
            speed_max=6.0,
        )

    with (
        patch(
            "custom_components.pacekeeper.bluetooth.async_ble_device_from_address",
            return_value=fake_device,
        ),
        patch(
            "custom_components.pacekeeper.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
        patch.object(PaceKeeperTreadmill, "async_ensure_connected", fake_connect),
        patch.object(PaceKeeperTreadmill, "async_shutdown", new=AsyncMock()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        ent_reg = er.async_get(hass)
        state_entity_id = ent_reg.async_get_entity_id(
            "sensor", DOMAIN, f"{ADDRESS}_state"
        )
        assert state_entity_id is not None
        assert hass.states.get(state_entity_id).state == "running"

        speed_entity_id = ent_reg.async_get_entity_id(
            "number", DOMAIN, f"{ADDRESS}_speed"
        )
        assert speed_entity_id is not None
        assert float(hass.states.get(speed_entity_id).state) == 3.0

        # Three control buttons are exposed.
        button_entities = [
            e for e in ent_reg.entities.values() if e.domain == "button"
        ]
        assert len(button_entities) == 3

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_number_set_value_sends_commands(hass: HomeAssistant) -> None:
    """Setting the speed number drives the treadmill (and 0 stops it)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        title="PaceKeeper Treadmill",
        data={CONF_ADDRESS: ADDRESS},
    )
    entry.add_to_hass(hass)

    fake_device = MagicMock()
    fake_device.address = ADDRESS
    fake_device.name = "PitPat-T01"

    async def fake_connect(self: PaceKeeperTreadmill) -> None:
        self._connected = True
        self._client = MagicMock(is_connected=True)
        self._data = TreadmillData(status=Status.RUNNING)

    set_speed = AsyncMock()
    stop = AsyncMock()

    with (
        patch(
            "custom_components.pacekeeper.bluetooth.async_ble_device_from_address",
            return_value=fake_device,
        ),
        patch(
            "custom_components.pacekeeper.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
        patch.object(PaceKeeperTreadmill, "async_ensure_connected", fake_connect),
        patch.object(PaceKeeperTreadmill, "async_shutdown", new=AsyncMock()),
        patch.object(PaceKeeperTreadmill, "async_set_speed", new=set_speed),
        patch.object(PaceKeeperTreadmill, "async_stop", new=stop),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        ent_reg = er.async_get(hass)
        speed_entity_id = ent_reg.async_get_entity_id(
            "number", DOMAIN, f"{ADDRESS}_speed"
        )

        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": speed_entity_id, "value": 2.5},
            blocking=True,
        )
        set_speed.assert_awaited_once_with(2500)

        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": speed_entity_id, "value": 0},
            blocking=True,
        )
        stop.assert_awaited_once()
