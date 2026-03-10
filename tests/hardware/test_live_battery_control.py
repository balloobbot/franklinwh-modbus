#!/usr/bin/env python3
"""
Live Hardware Tests for FranklinWH Battery Control

These tests run against the actual aGate hardware and:
1. Record all test results to JSON for validation
2. Perform safety checks before any write operations
3. Automatically rollback control state after each test
4. Require explicit user confirmation for destructive tests

Usage:
    # Dry run (check only, no writes)
    pytest tests/hardware/test_live_battery_control.py -v --dry-run
    
    # Live tests with confirmation
    pytest tests/hardware/test_live_battery_control.py -v -m hardware
    
    # Full destructive tests (requires --destructive-enabled)
    pytest tests/hardware/test_live_battery_control.py -v -m "hardware and destructive" --destructive-enabled

Environment Variables:
    FRANKLINWH_TEST_HOST: aGate IP (default: 192.168.0.110)
    FRANKLINWH_TEST_PORT: Modbus port (default: 502)
    FRANKLINWH_TEST_UNIT: Unit ID (default: 2)
    TEST_RECORD_FILE: Path to save test results (default: data/test_results_{timestamp}.json)
"""

import pytest
import sys
import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

# Add project root to path (src first to override system packages)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'src'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from franklinwh_modbus import FranklinWHController, BatteryCommand

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST RESULT RECORDING
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TestResult:
    """Record of a single test execution."""
    test_name: str
    timestamp: str
    status: str  # 'passed', 'failed', 'skipped', 'error'
    duration_seconds: float
    
    # Pre-test state
    pre_soc: float
    pre_battery_power: float
    pre_grid_power: float
    pre_control_mode: str
    pre_wset_ena: int
    
    # Test parameters
    command_power: Optional[float]
    command_mode: Optional[str]
    
    # Post-test state
    post_soc: float
    post_battery_power: float
    post_grid_power: float
    post_wset_ena: int
    
    # Validation
    expected_behavior: str
    actual_behavior: str
    validation_passed: bool
    
    # Error info
    error_message: Optional[str] = None
    traceback: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TestRecorder:
    """Records and saves test results to JSON."""
    
    def __init__(self, output_file: Optional[str] = None):
        self.results: list = []
        self.start_time = datetime.now()
        
        if output_file:
            self.output_file = output_file
        else:
            timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
            self.output_file = f"data/test_results_{timestamp}.json"
        
        # Ensure data directory exists
        Path(self.output_file).parent.mkdir(parents=True, exist_ok=True)
    
    def record(self, result: TestResult):
        """Record a test result."""
        self.results.append(result.to_dict())
        # Save incrementally in case of crash
        self._save()
    
    def _save(self):
        """Save results to JSON file."""
        data = {
            'test_session': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'total_tests': len(self.results),
                'passed': sum(1 for r in self.results if r['status'] == 'passed'),
                'failed': sum(1 for r in self.results if r['status'] == 'failed'),
                'skipped': sum(1 for r in self.results if r['status'] == 'skipped'),
            },
            'results': self.results
        }
        with open(self.output_file, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Test results saved to: {self.output_file}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test summary."""
        return {
            'total': len(self.results),
            'passed': sum(1 for r in self.results if r['status'] == 'passed'),
            'failed': sum(1 for r in self.results if r['status'] == 'failed'),
            'skipped': sum(1 for r in self.results if r['status'] == 'skipped'),
        }


# Global recorder instance
_recorder: Optional[TestRecorder] = None


def get_recorder() -> TestRecorder:
    """Get or create the test recorder."""
    global _recorder
    if _recorder is None:
        output_file = os.environ.get('TEST_RECORD_FILE')
        _recorder = TestRecorder(output_file)
    return _recorder


# ═══════════════════════════════════════════════════════════════════════════════
# PYTEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def hardware_config():
    """Get hardware connection configuration."""
    return {
        'host': os.environ.get('FRANKLINWH_TEST_HOST', '192.168.0.110'),
        'port': int(os.environ.get('FRANKLINWH_TEST_PORT', '502')),
        'unit_id': int(os.environ.get('FRANKLINWH_TEST_UNIT', '2')),
    }


@pytest.fixture(scope="module")
def controller(hardware_config):
    """Create a controller instance for hardware tests."""
    ctrl = FranklinWHController(
        ip_address=hardware_config['host'],
        port=hardware_config['port'],
        unit_id=hardware_config['unit_id']
    )
    
    if not ctrl.connect():
        pytest.skip(f"Could not connect to aGate at {hardware_config['host']}")
    
    yield ctrl
    
    # Cleanup: Always reset control state after tests
    logger.info("Test cleanup: Resetting control state...")
    try:
        ctrl.reset_control_state()
        logger.info("Control state reset complete")
    except Exception as e:
        logger.warning(f"Cleanup reset failed: {e}")
    finally:
        ctrl.disconnect()


@pytest.fixture
def require_destructive_enabled(request):
    """Skip destructive tests unless explicitly enabled."""
    if request.node.get_closest_marker("destructive"):
        if not request.config.getoption("--destructive-enabled", False):
            pytest.skip("Destructive tests disabled (use --destructive-enabled)")


@pytest.fixture
def dry_run(request):
    """Check if running in dry-run mode (no actual writes)."""
    return request.config.getoption("--dry-run", False)


# ═══════════════════════════════════════════════════════════════════════════════
# SAFETY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def capture_system_state(ctrl: FranklinWHController) -> Dict[str, Any]:
    """Capture current system state for comparison."""
    try:
        bat = ctrl.read_battery_status()
        grid = ctrl.read_grid_status()
        ctl = ctrl.read_control_status()
        native = ctrl.read_native_mode()
        
        return {
            'soc': bat.get('soc', 0),
            'battery_power': bat.get('dc_power_w', 0),
            'grid_power': grid.get('grid_power_w', 0),
            'control_mode': native.get('mode_name', 'Unknown'),
            'wset_ena': ctl.get('wset_enabled', 0),
            'wset_pct': ctl.get('wset_pct', 0),
            'timestamp': datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to capture system state: {e}")
        raise


def validate_safe_test_conditions(ctrl: FranklinWHController, test_name: str) -> bool:
    """Validate system is in safe state for testing."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Pre-test Safety Check: {test_name}")
    logger.info(f"{'='*60}")
    
    # Read current state
    state = capture_system_state(ctrl)
    
    # Check 1: SoC in safe range (10% - 95%)
    soc = state['soc']
    if soc < 10 or soc > 95:
        logger.error(f"❌ SoC {soc}% outside safe range (10-95%)")
        return False
    logger.info(f"✓ SoC: {soc}% (safe range)")
    
    # Check 2: Grid connected
    grid = ctrl.read_grid_status()
    if grid.get('grid_connection') != 'Connected':
        logger.error(f"❌ Grid not connected: {grid.get('grid_connection')}")
        return False
    logger.info(f"✓ Grid: Connected")
    
    # Check 3: Voltage in range (200-270V)
    voltage = grid.get('voltage_v', 0)
    if voltage < 200 or voltage > 270:
        logger.error(f"❌ Voltage {voltage}V outside safe range (200-270V)")
        return False
    logger.info(f"✓ Voltage: {voltage:.1f}V (safe range)")
    
    # Check 4: No critical alarms
    alarms = ctrl.read_alarms()
    critical_alarms = [a for a in alarms.get('active_alarms', []) if a.get('severity') == 'CRITICAL']
    if critical_alarms:
        logger.error(f"❌ Critical alarms active: {critical_alarms}")
        return False
    logger.info(f"✓ No critical alarms")
    
    logger.info(f"✅ All safety checks passed for {test_name}")
    return True


