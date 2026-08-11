"""Batched, verified writes on top of ``Component.write``.

modbus-connection writes one field per call, and re-reads that field's scale
factor first, so a multi-field write costs two round trips per field. This
module plans a set of fields into contiguous FC16 runs and reads each distinct
scale factor once — the write-side counterpart of the library's ``ReadPlan``.

Two aGate behaviours make this more than a saving:

* Writing register 15507 (operating mode) resets the adjacent reserve
  registers to a default, so three sequential single-register writes are not
  equivalent to one three-register write.
* A write the device intends to reject is answered with a success echo rather
  than an exception, so a write is only known to have landed once it has been
  read back.

Where a field sits comes from ``Component.resolved_fields`` — modbus-connection
4.4 exposes the read path's resolution (absolute address, scale register, space)
as public data, so planning a write no longer needs private state. What is still
missing upstream is the planner itself; see MIGRATION-NOTES.md.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from modbus_connection.decode import decode_int

if TYPE_CHECKING:
    from modbus_connection.model import Component, ResolvedField

_LOGGER = logging.getLogger(__name__)


class WriteRejected(Exception):
    """A write was acknowledged but the register did not take the value."""


@dataclass(frozen=True)
class _Placed:
    """One field's encoded words at its absolute address."""

    name: str
    address: int
    words: list[int]
    force_fc16: bool = False

    @property
    def end(self) -> int:
        """The address just past this field's last register."""
        return self.address + len(self.words)


async def _scale_exponents(
    unit: Any, placements: list[ResolvedField]
) -> dict[int, int | None]:
    """Read every distinct scale register these fields need, once each.

    Distinct across the whole batch, not per component: a repeating block's
    instances all reference the same scale factor in the model's fixed block,
    so writing a whole curve should read it once rather than once per point.
    """
    addresses = {
        placement.scale_address
        for placement in placements
        if placement.scale_address is not None
    }
    exponents: dict[int, int | None] = {}
    for address in sorted(addresses):
        (word,) = await unit.read_holding_registers(address, 1)
        exponents[address] = decode_int([word], signed=True)
    return exponents


def _plan(placed: list[_Placed], max_span: int) -> list[list[_Placed]]:
    """Group fields into runs of strictly contiguous registers.

    Deliberately stricter than ``ReadPlan``, which merges across small gaps:
    a write must not touch a register the caller did not name.
    """
    runs: list[list[_Placed]] = []
    for item in sorted(placed, key=lambda p: p.address):
        if runs and runs[-1][-1].end == item.address:
            span = item.end - runs[-1][0].address
            if span <= max_span:
                runs[-1].append(item)
                continue
        runs.append([item])
    return runs


async def write_many(
    component: Component,
    values: dict[str, Any],
    *,
    verify: bool = True,
    settle: float = 0.0,
) -> None:
    """Write several fields of one component, batching contiguous runs.

    Fields adjacent in the register map go out as a single FC16; each distinct
    scale factor is read once rather than once per field. Set ``settle`` to
    wait before reading back, for a device that applies a write asynchronously.

    Raises ``AttributeError`` for an unknown or read-only field, ``ValueError``
    if a value cannot be encoded, and ``WriteRejected`` if a verified register
    does not hold the value afterwards.
    """
    await write_across(
        [(component, name, value) for name, value in values.items()],
        verify=verify,
        settle=settle,
    )


async def write_across(
    entries: list[tuple[Component, str, Any]],
    *,
    verify: bool = True,
    settle: float = 0.0,
) -> None:
    """Write fields spread over several components as one plan.

    The run that matters is often not inside a single component. A SunSpec
    curve's points are one sub-component each, so the eight contiguous
    registers of a four-point curve span four components — batching within a
    component cannot reach them, and they all share the same two scale factors
    in the model's fixed block. Planning across the whole set turns a curve
    write from seventeen round trips into three.

    Every component must be on the same unit.

    Raises ``AttributeError`` for an unknown or read-only field, ``ValueError``
    if a value cannot be encoded or the components differ in unit, and
    ``WriteRejected`` if a verified register does not hold the value after.
    """
    if not entries:
        return
    units = {
        id(component.modbus_unit): component.modbus_unit
        for component, _, _ in entries
    }
    if len(units) > 1:
        raise ValueError("write_across needs every component on one unit")
    unit = next(iter(units.values()))
    max_span = min(component.max_span for component, _, _ in entries)

    placements: list[ResolvedField] = []
    for component, name, _ in entries:
        placement = component.resolved_fields.get(name)
        if placement is None:
            raise AttributeError(f"unknown field {name!r}")
        if not placement.field.writable:
            raise AttributeError(f"{name} is read-only")
        placements.append(placement)

    exponents = await _scale_exponents(unit, placements)
    placed: list[_Placed] = []
    for placement, (_, name, value) in zip(placements, entries, strict=True):
        field = placement.field
        if callable(field.writable):
            value = field.writable(value)
        exponent = (
            exponents[placement.scale_address]
            if placement.scale_address is not None
            else None
        )
        placed.append(
            _Placed(
                name,
                placement.address,
                field.encode(value, exponent),
                force_fc16=field.force_fc16,
            )
        )

    for run in _plan(placed, max_span):
        words = [word for item in run for word in item.words]
        start = run[0].address
        if len(words) == 1 and not run[0].force_fc16:
            await unit.write_register(start, words[0])
        else:
            await unit.write_registers(start, words)
        _LOGGER.debug(
            "wrote %s at %d: %s", ", ".join(i.name for i in run), start, words
        )

    if not verify:
        return
    if settle:
        await asyncio.sleep(settle)
    await _verify(unit, placed, max_span)


async def _verify(unit: Any, placed: list[_Placed], max_span: int) -> None:
    """Read each written run back and compare it to what was sent.

    Raises ``WriteRejected`` naming every field that did not take.
    """
    mismatched: list[str] = []
    for run in _plan(placed, max_span):
        start = run[0].address
        count = run[-1].end - start
        got = await unit.read_holding_registers(start, count)
        for item in run:
            offset = item.address - start
            actual = list(got[offset : offset + len(item.words)])
            if actual != item.words:
                mismatched.append(f"{item.name} (wrote {item.words}, read {actual})")
    if mismatched:
        raise WriteRejected(
            "the device acknowledged but did not apply: " + "; ".join(mismatched)
        )


async def write_verified(
    component: Component,
    field: str,
    value: Any,
    *,
    settle: float = 0.0,
) -> None:
    """Write one field and confirm the device kept it."""
    await write_many(component, {field: value}, settle=settle)
