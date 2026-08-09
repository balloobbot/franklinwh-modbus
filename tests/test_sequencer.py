"""Run the shipped JSON sequences against the reconstructed device."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from franklinwh_modbus.sequencer import SequenceError, Sequencer, TransitionValidationError

if TYPE_CHECKING:
    from modbus_connection.mock import MockModbusUnit

    from franklinwh_modbus.device import AGate

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "sequencer"


@pytest.fixture
def sequencer(agate: AGate) -> Sequencer:
    return Sequencer(agate)


# -- tag resolution ----------------------------------------------------------


@pytest.mark.parametrize(
    ("tag", "field"),
    [
        ("704.WSetEna", "w_set_ena"),
        ("704.WSetPct", "w_set_pct"),
        ("701.W", "w"),
        ("713.SoC", "so_c"),
        ("715.LocRemCtl", "loc_rem_ctl"),
    ],
)
def test_point_tags_resolve(sequencer: Sequencer, tag: str, field: str) -> None:
    assert sequencer.resolve(tag).field == field


def test_bare_address_resolves_to_an_extension_register(
    sequencer: Sequencer,
) -> None:
    """The 15500 block was unreachable through pysunspec2; it is a field now."""
    target = sequencer.resolve("15507")
    assert target.field == "on_grid_mode"
    assert sequencer.value_of("15507") == 2


def test_instance_suffix_reaches_a_repeating_block(sequencer: Sequencer) -> None:
    assert sequencer.resolve("714.DCW_1").field == "dcw"
    assert sequencer.value_of("714.DCW_1") == 1500


@pytest.mark.parametrize(
    ("tag", "message"),
    [
        ("nonsense", "expected"),
        ("704.NotAPoint", "no point"),
        ("999.W", "not present"),
        ("1234", "below the manufacturer block"),
        ("714.DCW_9", "outside 1..1"),
    ],
)
def test_a_bad_tag_says_what_is_wrong(
    sequencer: Sequencer, tag: str, message: str
) -> None:
    with pytest.raises(SequenceError, match=message):
        sequencer.resolve(tag)


# -- running -----------------------------------------------------------------


async def test_a_shipped_sequence_runs(
    sequencer: Sequencer, unit: MockModbusUnit, monkeypatch: pytest.MonkeyPatch
) -> None:
    """basic_charge_release.json, with its 10-second pause skipped."""
    monkeypatch.setattr(
        "franklinwh_modbus.sequencer.asyncio.sleep", _no_sleep
    )
    steps = json.loads((EXAMPLES / "basic_charge_release.json").read_text())
    results = await sequencer.run(steps)

    assert [step.ok for step in results] == [True] * len(steps)
    assert results[0].written == {"704.WSetEna": 1}
    assert results[1].written == {"704.WSetPct": 30}
    # Step 4 drops both, and sees the setpoint step 2 left behind — the skip
    # check reads the device rather than the poll that preceded the sequence.
    assert results[3].written == {"704.WSetEna": 0, "704.WSetPct": 0}
    assert results[3].skipped == []


async def test_a_dry_run_writes_nothing(
    sequencer: Sequencer, unit: MockModbusUnit, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("franklinwh_modbus.sequencer.asyncio.sleep", _no_sleep)
    writes: list[int] = []
    unit.on_write(lambda event: writes.append(event.address))
    steps = json.loads((EXAMPLES / "basic_charge_release.json").read_text())
    await sequencer.run(steps, dry_run=True)
    assert writes == []


async def test_writes_to_one_component_are_batched(
    sequencer: Sequencer, unit: MockModbusUnit
) -> None:
    """Adjacent registers in a step go out as one FC16, not one call each."""
    unit.holding[15508] = 10
    unit.holding[15509] = 10
    frames: list[tuple[int, int, int]] = []
    unit.on_write(
        lambda e: frames.append((e.address, len(e.values), e.function_code))
    )
    await sequencer.run(
        [{"name": "both reserves", "writes": {"15508": 25, "15509": 35}}]
    )
    assert frames == [(15508, 2, 16)]


async def test_a_step_that_is_already_satisfied_is_skipped(
    sequencer: Sequencer, unit: MockModbusUnit
) -> None:
    """Sequences stay idempotent: no write when the point already matches."""
    writes: list[int] = []
    unit.on_write(lambda event: writes.append(event.address))
    result = await sequencer.run([{"name": "mode", "writes": {"15507": 2}}])
    assert writes == []
    assert result[0].skipped == ["15507"]


async def test_require_transition_rejects_a_no_op(sequencer: Sequencer) -> None:
    with pytest.raises(TransitionValidationError, match="already holds"):
        await sequencer.run(
            [{"name": "mode", "writes": {"15507": 2}, "require_transition": True}]
        )


async def test_a_device_that_ignores_a_write_fails_the_step(
    sequencer: Sequencer, unit: MockModbusUnit
) -> None:
    """The aGate acknowledges writes it discards; the step must not pass."""
    unit.on_write(lambda event: unit.holding.__setitem__(15507, 2))
    results = await sequencer.run([{"name": "mode", "writes": {"15507": 3}}])
    assert results[0].ok is False


async def test_wait_for_polls_until_the_condition_holds(
    sequencer: Sequencer, unit: MockModbusUnit
) -> None:
    results = await sequencer.run(
        [
            {
                "name": "wait for SoC",
                "wait_for": {"point": "713.SoC", "operator": ">=", "value": 50},
                "reads": ["713.SoC"],
            }
        ]
    )
    assert results[0].ok
    assert results[0].read["713.SoC"] == 60.0


async def test_wait_for_gives_up_and_fails_the_step(
    sequencer: Sequencer, unit: MockModbusUnit
) -> None:
    results = await sequencer.run(
        [
            {
                "name": "impossible",
                "wait_for": {
                    "point": "713.SoC",
                    "operator": ">",
                    "value": 200,
                    "timeout_ms": 0,
                },
            }
        ]
    )
    assert results[0].ok is False


async def test_a_failed_step_aborts_the_rest(
    sequencer: Sequencer, unit: MockModbusUnit
) -> None:
    unit.on_write(lambda event: unit.holding.__setitem__(15507, 2))
    results = await sequencer.run(
        [
            {"name": "will fail", "writes": {"15507": 3}},
            {"name": "never runs", "writes": {"15508": 40}},
        ]
    )
    assert len(results) == 1


async def _no_sleep(seconds: float) -> None:
    """Stand in for ``asyncio.sleep`` so the shipped pauses do not run."""
    return None
