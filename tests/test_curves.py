"""Read and write the curve models — what the 1547 profile exists for."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from franklinwh_modbus.curves import (
    CurveError,
    is_writable,
    read_curve,
    read_trip_curve,
    write_curve,
)

if TYPE_CHECKING:
    from modbus_connection.mock import MockModbusUnit

    from franklinwh_modbus.device import AGate


async def test_a_curve_write_is_three_round_trips(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """The eight point registers span four sub-components but one FC16.

    Writing them a field at a time costs 17 round trips: 9 writes plus a
    scale-factor read before each of the 8 scaled ones.
    """
    curve = agate.model(705).crv[0]
    frames: list[tuple[int, int, int]] = []
    unit.on_write(lambda e: frames.append((e.address, len(e.values), e.function_code)))
    unit.read_events.clear()

    await write_curve(
        curve, [(95.0, 30.0), (98.0, 0.0), (102.0, 0.0), (105.0, -30.0)],
        verify=False,
    )

    scale_reads = len(unit.read_events)
    assert scale_reads == 2  # V_SF and DeptRef_SF, once each, not once per point
    assert len(frames) == 2  # one FC16 for the points, one FC06 for ActPt
    points_frame, act_pt_frame = frames
    assert points_frame == (388, 8, 16)
    assert act_pt_frame[0] == 378  # ActPt
    assert scale_reads + len(frames) == 4  # vs 17 one field at a time


async def test_act_pt_is_written_after_the_points(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """A curve must never claim more active points than it holds."""
    order: list[int] = []
    unit.on_write(lambda e: order.append(e.address))
    await write_curve(agate.model(705).crv[0], [(95.0, 30.0)], verify=False)
    assert order[-1] == 378  # ActPt last


async def test_read_curve_truncates_to_act_pt(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """Points past ActPt are allocated slots, not part of the curve."""
    await write_curve(
        agate.model(705).crv[0], [(95.0, 30.0), (105.0, -30.0)], verify=False
    )
    await agate.async_update()
    curve = agate.model(705).crv[0]
    assert len(curve.pt) == 4  # NPt slots exist and were read
    assert read_curve(curve) == [(95.0, 30.0), (105.0, -30.0)]


async def test_a_read_only_curve_is_refused(
    agate: AGate, unit: MockModbusUnit
) -> None:
    """ReadOnly is per curve instance, so nothing in the layout can enforce it."""
    unit.holding[387] = 1  # crv[0].ReadOnly
    await agate.async_update()
    curve = agate.model(705).crv[0]
    assert not is_writable(curve)
    with pytest.raises(CurveError, match="ReadOnly"):
        await write_curve(curve, [(95.0, 30.0)])


async def test_a_curve_longer_than_npt_is_refused(agate: AGate) -> None:
    with pytest.raises(CurveError, match="4 point slots"):
        await write_curve(agate.model(705).crv[0], [(0.0, 0.0)] * 5)


@pytest.mark.parametrize("model_id", [705, 706, 712])
async def test_every_curve_model_reads(agate: AGate, model_id: int) -> None:
    for curve in agate.model(model_id).crv:
        assert read_curve(curve) == []  # ActPt is 0 on an unconfigured device


@pytest.mark.parametrize("model_id", [707, 708, 709, 710])
async def test_every_trip_model_reads_all_three_regions(
    agate: AGate, model_id: int
) -> None:
    for curve in agate.model(model_id).crv:
        assert sorted(read_trip_curve(curve)) == [
            "may_trip",
            "mom_cess",
            "must_trip",
        ]
