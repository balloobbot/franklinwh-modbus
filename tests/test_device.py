"""Drive the whole device: one pooled poll, then reads and verified writes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from franklinwh_modbus.device import AGate, AGateError
from franklinwh_modbus.models.extensions import OnGridMode
from franklinwh_modbus.types import BatteryCommand
from franklinwh_modbus.writing import WriteRejected

if TYPE_CHECKING:
    from modbus_connection.mock import MockModbusConnection, MockModbusUnit

# Absolute addresses on this device, from tests/test_register_map.py's chain.
M701_ALRM = 70 + 6  # bitfield32, so the low word is at +1
M704_WSET_ENA = 318
M704_WSET_MOD = 319
M704_WSET_PCT = 324


async def test_connect_discovers_every_model(agate: AGate) -> None:
    assert sorted(agate.models) == [
        1, 502, 701, 702, 703, 704, 705, 706, 707,
        708, 709, 710, 711, 712, 713, 714, 715,
    ]  # fmt: skip


async def test_connect_rejects_a_device_without_the_required_models(
    connection: MockModbusConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A chain that stops before model 701 is refused, naming what is missing."""
    unit = connection.for_unit(2)
    unit.holding[2] = 0xFFFF  # end the chain immediately after the marker
    device = AGate("mock-host")
    monkeypatch.setattr(device, "_connection", connection)
    with pytest.raises(AGateError, match=r"missing required model"):
        await device.async_connect()


async def test_a_poll_is_a_handful_of_reads(agate: AGate, unit: MockModbusUnit) -> None:
    """Every model plus the extension block, in one pooled pass."""
    unit.read_events.clear()
    await agate.async_update()
    assert len(unit.read_events) <= 14


