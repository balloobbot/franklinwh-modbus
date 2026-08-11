"""Run declarative register sequences with verification.

A sequence is a list of steps in JSON (see ``examples/sequencer/``). Each step
writes some points, optionally waits for a condition, reads some points back
and then pauses. Its reason for existing is that the aGate's control path is
ordered and stateful: a setpoint written while the enable register is still set
is ignored, and the enable register has to go last.

Tags name a point as ``"<model>.<Point>"`` (``704.WSetPct``), with an optional
``_<n>`` suffix to reach instance *n* of a repeating block (``714.DCW_1``), or
a bare address for a manufacturer register (``15507``). The tag grammar is a
user-facing contract — the shipped sequences use it — so it is unchanged from
before the migration even though the resolution behind it is completely
different: the old implementation could not reach the 15500 block through
pysunspec2 at all and hand-assembled Modbus TCP frames onto the raw socket.
"""

from __future__ import annotations

import asyncio
import logging
import operator
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .models.extensions import EXTENSION_BASE
from .writing import WriteRejected, write_many

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from modbus_connection.model import Component

    from .device import AGate

_LOGGER = logging.getLogger(__name__)

DEFAULT_VERIFY_TIMEOUT_MS = 2000
DEFAULT_WAIT_TIMEOUT_MS = 30_000
DEFAULT_POLL_MS = 1000

_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "in": lambda current, target: current in target,
    "not in": lambda current, target: current not in target,
}


class TransitionValidationError(Exception):
    """A step demanded a state change and the point was already there."""


class SequenceError(Exception):
    """A sequence could not be run as written."""


@dataclass(frozen=True)
class Target:
    """A resolved point: which component, and which field of it."""

    component: Component
    field: str
    label: str


@dataclass
class StepResult:
    """What one step did."""

    name: str
    written: dict[str, Any] = field(default_factory=dict)
    read: dict[str, Any] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    ok: bool = True


