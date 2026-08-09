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

It reaches into ``Component._register_fields`` and ``Component._address``,
which are private. See MIGRATION-NOTES.md — this belongs upstream.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from modbus_connection.decode import decode_int

if TYPE_CHECKING:
    from modbus_connection.model import Component

_LOGGER = logging.getLogger(__name__)


class WriteRejected(Exception):
    """A write was acknowledged but the register did not take the value."""


@dataclass(frozen=True)
class _Placed:
    """One field's encoded words at its absolute address."""

    name: str
    address: int
    words: list[int]

    @property
    def end(self) -> int:
        """The address just past this field's last register."""
        return self.address + len(self.words)


async def _scale_exponents(
    component: Component, names: list[str]
) -> dict[int, int | None]:
    """Read every distinct scale register the named fields need, once each."""
    fields = component._register_fields  # noqa: SLF001 — no public accessor
    addresses = {
        component._scale_address(fields[name])  # noqa: SLF001
        for name in names
        if fields[name].scale_register is not None
    }
    exponents: dict[int, int | None] = {}
    for address in sorted(addresses):
        (word,) = await component._unit.read_holding_registers(address, 1)  # noqa: SLF001
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
    if not values:
        return
    fields = component._register_fields  # noqa: SLF001
    unknown = set(values) - set(fields)
    if unknown:
        raise AttributeError(f"unknown field(s): {', '.join(sorted(unknown))}")
    read_only = [name for name in values if not fields[name].writable]
    if read_only:
        raise AttributeError(f"read-only field(s): {', '.join(sorted(read_only))}")

    exponents = await _scale_exponents(component, list(values))
    placed: list[_Placed] = []
    for name, value in values.items():
        field = fields[name]
        if callable(field.writable):
            value = field.writable(value)
        exponent = (
            exponents[component._scale_address(field)]  # noqa: SLF001
            if field.scale_register is not None
            else None
        )
        placed.append(
            _Placed(name, component._address(field), field.encode(value, exponent))  # noqa: SLF001
        )

    for run in _plan(placed, component.max_span):
        words = [word for item in run for word in item.words]
        start = run[0].address
        if len(words) == 1 and not fields[run[0].name].force_fc16:
            await component._unit.write_register(start, words[0])  # noqa: SLF001
        else:
            await component._unit.write_registers(start, words)  # noqa: SLF001
        _LOGGER.debug(
            "wrote %s at %d: %s", ", ".join(i.name for i in run), start, words
        )

    if not verify:
        return
    if settle:
        await asyncio.sleep(settle)
    await _verify(component, placed)


async def _verify(component: Component, placed: list[_Placed]) -> None:
    """Read each written run back and compare it to what was sent.

    Raises ``WriteRejected`` naming every field that did not take.
    """
    mismatched: list[str] = []
    for run in _plan(placed, component.max_span):
        start = run[0].address
        count = run[-1].end - start
        got = await component._unit.read_holding_registers(start, count)  # noqa: SLF001
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
