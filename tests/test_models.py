"""Read every model the aGate carries, including the seven curve models.

Issue 156 lists 705, 706, 712 and 707-710 as inexpressible against
modbus-connection. They are expressed here, so this file is the evidence for
that claim being about the *runtime*-counted case rather than these models
being unreachable — see MIGRATION-NOTES.md for what it cost.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from modbus_connection.model import ComponentGroup
from modbus_connection.model.sunspec import scan

from franklinwh_modbus.models import MODELS
from franklinwh_modbus.models.extensions import EXTENSION_BASE, Extensions

if TYPE_CHECKING:
    from modbus_connection.mock import MockModbusUnit

# The counts the aGate reports, and the curve shape each one implies. The last
# entry names a point of the innermost block, which is the level the layout
# only reaches if every count above it resolved.
TRIP_BLOCKS = ("must_trip", "may_trip", "mom_cess")
CURVE_SHAPES = [
    # model, curve group, curves, sub-blocks per curve, points, leaf point
    (705, "crv", 3, None, 4, "v"),
    (706, "crv", 2, None, 2, "v"),
    (707, "crv", 2, TRIP_BLOCKS, 5, "v"),
    (708, "crv", 2, TRIP_BLOCKS, 5, "v"),
    (709, "crv", 2, TRIP_BLOCKS, 5, "hz"),
    (710, "crv", 2, TRIP_BLOCKS, 5, "hz"),
    (712, "crv", 2, None, 6, "w"),
]


@pytest.fixture
async def components(unit: MockModbusUnit) -> dict[int, object]:
    """Every model, scanned, built and read in one pooled poll."""
    discovered = await scan(unit, 0)
    built = {
        model_id: component_class(unit, discovered.first(model_id))
        for model_id, component_class in MODELS.items()
        if discovered.first(model_id) is not None
    }
    await ComponentGroup(unit, list(built.values())).async_update()
    return built


async def test_scan_finds_every_model(unit: MockModbusUnit) -> None:
    discovered = await scan(unit, 0)
    assert sorted(discovered) == sorted(MODELS)


async def test_every_model_reads(components: dict[int, object]) -> None:
    assert sorted(components) == sorted(MODELS)


async def test_model_header_verification_passes(
    components: dict[int, object],
) -> None:
    """Each component's read-back ID and length match what the scan found.

    This is what catches a device whose curve counts differ from the ones these
    components were generated for: the counts decide the model's length.
    """
    for model_id, component in components.items():
        assert component.model_id == model_id
        component._verify_read()


@pytest.mark.parametrize(
    ("model_id", "group", "curves", "sub_blocks", "points", "leaf"), CURVE_SHAPES
)
async def test_curve_model_is_fully_populated(
    components: dict[int, object],
    model_id: int,
    group: str,
    curves: int,
    sub_blocks: tuple[str, ...] | None,
    points: int,
    leaf: str,
) -> None:
    """Every curve, sub-block and curve point exists and decoded."""
    component = components[model_id]
    instances = getattr(component, group)
    assert len(instances) == curves
    for curve in instances:
        if sub_blocks is None:
            assert len(curve.pt) == points
            assert all(getattr(point, leaf) is not None for point in curve.pt)
            continue
        for name in sub_blocks:
            region = getattr(curve, name)
            assert len(region) == 1
            assert len(region[0].pt) == points
            assert all(getattr(point, leaf) is not None for point in region[0].pt)


async def test_curve_counts_match_the_layout(components: dict[int, object]) -> None:
    """The count points read back the values the layout was sized with."""
    assert (components[705].n_pt, components[705].n_crv) == (4, 3)
    assert (components[706].n_pt, components[706].n_crv) == (2, 2)
    assert (components[707].n_pt, components[707].n_crv_set) == (5, 2)
    assert (components[712].n_pt, components[712].n_crv) == (6, 2)
    assert components[711].n_ctl == 2
    assert components[714].n_prt == 1


async def test_runtime_counted_groups_still_size_themselves(
    components: dict[int, object],
) -> None:
    """711 and 714 keep their register-read counts; nothing was baked there."""
    assert len(components[711].ctl) == 2
    assert len(components[714].prt) == 1


async def test_scaling_uses_the_devices_scale_factors(
    components: dict[int, object],
) -> None:
    """A point with a sunssf decodes through it, not raw."""
    assert components[713].so_c == 60.0  # raw 6000, Pct_SF -2
    assert components[701].w == 250.0  # raw 2500, W_SF -1
    assert components[701].hz == 60.0  # raw 6000, Hz_SF -2


async def test_the_whole_device_reads_in_few_blocks(unit: MockModbusUnit) -> None:
    """Pooling the models makes a poll a handful of reads, not one per model.

    Thirteen rather than eleven-plus-nothing: two are the second pass over the
    register-counted repeating blocks in M711 and M714, and one is M1 on its
    own. From modbus-connection 4.4 a pooled read no longer bridges a gap
    between what its members claim, and M1's last point is a Pad the generated
    component does not read — so register 69 belongs to nobody and M1 cannot
    join M701 onwards. Everything from 70 to 963 is still one merged span.
    """
    discovered = await scan(unit, 0)
    built = [
        component_class(unit, discovered.first(model_id))
        for model_id, component_class in MODELS.items()
        if discovered.first(model_id) is not None
    ]
    group = ComponentGroup(unit, built)
    unit.read_events.clear()
    await group.async_update()
    assert len(unit.read_events) <= 13
    # The chain from M701 to M711's fixed block stays one span, chunked only by
    # the 125-register Modbus ceiling.
    merged = [e for e in unit.read_events if 70 <= e.address <= 963]
    assert [e.address for e in merged] == [70, 193, 318, 443, 567, 692, 817, 941]


async def test_the_extension_map_pools_with_models_that_declare_none(
    unit: MockModbusUnit,
) -> None:
    """Stating the manufacturer block's holey map no longer costs pooling.

    Before modbus-connection 4.4 a ComponentGroup refused a member that
    declared ``register_ranges`` alongside members that did not, so the map had
    to be dropped to keep the extension block in the poll. It is declared now,
    and the two runs it names are the only addresses read there — nothing
    bridges the 486 dead registers between 15513 and 16000.
    """
    discovered = await scan(unit, 0)
    group = ComponentGroup(
        unit,
        [
            *(
                component_class(unit, discovered.first(model_id))
                for model_id, component_class in MODELS.items()
                if discovered.first(model_id) is not None
            ),
            Extensions(unit),
        ],
    )
    unit.read_events.clear()
    await group.async_update()
    extension_reads = [e for e in unit.read_events if e.address >= EXTENSION_BASE]
    assert [(e.address, e.count) for e in extension_reads] == [(15500, 14), (16000, 1)]
