"""Check a real aGate against what this migration assumed about it.

Read-only. It issues no writes, changes no mode and moves no power, so it is
safe to run against a live system at any state of charge.

Everything this library knows about the register map was reconstructed from the
SunSpec model definitions rather than captured from a device (see
MIGRATION-NOTES.md §0). This script is the check: it walks the chain, compares
every model's address and length against the reconstruction, reports the curve
counts the generated components were built for, and flags the assumptions that
turn out to be wrong.

    python3 scripts/hardware_check.py 192.168.1.100
    python3 scripts/hardware_check.py 192.168.1.100 --unit 2 --json report.json

See HARDWARE-VERIFICATION.md for what each check means and for the ones that
need a write and so cannot go in here.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

from modbus_connection import ModbusExceptionError, ModbusTcpParams
from modbus_connection.model.sunspec import SunSpecMapShiftError, scan
from modbus_connection.tmodbus import ModbusConnection

from franklinwh_modbus.curves import read_curve, read_trip_curve
from franklinwh_modbus.device import DEFAULT_UNIT_ID, AGate

# What the reconstruction says: model ID -> (header address, length).
EXPECTED_CHAIN: dict[int, tuple[int, int]] = {
    1: (2, 66),
    701: (70, 153),
    702: (225, 50),
    703: (277, 17),
    704: (296, 65),
    705: (363, 67),
    706: (432, 31),
    707: (465, 105),
    708: (572, 105),
    709: (679, 135),
    710: (816, 135),
    711: (953, 32),
    712: (987, 44),
    713: (1033, 7),
    714: (1042, 43),
    715: (1087, 7),
    # M502's position is inferred, not documented — see MIGRATION-NOTES.md §0.
    502: (1096, 28),
}

# The counts the generated components were built for.
EXPECTED_COUNTS: dict[int, dict[str, int]] = {
    705: {"n_pt": 4, "n_crv": 3},
    706: {"n_pt": 2, "n_crv": 2},
    707: {"n_pt": 5, "n_crv_set": 2},
    708: {"n_pt": 5, "n_crv_set": 2},
    709: {"n_pt": 5, "n_crv_set": 2},
    710: {"n_pt": 5, "n_crv_set": 2},
    711: {"n_ctl": 2},
    712: {"n_pt": 6, "n_crv": 2},
    714: {"n_prt": 1},
}

# Base addresses to probe. The aGate is documented as answering from 0 and
# returning ILLEGAL_DATA_ADDRESS at the two SunSpec alternatives.
PROBE_BASES = (0, 40000, 50000)


@dataclass
class Check:
    """One verified assumption."""

    name: str
    verdict: str  # "ok" | "differs" | "unknown"
    detail: str
    data: Any = None


@dataclass
class Report:
    """Everything this run learned."""

    host: str
    unit_id: int
    checks: list[Check] = field(default_factory=list)

    def record(self, name: str, verdict: str, detail: str, data: Any = None) -> None:
        """Add a check and print it as it happens."""
        self.checks.append(Check(name, verdict, detail, data))
        mark = {"ok": "  ok  ", "differs": "DIFFERS", "unknown": "  ?   "}[verdict]
        print(f"[{mark}] {name}: {detail}")

    @property
    def differences(self) -> list[Check]:
        """The checks whose answer was not what the reconstruction expected."""
        return [c for c in self.checks if c.verdict == "differs"]


async def probe_base_addresses(unit: Any, report: Report) -> None:
    """Which base addresses carry a SunSpec chain."""
    answered = []
    for base in PROBE_BASES:
        try:
            await scan(unit, base)
        except ModbusExceptionError as err:
            report.record(
                f"base address {base}",
                "ok" if base else "differs",
                f"rejected ({type(err).__name__}) — expected for a non-base"
                if base
                else f"rejected ({type(err).__name__}) — but 0 should be the base",
            )
            continue
        except Exception as err:  # noqa: BLE001 — any failure means "not here"
            report.record(
                f"base address {base}",
                "ok" if base else "differs",
                f"no chain ({type(err).__name__}: {err})",
            )
            continue
        answered.append(base)
        report.record(
            f"base address {base}",
            "ok" if base == 0 else "differs",
            "carries a SunSpec chain"
            + ("" if base == 0 else " — a second chain was not expected"),
        )
    report.record(
        "base addresses answering",
        "ok" if answered == [0] else "differs",
        f"{answered} (expected [0])",
        data=answered,
    )


async def check_chain(unit: Any, report: Report) -> None:
    """Every model's ID, address and length against the reconstruction."""
    discovered = await scan(unit, 0)
    found = {
        model_id: (located[0].address, located[0].length)
        for model_id, located in discovered.items()
    }
    report.record(
        "models discovered",
        "ok" if sorted(found) == sorted(EXPECTED_CHAIN) else "differs",
        f"{sorted(found)}",
        data=sorted(found),
    )

    repeated = {m: len(v) for m, v in discovered.items() if len(v) > 1}
    report.record(
        "repeated model IDs",
        "ok" if not repeated else "differs",
        f"{repeated}" if repeated else "none — each model appears once",
        data=repeated,
    )

    for model_id, (address, length) in sorted(EXPECTED_CHAIN.items()):
        actual = found.get(model_id)
        if actual is None:
            report.record(f"M{model_id} placement", "differs", "not on this device")
        elif actual == (address, length):
            report.record(
                f"M{model_id} placement", "ok", f"@{address} L={length}"
            )
        else:
            report.record(
                f"M{model_id} placement",
                "differs",
                f"@{actual[0]} L={actual[1]} — reconstruction said "
                f"@{address} L={length}",
                data={"actual": actual, "expected": [address, length]},
            )
    for model_id in sorted(set(found) - set(EXPECTED_CHAIN)):
        report.record(
            f"M{model_id} placement",
            "differs",
            f"@{found[model_id][0]} — not in the reconstruction at all",
        )


