"""
Data models for FranklinWH Battery Manager.
These are pure data classes with no dependencies.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class BatteryMode(IntEnum):
    """Battery operating modes."""
    IDLE = 0
    CHARGING = 1
    DISCHARGING = 2


class InverterStatus(IntEnum):
    """Inverter status codes."""
    OFF = 1
    SLEEPING = 2
    STARTING = 3
    MPPT = 4
    THROTTLED = 5
    SHUTTING_DOWN = 6
    FAULT = 7
    STANDBY = 8


@dataclass
class BatteryMetrics:
    """Battery metrics from Model 713/714."""
    rated_energy_wh: Optional[float] = None
    available_energy_wh: Optional[float] = None
    state_of_charge_percent: Optional[float] = None
    state_of_health_percent: Optional[float] = None
    status: Optional[int] = None
    status_text: str = "Unknown"
    temperature_c: Optional[float] = None
    cycle_count: Optional[int] = None
    # Model 714 additions - DC power and energy
    dc_power_w: Optional[float] = None  # Model 714.DCW - instantaneous DC power (+ = discharge, - = charge)
    dc_energy_injected_wh: Optional[float] = None  # Total discharged from battery
    dc_energy_absorbed_wh: Optional[float] = None  # Total charged to battery


@dataclass
class SolarPVMetrics:
    """Solar PV metrics from Model 502."""
    output_power_w: Optional[float] = None        # Current PV power output
    output_energy_wh: Optional[float] = None      # Lifetime PV energy produced


@dataclass
class HomeLoadMetrics:
    """Home load metrics from FranklinWH extension registers (15500+)."""
    home_loads_w: Optional[float] = None          # 15506: Home Loads Active Power W
    pv_output_w: Optional[float] = None           # 15502: PV Output Power W
    pv_proximal_w: Optional[float] = None         # 15503: Proximal PV Output W
    remote1_pv_w: Optional[float] = None          # 15504: Remote1 PV W
    remote2_pv_w: Optional[float] = None          # 15505: Remote2 PV W
    pv_output_wh: Optional[float] = None          # 15510-15511: PV Output Energy Wh (int64)
    pv_proximal_wh: Optional[float] = None        # 15512-15513: Proximal PV Output Wh (int64)


@dataclass
class InverterACMetrics:
    """AC inverter metrics from Model 701."""
    power_w: Optional[float] = None
    voltage_v: Optional[float] = None
    current_a: Optional[float] = None
    frequency_hz: Optional[float] = None
    apparent_power_va: Optional[float] = None
    reactive_power_var: Optional[float] = None
    power_factor: Optional[float] = None
    # Temperatures from Model 701
    ambient_temperature_c: Optional[float] = None  # TmpAmb
    cabinet_temperature_c: Optional[float] = None  # TmpCab
    # Status enums from Model 701
    inverter_state: Optional[int] = None  # InvSt
    inverter_state_text: str = "Unknown"
    grid_connection_state: Optional[int] = None  # ConnSt
    grid_connection_state_text: str = "Unknown"
    # Lifetime energy from Model 701
    total_energy_injected_wh: Optional[float] = None  # TotWhInj (exported to grid)
    total_energy_absorbed_wh: Optional[float] = None  # TotWhAbs (imported from grid)


@dataclass
class DERCapacity:
    """DER capacity from Model 703."""
    max_charge_w: Optional[float] = None
    max_discharge_w: Optional[float] = None
    max_charge_va: Optional[float] = None
    max_discharge_va: Optional[float] = None


@dataclass
class DeviceInfo:
    """Device information from Model 1."""
    manufacturer: str = "Unknown"
    model: str = "Unknown"
    version: str = "Unknown"
    serial_number: str = "Unknown"
    device_address: Optional[int] = None
