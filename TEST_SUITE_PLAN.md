# FranklinWH Battery Manager - Comprehensive Test Suite Plan

> **Status**: Draft - For review and implementation  
> **Target**: `franklinwh_control_standalone.py` → split into `franklinwh_modbus_library.py` + `franklinwh_modbus_cli.py`  
> **Date**: 2026-02-21

---

## Executive Summary

This test suite plan addresses the critical need for **systematic testing** of the FranklinWH battery control library. Current testing relies on ad-hoc scripts and manual validation against hardware. This plan establishes a **pytest-based** testing framework with clear separation between:

1. **Unit Tests** - Pure logic, no hardware dependencies
2. **Integration Tests** - With mocked Modbus responses
3. **Hardware Tests** - Against real aGate (optional, marked)
4. **CLI Tests** - Command-line interface validation

---

## 1. Current State Analysis

### Existing Test Files (Ad-hoc)

| File | Purpose | Status | Issue |
|------|---------|--------|-------|
| `test_battery_control.py` | Battery control testing with rollback | Works | Not pytest, standalone script |
| `test_register_writability.py` | Safe register writability tester | Works | Standalone, not integrated |
| `test_battery_control.sh` | Shell-based battery control tests | Works | Requires manual intervention |
| `connect_test.py` | Raw + SunSpec connection tests | Works | Ad-hoc, no assertions |
| `quicktest.py` | Quick raw Modbus test | Works | Hardcoded, not reusable |
| `vpp_test.py` | VPP mode testing | Partial | Incomplete |

### What's Missing

- ❌ No pytest framework
- ❌ No automated test discovery
- ❌ No CI/CD integration
- ❌ No mocking for Modbus hardware
- ❌ No coverage reporting
- ❌ No test categorization (unit vs integration vs hardware)

---

## 2. Proposed Test Architecture

```
tests/
├── conftest.py                 # pytest fixtures and configuration
├── unit/                       # Pure unit tests (fast, no I/O)
│   ├── test_models.py          # Data model tests
│   ├── test_calculations.py    # Power calculation tests
│   ├── test_tou_schedule.py    # TOU schedule logic tests
│   └── test_safety.py          # Safety clamp/validation tests
├── integration/                # Integration tests (mocked Modbus)
│   ├── test_controller_mock.py # FranklinWHController with mocks
│   ├── test_virtual_modes.py   # Virtual mode controller tests
│   └── test_cli.py             # CLI argument parsing tests
├── hardware/                   # Hardware tests (requires aGate)
│   ├── test_connection.py      # Real connection tests
│   ├── test_read_operations.py # Safe read-only tests
│   └── test_write_operations.py # Destructive write tests (marked)
└── fixtures/                   # Test data and mock responses
    ├── mock_sunspec.py         # Mock SunSpec model responses
    ├── mock_registers.py       # Mock register values
    └── sample_configs.py       # Sample configurations
```

---

## 3. Test Categories

### 3.1 Unit Tests (pytest markers: `unit`)

**Fast, deterministic, no external dependencies**

#### `test_models.py`
```python
# Test data classes in src/models.py
def test_battery_metrics_defaults():
    """BatteryMetrics dataclass initializes correctly."""
    
def test_battery_mode_enum():
    """BatteryMode enum values are correct."""
    
def test_inverter_status_mapping():
    """Inverter status codes map to correct text."""
```

#### `test_calculations.py`
```python
# Test power calculation logic
def test_self_consumption_calculation():
    """Self-consumption mode calculates correct power."""
    
def test_emergency_backup_calculation():
    """Emergency backup respects target SoC."""
    
def test_time_of_use_arbitrage():
    """TOU mode charges/discharges based on price."""
    
def test_grid_zero_tolerance():
    """Grid zero mode respects buffer tolerance."""
```

#### `test_tou_schedule.py`
```python
# Test TOUSchedule class
def test_tou_period_detection():
    """Correctly identifies peak/shoulder/off-peak hours."""
    
def test_tou_price_lookup():
    """Returns correct price for current period."""
    
def test_tou_custom_schedule():
    """Custom hour ranges work correctly."""
```

