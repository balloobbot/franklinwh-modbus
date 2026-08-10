"""The hardware diagnostic, run against the reconstructed map.

It should report zero differences there — the reconstruction is what it checks
against — which is exactly what makes a difference on real hardware meaningful.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hardware_check  # noqa: E402

if TYPE_CHECKING:
    from modbus_connection.mock import MockModbusConnection


@pytest.fixture
def offline(
    connection: MockModbusConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point every connection constructor the script reaches at the mock."""
    import franklinwh_modbus.device as device_module

    monkeypatch.setattr(
        hardware_check, "ModbusConnection", lambda *a, **kw: connection
    )
    monkeypatch.setattr(
        device_module, "ModbusConnection", lambda *a, **kw: connection
    )


async def test_the_reconstruction_reports_no_differences(offline: None) -> None:
    report = await hardware_check.run("mock-host", 502, 2, 1.0)
    assert [c.name for c in report.differences] == []


async def test_it_confirms_the_counts_and_the_quirks(offline: None) -> None:
    report = await hardware_check.run("mock-host", 502, 2, 1.0)
    by_name = {check.name: check for check in report.checks}

    assert by_name["M705 counts"].data["actual"] == {"n_pt": 4, "n_crv": 3}
    assert by_name["M707 counts"].data["actual"] == {"n_pt": 5, "n_crv_set": 2}
    assert by_name["component header verification"].verdict == "ok"
    assert by_name["M713.Sta is unusable"].verdict == "ok"
    assert by_name["M714.DCA is unimplemented"].verdict == "ok"


async def test_it_flags_a_device_whose_counts_differ(
    connection: MockModbusConnection, offline: None
) -> None:
    """A curve model's length is a function of its counts, so this is caught."""
    connection.for_unit(2).holding[363 + 5] = 6  # M705 NPt: 4 -> 6
    report = await hardware_check.run("mock-host", 502, 2, 1.0)
    assert any("M705" in check.name for check in report.differences)


async def test_it_flags_an_out_of_range_scale_factor(
    connection: MockModbusConnection, offline: None
) -> None:
    connection.for_unit(2).holding[1033 + 8] = 0x8000  # M713 Pct_SF unimplemented
    report = await hardware_check.run("mock-host", 502, 2, 1.0)
    names = [check.name for check in report.differences]
    assert "scale factors in range" in names