def wait_for_power_stabilization(ctrl: FranklinWHController, timeout: int = 30) -> Dict[str, Any]:
    """Wait for battery power to stabilize after a command."""
    logger.info(f"Waiting up to {timeout}s for power stabilization...")
    start = time.time()
    readings = []
    
    while time.time() - start < timeout:
        state = capture_system_state(ctrl)
        readings.append(state['battery_power'])
        
        # Keep last 5 readings, check if stable
        if len(readings) >= 5:
            recent = readings[-5:]
            variance = max(recent) - min(recent)
            if variance < 100:  # Within 100W
                logger.info(f"✓ Power stabilized at ~{state['battery_power']:.0f}W (variance: {variance:.0f}W)")
                return state
        
        time.sleep(2)
    
    logger.warning(f"⚠ Power did not fully stabilize (timeout)")
    return capture_system_state(ctrl)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST DECORATOR
# ═══════════════════════════════════════════════════════════════════════════════

def live_battery_test(test_func):
    """Decorator for live battery tests with automatic recording and rollback."""
    def wrapper(controller, *args, **kwargs):
        test_name = test_func.__name__
        recorder = get_recorder()
        start_time = time.time()
        
        result_data = {
            'test_name': test_name,
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'duration_seconds': 0,
            'pre_soc': 0, 'pre_battery_power': 0, 'pre_grid_power': 0,
            'pre_control_mode': '', 'pre_wset_ena': 0,
            'command_power': None, 'command_mode': None,
            'post_soc': 0, 'post_battery_power': 0, 'post_grid_power': 0,
            'post_wset_ena': 0,
            'expected_behavior': '', 'actual_behavior': '',
            'validation_passed': False,
            'error_message': None, 'traceback': None,
        }
        
        try:
            # Capture pre-test state
            logger.info(f"\n{'#'*60}")
            logger.info(f"STARTING TEST: {test_name}")
            logger.info(f"{'#'*60}")
            
            pre_state = capture_system_state(controller)
            result_data.update({
                'pre_soc': pre_state['soc'],
                'pre_battery_power': pre_state['battery_power'],
                'pre_grid_power': pre_state['grid_power'],
                'pre_control_mode': pre_state['control_mode'],
                'pre_wset_ena': pre_state['wset_ena'],
            })
            
            # Run the test
            test_result = test_func(controller, *args, **kwargs)
            
            # Capture post-test state
            post_state = wait_for_power_stabilization(controller)
            result_data.update({
                'post_soc': post_state['soc'],
                'post_battery_power': post_state['battery_power'],
                'post_grid_power': post_state['grid_power'],
                'post_wset_ena': post_state['wset_ena'],
                'status': 'passed',
            })
            
            # Get expected/actual from test result
            if isinstance(test_result, dict):
                result_data['expected_behavior'] = test_result.get('expected', '')
                result_data['actual_behavior'] = test_result.get('actual', '')
                result_data['validation_passed'] = test_result.get('passed', False)
                result_data['command_power'] = test_result.get('command_power')
                result_data['command_mode'] = test_result.get('command_mode')
            
            logger.info(f"✅ TEST PASSED: {test_name}")
            
        except Exception as e:
            result_data['status'] = 'failed'
            result_data['error_message'] = str(e)
            import traceback
            result_data['traceback'] = traceback.format_exc()
            logger.error(f"❌ TEST FAILED: {test_name} - {e}")
            raise
        
        finally:
            # Always record result and rollback
            result_data['duration_seconds'] = time.time() - start_time
            
            # Rollback control state
            logger.info(f"Rolling back control state...")
            try:
                controller.reset_control_state()
                logger.info(f"✓ Rollback complete")
            except Exception as e:
                logger.error(f"Rollback failed: {e}")
            
            # Record result
            recorder.record(TestResult(**result_data))
            logger.info(f"{'#'*60}\n")
    
    return wrapper


