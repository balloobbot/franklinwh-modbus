#!/usr/bin/env python3
"""
FranklinWH Systematic Register Test Utility

Automated test of each writable SunSpec register to determine:
- Which registers the aGate actually accepts (vs silently rejects)
- Correct sign conventions
- Effect on battery/grid power
- Alarm/fault behavior during writes

Outputs a JSON report with per-register results.

Usage:
    python3 franklinwh_register_test.py -i 192.168.0.110
    python3 franklinwh_register_test.py -i 192.168.0.110 --settle 20 --power 1000
    python3 franklinwh_register_test.py -i 192.168.0.110 --output results.json
"""

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP
except ImportError:
    print("Error: pip install pysunspec2")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── FranklinWH Constants ─────────────────────────────────────────────
RATED_MAX_W = 5000
UNIT_ID = 2

# ── Alarm bitfield definitions (Model 701) ───────────────────────────
ALARM_BITS = {
    0: "GROUND_FAULT",
    1: "DC_OVER_VOLT",
    2: "AC_DISCONNECT",
    3: "DC_DISCONNECT",
    4: "GRID_DISCONNECT",
    5: "CABINET_OPEN",
    6: "MANUAL_SHUTDOWN",
    7: "OVER_TEMP",
    8: "OVER_FREQ",
    9: "UNDER_FREQ",
    10: "AC_OVER_VOLT",
    11: "AC_UNDER_VOLT",
    12: "BLOWN_FUSE",
    13: "UNDER_TEMP",
    14: "MEMORY_LOSS",
    15: "HW_TEST_FAIL",
}

# Inverter states (Model 701 InvSt)
INV_STATES = {0: "Off", 1: "Sleeping", 2: "Starting", 3: "Running",
              4: "Throttled", 5: "Shutting Down", 6: "Fault",
              7: "Standby", 8: "No Solar"}

# Operating states (Model 701 St)
OP_STATES = {0: "Off", 1: "On"}


@dataclass
class SystemSnapshot:
    """Full system state at a point in time."""
    timestamp: str
    soc: float
    dc_power_w: float
    grid_power_w: float
    inverter_state: int
    inverter_state_name: str
    operating_state: int
    alarm_bitfield: int
    alarm_names: List[str]
    der_mode: int
    # Model 704 control state
    wset_ena: int
    wset_mod: int
    wset: int
    wset_pct: int
    wset_pct_actual: float
    # Model 715 state
    opctl: int
    loc_rem_ctl: int


@dataclass
class RegisterTestResult:
    """Result of testing a single register write."""
    register_name: str
    model_id: int
    address: int
    test_value: Any
    test_description: str
    # Before
    value_before: Any
    snapshot_before: Dict[str, Any]
    # After write
    value_after_write: Any
    write_accepted: bool
    # After settle
    snapshot_after: Dict[str, Any]
    dc_power_change_w: float
    grid_power_change_w: float
    # Health
    alarms_during: List[str]
    inverter_faulted: bool
    # Timing
    settle_time_s: float
    notes: List[str] = field(default_factory=list)


@dataclass
class TestReport:
    """Complete test report."""
    timestamp: str
    agate_ip: str
    rated_max_w: int
    test_power_w: int
    settle_time_s: int
    solar_present: bool
    initial_snapshot: Dict[str, Any]
    register_tests: List[Dict[str, Any]]
    summary: Dict[str, Any] = field(default_factory=dict)


