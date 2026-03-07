"""
FranklinWH Modbus Battery Manager

A Python library for controlling FranklinWH aGate battery systems via Modbus TCP.

Example usage:
    from franklinwh import FranklinWHController, VirtualModeController, VirtualMode
    
    # Connect to aGate
    ctrl = FranklinWHController('192.168.1.100')
    ctrl.connect()
    
    # Use virtual modes
    vmc = VirtualModeController(ctrl)
    vmc.set_mode(VirtualMode.SELF_CONSUMPTION)
    vmc.run_continuous(duration_seconds=3600)
"""

__version__ = '1.0.0'

from .types import (
    ControlMode,
    VirtualMode,
    BatteryCommand,
    HealthStatus,
    ONGRID_MODES,
)

from .schedule import TOUSchedule, DEFAULT_SCHEDULE

from .controller import FranklinWHController

from .modes import VirtualModeController

# Optional monitor import (requires rich dependency)
try:
    from .monitor import CLIMonitor, MonitorConfig
    HAS_MONITOR = True
except ImportError:
    HAS_MONITOR = False
    CLIMonitor = None
    MonitorConfig = None

__all__ = [
    # Types
    'ControlMode',
    'VirtualMode',
    'BatteryCommand',
    'HealthStatus',
    'ONGRID_MODES',
    # Schedule
    'TOUSchedule',
    'DEFAULT_SCHEDULE',
    # Controller
    'FranklinWHController',
    # Modes
    'VirtualModeController',
    # Monitor (optional)
    'CLIMonitor',
    'MonitorConfig',
    'HAS_MONITOR',
]