def check_counts(agate: AGate, report: Report) -> None:
    """The curve counts the generated components were sized with."""
    for model_id, expected in sorted(EXPECTED_COUNTS.items()):
        component = agate.model(model_id)
        if component is None:
            report.record(f"M{model_id} counts", "unknown", "model not present")
            continue
        actual = {name: component_value(component, name) for name in expected}
        verdict = "ok" if actual == expected else "differs"
        report.record(
            f"M{model_id} counts",
            verdict,
            f"{actual}" + ("" if verdict == "ok" else f" — expected {expected}"),
            data={"actual": actual, "expected": expected},
        )


def component_value(component: Any, name: str) -> Any:
    """A point's decoded value as a plain number where possible."""
    value = getattr(component, name, None)
    return int(value) if isinstance(value, (int, float)) else value


async def check_scale_factors(agate: AGate, unit: Any, report: Report) -> None:
    """Whether any sunssf on this device is unimplemented or out of range.

    ha-sunspec's migration notes rest on "all 55 hold valid in-range exponents"
    on this hardware. If that is false, the question of what an unimplemented
    scale factor should decode to stops being theoretical: modbus-connection
    decodes a point whose factor is out of range to None, and pysunspec2 hands
    back the raw value instead.

    A referenced sunssf is not a field of the generated component — it becomes
    the ``scale_register`` of the points that use it — so the addresses have to
    be collected from the fields and read directly.
    """
    addresses: dict[int, str] = {}
    for model_id, component in sorted(agate.models.items()):
        for name, register in component.declared_fields.items():
            scale = getattr(register, "scale_register", None)
            if scale is None:
                continue
            # No public accessor for a field's resolved scale address.
            addresses.setdefault(
                component._scale_address(register),  # noqa: SLF001
                f"M{model_id} (used by {name})",
            )
    suspicious: dict[str, Any] = {}
    for address, where in sorted(addresses.items()):
        (word,) = await unit.read_holding_registers(address, 1)
        exponent = word - 0x10000 if word >= 0x8000 else word
        if not -10 <= exponent <= 10:
            suspicious[f"{address} {where}"] = exponent
    report.record(
        "scale factors in range",
        "ok" if not suspicious else "differs",
        f"{len(addresses)} sunssf registers, all in -10..10"
        if not suspicious
        else f"{len(suspicious)} of {len(addresses)} unimplemented or out of "
        f"range: {suspicious}",
        data={"total": len(addresses), "suspicious": suspicious},
    )