class Sequencer:
    """Resolve tags against a connected device and run sequences on it."""

    def __init__(self, device: AGate) -> None:
        self._device = device
        self._by_point: dict[tuple[int, str], str] | None = None

    # -- tag resolution --------------------------------------------------------

    def resolve(self, tag: str | Mapping[str, Any]) -> Target:
        """Resolve a tag to the component and field it names.

        Raises ``SequenceError`` for a malformed tag, an absent model, or a
        point the device's components do not carry.
        """
        text = _tag_text(tag)
        if "." not in text:
            return self._resolve_extension(text)
        model_part, _, point = text.partition(".")
        if not model_part.isdigit():
            raise SequenceError(
                f"invalid tag {text!r}: expected '<model>.<Point>' or an address"
            )
        component = self._device.model(int(model_part))
        if component is None:
            raise SequenceError(f"model {model_part} is not present on this device")
        point, index = _split_instance(point)
        attribute = self._attribute_for(int(model_part), point)
        if index is not None:
            component = _instance(component, index, text)
        if attribute not in component.declared_fields:
            raise SequenceError(f"{text}: model {model_part} has no point {point!r}")
        return Target(component, attribute, text)

    def _resolve_extension(self, text: str) -> Target:
        """Resolve a bare address in the manufacturer block."""
        try:
            address = int(text)
        except ValueError as err:
            raise SequenceError(
                f"invalid tag {text!r}: expected '<model>.<Point>' or an address"
            ) from err
        if address < EXTENSION_BASE:
            raise SequenceError(
                f"address {address} is below the manufacturer block at"
                f" {EXTENSION_BASE}; name a SunSpec point as '<model>.<Point>'"
            )
        extensions = self._device.extensions
        # resolved_fields, not declared_fields: the tag names an absolute
        # address on the wire, and a declared address is stated before whatever
        # places the layout.
        for name, resolved in extensions.resolved_fields.items():
            if resolved.address == address:
                return Target(extensions, name, text)
        raise SequenceError(f"address {address} is not a known extension register")

    def _attribute_for(self, model_id: int, point: str) -> str:
        """Map a SunSpec point name to the generated attribute name.

        The generated components snake-case point names (``WSetPct`` becomes
        ``w_set_pct``), so the mapping is built once by matching the
        de-punctuated forms rather than reimplementing the generator's rule.
        """
        if self._by_point is None:
            self._by_point = {}
            components = {**self._device.models, 0: self._device.extensions}
            for identifier, component in components.items():
                for attribute in component.declared_fields:
                    key = attribute.replace("_", "").lower()
                    self._by_point[(identifier, key)] = attribute
                for group, instances in component._groups.items():  # noqa: SLF001
                    for instance in instances[:1]:
                        for attribute in instance.declared_fields:
                            key = attribute.replace("_", "").lower()
                            self._by_point.setdefault((identifier, key), attribute)
                    del group
        return self._by_point.get((model_id, point.replace("_", "").lower()), point)

    # -- reading ---------------------------------------------------------------

    async def read(self, tag: str | Mapping[str, Any]) -> Any:
        """Read one point, refreshing its component first."""
        target = self.resolve(tag)
        await target.component.async_update()
        return getattr(target.component, target.field)

    def value_of(self, tag: str | Mapping[str, Any]) -> Any:
        """One point's value from the last poll, without going to the device."""
        target = self.resolve(tag)
        return getattr(target.component, target.field)

    # -- running ---------------------------------------------------------------

    async def run(
        self, sequence: Sequence[Mapping[str, Any]], *, dry_run: bool = False
    ) -> list[StepResult]:
        """Run every step in order, stopping at the first that fails hard.

        Returns one :class:`StepResult` per step attempted.
        """
        results: list[StepResult] = []
        for number, step in enumerate(sequence, start=1):
            name = str(step.get("name", step.get("step", f"Step {number}")))
            _LOGGER.info("[%d/%d] %s", number, len(sequence), name)
            result = await self._run_step(name, step, dry_run=dry_run)
            results.append(result)
            if not result.ok and step.get("abort_on_failure", True):
                _LOGGER.error("aborting: %s failed", name)
                break
        return results

    async def _run_step(
        self, name: str, step: Mapping[str, Any], *, dry_run: bool
    ) -> StepResult:
        """Run one step's writes, wait condition, reads and pause."""
        result = StepResult(name=name)
        writes = step.get("writes") or {}
        if writes:
            result.ok = await self._execute_writes(step, writes, result, dry_run)
            if not result.ok:
                return result

        wait_for = step.get("wait_for")
        if wait_for and not await self._wait_for(wait_for):
            result.ok = False
            return result

        for tag in step.get("reads") or []:
            result.read[_tag_text(tag)] = await self.read(tag)
            _LOGGER.info("  read %s: %s", _tag_text(tag), result.read[_tag_text(tag)])

        pause_ms = step.get("sleep_ms", step.get("post_sleep_ms", 0))
        if pause_ms:
            _LOGGER.info("  sleeping %dms", pause_ms)
            await asyncio.sleep(pause_ms / 1000)
        return result

    async def _execute_writes(
        self,
        step: Mapping[str, Any],
        writes: Mapping[str, Any],
        result: StepResult,
        dry_run: bool,
    ) -> bool:
        """Write a step's points, batching the ones that share a component.

        Points already holding their target are skipped, so a sequence stays
        idempotent — except under ``require_transition``, where a point that is
        already there means the step's premise was wrong. The skip decision has
        to be made against the device rather than the last poll, so every
        component this step touches is refreshed first: an earlier step in the
        same sequence has very likely just moved one of these registers.
        """
        require_transition = bool(step.get("require_transition", False))
        targets = {tag: self.resolve(tag) for tag in writes}
        for component in {id(t.component): t.component for t in targets.values()}.values():
            await component.async_update()

        pending: dict[Component, dict[str, Any]] = {}
        for tag, raw in writes.items():
            target = targets[tag]
            value = raw.get("value") if isinstance(raw, dict) else raw
            before = getattr(target.component, target.field)
            if before == value:
                if require_transition:
                    raise TransitionValidationError(
                        f"{step.get('name')}: {target.label} already holds {value}"
                    )
                _LOGGER.info("  %s already %s — no transition", target.label, value)
                result.skipped.append(target.label)
                continue
            if dry_run:
                _LOGGER.info("  [dry run] %s: %s -> %s", target.label, before, value)
            pending.setdefault(target.component, {})[target.field] = value
            result.written[target.label] = value

        if dry_run or not pending:
            return True

        settle = step.get("settle_ms", 0) / 1000
        verify = bool(step.get("verify", True))
        started = time.monotonic()
        try:
            for component, values in pending.items():
                await write_many(component, values, verify=verify, settle=settle)
        except WriteRejected as err:
            _LOGGER.error("  %s", err)
            return False
        _LOGGER.info(
            "  wrote %s in %dms",
            ", ".join(result.written),
            int((time.monotonic() - started) * 1000),
        )
        return True

    async def _wait_for(self, config: Mapping[str, Any]) -> bool:
        """Poll one point until a condition holds or the timeout expires."""
        tag = config.get("point")
        if not tag:
            raise SequenceError("wait_for needs a 'point'")
        symbol = config.get("operator", "==")
        compare = _OPERATORS.get(symbol)
        if compare is None:
            raise SequenceError(f"unsupported wait_for operator {symbol!r}")
        target = config.get("value")
        timeout = config.get("timeout_ms", DEFAULT_WAIT_TIMEOUT_MS) / 1000
        poll = config.get("poll_ms", DEFAULT_POLL_MS) / 1000

        _LOGGER.info("  waiting for %s %s %s", _tag_text(tag), symbol, target)
        deadline = time.monotonic() + timeout
        while True:
            current = await self.read(tag)
            if compare(current, target):
                _LOGGER.info("  condition met: %s %s %s", current, symbol, target)
                return True
            if time.monotonic() >= deadline:
                _LOGGER.error(
                    "  timed out waiting for %s %s %s (last %s)",
                    _tag_text(tag),
                    symbol,
                    target,
                    current,
                )
                return False
            await asyncio.sleep(poll)


def _tag_text(tag: str | Mapping[str, Any]) -> str:
    """The tag string, whether it came bare or inside an override dict."""
    if isinstance(tag, str):
        return tag
    for key in ("point", "addr", "address"):
        if key in tag:
            return str(tag[key])
    raise SequenceError(f"tag {tag!r} names no point or address")


def _split_instance(point: str) -> tuple[str, int | None]:
    """Split a ``Point_2`` suffix into the point name and its instance index."""
    base, separator, suffix = point.rpartition("_")
    if separator and suffix.isdigit():
        return base, int(suffix)
    return point, None


def _instance(component: Component, index: int, tag: str) -> Component:
    """The ``index``-th sub-instance of a component's single repeating group.

    Raises ``SequenceError`` if the component has no repeating group, has more
    than one so the index is ambiguous, or does not have that many instances.
    """
    groups = {name: members for name, members in component._groups.items() if members}  # noqa: SLF001
    if not groups:
        raise SequenceError(f"{tag}: this model has no repeating block to index")
    if len(groups) > 1:
        raise SequenceError(
            f"{tag}: this model has several repeating blocks "
            f"({', '.join(sorted(groups))}), so an index is ambiguous"
        )
    members = next(iter(groups.values()))
    if not 1 <= index <= len(members):
        raise SequenceError(
            f"{tag}: instance {index} is outside 1..{len(members)}"
        )
    return members[index - 1]