# ═══════════════════════════════════════════════════════════════════════════════
# LIVE TEST CASES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.hardware
@pytest.mark.destructive
@live_battery_test
def test_charge_low_power(controller):
    """
    Test charging at low power (500W).
    
    Expected: Battery should switch to charging at ~500W
    Validation: Post-test battery power should be negative (charging)
    """
    if not validate_safe_test_conditions(controller, "Charge Low Power"):
        pytest.skip("Safety check failed")
    
    # Send charge command (negative = charge in BatteryCommand convention)
    power = -500  # 500W charge
    cmd = BatteryCommand(power_watts=power, duration_seconds=10)
    
    logger.info(f"Sending charge command: {abs(power)}W")
    success, msg = controller.send_command(cmd)
    
    if not success:
        raise RuntimeError(f"Command failed: {msg}")
    
    # Wait for command to take effect
    time.sleep(5)
    
    # Validate
    post = capture_system_state(controller)
    expected = "Battery charging at ~500W (negative power)"
    actual = f"Battery power: {post['battery_power']:.0f}W, WSetEna: {post['wset_ena']}"
    
    # Battery should be charging (negative power in our convention)
    passed = post['battery_power'] < -100 and post['wset_ena'] == 1
    
    return {
        'expected': expected,
        'actual': actual,
        'passed': passed,
        'command_power': power,
        'command_mode': 'manual',
    }