def check_known_quirks(agate: AGate, report: Report) -> None:
    """The unimplemented points this library works around."""
    storage = agate.model(713)
    if storage is not None:
        value = component_value(storage, "sta")
        report.record(
            "M713.Sta is unusable",
            "ok" if value in (0, None) else "differs",
            f"reads {value}"
            + (
                " — as assumed, so battery state comes from DC power"
                if value in (0, None)
                else " — it carries a real value, so the DC-power workaround "
                "may be unnecessary"
            ),
            data=value,
        )
    ports = list(agate.model(714).prt) if agate.model(714) else []
    currents = [component_value(port, "dca") for port in ports]
    report.record(
        "M714.DCA is unimplemented",
        "ok" if all(not c for c in currents) else "differs",
        f"{currents}"
        + (
            " — as assumed, so current is derived from DCW / DCV"
            if all(not c for c in currents)
            else " — real values, so the derivation is unnecessary"
        ),
        data=currents,
    )
    report.record(
        "battery ports (NPrt)",
        "ok" if len(ports) == 1 else "differs",
        f"{len(ports)} port(s)"
        + (
            ""
            if len(ports) == 1
            else " — multi-battery summing has never been exercised, see "
            "HARDWARE-VERIFICATION.md item 14"
        ),
        data=len(ports),
    )


def check_curves(agate: AGate, report: Report) -> None:
    """What the curve models actually hold — the issue-156 payload."""
    for model_id in (705, 706, 712):
        component = agate.model(model_id)
        if component is None:
            continue
        curves = [
            {
                "act_pt": component_value(curve, "act_pt"),
                "read_only": component_value(curve, "read_only"),
                "points": [list(point) for point in read_curve(curve)],
            }
            for curve in component.crv
        ]
        configured = sum(1 for c in curves if c["act_pt"])
        report.record(
            f"M{model_id} curves",
            "ok",
            f"{len(curves)} curve(s), {configured} with active points",
            data=curves,
        )
    for model_id in (707, 708, 709, 710):
        component = agate.model(model_id)
        if component is None:
            continue
        sets = [read_trip_curve(curve) for curve in component.crv]
        report.record(
            f"M{model_id} trip curve sets",
            "ok" if all(len(s) == 3 for s in sets) else "differs",
            f"{len(sets)} set(s), regions per set "
            f"{[sorted(s) for s in sets][:1]}",
            data=[{k: [list(p) for p in v] for k, v in s.items()} for s in sets],
        )
    read_only_flags = {
        f"M{model_id}.crv[{index}]": component_value(curve, "read_only")
        for model_id in (705, 706, 707, 708, 709, 710, 712)
        if (component := agate.model(model_id)) is not None
        for index, curve in enumerate(component.crv)
    }
    any_locked = any(flag for flag in read_only_flags.values())
    report.record(
        "curve ReadOnly flags",
        "ok" if any_locked else "unknown",
        f"{read_only_flags}"
        if any_locked
        else "every curve reports writable — so per-instance writability "
        "(issue 156 item 4) is untested on this device",
        data=read_only_flags,
    )


def check_extensions(agate: AGate, report: Report) -> None:
    """The manufacturer block: does it answer, and does the mirror exist?"""
    extensions = agate.extensions
    mode = extensions.mode
    report.record(
        "extension block reads",
        "ok" if mode is not None else "differs",
        f"mode={mode.name if mode else extensions.on_grid_mode}, "
        f"self_reserve={component_value(extensions, 'self_reserve')}%, "
        f"tou_reserve={component_value(extensions, 'tou_reserve')}%",
        data=agate.native_mode(),
    )
    hires = component_value(extensions, "load_active_p_hires")
    coarse = component_value(extensions, "load_active_p")
    report.record(
        "high-resolution load mirror (16000)",
        "ok" if hires else "differs",
        f"16000={hires} W vs 15506={coarse} W"
        + (
            ""
            if hires
            else " — the undocumented mirror reads 0, so home load falls back "
            "to the quantized register"
        ),
        data={"hires": hires, "coarse": coarse},
    )


