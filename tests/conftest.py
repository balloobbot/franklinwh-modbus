"""Shared fixtures: an aGate backed by its reconstructed register map."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from modbus_connection.mock import MockModbusConnection

from franklinwh_modbus import device as device_module
from franklinwh_modbus.device import DEFAULT_UNIT_ID, AGate

from .fixtures.agate_registers import REGISTERS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from modbus_connection.mock import MockModbusUnit


@pytest.fixture
def connection() -> MockModbusConnection:
    """A mock connection answering the aGate's whole holding-register map."""
    mock = MockModbusConnection()
    mock.for_unit(DEFAULT_UNIT_ID).holding.update(REGISTERS)
    return mock


@pytest.fixture
def unit(connection: MockModbusConnection) -> MockModbusUnit:
    """The mock unit the device talks to."""
    return connection.for_unit(DEFAULT_UNIT_ID)


@pytest_asyncio.fixture
async def agate(
    connection: MockModbusConnection, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AGate]:
    """A connected :class:`AGate` whose transport is the mock connection."""
    # The device wants a beat between control phases; a mock does not.
    monkeypatch.setattr(device_module, "CONTROL_SETTLE_S", 0.0)
    monkeypatch.setattr(device_module, "ENABLE_SETTLE_S", 0.0)
    device = AGate("mock-host")
    monkeypatch.setattr(device, "_connection", connection)
    await device.async_connect()
    yield device
    device.cancel_command_timer()
