"""Build the aGate register-map fixture from the SunSpec model definitions.

Development tool, not part of the package: it needs the official model JSON
(https://github.com/sunspec/models), which the runtime does not. Run it to
regenerate ``tests/fixtures/agate_registers.py`` after changing the counts or
the seeded values.

The map it writes is a reconstruction, not a capture. It is built from the
model definitions sized with the counts the aGate reports, and it is trusted
because it reproduces every absolute address documented in
``SUNSPEC_MODEL_REFERENCE.md`` — see ``tests/test_register_map.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# Firmware V10R01B04D00's model chain, in the order the device presents it.
# M502's position is the one thing here that is inferred rather than pinned: the
# documented addresses place M701 directly after M1, and hold to M715, so 502
# sits somewhere after 715. Nothing in this library depends on where.
CHAIN = [
    1, 701, 702, 703, 704, 705, 706, 707,
    708, 709, 710, 711, 712, 713, 714, 715, 502,
]

# The counts this unit reports, per model (see MIGRATION-NOTES.md).
COUNTS: dict[int, dict[str, int]] = {
    705: {"NPt": 4, "NCrv": 3},
    706: {"NPt": 2, "NCrv": 2},
    707: {"NPt": 5, "NCrvSet": 2},
    708: {"NPt": 5, "NCrvSet": 2},
    709: {"NPt": 5, "NCrvSet": 2},
    710: {"NPt": 5, "NCrvSet": 2},
    711: {"NCtl": 2},
    712: {"NPt": 6, "NCrv": 2},
    714: {"NPrt": 1},
}

STRINGS = {
    "Mn": "FranklinWH",
    "Md": "aGate X",
    "Vr": "V10R01B04D00",
    "SN": "AG24X0000001",
}

# Points seeded with a plausible reading so the ported control and telemetry
# paths have something to decode. Keyed "<model>.<point>" -> raw register value.
SEEDED: dict[str, int] = {
    # Scale factors. Every sunssf on this device holds a valid exponent, so the
    # fixture uses real ones rather than a flat 0 — otherwise nothing exercises
    # the scaled-decode path.
    "701.W_SF": -1,
    "701.V_SF": -1,
    "701.Hz_SF": -2,
    "701.PF_SF": -4,
    "701.Var_SF": -1,
    "701.VA_SF": -1,
    "701.A_SF": -2,
    "701.TotWh_SF": 0,
    "701.TotVarh_SF": 0,
    "701.Tmp_SF": -1,
    "702.W_SF": 0,
    "702.V_SF": -1,
    "702.A_SF": -2,
    "702.PF_SF": -4,
    "702.VA_SF": 0,
    "702.Var_SF": 0,
    "702.S_SF": 0,
    "704.WSetPct_SF": -2,
    "704.WMaxLimPct_SF": -2,
    "704.WSet_SF": 0,
    "704.PF_SF": -4,
    "704.VarSet_SF": 0,
    "704.VarSetPct_SF": -2,
    "705.V_SF": -2,
    "705.DeptRef_SF": -2,
    "705.RspTms_SF": 0,
    "713.WH_SF": 0,
    "713.Pct_SF": -2,
    "714.DCA_SF": -2,
    "714.DCV_SF": -1,
    "714.DCW_SF": 0,
    "714.DCWH_SF": 0,
    "714.Tmp_SF": -1,
    # Telemetry.
    "701.St": 1,  # ON
    "701.W": 2500,  # x10^-1 -> 250.0 W injected
    "701.Var": -300,
    "701.InvSt": 3,  # RUNNING
    "701.ConnSt": 1,  # CONNECTED
    "701.PF": 9800,
    "701.LNV": 2401,
    "701.Hz": 6000,
    "701.TotWhInj": 12_345_678,
    "701.TotWhAbs": 9_876_543,
    "702.WMaxRtg": 10_000,
    "702.WMax": 10_000,
    "702.WChaRteMaxRtg": 5000,
    "702.WDisChaRteMaxRtg": 5000,
    "702.CtrlModes": 0b0000_0111,
    "704.WSetEna": 0,
    "704.WSetPct": 0,
    "704.WMaxLimPct": 10_000,
    "713.WHRtg": 13_600,
    "713.WHAvail": 8160,
    "713.SoC": 6000,
    "713.SoH": 9900,
    "714.DCW": 1500,
    "714.DCV": 4800,
    "714.Tmp": 250,
    "715.LocRemCtl": 1,
    "715.ControllerHb": 0,
}

# The FranklinWH extension block (15500+), which is outside the SunSpec chain.
EXTENSIONS: dict[int, int] = {
    15500: 1,  # PVUse
    15501: 0,  # apBoxPVUse
    15502: 3200,  # PVOutputP
    15503: 3200,  # proximalPVOutputP
    15504: 0,
    15505: 0,
    15506: 1800,  # LoadActiveP
    15507: 2,  # OnGridMode = Self-Consumption
    15508: 20,  # SelfReserve %
    15509: 30,  # TouReserve %
    15510: 0,  # PVOutputWh high
    15511: 45_000,  # PVOutputWh low
    15512: 0,
    15513: 45_000,
    16000: 1837,  # high-resolution home load mirror
}

_NAN = {
    "int16": 0x8000,
    "uint16": 0xFFFF,
    "int32": 0x8000_0000,
    "uint32": 0xFFFF_FFFF,
    "int64": 0x8000_0000_0000_0000,
    "uint64": 0xFFFF_FFFF_FFFF_FFFF,
}


def _words(value: int, size: int) -> list[int]:
    """Split a value into ``size`` big-endian 16-bit words (two's complement)."""
    raw = value & ((1 << (16 * size)) - 1)
    return [(raw >> (16 * (size - 1 - i))) & 0xFFFF for i in range(size)]


def _string_words(text: str, size: int) -> list[int]:
    data = text.encode("ascii").ljust(size * 2, b"\0")[: size * 2]
    return [int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)]