async def check_block_limits(unit: Any, report: Report) -> None:
    """Whether the device answers a full-width FC03.

    The planner caps a block at 125 registers, the Modbus ceiling. A gateway
    that caps lower needs Component.max_span lowered to match.
    """
    for count in (125, 100, 50):
        try:
            await unit.read_holding_registers(0, count)
        except Exception as err:  # noqa: BLE001 — any failure is the answer
            report.record(
                f"FC03 of {count} registers",
                "differs" if count == 125 else "unknown",
                f"refused ({type(err).__name__}: {err}) — lower max_span",
            )
            continue
        report.record(f"FC03 of {count} registers", "ok", "answered")
        return


async def check_poll(agate: AGate, report: Report) -> None:
    """How much a whole-device poll costs on the wire."""
    import time

    started = time.monotonic()
    await agate.async_update()
    elapsed = time.monotonic() - started
    report.record(
        "whole-device poll",
        "ok",
        f"{elapsed * 1000:.0f} ms for all {len(agate.models)} models plus the "
        f"extension block",
        data={"seconds": round(elapsed, 3)},
    )


async def run(host: str, port: int, unit_id: int, timeout: float) -> Report:
    """Run every read-only check and return the report."""
    report = Report(host=host, unit_id=unit_id)

    # The first phase talks to the unit directly, because it is checking the
    # things a Component takes for granted: where the chain is and how wide a
    # block the device will answer.
    connection = ModbusConnection(
        ModbusTcpParams(host=host, port=port), timeout=timeout
    )
    await connection.connect()
    unit = connection.for_unit(unit_id)
    print(f"\n-- chain and placement ({host}:{port} unit {unit_id})\n")
    try:
        await probe_base_addresses(unit, report)
        await check_chain(unit, report)
        await check_block_limits(unit, report)
    finally:
        await connection.disconnect()

    print("\n-- values, with the components this library ships\n")
    agate = AGate(host, port=port, unit_id=unit_id, timeout=timeout)
    try:
        await agate.async_connect()
    except SunSpecMapShiftError as err:
        report.record(
            "component header verification",
            "differs",
            f"{err} — a model's length does not match, which for a curve model "
            f"means its counts differ from the ones these components were "
            f"generated for",
        )
        await agate.async_close()
        return report
    try:
        report.record(
            "component header verification",
            "ok",
            "every model's ID and length matched — which for M705-M712 also "
            "confirms their counts, since the counts decide the length",
        )
        report.record(
            "nameplate", "ok", f"{agate.nameplate()}", data=agate.nameplate()
        )
        check_counts(agate, report)
        await check_scale_factors(agate, unit, report)
        check_known_quirks(agate, report)
        check_curves(agate, report)
        check_extensions(agate, report)
        await check_poll(agate, report)
    finally:
        await agate.async_close()
    return report


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="the aGate's IP address")
    parser.add_argument("-p", "--port", type=int, default=502)
    parser.add_argument("-u", "--unit", type=int, default=DEFAULT_UNIT_ID)
    parser.add_argument("-t", "--timeout", type=float, default=10.0)
    parser.add_argument("--json", help="also write the full report here")
    options = parser.parse_args()

    report = asyncio.run(
        run(options.host, options.port, options.unit, options.timeout)
    )

    print(f"\n-- {len(report.checks)} checks, {len(report.differences)} differing\n")
    for check in report.differences:
        print(f"  {check.name}: {check.detail}")
    if not report.differences:
        print("  the device matches the reconstruction exactly")

    if options.json:
        with open(options.json, "w", encoding="utf-8") as file:
            json.dump(asdict(report), file, indent=2, default=str)
        print(f"\nfull report written to {options.json}")
    print(
        "\nThe checks that need a write are in HARDWARE-VERIFICATION.md; they "
        "move a battery, so they are not in here."
    )
    return 1 if report.differences else 0


if __name__ == "__main__":
    sys.exit(main())
