"""One failing model must not take the rest of the poll with it.

The aGate answers seventeen SunSpec models and a manufacturer block. They used
to be read as one pooled plan, so a single slow or refused block aborted the
cycle, discarded everything already read, and raised — every reading gone
because one model was busy. Each component is now read on its own and the poll
reports what came back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from modbus_connection import ModbusConnectionError, ModbusTimeoutError

from franklinwh_modbus.device import DEFAULT_UNIT_ID, AGate, AGateError
from franklinwh_modbus.modes import VirtualModeController

if TYPE_CHECKING:
    from modbus_connection.mock import MockModbusConnection, MockModbusUnit

# Documented in SUNSPEC_MODEL_REFERENCE.md. A failure is aimed at a data point
# rather than a model header: the chain walk reads the headers, so failing one
# would break discovery instead of the poll under test.
M701_W = 80
M713_SOC = 1037  # scaled by -2, so the device holds hundredths
M707_POINT = 475  # inside model 707 (465..572), clear of both headers


async def test_a_failed_model_leaves_the_rest_fresh(
    agate: AGate, unit: MockModbusUnit
) -> None:
    before = agate.grid_status()["grid_power_w"]

    unit.holding[M701_W] = 4321  # grid power changes on the device
    unit.holding[M713_SOC] = 5500  # so does the state of charge
    unit.fail_read(M701_W, ModbusTimeoutError("slow 701 block"))
    report = await agate.async_update()

    assert not report.complete
    assert set(report.failed) == {"model_701"}
    assert isinstance(report.failed["model_701"], ModbusTimeoutError)
    assert "model_713" in report.updated
    assert agate.grid_status()["grid_power_w"] == before  # previous value kept
    assert agate.battery_status()["soc"] == 55.0


async def test_listeners_fire_at_the_end_and_only_for_fresh_components(
    agate: AGate, unit: MockModbusUnit
) -> None:
    seen: list[int] = []
    agate.models[713].add_update_listener(lambda: seen.append(len(unit.read_events)))
    agate.models[701].add_update_listener(lambda: seen.append(-1))

    unit.fail_read(M701_W, ModbusTimeoutError("slow 701 block"))
    unit.read_events.clear()
    await agate.async_update()

    # Model 713 is read before 714, 715 and the extensions, so a notification
    # fired inline would have seen fewer reads than the poll ended with.
    assert seen == [len(unit.read_events)]


async def test_a_dead_link_raises_instead_of_reporting(
    agate: AGate, unit: MockModbusUnit
) -> None:
    unit.fail_requests(ModbusConnectionError("link down"))
    with pytest.raises(ModbusConnectionError):
        await agate.async_update()


async def test_every_component_refreshes_on_a_healthy_device(agate: AGate) -> None:
    report = await agate.async_update()
    assert report.complete
    assert report.failed == {}
    assert report.updated == {f"model_{mid}" for mid in agate.models} | {"extensions"}


async def test_the_extension_block_fails_on_its_own(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """The manufacturer block is outside the SunSpec chain and fails alone."""
    before = agate.native_mode()["self_reserve_pct"]

    unit.holding[15508] = 45  # the reserve changes on the device
    unit.fail_read(15500, ModbusTimeoutError("extensions busy"))
    report = await agate.async_update()

    assert set(report.failed) == {"extensions"}
    assert agate.native_mode()["self_reserve_pct"] == before
    assert agate.grid_status()["grid_power_w"] == 250.0  # SunSpec side refreshed


async def test_control_refuses_to_command_on_stale_telemetry(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """Containment must not quietly become "drive on last cycle's readings".

    The run loop counts a raising tick as a failure and releases control after
    five of them. A poll that now contains its failures has to say so, or a
    dead grid meter would hold whatever setpoint it computed last.
    """
    controller = VirtualModeController(agate)
    unit.fail_read(M701_W, ModbusTimeoutError("slow 701 block"))
    with pytest.raises(AGateError, match="stale telemetry"):
        await controller.async_execute_once()


async def test_control_still_runs_when_a_trip_curve_model_is_slow(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """Model 707 is configuration; no calculator reads it, so a tick proceeds."""
    unit.fail_read(M707_POINT, ModbusTimeoutError("slow 707 block"))
    assert set((await agate.async_update()).failed) == {"model_707"}

    controller = VirtualModeController(agate)
    await controller.async_execute_once()
    assert agate.control_status()["wset_enabled"] == 1


async def test_a_refused_model_does_not_stop_the_first_poll(
    connection: MockModbusConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Connecting through a busy model leaves a device that works, and recovers."""
    unit = connection.for_unit(DEFAULT_UNIT_ID)
    unit.fail_read(M701_W, ModbusTimeoutError("slow 701 block"))
    device = AGate("mock-host")
    monkeypatch.setattr(device, "_connection", connection)

    await device.async_connect()
    assert device.grid_status()["grid_power_w"] == 0.0  # never read

    unit.fail_read(M701_W, None)
    assert (await device.async_update()).complete
    assert device.grid_status()["grid_power_w"] == 250.0


async def test_a_failed_scan_leaves_the_device_unset_up(
    connection: MockModbusConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Discovery is the poll's foundation; without it there is nothing partial."""
    unit = connection.for_unit(DEFAULT_UNIT_ID)
    unit.fail_read(0, ModbusTimeoutError("no marker"))
    device = AGate("mock-host")
    monkeypatch.setattr(device, "_connection", connection)

    with pytest.raises(ModbusTimeoutError):
        await device.async_connect()
    with pytest.raises(AGateError, match="not connected"):
        await device.async_update()

    unit.fail_read(0, None)
    await device.async_connect()
    assert (await device.async_update()).complete