class RegisterTester:
    """Systematic register tester with alarm monitoring."""

    def __init__(self, ip: str, port: int = 502, timeout: float = 10.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.dev = None
        self.models = {}

    def connect(self) -> bool:
        logger.info(f"Connecting to {self.ip}:{self.port} (unit {UNIT_ID})")
        try:
            self.dev = SunSpecModbusClientDeviceTCP(
                slave_id=UNIT_ID, ipaddr=self.ip,
                ipport=self.port, timeout=self.timeout
            )
            try:
                self.dev.scan(base_addr=1)
            except TypeError:
                self.dev.scan()

            self.models = {
                int(k) if str(k).isdigit() else k: v
                for k, v in self.dev.models.items()
            }
            numeric = sorted(k for k in self.models if isinstance(k, int))
            logger.info(f"Connected. Models: {numeric}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        if self.dev:
            self.dev.close()
            self.dev = None

    def get_model(self, mid):
        m = self.models.get(mid)
        return m[0] if isinstance(m, list) else m

    def _sf(self, model, name) -> int:
        try:
            v = getattr(model, name).value
            return v if v is not None else 0
        except:
            return 0

    # ── Snapshot ──────────────────────────────────────────────────────

    def take_snapshot(self) -> SystemSnapshot:
        """Capture complete system state including alarms."""
        m701 = self.get_model(701)
        m704 = self.get_model(704)
        m713 = self.get_model(713)
        m714 = self.get_model(714)
        m715 = self.get_model(715)

        m701.read(); m704.read(); m713.read(); m714.read()
        if m715:
            m715.read()

        soc_sf = self._sf(m713, 'Pct_SF')
        pct_sf = self._sf(m704, 'WSetPct_SF')

        alarm_val = m701.Alrm.value if m701.Alrm.value else 0
        alarm_names = [name for bit, name in ALARM_BITS.items()
                       if alarm_val & (1 << bit)]

        inv_st = m701.InvSt.value if m701.InvSt.value is not None else -1
        wset_pct_raw = m704.WSetPct.value if m704.WSetPct.value else 0
        wset_pct_actual = wset_pct_raw * (10 ** pct_sf) if pct_sf else wset_pct_raw

        return SystemSnapshot(
            timestamp=datetime.now().isoformat(),
            soc=m713.SoC.value * (10 ** soc_sf),
            dc_power_w=m714.DCW.value if m714.DCW.value else 0,
            grid_power_w=m701.W.value if m701.W.value else 0,
            inverter_state=inv_st,
            inverter_state_name=INV_STATES.get(inv_st, f"Unknown({inv_st})"),
            operating_state=m701.St.value if m701.St.value is not None else -1,
            alarm_bitfield=alarm_val,
            alarm_names=alarm_names,
            der_mode=m701.DERMode.value if m701.DERMode.value is not None else -1,
            wset_ena=m704.WSetEna.value if m704.WSetEna.value is not None else 0,
            wset_mod=m704.WSetMod.value if m704.WSetMod.value is not None else 0,
            wset=m704.WSet.value if m704.WSet.value is not None else 0,
            wset_pct=wset_pct_raw,
            wset_pct_actual=wset_pct_actual,
            opctl=m715.OpCtl.value if m715 and m715.OpCtl.value is not None else 0,
            loc_rem_ctl=m715.LocRemCtl.value if m715 and m715.LocRemCtl.value is not None else 0,
        )

    def print_snapshot(self, snap: SystemSnapshot, label: str = ""):
        prefix = f"  [{label}]" if label else "  "
        inv_warn = " ⚠️" if snap.inverter_state == 6 else ""
        alm_warn = f" ALARMS: {snap.alarm_names}" if snap.alarm_names else ""
        print(f"{prefix} SoC={snap.soc}% | DC={snap.dc_power_w}W | Grid={snap.grid_power_w}W | "
              f"Inv={snap.inverter_state_name}{inv_warn} | "
              f"WSetEna={snap.wset_ena} WSetPct={snap.wset_pct_actual}% WSet={snap.wset} | "
              f"OpCtl={snap.opctl} LocRem={snap.loc_rem_ctl}{alm_warn}")

    # ── Reset ────────────────────────────────────────────────────────

    def reset_all(self):
        """Deep reset — clear all control registers."""
        m704 = self.get_model(704)
        m704.read()
        m704.WSetEna.value = 0
        m704.WSetPct.value = 0
        m704.WSet.value = 0
        m704.WSetMod.value = 0
        m704.WSetRvrtTms.value = 0
        m704.write()
        time.sleep(0.5)

    # ── Individual Register Tests ────────────────────────────────────

    def test_register_write(self, model_id: int, attr_name: str,
                            test_value: Any, description: str,
                            settle_time: float = 15.0,
                            address: int = 0) -> RegisterTestResult:
        """
        Test writing a single register value.

        Sequence:
        1. Take BEFORE snapshot
        2. Read current register value
        3. Write test value
        4. Read back immediately (check if accepted)
        5. Wait settle_time, monitoring for alarms
        6. Take AFTER snapshot
        7. Reset to clean state
        """
        model = self.get_model(model_id)
        if not model:
            return RegisterTestResult(
                register_name=attr_name, model_id=model_id, address=address,
                test_value=test_value, test_description=description,
                value_before=None, snapshot_before={},
                value_after_write=None, write_accepted=False,
                snapshot_after={}, dc_power_change_w=0, grid_power_change_w=0,
                alarms_during=[], inverter_faulted=False,
                settle_time_s=settle_time, notes=[f"Model {model_id} not found"]
            )

        notes = []
        alarms_during = []

        # 1. BEFORE snapshot
        snap_before = self.take_snapshot()
        self.print_snapshot(snap_before, "BEFORE")

        # 2. Read current value
        model.read()
        try:
            val_before = getattr(model, attr_name).value
        except AttributeError:
            return RegisterTestResult(
                register_name=attr_name, model_id=model_id, address=address,
                test_value=test_value, test_description=description,
                value_before=None, snapshot_before=asdict(snap_before),
                value_after_write=None, write_accepted=False,
                snapshot_after=asdict(snap_before),
                dc_power_change_w=0, grid_power_change_w=0,
                alarms_during=[], inverter_faulted=False,
                settle_time_s=settle_time,
                notes=[f"Attribute '{attr_name}' does not exist on Model {model_id}"]
            )

        logger.info(f"  Writing {attr_name} = {test_value} (was {val_before})")

        # 3. Write
        try:
            getattr(model, attr_name).value = test_value
            model.write()
            time.sleep(0.3)
        except Exception as e:
            notes.append(f"Write exception: {e}")

        # 4. Read back
        model.read()
        val_after = getattr(model, attr_name).value
        write_accepted = (val_after == test_value)
        if not write_accepted:
            notes.append(f"Write rejected: wrote {test_value}, readback {val_after}")
            logger.warning(f"  ❌ REJECTED: wrote {test_value}, got {val_after}")
        else:
            logger.info(f"  ✅ ACCEPTED: {attr_name} = {val_after}")

        # 5. Settle + monitor
        inverter_faulted = False
        check_interval = min(5.0, settle_time / 3)
        elapsed = 0
        while elapsed < settle_time:
            time.sleep(check_interval)
            elapsed += check_interval
            try:
                mid_snap = self.take_snapshot()
                self.print_snapshot(mid_snap, f"T+{elapsed:.0f}s")
                if mid_snap.alarm_names:
                    for a in mid_snap.alarm_names:
                        if a not in alarms_during:
                            alarms_during.append(a)
                if mid_snap.inverter_state == 6:
                    inverter_faulted = True
                    notes.append(f"Inverter FAULT at T+{elapsed:.0f}s")
            except Exception as e:
                notes.append(f"Snapshot failed at T+{elapsed:.0f}s: {e}")

        # 6. AFTER snapshot
        snap_after = self.take_snapshot()
        self.print_snapshot(snap_after, "AFTER")

        dc_change = snap_after.dc_power_w - snap_before.dc_power_w
        grid_change = snap_after.grid_power_w - snap_before.grid_power_w

        # 7. Reset
        self.reset_all()
        time.sleep(2)  # Extra settle after reset
        snap_reset = self.take_snapshot()
        if snap_reset.inverter_state == 6:
            notes.append("Inverter still in FAULT after reset")

        return RegisterTestResult(
            register_name=attr_name,
            model_id=model_id,
            address=address,
            test_value=test_value,
            test_description=description,
            value_before=val_before,
            snapshot_before=asdict(snap_before),
            value_after_write=val_after,
            write_accepted=write_accepted,
            snapshot_after=asdict(snap_after),
            dc_power_change_w=dc_change,
            grid_power_change_w=grid_change,
            alarms_during=alarms_during,
            inverter_faulted=inverter_faulted,
            settle_time_s=settle_time,
            notes=notes,
        )

    # ── Test Suite ───────────────────────────────────────────────────

    def build_test_suite(self, power_w: int = 1500) -> list:
        """Build systematic test list for all interesting RW registers."""
        pct_val = int((power_w / RATED_MAX_W) * 1000)  # SF=-1

        tests = [
            # ── Model 704 (DERCtlAC) — the proven control path ────────
            {
                "model": 704, "attr": "WSetPct", "value": pct_val,
                "addr": 40324,
                "desc": f"Discharge {power_w}W via WSetPct (+{pct_val} raw, SF=-1)",
            },
            {
                "model": 704, "attr": "WSetPct", "value": -pct_val,
                "addr": 40324,
                "desc": f"Charge {power_w}W via WSetPct (-{pct_val} raw, SF=-1)",
            },
            {
                "model": 704, "attr": "WSet", "value": power_w,
                "addr": 40320,
                "desc": f"Discharge {power_w}W via WSet only (positive)",
            },
            {
                "model": 704, "attr": "WSet", "value": -power_w,
                "addr": 40320,
                "desc": f"Charge {power_w}W via WSet only (negative)",
            },
            {
                "model": 704, "attr": "WMaxLimPctEna", "value": 1,
                "addr": 40310,
                "desc": "Enable WMaxLimPct (power limiting)",
            },
            {
                "model": 704, "attr": "WMaxLimPct", "value": 300,
                "addr": 40311,
                "desc": "Set WMaxLimPct to 30% (1500W of 5kW)",
            },

            # ── Model 702 (DERCapacity) — rate limit registers ────────
            {
                "model": 702, "attr": "WChaRteMax", "value": power_w,
                "addr": 40259,
                "desc": f"Set WChaRteMax to {power_w}W (charge rate limit)",
            },
            {
                "model": 702, "attr": "WDisChaRteMax", "value": power_w,
                "addr": 40260,
                "desc": f"Set WDisChaRteMax to {power_w}W (discharge rate limit)",
            },
            {
                "model": 702, "attr": "VAChaRteMax", "value": power_w,
                "addr": 40261,
                "desc": f"Set VAChaRteMax to {power_w}VA (charge VA rate limit)",
            },
            {
                "model": 702, "attr": "VADisChaRteMax", "value": power_w,
                "addr": 40262,
                "desc": f"Set VADisChaRteMax to {power_w}VA (discharge VA rate limit)",
            },

            # ── Model 715 (DERStorageCtl) — authority/control ─────────
            {
                "model": 715, "attr": "OpCtl", "value": 1,
                "addr": 41095,
                "desc": "Set OpCtl=1 (External Control)",
            },
            {
                "model": 715, "attr": "OpCtl", "value": 2,
                "addr": 41095,
                "desc": "Set OpCtl=2 (Charge mode)",
            },
            {
                "model": 715, "attr": "OpCtl", "value": 3,
                "addr": 41095,
                "desc": "Set OpCtl=3 (Discharge mode)",
            },
        ]
        return tests

    def run_full_test(self, power_w: int = 1500, settle_time: int = 15,
                      output_file: str = None) -> TestReport:
        """Run systematic test of all writable registers."""
        tests = self.build_test_suite(power_w)

        # Initial state
        self.reset_all()
        time.sleep(1)
        initial_snap = self.take_snapshot()

        print("\n" + "=" * 72)
        print("  FRANKLINWH SYSTEMATIC REGISTER TEST")
        print(f"  Target: {self.ip}:{self.port} | Power: {power_w}W | Settle: {settle_time}s")
        print(f"  Registers to test: {len(tests)}")
        print("=" * 72)
        self.print_snapshot(initial_snap, "INITIAL")

        results = []
        for i, test in enumerate(tests, 1):
            print(f"\n{'─' * 72}")
            print(f"  TEST {i}/{len(tests)}: {test['desc']}")
            print(f"  Register: Model {test['model']}.{test['attr']} (addr {test['addr']})")
            print(f"{'─' * 72}")

            # For WSetPct and WSet tests, we also need to enable WSetEna
            setup_ena = test['attr'] in ('WSetPct', 'WSet')

            if setup_ena:
                # Pre-configure: set WSetMod=0 and the test value, then enable
                m704 = self.get_model(704)
                m704.read()
                m704.WSetEna.value = 0
                m704.write()
                time.sleep(0.3)

                m704.read()
                m704.WSetMod.value = 0

                if test['attr'] == 'WSetPct':
                    m704.WSetPct.value = test['value']
                    # Zero WSet to isolate the test
                    m704.WSet.value = 0
                elif test['attr'] == 'WSet':
                    m704.WSet.value = test['value']
                    # Zero WSetPct to isolate the test
                    m704.WSetPct.value = 0

                m704.write()
                time.sleep(0.3)

                # Take before snapshot, then enable
                snap_before = self.take_snapshot()
                self.print_snapshot(snap_before, "BEFORE")

                m704.read()
                m704.WSetEna.value = 1
                m704.write()
                time.sleep(0.5)

                # Monitor
                alarms_during = []
                inverter_faulted = False
                elapsed = 0
                check_interval = min(5.0, settle_time / 3)
                while elapsed < settle_time:
                    time.sleep(check_interval)
                    elapsed += check_interval
                    try:
                        mid_snap = self.take_snapshot()
                        self.print_snapshot(mid_snap, f"T+{elapsed:.0f}s")
                        if mid_snap.alarm_names:
                            for a in mid_snap.alarm_names:
                                if a not in alarms_during:
                                    alarms_during.append(a)
                        if mid_snap.inverter_state == 6:
                            inverter_faulted = True
                    except Exception as e:
                        logger.warning(f"  Snapshot error: {e}")

                snap_after = self.take_snapshot()
                self.print_snapshot(snap_after, "AFTER")

                # Read back the specific register
                m704.read()
                val_after = getattr(m704, test['attr']).value

                result = RegisterTestResult(
                    register_name=test['attr'], model_id=test['model'],
                    address=test['addr'], test_value=test['value'],
                    test_description=test['desc'],
                    value_before=0, snapshot_before=asdict(snap_before),
                    value_after_write=val_after,
                    write_accepted=(val_after == test['value']),
                    snapshot_after=asdict(snap_after),
                    dc_power_change_w=snap_after.dc_power_w - snap_before.dc_power_w,
                    grid_power_change_w=snap_after.grid_power_w - snap_before.grid_power_w,
                    alarms_during=alarms_during,
                    inverter_faulted=inverter_faulted,
                    settle_time_s=settle_time,
                )
                results.append(result)

                # Reset
                self.reset_all()
                time.sleep(3)

            else:
                # Simple register write test (no WSetEna needed)
                result = self.test_register_write(
                    model_id=test['model'],
                    attr_name=test['attr'],
                    test_value=test['value'],
                    description=test['desc'],
                    settle_time=settle_time,
                    address=test['addr'],
                )
                results.append(result)
                time.sleep(2)  # Gap between tests

        # ── Summary ──────────────────────────────────────────────────
        accepted = [r for r in results if r.write_accepted]
        rejected = [r for r in results if not r.write_accepted]
        effective = [r for r in accepted if abs(r.dc_power_change_w) > 100 or abs(r.grid_power_change_w) > 100]
        faulted = [r for r in results if r.inverter_faulted]

        summary = {
            "total_tests": len(results),
            "writes_accepted": len(accepted),
            "writes_rejected": len(rejected),
            "effective_on_power": len(effective),
            "caused_fault": len(faulted),
            "accepted_registers": [
                {"name": r.register_name, "model": r.model_id,
                 "value": r.test_value, "dc_change": r.dc_power_change_w,
                 "grid_change": r.grid_power_change_w}
                for r in accepted
            ],
            "rejected_registers": [
                {"name": r.register_name, "model": r.model_id,
                 "value": r.test_value, "notes": r.notes}
                for r in rejected
            ],
            "power_effective_registers": [
                {"name": r.register_name, "model": r.model_id,
                 "value": r.test_value, "dc_change": r.dc_power_change_w,
                 "grid_change": r.grid_power_change_w}
                for r in effective
            ],
        }

        report = TestReport(
            timestamp=datetime.now().isoformat(),
            agate_ip=self.ip,
            rated_max_w=RATED_MAX_W,
            test_power_w=power_w,
            settle_time_s=settle_time,
            solar_present=initial_snap.dc_power_w > 50,
            initial_snapshot=asdict(initial_snap),
            register_tests=[asdict(r) for r in results],
            summary=summary,
        )

        # Print summary
        print("\n" + "=" * 72)
        print("  RESULTS SUMMARY")
        print("=" * 72)
        print(f"  Total tests:        {len(results)}")
        print(f"  Writes accepted:    {len(accepted)}")
        print(f"  Writes rejected:    {len(rejected)}")
        print(f"  Changed power:      {len(effective)}")
        print(f"  Caused fault:       {len(faulted)}")

        if accepted:
            print(f"\n  ✅ ACCEPTED:")
            for r in accepted:
                eff = "→ DC Δ{:+.0f}W, Grid Δ{:+.0f}W".format(
                    r.dc_power_change_w, r.grid_power_change_w)
                print(f"     M{r.model_id}.{r.register_name} = {r.test_value}  {eff}")

        if rejected:
            print(f"\n  ❌ REJECTED:")
            for r in rejected:
                note = f" ({r.notes[0]})" if r.notes else ""
                print(f"     M{r.model_id}.{r.register_name} = {r.test_value}"
                      f" (wrote {r.test_value}, got {r.value_after_write}){note}")

        if effective:
            print(f"\n  ⚡ EFFECTIVE ON POWER:")
            for r in effective:
                print(f"     M{r.model_id}.{r.register_name} = {r.test_value}"
                      f"  → DC Δ{r.dc_power_change_w:+.0f}W, Grid Δ{r.grid_power_change_w:+.0f}W")

        # Save
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(asdict(report), f, indent=2, default=str)
            print(f"\n  📄 Report saved to: {output_file}")

        return report


def main():
    parser = argparse.ArgumentParser(
        description="FranklinWH Systematic Register Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-i", "--ip", required=True, help="aGate IP address")
    parser.add_argument("-p", "--port", type=int, default=502)
    parser.add_argument("-u", "--unit", type=int, default=2)
    parser.add_argument("--power", type=int, default=1500,
                        help="Test power level in watts (default: 1500)")
    parser.add_argument("--settle", type=int, default=15,
                        help="Settle time per test in seconds (default: 15)")
    parser.add_argument("-o", "--output", default=None,
                        help="Output JSON file (default: auto-named)")
    parser.add_argument("-t", "--timeout", type=float, default=10.0)

    args = parser.parse_args()

    if not args.output:
        args.output = f"register_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    tester = RegisterTester(args.ip, args.port, args.timeout)
    if not tester.connect():
        return 1

    try:
        tester.run_full_test(
            power_w=args.power,
            settle_time=args.settle,
            output_file=args.output,
        )
    except KeyboardInterrupt:
        logger.info("Interrupted — resetting...")
        tester.reset_all()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        tester.reset_all()
        raise
    finally:
        tester.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
