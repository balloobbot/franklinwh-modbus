"""The virtual modes' sign convention, end to end to the device's WSetPct.

Every calculator returns positive watts to charge and negative to discharge.
The shipped code mixed the two, which cost more than tidiness: the SOC and PCS
limiters read the convention the other way round, so "charge flat out" tripped
the discharge floor. An aGate X settled the device's half of it — a negative
WSetPct charges, a positive one moves nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from franklinwh_modbus.modes import VirtualModeController
from franklinwh_modbus.types import VirtualMode

if TYPE_CHECKING:
    from modbus_connection.mock import MockModbusUnit

    from franklinwh_modbus.device import AGate

M704_WSET_PCT = 324


@pytest.fixture
def controller(agate: AGate) -> VirtualModeController:
    return VirtualModeController(agate)


def test_below_target_charges_flat_out(controller: VirtualModeController) -> None:
    """Self-consumption's charge branch is positive, not negative."""
    controller.target_soc = 100
    assert controller._calc_self_consumption(0.0, 500.0, 500.0, 19.0) == (
        controller.max_charge_w
    )


def test_self_consumption_discharges_to_cover_a_deficit(
    controller: VirtualModeController,
) -> None:
    controller.target_soc = 0
    assert controller._calc_self_consumption(200.0, 900.0, 700.0, 80.0) == -700.0


def test_self_consumption_charges_from_excess_solar(
    controller: VirtualModeController,
) -> None:
    controller.target_soc = 0
    assert controller._calc_self_consumption(2000.0, 500.0, -1500.0, 80.0) == 1500.0


def test_peak_shave_discharges_negative(controller: VirtualModeController) -> None:
    """The branch that used to return positive, which the device ignores."""
    controller.peak_shave_threshold = 2000
    controller.min_discharge_soc = 20
    assert controller._calc_peak_shave(0.0, 3000.0, 3000.0, 80.0) == -3000.0


def test_peak_shave_asks_for_nothing_when_solar_covers_the_peak(
    controller: VirtualModeController,
) -> None:
    """A negative net load must not become a charge command by sign accident."""
    controller.peak_shave_threshold = 2000
    controller.min_discharge_soc = 20
    assert controller._calc_peak_shave(4000.0, 3000.0, -1000.0, 80.0) == 0.0


def test_time_of_use_discharge_is_negative(controller: VirtualModeController) -> None:
    controller.mode = VirtualMode.TIME_OF_USE
    controller.min_discharge_soc = 20
    controller.tou.get_strategy = lambda: "discharge"  # type: ignore[method-assign]
    controller.tou.get_min_soc = lambda: 20  # type: ignore[method-assign]
    controller.tou.get_max_soc = lambda: 100  # type: ignore[method-assign]
    assert controller._calc_time_of_use(0.0, 2500.0, 2500.0, 80.0) == -2500.0


def test_the_soc_floor_no_longer_blocks_charging(
    controller: VirtualModeController,
) -> None:
    """At 19% SOC the mode charges; under the old sign the floor blocked it."""
    controller.min_discharge_soc = 20
    controller.max_charge_soc = 100
    assert controller._apply_soc_limits(controller.max_charge_w, 19.0) > 0


async def test_charging_reaches_the_device_as_a_negative_setpoint(
    agate: AGate, unit: MockModbusUnit, controller: VirtualModeController
) -> None:
    """The whole chain: below target, charge flat out, negative WSetPct.

    This is the case an aGate X measured at -30% charging 1500 W, and the case
    the old chain sent as +100% — a setpoint the device reads back correctly
    and acts on not at all.
    """
    controller.mode = VirtualMode.SELF_CONSUMPTION
    controller.target_soc = 100
    writes: dict[int, list[int]] = {}
    unit.on_write(lambda event: writes.update({event.address: list(event.values)}))

    watts = await controller.async_execute_once()

    assert watts > 0
    assert writes[M704_WSET_PCT][0] & 0x8000  # negative, so charging
