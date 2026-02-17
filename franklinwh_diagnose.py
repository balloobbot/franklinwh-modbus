#!/usr/bin/env python3
"""
FranklinWH aGate Diagnostic Utility - Orchestration Monitoring Version
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Import from core module
from franklinwh_core import (
    FranklinWHController,
    BatteryCommand,
    ControlMode,
    HealthStatus,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OpCtlMode(IntEnum):
    """SunSpec Model 715 OpCtl values."""
    NORMAL = 0              
    CHARGE = 1              
    DISCHARGE = 2           
    IDLE = 3                
    MAX_SELF_CONSUMPTION = 4  
    MAX_EXPORT = 5          

@dataclass
class ModeTestResult:
    """Result from single OpCtl mode test."""
    mode: int
    mode_name: str
    settling_time: float
    start_time: str
    end_time: str
    initial_soc: float
    initial_grid_power_w: float
    initial_solar_power_w: Optional[float]
    initial_dc_power_w: Optional[float]
    final_soc: float
    final_grid_power_w: float
    final_solar_power_w: Optional[float]
    final_dc_power_w: Optional[float]
    final_battery_status: str
    wset_watts: float
    wset_mode: str
    wset_ena: int
    power_delta_w: float = field(init=False)
    grid_delta_w: float = field(init=False)
    aborted: bool = False
    abort_reason: Optional[str] = None
    alarms_triggered: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.power_delta_w = self.final_dc_power_w - self.initial_dc_power_w if self.final_dc_power_w is not None and self.initial_dc_power_w is not None else 0
        self.grid_delta_w = self.final_grid_power_w - self.initial_grid_power_w

@dataclass
class DiagnosticReport:
    """Complete diagnostic report."""
    timestamp: str
    aGate_ip: str
    settling_time_s: int
    solar_detected: bool
    health_check: Dict[str, Any]
    mode_results: List[ModeTestResult]
    summary: Dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> Dict[str, Any]: return asdict(self)

class DiagnosticRunner:
    VOLTAGE_MIN, VOLTAGE_MAX = 200.0, 270.0
    SOC_MIN_TEST, SOC_MAX_TEST = 10.0, 98.0
    
    def __init__(self, controller: FranklinWHController):
        self.ctrl = controller
        self.results: List[ModeTestResult] = []
        self.abort_requested = False

    def check_safety(self) -> Tuple[bool, str]:
        grid = self.ctrl.read_grid_status()
        bat = self.ctrl.read_battery_status()
        
        # Franklin Grid Voltage is scaled by 0.1 (e.g., 2422 raw = 242.2V)
        v_raw = grid.get('voltage_v', 0)
        v = v_raw / 10.0 if v_raw > 1000 else v_raw
        
        soc = bat.get('soc', 50)
        
        logger.debug(f"Safety Check -> Voltage: {v}V, SoC: {soc}%")

        if v < self.VOLTAGE_MIN or v > self.VOLTAGE_MAX: 
            return False, f"Voltage {v:.1f}V out of range ({self.VOLTAGE_MIN}-{self.VOLTAGE_MAX})"
        
        if soc < self.SOC_MIN_TEST: 
            return False, f"SoC {soc}% too low for testing"
            
        return True, "Safe"

    def take_snapshot(self) -> Dict[str, Any]:
        return {
            'timestamp': datetime.now().isoformat(),
            'battery': self.ctrl.read_battery_status(),
            'grid': self.ctrl.read_grid_status(),
            'solar': self.ctrl.read_solar_status(),
            'control': self.ctrl.read_control_status(),
            'opctl': self.ctrl.read_opctl_status(),
        }

    def _reconnect(self):
        """Attempt to reconnect the underlying Modbus socket."""
        try:
            self.ctrl.dev.client.connect(self.ctrl.timeout)
            return True
        except Exception as e:
            logger.warning(f"Reconnect failed: {e}")
            return False

    def _safe_snapshot(self, fallback=None):
        """Take a snapshot with reconnection fallback."""
        try:
            return self.take_snapshot()
        except Exception:
            logger.warning("Connection lost, attempting reconnect for snapshot...")
            if self._reconnect():
                try:
                    return self.take_snapshot()
                except Exception as e:
                    logger.error(f"Snapshot failed after reconnect: {e}")
            return fallback or self.take_snapshot()

    def run_mode_test(self, mode: OpCtlMode, settling_time: float, wset_power: float = 0, include_heartbeat: bool = True) -> ModeTestResult:
        mode_name = mode.name.title()
        logger.info(f"\n{'='*60}\nTesting {mode_name} (OpCtl {mode.value})\n{'='*60}")
        
        safe, reason = self.check_safety()
        if not safe: 
            return ModeTestResult(mode=mode.value, mode_name=mode_name, settling_time=0, start_time="", end_time="", initial_soc=0, initial_grid_power_w=0, initial_solar_power_w=0, initial_dc_power_w=0, final_soc=0, final_grid_power_w=0, final_solar_power_w=0, final_dc_power_w=0, final_battery_status="", wset_watts=0, wset_mode="", wset_ena=0, aborted=True, abort_reason=reason)

        initial = self.take_snapshot()
        try:
            if mode in (OpCtlMode.CHARGE, OpCtlMode.DISCHARGE):
                power = abs(wset_power) if mode == OpCtlMode.CHARGE else -abs(wset_power)
                cmd = BatteryCommand(power_watts=power)
                # Disable threaded heartbeat — we send heartbeats inline below
                # to avoid thread-unsafe concurrent socket access (Broken pipe)
                success, msg = self.ctrl.send_command(cmd, heartbeat_interval=0)
                if not success:
                    logger.error(f"Command Rejected: {msg}")
            else:
                m715 = self.ctrl.get_model(715)
                if m715:
                    m715.read(); m715.OpCtl.value = mode.value; m715.write()

            # Active Monitoring Loop with inline heartbeat
            start_loop = time.time()
            hb_count = 0
            while time.time() - start_loop < settling_time:
                # Inline heartbeat (serialized with reads to avoid socket conflicts)
                if include_heartbeat and mode in (OpCtlMode.CHARGE, OpCtlMode.DISCHARGE):
                    hb_count = (hb_count + 1) % 10000
                    m715 = self.ctrl.get_model(715)
                    if m715:
                        try:
                            m715.ControllerHb.value = hb_count
                            m715.write()
                        except Exception:
                            pass

                grid = self.ctrl.read_grid_status()
                op = self.ctrl.read_opctl_status()
                ctrl = self.ctrl.read_control_status()
                bat = self.ctrl.read_battery_status()
                
                if grid.get('alarms'):
                    logger.warning(f"  ALARM: {grid['alarms']}")

                logger.info(f"  Orch -> SoC:{bat['soc']}% | OpCtl:{op.get('opctl')} | Hb:{op.get('controller_hb')} | WSetEna:{ctrl.get('wset_ena')} | Grid:{grid.get('grid_power_w')}W")
                
                time.sleep(10)

        except Exception as e: 
            logger.error(f"Test execution error: {e}")
        
        final = self._safe_snapshot(fallback=initial)
        return ModeTestResult(
            mode=mode.value, mode_name=mode_name, settling_time=settling_time,
            start_time=initial['timestamp'], end_time=final['timestamp'],
            initial_soc=initial['battery'].get('soc', 0), initial_grid_power_w=initial['grid'].get('grid_power_w', 0),
            initial_solar_power_w=initial['solar'].get('ac_power_w', 0), initial_dc_power_w=initial['solar'].get('dc_power_w', 0),
            final_soc=final['battery'].get('soc', 0), final_grid_power_w=final['grid'].get('grid_power_w', 0),
            final_solar_power_w=final['solar'].get('ac_power_w', 0), final_dc_power_w=final['solar'].get('dc_power_w', 0),
            final_battery_status=final['battery'].get('status_name', ''),
            wset_watts=final['control'].get('wset_watts', 0), wset_mode=str(final['control'].get('wset_mode')), wset_ena=final['control'].get('wset_ena', 0)
        )

    def run_diagnostic(self, settling_time: int = 60, include_discharge: bool = False, wset_power: float = 2000) -> DiagnosticReport:
        health = self.ctrl.healthcheck()
        modes = [OpCtlMode.NORMAL, OpCtlMode.CHARGE]
        if include_discharge: modes.append(OpCtlMode.DISCHARGE)
        
        results = []
        for mode in modes:
            results.append(self.run_mode_test(mode, settling_time, wset_power))
            self.ctrl.reset_control_state()
            time.sleep(5)
            
        return DiagnosticReport(datetime.now().isoformat(), self.ctrl.ip_address, settling_time, True, health.__dict__, results)

def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--ip', required=True)
    parser.add_argument('-u', '--unit', type=int, default=2)
    parser.add_argument('-t', '--timeout', type=float, default=10.0, help='Modbus timeout in seconds (default: 10)')
    parser.add_argument('-s', '--settling', type=int, default=60)
    parser.add_argument('--wset-power', type=float, default=1500)
    parser.add_argument('--include-discharge', action='store_true')
    return parser

def main():
    args = create_parser().parse_args()
    ctrl = FranklinWHController(args.ip, unit_id=args.unit, timeout=args.timeout)
    if not ctrl.connect(): sys.exit(1)
    
    try:
        runner = DiagnosticRunner(ctrl)
        report = runner.run_diagnostic(settling_time=args.settling, include_discharge=args.include_discharge, wset_power=args.wset_power)
        print("\n" + "="*70 + "\nFINAL REPORT SUMMARY\n" + "="*70)
        print(json.dumps(report.to_dict(), indent=2, default=str))
    finally:
        ctrl.reset_control_state()
        ctrl.disconnect()

if __name__ == '__main__':
    main()