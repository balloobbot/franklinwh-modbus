"""Read and write the IEEE 1547 curve models.

Models 705 (volt-var), 706 (volt-watt) and 712 (watt-var) each hold ``NCrv``
curves of up to ``NPt`` points; 707-710 (the low/high voltage and frequency
trip models) hold ``NCrvSet`` curve sets, each with a must-trip, may-trip and
momentary-cessation region of up to ``NPt`` points.

Two things this layer exists for:

* **``ActPt`` versus ``NPt``.** A curve's storage is ``NPt`` points and its
  addresses are fixed by ``NPt``, but only the first ``ActPt`` of them mean
  anything — the rest are allocated slots holding whatever was there before.
  Every consumer of these models has to make that distinction and the register
  map has no way to express it, so :func:`read_curve` truncates and
  :func:`write_curve` sets ``ActPt`` to match what it wrote.
* **``ReadOnly``.** Each curve carries a point saying whether that curve
  instance may be written. It is per instance, not per field, so nothing in the
  layout can enforce it; :func:`write_curve` checks it before writing, because
  this device's documented behaviour is to accept writes it should reject.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, NamedTuple

from .writing import write_across

if TYPE_CHECKING:
    from collections.abc import Sequence

    from modbus_connection.model import Component

_LOGGER = logging.getLogger(__name__)

#: ``ReadOnly`` reads 1 when the curve instance refuses writes.
_READ_ONLY = 1


class CurveError(Exception):
    """A curve cannot be read or written as asked."""


class CurvePoint(NamedTuple):
    """One point of a curve: an x value and its dependent y value."""

    x: float
    y: float


def _axes(point: Component) -> tuple[str, str]:
    """The attribute names of a curve point's x and y, per model.

    705/706 index by voltage, 712 by watts, 709/710 by frequency; the dependent
    value is vars, watts or a trip time. Rather than a table per model, the
    names are found on the component, which is what the generator produced from
    the definition.
    """
    fields = point.declared_fields
    for x_name in ("v", "w", "hz"):
        if x_name in fields:
            break
    else:
        raise CurveError(f"{type(point).__name__} has no recognised curve x axis")
    for y_name in ("var", "w", "tms"):
        if y_name in fields and y_name != x_name:
            return x_name, y_name
    raise CurveError(f"{type(point).__name__} has no recognised curve y axis")


def read_curve(curve: Component) -> list[CurvePoint]:
    """The active points of one curve, from the last poll.

    Truncated to ``ActPt``: the points beyond it exist in the map and were read,
    but they are unwritten slots, not part of the curve.
    """
    points = list(curve.pt)
    if not points:
        return []
    x_name, y_name = _axes(points[0])
    active = curve.act_pt
    count = len(points) if active is None else min(int(active), len(points))
    return [
        CurvePoint(getattr(point, x_name), getattr(point, y_name))
        for point in points[:count]
    ]


def is_writable(curve: Component) -> bool:
    """Whether this curve instance says it may be written.

    ``ReadOnly`` is a point of the curve, so it differs per instance; the field
    definitions cannot express that, which is why this is a runtime check.
    """
    read_only = curve.read_only
    return read_only is None or int(read_only) != _READ_ONLY


async def write_curve(
    curve: Component,
    points: Sequence[tuple[float, float]],
    *,
    verify: bool = True,
    settle: float = 0.0,
) -> None:
    """Write a whole curve in one plan and set ``ActPt`` to match.

    The curve's point registers are contiguous, so they go out as a single FC16
    with each scale factor read once — three round trips for a four-point
    curve, against seventeen writing a field at a time.

    Points beyond ``len(points)`` are left as they are; ``ActPt`` is what makes
    them inactive, and it is written last so the curve is never briefly
    advertised as longer than the values behind it.

    Raises ``CurveError`` if the curve refuses writes or is too short for the
    points given, and ``WriteRejected`` if the device does not keep them.
    """
    if not is_writable(curve):
        raise CurveError(
            "this curve instance reports ReadOnly; writing it would be "
            "accepted by the device and silently discarded"
        )
    slots = list(curve.pt)
    if len(points) > len(slots):
        raise CurveError(
            f"curve has {len(slots)} point slots (NPt), got {len(points)} points"
        )
    if not points:
        raise CurveError("a curve needs at least one point")

    x_name, y_name = _axes(slots[0])
    entries: list[tuple[Component, str, Any]] = []
    for slot, (x, y) in zip(slots, points, strict=False):
        entries.append((slot, x_name, x))
        entries.append((slot, y_name, y))
    await write_across(entries, verify=verify, settle=settle)

    # ActPt last: until it moves, the points just written are not in effect,
    # and a curve that claims more active points than it holds is worse than
    # one that claims fewer.
    await write_across([(curve, "act_pt", len(points))], verify=verify)
    _LOGGER.debug("wrote %d-point curve", len(points))


def read_trip_curve(curve: Component) -> dict[str, list[CurvePoint]]:
    """The three regions of one trip curve set (models 707-710)."""
    return {
        region: read_curve(getattr(curve, region)[0])
        for region in ("must_trip", "may_trip", "mom_cess")
        if getattr(curve, region, None)
    }
