"""The FranklinWH extension registers at 15500+.

These are manufacturer registers, outside the SunSpec chain: operating mode,
the two SOC reserves, and PV/load telemetry at a finer granularity than the
SunSpec points give. Writing them needs the installer-enabled "SPAN Modbus"
option; without it the device answers a write with a success echo and keeps
the old value, so every write here is verified by reading it back.
"""

from __future__ import annotations

from enum import IntEnum

from modbus_connection.model import Component, boolean, integer, uint32


def uint16(address: int, **kwargs: object) -> object:
    """A plain unsigned 16-bit manufacturer register.

    Deliberately not ``sunspec.uint16``: these are not SunSpec points, so
    0xFFFF is a real value here rather than the "unimplemented" sentinel.
    """
    return integer(address, signed=False, **kwargs)  # type: ignore[arg-type]

EXTENSION_BASE = 15500
#: The high-resolution home-load mirror, far enough from the rest to be its own
#: block. Undocumented; reports ~1 W where 15506 quantizes to ~100 W.
HOME_LOAD_HIRES_ADDRESS = 16000


class OnGridMode(IntEnum):
    """The aGate's native operating mode (register 15507)."""

    EMERGENCY_BACKUP = 1
    SELF_CONSUMPTION = 2
    TIME_OF_USE = 3
    MANUAL = 4


def _percentage(value: int) -> int:
    """Reject a reserve level outside 0-100 before it reaches the device.

    The aGate does no input validation of its own.
    """
    if not 0 <= int(value) <= 100:
        raise ValueError(f"reserve must be 0-100%, got {value}")
    return int(value)


class Extensions(Component):
    """The FranklinWH manufacturer register block."""

    # The readable map here is known exactly — 15500-15513 and 16000 — but it
    # is deliberately not declared as ``register_ranges``: a ComponentGroup
    # requires every member to declare its ranges once any member does, and the
    # SunSpec models have no reason to. Gap-based planning reaches the same two
    # blocks anyway, since 15513 to 16000 is far wider than ``max_gap``.
    # See MIGRATION-NOTES.md.

    pv_use = boolean(15500)
    """Whether native PV is installed."""

    ap_box_pv_use = boolean(15501)
    """Whether remote (apBox) PV is installed."""

    pv_output_p = uint16(15502, unit="W")
    """Total PV power, native plus remote."""

    proximal_pv_output_p = uint16(15503, unit="W")
    """PV power from the locally wired array."""

    remote1_pv = uint16(15504, unit="W")
    """PV power reported by the first remote apBox."""

    remote2_pv = uint16(15505, unit="W")
    """PV power reported by the second remote apBox."""

    load_active_p = uint16(15506, unit="W")
    """Home load power, quantized to roughly 100 W."""

    on_grid_mode = uint16(15507, writable=True)
    """Operating mode; see :class:`OnGridMode`."""

    self_reserve = uint16(15508, writable=_percentage, unit="%")
    """SOC floor held in Self-Consumption mode."""

    tou_reserve = uint16(15509, writable=_percentage, unit="%")
    """SOC floor held in Time-of-Use mode."""

    pv_output_wh = uint32(15510, unit="Wh")
    """Lifetime PV generation, total."""

    proximal_output_wh = uint32(15512, unit="Wh")
    """Lifetime PV generation from the locally wired array."""

    load_active_p_hires = uint16(HOME_LOAD_HIRES_ADDRESS, unit="W")
    """Home load power at roughly 1 W resolution (undocumented mirror)."""

    @property
    def mode(self) -> OnGridMode | None:
        """The operating mode as an enum, or ``None`` if it is unrecognised."""
        raw = self.on_grid_mode
        if raw is None:
            return None
        try:
            return OnGridMode(int(raw))
        except ValueError:
            return None

    @property
    def home_load_w(self) -> float | None:
        """Home load, preferring the high-resolution mirror when it answers."""
        if self.load_active_p_hires:
            return self.load_active_p_hires
        return self.load_active_p