#### `test_safety.py`
```python
# Test safety mechanisms
def test_power_clamp_charge_limit():
    """Power clamped to max charge rating."""
    
def test_power_clamp_discharge_limit():
    """Power clamped to max discharge rating."""
    
def test_soc_safety_bounds():
    """Operations blocked outside safe SoC range."""
    
def test_grid_voltage_safety():
    """Operations blocked outside voltage limits."""
```

### 3.2 Integration Tests (pytest markers: `integration`)

**Uses mocked Modbus responses, no hardware required**

#### `test_controller_mock.py`
```python
# Test FranklinWHController with mocked SunSpec
def test_controller_connect_success(mock_device):
    """Connect succeeds with valid device."""
    
def test_controller_connect_failure():
    """Connect fails gracefully with timeout."""
    
def test_read_battery_status(mock_model_713):
    """Battery status parsed correctly from Model 713."""
    
def test_read_grid_status(mock_model_701):
    """Grid status parsed correctly from Model 701."""
    
def test_read_control_status(mock_model_704):
    """Control status parsed correctly from Model 704."""
    
def test_send_command_sequence(mock_model_704):
    """Command follows correct 4-step sequence."""
    
def test_healthcheck_pass(mock_models):
    """Healthcheck passes with valid state."""
    
def test_healthcheck_zombie_state(mock_model_704_zombie):
    """Healthcheck detects zombie state."""
    
def test_reset_control_state(mock_model_704):
    """Reset clears all control registers."""
```

#### `test_virtual_modes.py`
```python
# Test VirtualModeController with mocked controller
def test_mode_self_consumption(mock_status):
    """Self-consumption mode with excess solar."""
    
def test_mode_emergency_backup_low_soc(mock_status_low_soc):
    """Emergency backup charges when below target."""
    
def test_mode_time_of_use_peak(mock_status_peak_period):
    """TOU discharges during peak pricing."""
    
def test_mode_grid_zero_exporting(mock_status_exporting):
    """Grid zero reduces export."""
    
def test_mode_manual_power(mock_status):
    """Manual mode applies requested power."""
    
def test_emergency_idle_on_exit(mock_controller):
    """Emergency idle called on unexpected exit."""
```

#### `test_cli.py`
```python
# Test CLI argument parsing
def test_cli_status_command():
    """Status command parsed correctly."""
    
def test_cli_power_command():
    """Power command with valid wattage."""
    
def test_cli_mode_command():
    """Mode command with valid mode."""
    
def test_cli_healthcheck_command():
    """Healthcheck command parsed."""
    
def test_cli_invalid_power():
    """Invalid power value rejected."""
    
def test_cli_invalid_mode():
    """Invalid mode rejected."""
```

### 3.3 Hardware Tests (pytest markers: `hardware`, `destructive`)

**Requires real aGate connection - marked to skip by default**

#### `test_connection.py`
```python
# Real connection tests (safe, read-only)
@pytest.mark.hardware
def test_real_connection():
    """Connect to real aGate device."""
    
@pytest.mark.hardware
def test_model_discovery():
    """Discover available SunSpec models."""
    
@pytest.mark.hardware
def test_extension_registers():
    """Read FranklinWH extension registers."""
```

#### `test_read_operations.py`
```python
# Safe read-only tests against hardware
@pytest.mark.hardware
def test_read_battery_metrics():
    """Read actual battery metrics."""
    
@pytest.mark.hardware
def test_read_grid_metrics():
    """Read actual grid metrics."""
    
@pytest.mark.hardware
def test_healthcheck_live():
    """Run healthcheck against live system."""
```

#### `test_write_operations.py`
```python
# Destructive write tests - require explicit enable
@pytest.mark.hardware
@pytest.mark.destructive
def test_write_enable_disable():
    """Test WSetEna enable/disable cycle."""
    
@pytest.mark.hardware
@pytest.mark.destructive
def test_write_power_command():
    """Send actual power command."""
    
@pytest.mark.hardware
@pytest.mark.destructive
def test_write_reset_state():
    """Reset control state on hardware."""
```