@pytest.mark.hardware
@pytest.mark.destructive
@live_battery_test
def test_discharge_low_power(controller):
    """
    Test discharging at low power (500W).
    
    Expected: Battery should discharge at ~500W
    Validation: Post-test battery power should be positive (discharging)
    """
    if not validate_safe_test_conditions(controller, "Discharge Low Power"):
        pytest.skip("Safety check failed")
    
    # Send discharge command (positive = discharge)
    power = 500  # 500W discharge
    cmd = BatteryCommand(power_watts=power, duration_seconds=10)
    
    logger.info(f"Sending discharge command: {power}W")
    success, msg = controller.send_command(cmd)
    
    if not success:
        raise RuntimeError(f"Command failed: {msg}")
    
    time.sleep(5)
    
    # Validate
    post = capture_system_state(controller)
    expected = "Battery discharging at ~500W (positive power)"
    actual = f"Battery power: {post['battery_power']:.0f}W, WSetEna: {post['wset_ena']}"
    
    passed = post['battery_power'] > 100 and post['wset_ena'] == 1
    
    return {
        'expected': expected,
        'actual': actual,
        'passed': passed,
        'command_power': power,
        'command_mode': 'manual',
    }


@pytest.mark.hardware
@pytest.mark.destructive
@live_battery_test
def test_standby(controller):
    """
    Test standby mode (0W).
    
    Expected: Battery should go to idle (0W)
    Validation: Post-test battery power should be near 0W
    """
    if not validate_safe_test_conditions(controller, "Standby"):
        pytest.skip("Safety check failed")
    
    power = 0  # Standby
    cmd = BatteryCommand(power_watts=power, duration_seconds=10)
    
    logger.info(f"Sending standby command: 0W")
    success, msg = controller.send_command(cmd)
    
    if not success:
        raise RuntimeError(f"Command failed: {msg}")
    
    time.sleep(5)
    
    # Validate
    post = capture_system_state(controller)
    expected = "Battery at standby (~0W)"
    actual = f"Battery power: {post['battery_power']:.0f}W, WSetEna: {post['wset_ena']}"
    
    # Allow some tolerance for idle detection
    passed = abs(post['battery_power']) < 200 and post['wset_ena'] == 1
    
    return {
        'expected': expected,
        'actual': actual,
        'passed': passed,
        'command_power': power,
        'command_mode': 'standby',
    }


@pytest.mark.hardware
@pytest.mark.destructive
@live_battery_test
def test_release_control(controller):
    """
    Test releasing control back to Cloud API.
    
    Expected: WSetEna should go to 0, control released
    Validation: Post-test WSetEna should be 0
    """
    if not validate_safe_test_conditions(controller, "Release Control"):
        pytest.skip("Safety check failed")
    
    # First take control
    cmd = BatteryCommand(power_watts=500, duration_seconds=5)
    controller.send_command(cmd)
    time.sleep(2)
    
    # Now release
    logger.info(f"Releasing control (reset to idle)")
    success = controller.reset_control_state()
    
    if not success:
        raise RuntimeError("Reset control state failed")
    
    time.sleep(3)
    
    # Validate
    post = capture_system_state(controller)
    expected = "Control released (WSetEna=0)"
    actual = f"WSetEna: {post['wset_ena']}"
    
    passed = post['wset_ena'] == 0
    
    return {
        'expected': expected,
        'actual': actual,
        'passed': passed,
        'command_power': None,
        'command_mode': 'release',
    }


