"""
FranklinWH Modbus Battery Manager - Core Types and Enums

This module contains all shared types, enums, and data classes used by
the FranklinWH Modbus library.
"""

from enum import Enum, IntEnum
from dataclasses import dataclass
from typing import Optional


class ControlMode(IntEnum):
    """Battery control modes per SunSpec Model 704."""
    LIMIT_ABS = 0       # Absolute power limit (W)
    LIMIT_PCT = 1       # Percentage of max power
    SET_EXPORT = 2      # Target export power
    SET_IMPORT = 3      # Target import power


class VirtualMode(Enum):
    """Virtual/software control modes."""
    SELF_CONSUMPTION = "self_consumption"
    EMERGENCY_BACKUP = "emergency_backup"
    TIME_OF_USE = "time_of_use"
    GRID_ZERO = "grid_zero"
    PEAK_SHAVE = "peak_shave"
    MANUAL = "manual"


@dataclass
class BatteryCommand:
    """Battery control command.
    
    Attributes:
        power_watts: Target power in watts
                     Positive = charge, negative = discharge, 0 = idle
        mode: Control mode (usually LIMIT_ABS for absolute wattage)
    """
    power_watts: float
    mode: ControlMode = ControlMode.LIMIT_ABS


@dataclass
class HealthStatus:
    """System health check result.
    
    Attributes:
        healthy: True if system is in a good state
        message: Summary message describing health state
        recommendations: Suggested actions
        details: Additional diagnostic information
        zombie_state: True if system is in an unrecoverable state
    """
    healthy: bool
    message: str
    recommendations: list
    details: Optional[dict] = None
    zombie_state: bool = False


# Scale factor helpers
SUNSPEC_SCALES = {
    'W': 0,      # Watts
    'V': 0,      # Volts  
    'A': -3,     # Amps (often scaled)
    'Hz': -2,    # Hertz
    'C': 0,      # Celsius
    'Wh': 0,     # Watt-hours
    'kWh': 0,    # Kilowatt-hours
}


# Model IDs for reference
MODEL_IDS = {
    1: 'Common',
    502: 'METROLOGY',
    701: 'DERInfo',
    702: 'DERCapacity',
    703: 'DERRtg',
    704: 'DERCtrl',
    705: 'DERCtrl2',
    706: 'DERStatus',
    707: 'DERStatus2',
    708: 'DERStorageCapacity',
    709: 'DERStorageStatus',
    710: 'DERStorageCtrl',
    711: 'DERPricing',
    712: 'DERPricing2',
    713: 'DERPricing3',
    714: 'DERStorageStatus2',
    715: 'DERCtrl3',
}


# Grid connection states
GRID_CONNECTION_STATES = {
    0: 'Disconnected',
    1: 'Connected',
    2: 'Fault',
}


# Storage operation states
STORAGE_OPERATION_STATES = {
    1: 'Off',
    2: 'Standby',
    3: 'Starting',
    4: 'Charge',
    5: 'Discharge',
    6: 'Fault',
}


# Control modes from M704
WSET_MODES = {
    0: 'WSet',
    1: 'VarSet',
    2: 'VarSetPct',
    3: 'VArSet',
    4: 'VArSetPct',
    5: 'MinMaxVarSet',
    6: 'MinMaxVarSetPct',
}


# Local/Remote control states
LOC_REM_CTL = {
    0: 'Remote',
    1: 'Local',
}


# DER control modes
DER_CTRL_MODES = {
    0: 'None',
    1: 'WSet',
    2: 'VarSet',
    3: 'VArSet',
    4: 'MinMaxVarSet',
}


# OnGridMode values from FranklinWH extension registers
ONGRID_MODES = {
    0: 'Emergency Backup',
    1: 'Self-Consumption',
    2: 'TOU',
    3: 'Manual',
}