def _point_value(point: dict[str, Any], model_id: int, counts: dict[str, int]) -> int:
    name, ptype, size = point["name"], point["type"], int(point["size"])
    if name in counts:
        return counts[name]
    key = f"{model_id}.{name}"
    if key in SEEDED:
        return SEEDED[key]
    if ptype == "sunssf":
        # Every sunssf on this device holds a valid exponent; use the one the
        # definition's own scaled points imply, defaulting to 0.
        return 0
    if ptype in ("enum16", "enum32"):
        symbols = point.get("symbols") or []
        return int(symbols[0]["value"]) if symbols else 0
    if ptype == "pad":
        return 0x8000
    if ptype in _NAN:
        return 0
    return 0


def _emit_group(
    group: dict[str, Any],
    address: int,
    model_id: int,
    counts: dict[str, int],
    out: dict[int, int],
) -> int:
    """Write one block's registers; return the address just past it."""
    for point in group.get("points", []):
        size = int(point["size"])
        if point["type"] == "string":
            words = _string_words(STRINGS.get(point["name"], ""), size)
        else:
            words = _words(_point_value(point, model_id, counts), size)
        for offset, word in enumerate(words):
            out[address + offset] = word
        address += size
    for sub in group.get("groups", []):
        raw = sub.get("count", 1)
        repeats = counts[raw] if isinstance(raw, str) else int(raw)
        for _ in range(repeats):
            address = _emit_group(sub, address, model_id, counts, out)
    return address


def build(model_dir: Path) -> dict[int, int]:
    """Return the whole holding-register map, address -> word."""
    out: dict[int, int] = {}
    out[0], out[1] = 0x5375, 0x6E53  # "SunS"
    address = 2
    for model_id in CHAIN:
        definition = json.loads((model_dir / f"model_{model_id}.json").read_text())
        end = _emit_group(definition["group"], address, model_id, COUNTS.get(model_id, {}), out)
        out[address] = model_id
        out[address + 1] = end - address - 2  # L excludes ID and L themselves
        address = end
    out[address] = 0xFFFF  # end-of-chain marker
    out[address + 1] = 0  # the marker's length word, which scan() reads too
    out.update(EXTENSIONS)
    return out


def render(registers: dict[int, int]) -> str:
    chain_end = max(a for a in registers if a < 15000)
    lines = [
        '"""The aGate\'s holding registers, reconstructed from the model definitions.',
        "",
        "Generated by ``scripts/build_agate_fixture.py`` — do not edit by hand.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "# The SunSpec chain, address 0 through the end-of-chain marker.",
        "CHAIN_REGISTERS: list[int] = [",
    ]
    row: list[str] = []
    for address in range(chain_end + 1):
        row.append(f"{registers.get(address, 0)},")
        if len(row) == 12:
            lines.append("    " + " ".join(row))
            row = []
    if row:
        lines.append("    " + " ".join(row))
    lines += [
        "]",
        "",
        "# The FranklinWH extension block, which sits outside the chain.",
        "EXTENSION_REGISTERS: dict[int, int] = {",
    ]
    lines += [
        f"    {a}: {v}," for a, v in sorted(registers.items()) if a >= 15000
    ]
    lines += [
        "}",
        "",
        "REGISTERS: dict[int, int] = {",
        "    **dict(enumerate(CHAIN_REGISTERS)),",
        "    **EXTENSION_REGISTERS,",
        "}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_dir", type=Path, help="directory of model_N.json files")
    parser.add_argument("-o", "--out", type=Path, required=True)
    options = parser.parse_args()
    options.out.write_text(render(build(options.model_dir)))


if __name__ == "__main__":
    main()