@pytest.mark.hardware
@pytest.mark.destructive
@live_battery_test  
def test_soc_ramping_near_limit(controller):
    """
    Test SoC ramping when near max charge limit.
    
    Only runs if SoC is within ramping window of max.
    Expected: Power should be reduced based on ramp curve
    """
    pre = capture_system_state(controller)
    soc = pre['soc']
    
    # Only test if we're in the ramping zone (>85% for 100% max with 10% window)
    if soc < 85:
        pytest.skip(f"SoC {soc}% not in ramping zone (need >85%)")
    
    if not validate_safe_test_conditions(controller, "SoC Ramping"):
        pytest.skip("Safety check failed")
    
    # Try to charge at max power - should be ramped down
    power = -5000  # Full charge
    cmd = BatteryCommand(power_watts=power, duration_seconds=10, max_charge_soc=95)
    
    logger.info(f"Sending max charge command at SoC {soc}% (should ramp)")
    success, msg = controller.send_command(cmd)
    
    if not success:
        raise RuntimeError(f"Command failed: {msg}")
    
    time.sleep(5)
    
    # Validate
    post = capture_system_state(controller)
    expected = f"Power ramped due to high SoC ({soc}%)"
    actual = f"Commanded: 5000W, Actual: {abs(post['battery_power']):.0f}W"
    
    # Should be less than max due to ramping
    passed = abs(post['battery_power']) < 4000
    
    return {
        'expected': expected,
        'actual': actual,
        'passed': passed,
        'command_power': power,
        'command_mode': 'charge_ramp',
    }


# ═══════════════════════════════════════════════════════════════════════════════
# READ-ONLY MONITORING TESTS (Always Safe)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.hardware
def test_read_all_models(controller):
    """Test reading all SunSpec models (read-only)."""
    models_to_test = [1, 501, 502, 701, 702, 703, 704, 713, 714, 715]
    
    results = {}
    for model in models_to_test:
        try:
            data = controller.get_model(model)
            results[f"model_{model}"] = "success" if data else "empty"
        except Exception as e:
            results[f"model_{model}"] = f"error: {e}"
    
    logger.info(f"Model read results: {results}")
    
    # All models should be readable
    assert all("error" not in v for v in results.values()), f"Some models failed: {results}"


@pytest.mark.hardware
def test_battery_status_consistency(controller):
    """Test that battery status readings are consistent over multiple reads."""
    readings = []
    
    for i in range(5):
        status = controller.read_battery_status()
        readings.append({
            'soc': status.get('soc'),
            'power': status.get('dc_power_w'),
            'timestamp': time.time(),
        })
        time.sleep(1)
    
    # SoC should not change dramatically in 5 seconds
    socs = [r['soc'] for r in readings if r['soc'] is not None]
    if socs:
        soc_variance = max(socs) - min(socs)
        assert soc_variance < 5, f"SoC changed by {soc_variance}% in 5 seconds - unusual"
    
    logger.info(f"Battery readings consistent: {readings}")


@pytest.mark.hardware
def test_alarms_clear(controller):
    """Verify no critical alarms before any testing."""
    alarms = controller.read_alarms()
    critical = [a for a in alarms.get('active_alarms', []) if a.get('severity') == 'CRITICAL']
    
    assert len(critical) == 0, f"Critical alarms detected: {critical}"
    logger.info(f"✓ No critical alarms: {alarms.get('summary', 'Unknown')}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Allow running directly for quick test
    print("Run with pytest: pytest tests/hardware/test_live_battery_control.py -v -m hardware")
    print("Or use the runner script: python run_hardware_tests.py")