---

## 4. Test Fixtures (`conftest.py`)

```python
# Shared fixtures for all tests

@pytest.fixture
def mock_model_704():
    """Mock SunSpec Model 704 with standard values."""
    
@pytest.fixture
def mock_model_713():
    """Mock SunSpec Model 713 with battery data."""
    
@pytest.fixture
def mock_model_701():
    """Mock SunSpec Model 701 with grid data."""
    
@pytest.fixture
def mock_controller(mock_models):
    """FranklinWHController with mocked device."""
    
@pytest.fixture
def tou_schedule():
    """Standard TOU schedule for testing."""
    
@pytest.fixture(scope="session")
def hardware_config():
    """Hardware connection config (from env or file)."""
    # Skip if not configured
    # Read from tests/hardware_config.yaml or env vars
```

---

## 5. Implementation Roadmap

### Phase 1: Foundation (Week 1)

1. **Setup pytest infrastructure**
   ```bash
   pip install pytest pytest-asyncio pytest-mock pytest-cov
   ```

2. **Create test directory structure**
   ```bash
   mkdir -p tests/unit tests/integration tests/hardware tests/fixtures
   touch tests/conftest.py
   touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
   ```

3. **Add pytest configuration** (`pyproject.toml`)
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   python_files = ["test_*.py"]
   python_classes = ["Test*"]
   python_functions = ["test_*"]
   markers = [
       "unit: Unit tests (fast, no I/O)",
       "integration: Integration tests (mocked)",
       "hardware: Requires real hardware",
       "destructive: Modifies hardware state",
   ]
   addopts = "-v --tb=short --strict-markers"
   ```

4. **Implement mock fixtures**
   - Mock SunSpec models (704, 713, 701, 714, 715)
   - Mock register responses
   - Mock controller instance

### Phase 2: Unit Tests (Week 1-2)

1. `test_models.py` - Data model validation
2. `test_calculations.py` - Power calculation logic
3. `test_tou_schedule.py` - TOU schedule logic
4. `test_safety.py` - Safety mechanisms

**Goal**: 80%+ coverage of pure logic code

### Phase 3: Integration Tests (Week 2-3)

1. `test_controller_mock.py` - Controller with mocks
2. `test_virtual_modes.py` - Virtual mode logic
3. `test_cli.py` - CLI argument parsing

**Goal**: Test all code paths without hardware

### Phase 4: Hardware Tests (Week 3-4)

1. `test_connection.py` - Connection validation
2. `test_read_operations.py` - Read-only tests
3. `test_write_operations.py` - Write tests (destructive)

**Goal**: Validate against real aGate when available

### Phase 5: CI/CD Integration (Week 4)

1. GitHub Actions workflow
2. Coverage reporting (codecov)
3. Pre-commit hooks
4. Test badges in README

---

## 6. Running the Tests

### Default (Unit + Integration only)
```bash
pytest
# or explicitly
pytest -m "unit or integration"
```

### With Coverage
```bash
pytest --cov=src --cov-report=html --cov-report=term
```

### Hardware Tests (requires aGate)
```bash
# Set hardware config
export FRANKLINWH_TEST_HOST=192.168.0.110
export FRANKLINWH_TEST_UNIT=2

# Run hardware tests only
pytest -m hardware

# Run all tests including destructive
pytest -m "hardware or destructive" --destructive-enabled
```

### Specific Test Files
```bash
pytest tests/unit/test_calculations.py -v
pytest tests/integration/test_controller_mock.py::test_send_command_sequence -v
```

---

## 7. Code Split Testing Strategy

When splitting `franklinwh_control_standalone.py`:

### Current: Monolithic Script
```
franklinwh_control_standalone.py (26K lines)
├── FranklinWHController
├── VirtualModeController
├── CLI main()
└── All logic mixed together
```

### Target: Library + CLI
```
franklinwh_modbus_library.py (library)
├── FranklinWHController
├── VirtualModeController
├── TOUSchedule
├── HealthStatus
└── __all__ exports

