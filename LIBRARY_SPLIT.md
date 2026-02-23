# FranklinWH Library Split Summary

**Date:** 2026-02-22  
**Status:** ✅ Complete

## Overview

The FranklinWH Modbus Battery Manager has been successfully split into a proper Python package structure with the original CLI script preserved for backward compatibility.

## New Package Structure

```
franklinwh-modbus/
├── src/
│   └── franklinwh/              # New library package
│       ├── __init__.py          # Package exports
│       ├── types.py             # Enums and data classes
│       ├── controller.py        # FranklinWHController (hardware interface)
│       ├── schedule.py          # TOUSchedule (time-of-use scheduling)
│       └── modes.py             # VirtualModeController (mode logic)
├── franklinwh_cli.py            # New CLI (uses library)
├── franklinwh_control_standalone.py  # Original (preserved)
├── setup.py                     # Package installation
└── tests/
    ├── conftest.py              # Updated to use src/franklinwh
    ├── unit/
    │   └── test_tou_schedule.py
    └── integration/
        └── test_virtual_mode_controller.py
```

## Package Contents

### `franklinwh.types`
Core types and enums:
- `ControlMode` - Modbus control modes (LIMIT_ABS, LIMIT_PCT, etc.)
- `VirtualMode` - Software modes (SELF_CONSUMPTION, EMERGENCY_BACKUP, etc.)
- `BatteryCommand` - Command structure with power and mode
- `HealthStatus` - Health check results

### `franklinwh.controller`
Hardware interface:
- `FranklinWHController` - Main controller class
  - `connect()` / `disconnect()`
  - `read_battery_status()` - Model 713
  - `read_grid_status()` - Model 701
  - `read_solar_status()` - Model 714 + extensions
  - `read_control_status()` - Model 704
  - `read_native_mode()` - Extension registers 15507-15509
  - `send_command()` - Send BatteryCommand
  - `reset_control_state()` - Return to idle
  - `healthcheck()` - System health
  - `discover_ratings()` - Read M702 nameplate

### `franklinwh.schedule`
Time-of-use scheduling:
- `TOUSchedule` - Schedule management
  - `from_file()` - Load from JSON
  - `get_current_period()` - Current TOU period
  - `get_current_price()` - Current price
  - `get_strategy()` - Battery strategy
  - `get_min_soc()` / `get_max_soc()` - Constraints

### `franklinwh.modes`
Virtual mode controller:
- `VirtualModeController` - Software mode controller
  - `set_mode()` - Change mode with parameters
  - `calculate_power()` - Determine optimal power
  - `execute_once()` - Single control cycle
  - `run_continuous()` - Continuous operation
  - Mode calculators:
    - `_calc_self_consumption()`
    - `_calc_emergency_backup()`
    - `_calc_grid_zero()`
    - `_calc_peak_shave()`
    - `_calc_time_of_use()`
    - `_calc_manual()`

## Usage

### As a Library

```python
from franklinwh import (
    FranklinWHController,
    VirtualModeController,
    VirtualMode,
    TOUSchedule
)

# Connect to aGate
ctrl = FranklinWHController('192.168.1.100')
ctrl.connect()

# Use virtual modes
vmc = VirtualModeController(ctrl, max_charge_soc=95)
vmc.set_mode(VirtualMode.SELF_CONSUMPTION, target_soc=90)
vmc.run_continuous(duration_seconds=3600)

# Or direct control
from franklinwh import BatteryCommand, ControlMode
cmd = BatteryCommand(power_watts=-3000)  # Charge at 3kW
ctrl.send_command(cmd)
```

### CLI

```bash
# Using new CLI
python franklinwh_cli.py -i 192.168.1.100 --mode self_consumption --target-soc 90

# Original CLI still works
python franklinwh_control_standalone.py -i 192.168.1.100 --mode self_consumption --target-soc 90
```

## Key Differences from Original

1. **Importable Package**: Core functionality now in `src/franklinwh/`
2. **Clean Separation**: Types, controller, schedule, and modes are separate modules
3. **New CLI**: `franklinwh_cli.py` imports from package
4. **Original Preserved**: `franklinwh_control_standalone.py` still works standalone
5. **Tests Updated**: Tests now import from `franklinwh` package

## Installation

```bash
# Install as editable package
pip install -e .

# Or use directly with PYTHONPATH
PYTHONPATH=src python franklinwh_cli.py -i 192.168.1.100 --status
```

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test files
pytest tests/unit/test_tou_schedule.py
pytest tests/integration/test_virtual_mode_controller.py
```

All 23 tests pass (1 skipped - hardware test).

## Backward Compatibility

The original `franklinwh_control_standalone.py` is preserved and still works exactly as before. Users can:
- Continue using the original script
- Migrate to the new package structure
- Use the new CLI which has the same interface

## Future Work

- Add more unit tests for controller.py
- Add integration tests for actual hardware
- Consider publishing to PyPI
- Add async support for non-blocking operations
- Document sign convention fix (positive=charge vs discharge)
