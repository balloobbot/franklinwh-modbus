"""The blocking facade the TUI and CLI run on."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from franklinwh_modbus.sync import SyncAGate
from franklinwh_modbus.types import BatteryCommand

if TYPE_CHECKING:
    from modbus_connection.mock import MockModbusConnection


@pytest.fixture
def sync_agate(
    connection: MockModbusConnection, monkeypatch: pytest.MonkeyPatch
) -> SyncAGate:
    """A connected :class:`SyncAGate` over the mock device."""
    device = SyncAGate("mock-host")
    monkeypatch.setattr(device.device, "_connection", connection)
    device.connect()
    yield device
    device.close()


def test_reads_work_from_synchronous_code(sync_agate: SyncAGate) -> None:
    assert sync_agate.connected
    assert sync_agate.nameplate()["model"] == "aGate X"
    assert sync_agate.battery_status()["soc"] == 60.0
    assert sync_agate.max_charge_w == 5000


def test_writes_work_from_synchronous_code(sync_agate: SyncAGate) -> None:
    percent = sync_agate.send_command(BatteryCommand(power_watts=2500))
    assert percent == 50.0
    sync_agate.reset_control_state()
    sync_agate.update()
    assert sync_agate.control_status()["wset_enabled"] == 0


def test_close_stops_the_background_loop(
    connection: MockModbusConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    device = SyncAGate("mock-host")
    monkeypatch.setattr(device.device, "_connection", connection)
    device.connect()
    device.close()
    assert not device._thread.is_alive()