async def test_reads_come_from_the_poll_not_the_wire(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """The views are computed from the last poll; none of them touches the bus."""
    unit.read_events.clear()
    agate.nameplate()
    agate.battery_status()
    agate.grid_status()
    agate.solar_status()
    agate.control_status()
    agate.native_mode()
    agate.alarms()
    agate.healthcheck()
    assert unit.read_events == []


async def test_nameplate(agate: AGate) -> None:
    assert agate.nameplate() == {
        "manufacturer": "FranklinWH",
        "model": "aGate X",
        "serial": "AG24X0000001",
        "version": "V10R01B04D00",
        "options": "",
    }


async def test_battery_status(agate: AGate) -> None:
    status = agate.battery_status()
    assert status["soc"] == 60.0
    assert status["soh"] == 99.0
    assert status["wh_rating"] == 13_600
    assert status["battery_power_w"] == 1500  # DCW_SF 0
    assert status["battery_state"] == "Discharging"
    assert len(status["individual_batteries"]) == 1


async def test_dc_current_is_derived_when_dca_is_unimplemented(agate: AGate) -> None:
    """This firmware leaves DCA at 0, so current comes from power over voltage."""
    status = agate.battery_status()
    assert status["individual_batteries"][0]["current_a"] == 0
    assert status["battery_current_a"] == round(1500 / 480.0, 2)


async def test_grid_status(agate: AGate) -> None:
    status = agate.grid_status()
    assert status["grid_power_w"] == 250.0
    assert status["voltage_v"] == 240.1
    assert status["frequency_hz"] == 60.0
    assert status["inverter_state"] == "Running"
    assert status["connection_state"] == "Connected"
    assert status["ac_type"] == "Single-Phase (230V Nominal)"


async def test_extension_block_reads(agate: AGate) -> None:
    mode = agate.native_mode()
    assert mode["mode"] is OnGridMode.SELF_CONSUMPTION
    assert mode["self_reserve_pct"] == 20
    assert mode["tou_reserve_pct"] == 30
    assert agate.home_load_w() == 1837  # the high-resolution mirror, not 1800


async def test_effective_reserve_follows_the_mode(agate: AGate) -> None:
    assert agate.effective_reserve_level() == (20, "Self-Consumption reserve")


async def test_solar_status_prefers_the_extension_total(agate: AGate) -> None:
    solar = agate.solar_status()
    assert solar["total_solar_w"] == 3200
    assert solar["extension"]["pv_installed"] is True
    assert solar["battery_dc_power_w"] == 1500


async def test_healthcheck_is_happy_on_a_quiet_device(agate: AGate) -> None:
    health = agate.healthcheck()
    assert health.healthy
    assert "60.0% SOC" in health.message


async def test_alarms_decode_to_bit_names(
    agate: AGate, unit: MockModbusUnit
) -> None:
    unit.holding[M701_ALRM + 1] = 0x0080  # bit 7 -> OVER_TEMP
    await agate.async_update()
    alarms = agate.alarms()
    assert alarms["decoded"]["OVER_TEMP"] is True
    assert alarms["decoded"]["GROUND_FAULT"] is False


async def test_a_blocking_alarm_refuses_control(
    agate: AGate, unit: MockModbusUnit
) -> None:
    unit.holding[M701_ALRM + 1] = 0x0001  # bit 0 -> GROUND_FAULT
    await agate.async_update()
    can_control, reasons = agate.blocking_alarms()
    assert not can_control
    with pytest.raises(AGateError, match="alarms are active"):
        await agate.async_send_command(BatteryCommand(power_watts=1000))


# -- writes ------------------------------------------------------------------


async def test_send_command_writes_the_704_phases_in_order(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """Stop, set, then enable — the order the device needs."""
    writes: list[tuple[int, list[int]]] = []
    unit.on_write(lambda event: writes.append((event.address, list(event.values))))
    percent = await agate.async_send_command(BatteryCommand(power_watts=2500))

    assert percent == 50.0  # 2500 W of the 5000 W charge rating
    addresses = [address for address, _ in writes]
    assert addresses[0] == M704_WSET_ENA
    assert addresses[-1] == M704_WSET_ENA
    assert writes[0][1] == [0]  # phase 1: stop
    assert writes[-1][1] == [1]  # phase 3: enable
    # Phase 2 sets the mode and the setpoint; they are not adjacent registers,
    # so they stay two frames rather than being merged over WSet in between.
    assert M704_WSET_MOD in addresses
    # Positive watts is charge here, which is negative WSetPct on the device.
    assert dict(writes)[M704_WSET_PCT] == [(-5000) & 0xFFFF]


async def test_send_command_scales_through_wsetpct_sf(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """WSetPct_SF is -2, so 50% is written as 5000."""
    writes: dict[int, list[int]] = {}
    unit.on_write(lambda event: writes.update({event.address: list(event.values)}))
    await agate.async_send_command(BatteryCommand(power_watts=-5000))
    assert writes[M704_WSET_PCT] == [10_000]  # +100% discharge


async def test_a_write_the_device_ignores_is_caught(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """The aGate acknowledges writes it discards; readback is what catches it."""
    unit.holding[M704_WSET_ENA] = 0  # WSetEna refuses to leave 0

    def refuse(event: object) -> None:
        unit.holding[M704_WSET_ENA] = 0

    unit.on_write(refuse)
    with pytest.raises(WriteRejected, match="did not apply"):
        await agate.async_send_command(BatteryCommand(power_watts=1000))


async def test_setting_the_mode_rewrites_both_reserves_in_one_frame(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """15507-15509 go out together, because writing 15507 alone resets them."""
    writes: list[tuple[int, list[int], int]] = []
    unit.on_write(
        lambda e: writes.append((e.address, list(e.values), e.function_code))
    )
    await agate.async_set_native_mode(OnGridMode.TIME_OF_USE)
    assert writes == [(15507, [3, 20, 30], 16)]


async def test_reserve_bounds_are_checked_before_the_write(agate: AGate) -> None:
    with pytest.raises(ValueError, match="0-100"):
        await agate.async_set_self_consumption_reserve(120)


async def test_reset_control_state_disables_and_zeroes(
    agate: AGate, unit: MockModbusUnit
) -> None:
    writes: dict[int, list[int]] = {}
    unit.on_write(lambda event: writes.update({event.address: list(event.values)}))
    await agate.async_reset_control_state()
    assert writes[M704_WSET_ENA] == [0]
    assert writes[M704_WSET_PCT] == [0]
