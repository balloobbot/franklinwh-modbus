"""Check the reconstructed register map against the documented addresses.

The fixture is built from the SunSpec model definitions sized with the counts
the aGate reports, not captured from the device. What makes it trustworthy is
this test: the documented absolute addresses in ``SUNSPEC_MODEL_REFERENCE.md``
only land where they do if every model ahead of them is exactly as long as the
reconstruction says — and models 705-712's lengths are decided entirely by the
runtime counts. So this doubles as a check on the counts themselves.
"""

from __future__ import annotations

import pytest

from .fixtures.agate_registers import CHAIN_REGISTERS

_END_MODEL_ID = 0xFFFF

# Every address SUNSPEC_MODEL_REFERENCE.md states, as (model, point, address).
DOCUMENTED_ADDRESSES = [
    (1, "ID", 2),
    (1, "Mn", 4),
    (1, "Md", 20),
    (1, "Vr", 44),
    (1, "SN", 52),
    (701, "St", 73),
    (701, "W", 80),
    (701, "Var", 82),
    (701, "PF", 83),
    (701, "LNV", 86),
    (701, "Hz", 87),
    (702, "WMaxRtg", 227),
    (702, "CtrlModes", 248),
    (702, "WMax", 251),
    (704, "WMaxLimPctEna", 310),
    (704, "WMaxLimPct", 311),
    (704, "WSetEna", 318),
    (704, "WSet", 320),
    (704, "WSetPct", 324),
    (704, "WSetRvrtTms", 327),
    (704, "VarSetEna", 331),
    (713, "WHRtg", 1035),
    (713, "WHAvail", 1036),
    (713, "SoC", 1037),
    (714, "PrtAlrms", 1044),
    (714, "NPrt", 1046),
    (715, "LocRemCtl", 1089),
    (715, "ControllerHb", 1092),
    (715, "OpCtl", 1095),
]

# The header address each model sits at, per the reconstruction.
EXPECTED_CHAIN = {
    1: 2,
    701: 70,
    702: 225,
    703: 277,
    704: 296,
    705: 363,
    706: 432,
    707: 465,
    708: 572,
    709: 679,
    710: 816,
    711: 953,
    712: 987,
    713: 1033,
    714: 1042,
    715: 1087,
    502: 1096,
}

# Where the aGate's runtime counts live, and what it reports there.
DOCUMENTED_COUNTS = [
    (705, "NPt", 4),
    (705, "NCrv", 3),
    (706, "NPt", 2),
    (706, "NCrv", 2),
    (707, "NPt", 5),
    (707, "NCrvSet", 2),
    (708, "NPt", 5),
    (708, "NCrvSet", 2),
    (709, "NPt", 5),
    (709, "NCrvSet", 2),
    (710, "NPt", 5),
    (710, "NCrvSet", 2),
    (711, "NCtl", 2),
    (712, "NPt", 6),
    (712, "NCrv", 2),
    (714, "NPrt", 1),
]

# Model-relative offset of each count point, from the model definitions.
COUNT_OFFSETS = {
    ("705", "NPt"): 5,
    ("705", "NCrv"): 6,
    ("706", "NPt"): 5,
    ("706", "NCrv"): 6,
    ("707", "NPt"): 5,
    ("707", "NCrvSet"): 6,
    ("708", "NPt"): 5,
    ("708", "NCrvSet"): 6,
    ("709", "NPt"): 5,
    ("709", "NCrvSet"): 6,
    ("710", "NPt"): 5,
    ("710", "NCrvSet"): 6,
    ("711", "NCtl"): 5,
    ("712", "NPt"): 5,
    ("712", "NCrv"): 6,
    ("714", "NPrt"): 4,
}


def walk_chain() -> dict[int, tuple[int, int]]:
    """Walk the fixture's model chain, returning ``{model_id: (address, L)}``."""
    found: dict[int, tuple[int, int]] = {}
    address = 2
    while CHAIN_REGISTERS[address] != _END_MODEL_ID:
        model_id, length = CHAIN_REGISTERS[address], CHAIN_REGISTERS[address + 1]
        found[model_id] = (address, length)
        address += 2 + length
    return found


def test_marker_is_present() -> None:
    assert (CHAIN_REGISTERS[0] << 16) | CHAIN_REGISTERS[1] == 0x53756E53  # "SunS"


def test_chain_matches_the_reconstruction() -> None:
    assert {mid: addr for mid, (addr, _) in walk_chain().items()} == EXPECTED_CHAIN


@pytest.mark.parametrize(("model_id", "point", "address"), DOCUMENTED_ADDRESSES)
def test_documented_address_lands_where_documented(
    model_id: int, point: str, address: int
) -> None:
    """Every address SUNSPEC_MODEL_REFERENCE.md names falls inside its model."""
    start, length = walk_chain()[model_id]
    assert start <= address <= start + 1 + length, (
        f"{model_id}.{point} at {address} is outside model {model_id} "
        f"({start}..{start + 1 + length})"
    )


def test_model_1_identity_reads_back() -> None:
    """The documented offsets of Mn/Md/Vr/SN decode to the seeded strings."""
    base = walk_chain()[1][0]

    def text(address: int, registers: int) -> str:
        words = CHAIN_REGISTERS[address : address + registers]
        return b"".join(w.to_bytes(2, "big") for w in words).rstrip(b"\0").decode()

    assert text(base + 2, 16) == "FranklinWH"
    assert text(base + 18, 16) == "aGate X"
    assert text(base + 42, 8) == "V10R01B04D00"


@pytest.mark.parametrize(("model_id", "point", "count"), DOCUMENTED_COUNTS)
def test_count_points_hold_the_reported_counts(
    model_id: int, point: str, count: int
) -> None:
    """The counts issue 156 reports are what the fixture's count points hold."""
    start = walk_chain()[model_id][0]
    offset = COUNT_OFFSETS[(str(model_id), point)]
    assert CHAIN_REGISTERS[start + offset] == count