franklinwh_modbus_cli.py (CLI tool)
├── argparse setup
├── main()
└── imports from library
```

### Testing Each Component

| Component | Test File | Type |
|-----------|-----------|------|
| `FranklinWHController` | `test_controller_*.py` | Unit (mocked) + Hardware |
| `VirtualModeController` | `test_virtual_modes.py` | Integration (mocked) |
| `TOUSchedule` | `test_tou_schedule.py` | Unit |
| `HealthStatus` | `test_healthcheck.py` | Integration |
| CLI arguments | `test_cli.py` | Unit |
| CLI main flow | `test_cli_integration.py` | Integration |

---

## 8. Safety Considerations

### Test Isolation
- Each test gets fresh mock instances
- No shared state between tests
- Hardware tests require explicit environment variables

### Destructive Test Protection
```python
@pytest.fixture
def require_destructive_enabled(request):
    """Skip destructive tests unless explicitly enabled."""
    if request.node.get_closest_marker("destructive"):
        if not request.config.getoption("--destructive-enabled"):
            pytest.skip("Destructive tests disabled (use --destructive-enabled)")
```

### Hardware Test Requirements
```python
@pytest.fixture(scope="session")
def hardware_available():
    """Check if hardware is available for testing."""
    host = os.environ.get("FRANKLINWH_TEST_HOST")
    if not host:
        pytest.skip("Hardware tests disabled (set FRANKLINWH_TEST_HOST)")
    # Try to ping/connect
    if not ping_host(host):
        pytest.skip(f"Hardware not reachable at {host}")
```

---

## 9. Expected Outcomes

### Immediate Benefits
1. **Confidence in refactoring** - Tests catch regressions during library split
2. **Documentation** - Tests serve as usage examples
3. **Faster development** - No need for hardware to test logic changes

### Long-term Benefits
1. **CI/CD safety net** - Auto-run on every commit
2. **Contributor onboarding** - New devs can run tests without hardware
3. **Regression detection** - Catch bugs before release

### Metrics
- **Unit test coverage**: Target 90%+
- **Integration test coverage**: Target 80%+
- **Test execution time**: < 30 seconds (unit + integration)
- **Hardware test execution**: < 5 minutes

---

## 10. Next Steps

1. **Review this plan** - Discuss scope and priorities
2. **Setup pytest** - Install and configure
3. **Create first unit test** - `test_models.py` as template
4. **Implement mock fixtures** - Enable integration tests
5. **Migrate existing tests** - Convert ad-hoc scripts to pytest
6. **Add CI workflow** - GitHub Actions

---

## Appendix A: Existing Test Migration

| Current File | Migrates To | Notes |
|--------------|-------------|-------|
| `test_battery_control.py` | `tests/hardware/test_write_operations.py` | Keep as reference, extract to pytest |
| `test_register_writability.py` | `tests/hardware/test_register_discovery.py` | Hardware-only, destructive |
| `test_battery_control.sh` | `tests/hardware/test_control_sequence.py` | Convert shell to Python |
| `connect_test.py` | `tests/hardware/test_connection.py` | Simplify, add assertions |
| `quicktest.py` | `tests/integration/test_quick.py` | Mock version for CI |

---

## Appendix B: Test Data Examples

### Mock Model 704 (Control)
```python
MOCK_MODEL_704 = {
    "WSetEna": {"value": 0},
    "WSetMod": {"value": 0},
    "WSet": {"value": 0},
    "WSetPct": {"value": 0},
    "WSetPct_SF": {"value": -1},
    "WSet_SF": {"value": 0},
    "WSetRvrtTms": {"value": 0},
    "WSetRvrtRem": {"value": 0},
}
```

### Mock Model 713 (Battery)
```python
MOCK_MODEL_713 = {
    "SoC": {"value": 7500},  # 75% with SF -2
    "SoH": {"value": 9900},  # 99% with SF -2
    "WHRtg": {"value": 13600},  # 13.6 kWh
    "WHAvail": {"value": 10200},  # 10.2 kWh
    "Pct_SF": {"value": -2},
    "WH_SF": {"value": 0},
}
```

---

*End of Test Suite Plan*
