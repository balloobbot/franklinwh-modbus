from enum import IntFlag, IntEnum
from dataclasses import dataclass
from typing import Optional, List


# =============================================================================
# MODEL 701: DERMeasureAC - Alrm (40076) - System Alarms
# =============================================================================

class SystemAlarm(IntFlag):
    """Model 701 Alrm bitfield - Primary DER alarm status"""
    GROUND_FAULT = 1 << 0          # Ground fault detected
    INPUT_OVER_CURRENT = 1 << 1    # DC input overcurrent
    DC_OVER_VOLTAGE = 1 << 2       # DC bus overvoltage
    AC_DISCONNECT = 1 << 3         # AC disconnect open
    DC_DISCONNECT = 1 << 4         # DC disconnect open
    GRID_DISCONNECT = 1 << 5       # Grid connection lost
    CABINET_OPEN = 1 << 6          # Enclosure breach
    MANUAL_SHUTDOWN = 1 << 7       # Manual stop commanded
    OVER_TEMP = 1 << 8             # Thermal overload
    OVER_FREQUENCY = 1 << 9        # AC frequency high
    UNDER_FREQUENCY = 1 << 10      # AC frequency low
    AC_OVER_VOLTAGE = 1 << 11      # AC voltage high
    AC_UNDER_VOLTAGE = 1 << 12     # AC voltage low
    STRING_FAULT = 1 << 13         # Solar string fault
    ARC_FAULT = 1 << 14            # Arcing detected
    THERMAL_DERATE = 1 << 15       # Temperature limiting
    # Bits 16-31: VENDOR_DEFINED - FranklinWH specific
    
    # Convenience combinations
    CRITICAL_FAULTS = GROUND_FAULT | CABINET_OPEN | MANUAL_SHUTDOWN | STRING_FAULT | ARC_FAULT
    FREQUENCY_FAULTS = OVER_FREQUENCY | UNDER_FREQUENCY
    VOLTAGE_FAULTS = AC_OVER_VOLTAGE | AC_UNDER_VOLTAGE | DC_OVER_VOLTAGE


# =============================================================================
# MODEL 502: Solar Module - Evt (41104) - Solar Events
# =============================================================================

class SolarEvent(IntFlag):
    """Model 502 Evt bitfield - Solar module events"""
    INPUT_UNDER_VOLTAGE = 1 << 0   # PV string voltage low
    INPUT_OVER_VOLTAGE = 1 << 1    # PV string voltage high
    INPUT_UNDER_CURRENT = 1 << 2   # PV current low (shading/fault)
    INPUT_OVER_CURRENT = 1 << 3    # PV current high
    INPUT_UNDER_POWER = 1 << 4     # PV power below expected
    INPUT_OVER_POWER = 1 << 5      # PV power above rating
    OUTPUT_UNDER_VOLTAGE = 1 << 6  # DC output low
    OUTPUT_OVER_VOLTAGE = 1 << 7   # DC output high
    OUTPUT_UNDER_CURRENT = 1 << 8  # Output current low
    OUTPUT_OVER_CURRENT = 1 << 9   # Output current high
    OUTPUT_UNDER_POWER = 1 << 10   # Output power low
    OUTPUT_OVER_POWER = 1 << 11    # Output power high
    # Bits 12-31: VENDOR_DEFINED - FranklinWH solar specific
    
    INPUT_FAULTS = INPUT_UNDER_VOLTAGE | INPUT_OVER_VOLTAGE | INPUT_UNDER_CURRENT | INPUT_OVER_CURRENT
    OUTPUT_FAULTS = OUTPUT_UNDER_VOLTAGE | OUTPUT_OVER_VOLTAGE | OUTPUT_UNDER_CURRENT | OUTPUT_OVER_CURRENT


# =============================================================================
# MODEL 714: DERMeasureDC - PrtAlrms (41044) - DC Port Alarms
# =============================================================================

class DCPortAlarm(IntFlag):
    """Model 714 PrtAlrms bitfield - Battery DC port alarms"""
    PORT_OVER_VOLTAGE = 1 << 0     # Battery voltage high
    PORT_UNDER_VOLTAGE = 1 << 1    # Battery voltage low
    PORT_OVER_CURRENT = 1 << 2     # Charge/discharge current high
    PORT_OVER_TEMP = 1 << 3        # Battery temperature high
    PORT_UNDER_TEMP = 1 << 4       # Battery temperature low
    PORT_CONTACTOR_FAULT = 1 << 5  # DC contactor failed
    PORT_FUSE_FAULT = 1 << 6       # DC fuse blown
    PORT_GROUND_FAULT = 1 << 7     # Battery ground fault
    # Bits 8-31: VENDOR_DEFINED - FranklinWH battery specific
    
    ELECTRICAL_FAULTS = PORT_OVER_VOLTAGE | PORT_UNDER_VOLTAGE | PORT_OVER_CURRENT
    THERMAL_FAULTS = PORT_OVER_TEMP | PORT_UNDER_TEMP
    HARDWARE_FAULTS = PORT_CONTACTOR_FAULT | PORT_FUSE_FAULT


# =============================================================================
# MODEL 713: DERStorageCapacity - Sta (41039) - Battery Status
# =============================================================================

class BatteryStatus(IntEnum):
    """Model 713 Sta enum - Battery operational state"""
    IDLE = 0           # Standby, no charge/discharge
    CHARGING = 1       # Actively charging
    DISCHARGING = 2    # Actively discharging
    HOLDING = 3        # Maintaining SOC, no net flow
    FULL = 4           # At max SOC, charge blocked
    EMPTY = 5          # At min SOC, discharge blocked
    FAULT = 6          # Fault condition, operation blocked
    SLEEP = 7          # Low power mode
    # 8+ VENDOR_DEFINED


# =============================================================================
# MODEL 702: DERCapacity - CtrlModes (40248) - Supported Control Modes
# =============================================================================

class CtrlModes(IntFlag):
    """
    Model 702 CtrlModes bitfield - Supported DER control modes
    Your value: 14271 = 0x37BF = binary 0011 0111 1011 1111
    """
    # IEEE 1547-2018 / SunSpec standard modes
    FREQ_WATT = 1 << 0             # Frequency-Watt (under/over frequency response)
    VOLT_WATT = 1 << 1             # Volt-Watt (voltage-dependent power reduction)
    VOLT_VAR = 1 << 2              # Volt-VAr (voltage-dependent reactive power)
    FIXED_PF = 1 << 3              # Fixed power factor
    FIXED_VAR = 1 << 4             # Fixed VAr setpoint
    WATT_VAR = 1 << 5              # Watt-VAr (active power-dependent reactive power)
    FREQ_WATT_DROOP = 1 << 6       # Frequency-Watt with droop
    DYNAMIC_REACTIVE_CURRENT = 1 << 7   # Dynamic reactive current support
    
    # Extended modes
    LVRT = 1 << 8                  # Low voltage ride-through
    HVRT = 1 << 9                  # High voltage ride-through
    LFRT = 1 << 10                 # Low frequency ride-through
    HFRT = 1 << 11                 # High frequency ride-through
    SPECIFIC_MODES = 1 << 12       # Manufacturer-specific modes supported
    # Bits 13-31: Reserved or vendor-defined
    
    # Your aGate value 14271 (0x37BF) has these bits set:
    # 0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12 = 12 active modes


@dataclass
class CtrlModesDecoded:
    """Human-readable decoding of CtrlModes bitfield"""
    raw_value: int
    active_modes: List[str]
    supports_frequency_watt: bool
    supports_volt_watt: bool
    supports_volt_var: bool
    supports_fixed_pf: bool
    supports_fixed_var: bool
    supports_watt_var: bool
    supports_droop: bool
    supports_dynamic_reactive: bool
    supports_ride_through: bool
    supports_specific_modes: bool
    
    @classmethod
    def from_int(cls, value: int) -> "CtrlModesDecoded":
        modes = CtrlModes(value)
        active = [name for name, member in CtrlModes.__members__.items() if member in modes]
        
        return cls(
            raw_value=value,
            active_modes=active,
            supports_frequency_watt=CtrlModes.FREQ_WATT in modes,
            supports_volt_watt=CtrlModes.VOLT_WATT in modes,
            supports_volt_var=CtrlModes.VOLT_VAR in modes,
            supports_fixed_pf=CtrlModes.FIXED_PF in modes,
            supports_fixed_var=CtrlModes.FIXED_VAR in modes,
            supports_watt_var=CtrlModes.WATT_VAR in modes,
            supports_droop=CtrlModes.FREQ_WATT_DROOP in modes,
            supports_dynamic_reactive=CtrlModes.DYNAMIC_REACTIVE_CURRENT in modes,
            supports_ride_through=any(m in modes for m in [CtrlModes.LVRT, CtrlModes.HVRT, CtrlModes.LFRT, CtrlModes.HFRT]),
            supports_specific_modes=CtrlModes.SPECIFIC_MODES in modes,
        )
    
    def __str__(self) -> str:
        lines = [
            f"CtrlModes: 0x{self.raw_value:04X} ({self.raw_value})",
            f"Active modes ({len(self.active_modes)}):",
        ]
        for mode in self.active_modes:
            lines.append(f"  - {mode}")
        return "\n".join(lines)


# =============================================================================
# MODEL 701: DERMeasureAC - DERMode (40078) - Operational Characteristics
# =============================================================================

class DERMode(IntFlag):
    """
    Model 701 DERMode bitfield - Current DER operational mode
    Your value: 1 = 0x0001
    """
    # IEEE 1547-2018 operational modes
    PV = 1 << 0                    # Photovoltaic generator
    BATTERY = 1 << 1               # Battery energy storage
    HYBRID = 1 << 2                # Hybrid (PV + battery)
    CHARGER = 1 << 3               # Standalone battery charger
    STATCOM = 1 << 4               # Static synchronous compensator (VAr only)
    LOAD = 1 << 5                  # Controllable load (demand response)
    GENERATOR = 1 << 6             # Rotating generator (diesel, gas, etc.)
    # Bits 7-15: Reserved
    
    # Your aGate value 1 = PV mode only (battery controlled as part of PV system)
    
    # Extended characteristics (bits 16-31)
    GRID_FOLLOWING = 1 << 16       # Current source, follows grid voltage
    GRID_FORMING = 1 << 17         # Voltage source, establishes grid
    GRID_SUPPORTING = 1 << 18      # Grid-supporting functions active
    ISLANDED = 1 << 19             # Intentionally islanded (microgrid)
    CONNECTED = 1 << 20            # Grid-connected
    AVAILABLE = 1 << 21            # DER available for service
    OPERATING = 1 << 22            # DER currently producing/consuming
    TEST_MODE = 1 << 23            # In test/commissioning mode
    # Bits 24-31: Reserved or vendor-defined


@dataclass
class DERModeDecoded:
    """Human-readable decoding of DERMode bitfield"""
    raw_value: int
    source_type: Optional[str]
    grid_mode: Optional[str]
    operational_state: List[str]
    is_pv: bool
    is_battery: bool
    is_hybrid: bool
    is_grid_following: bool
    is_grid_forming: bool
    is_islanded: bool
    is_connected: bool
    is_available: bool
    is_operating: bool
    is_test_mode: bool
    
    @classmethod
    def from_int(cls, value: int) -> "DERModeDecoded":
        mode = DERMode(value)
        
        # Determine source type (mutually exclusive in practice)
        source_type = None
        if DERMode.PV in mode and DERMode.BATTERY in mode:
            source_type = "HYBRID"
        elif DERMode.PV in mode:
            source_type = "PV"
        elif DERMode.BATTERY in mode:
            source_type = "BATTERY"
        elif DERMode.GENERATOR in mode:
            source_type = "GENERATOR"
        elif DERMode.STATCOM in mode:
            source_type = "STATCOM"
        
        # Determine grid mode
        grid_mode = None
        if DERMode.GRID_FORMING in mode:
            grid_mode = "GRID_FORMING"
        elif DERMode.GRID_FOLLOWING in mode:
            grid_mode = "GRID_FOLLOWING"
        
        # Operational states
        states = []
        if DERMode.CONNECTED in mode:
            states.append("CONNECTED")
        if DERMode.ISLANDED in mode:
            states.append("ISLANDED")
        if DERMode.AVAILABLE in mode:
            states.append("AVAILABLE")
        if DERMode.OPERATING in mode:
            states.append("OPERATING")
        if DERMode.TEST_MODE in mode:
            states.append("TEST_MODE")
        
        return cls(
            raw_value=value,
            source_type=source_type,
            grid_mode=grid_mode,
            operational_state=states,
            is_pv=DERMode.PV in mode,
            is_battery=DERMode.BATTERY in mode,
            is_hybrid=DERMode.HYBRID in mode or (DERMode.PV in mode and DERMode.BATTERY in mode),
            is_grid_following=DERMode.GRID_FOLLOWING in mode,
            is_grid_forming=DERMode.GRID_FORMING in mode,
            is_islanded=DERMode.ISLANDED in mode,
            is_connected=DERMode.CONNECTED in mode,
            is_available=DERMode.AVAILABLE in mode,
            is_operating=DERMode.OPERATING in mode,
            is_test_mode=DERMode.TEST_MODE in mode,
        )
    
    def __str__(self) -> str:
        lines = [
            f"DERMode: 0x{self.raw_value:08X} ({self.raw_value})",
            f"Source type: {self.source_type or 'UNKNOWN'}",
            f"Grid mode: {self.grid_mode or 'UNKNOWN'}",
            f"Operational state: {', '.join(self.operational_state) if self.operational_state else 'NONE'}",
            f"Characteristics:",
            f"  PV: {self.is_pv}, Battery: {self.is_battery}, Hybrid: {self.is_hybrid}",
            f"  Grid-following: {self.is_grid_following}, Grid-forming: {self.is_grid_forming}",
            f"  Islanded: {self.is_islanded}, Connected: {self.is_connected}",
            f"  Available: {self.is_available}, Operating: {self.is_operating}, Test: {self.is_test_mode}",
        ]
        return "\n".join(lines)


# =============================================================================
# COMPLETE ALARM MONITORING CLASS
# =============================================================================

@dataclass
class FranklinWHAlarmStatus:
    """Complete alarm and status snapshot from aGate"""
    # Raw values
    system_alrm: int
    solar_evt: int
    dc_port_alrm: int
    battery_sta: int
    ctrl_modes: int
    der_mode: int
    
    # Decoded values
    system_alarms: SystemAlarm
    solar_events: SolarEvent
    dc_port_alarms: DCPortAlarm
    battery_status: BatteryStatus
    ctrl_modes_decoded: CtrlModesDecoded
    der_mode_decoded: DERModeDecoded
    
    # Derived health
    is_safe_to_operate: bool
    blocking_alarms: List[str]
    recommended_action: str
    
    @classmethod
    def from_registers(cls, 
                       system_alrm: int = 0,
                       solar_evt: int = 0,
                       dc_port_alrm: int = 0,
                       battery_sta: int = 0,
                       ctrl_modes: int = 14271,  # Your value
                       der_mode: int = 1) -> "FranklinWHAlarmStatus":
        
        # Decode all bitfields
        sys_alarms = SystemAlarm(system_alrm)
        sol_evts = SolarEvent(solar_evt)
        dc_alarms = DCPortAlarm(dc_port_alrm)
        bat_stat = BatteryStatus(battery_sta)
        ctrl_dec = CtrlModesDecoded.from_int(ctrl_modes)
        der_dec = DERModeDecoded.from_int(der_mode)
        
        # Determine safety
        blocking = []
        
        if sys_alarms & SystemAlarm.CRITICAL_FAULTS:
            blocking.extend([a.name for a in SystemAlarm if a in sys_alarms & SystemAlarm.CRITICAL_FAULTS])
        
        if dc_alarms & DCPortAlarm.ELECTRICAL_FAULTS:
            blocking.extend([a.name for a in DCPortAlarm if a in dc_alarms & DCPortAlarm.ELECTRICAL_FAULTS])
        
        if bat_stat == BatteryStatus.FAULT:
            blocking.append("BATTERY_STATUS_FAULT")
        
        safe = len(blocking) == 0
        
        # Recommend action
        if safe:
            action = "Normal operation permitted"
        elif sys_alarms & SystemAlarm.MANUAL_SHUTDOWN:
            action = "Manual reset required at unit"
        elif bat_stat == BatteryStatus.FAULT:
            action = "Check battery DC connections and temperature"
        else:
            action = "Clear faults and write AlarmReset (41094)"
        
        return cls(
            system_alrm=system_alrm,
            solar_evt=solar_evt,
            dc_port_alrm=dc_port_alrm,
            battery_sta=battery_sta,
            ctrl_modes=ctrl_modes,
            der_mode=der_mode,
            system_alarms=sys_alarms,
            solar_events=sol_evts,
            dc_port_alarms=dc_alarms,
            battery_status=bat_stat,
            ctrl_modes_decoded=ctrl_dec,
            der_mode_decoded=der_dec,
            is_safe_to_operate=safe,
            blocking_alarms=blocking,
            recommended_action=action,
        )
    
    def __str__(self) -> str:
        lines = [
            "=" * 60,
            "FRANKLINWH aGATE STATUS REPORT",
            "=" * 60,
            "",
            str(self.der_mode_decoded),
            "",
            str(self.ctrl_modes_decoded),
            "",
            f"Battery Status: {self.battery_status.name} ({self.battery_sta})",
            "",
            "ALARMS:",
            f"  System (701): 0x{self.system_alrm:08X}",
        ]
        if self.system_alarms:
            for alarm in SystemAlarm:
                if alarm in self.system_alarms:
                    lines.append(f"    [!] {alarm.name}")
        else:
            lines.append("    [OK] None active")
        
        lines.extend([
            f"  Solar (502): 0x{self.solar_evt:08X}",
        ])
        if self.solar_events:
            for evt in SolarEvent:
                if evt in self.solar_events:
                    lines.append(f"    [!] {evt.name}")
        else:
            lines.append("    [OK] None active")
        
        lines.extend([
            f"  DC Port (714): 0x{self.dc_port_alrm:08X}",
        ])
        if self.dc_port_alarms:
            for alrm in DCPortAlarm:
                if alrm in self.dc_port_alarms:
                    lines.append(f"    [!] {alrm.name}")
        else:
            lines.append("    [OK] None active")
        
        lines.extend([
            "",
            f"OPERATIONAL SAFETY: {'SAFE' if self.is_safe_to_operate else 'UNSAFE'}",
            f"Blocking issues: {self.blocking_alarms or 'None'}",
            f"Recommended action: {self.recommended_action}",
            "=" * 60,
        ])
        
        return "\n".join(lines)


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Decode your actual aGate values
    print("=== Your aGate CtrlModes (40248 = 14271) ===")
    ctrl = CtrlModesDecoded.from_int(14271)
    print(ctrl)
    print()
    
    print("=== Your aGate DERMode (40078 = 1) ===")
    der = DERModeDecoded.from_int(1)
    print(der)
    print()
    
    # Simulate alarm reading with your actual values
    # From your output: Alrm=0, Evt=0, PrtAlrms=0, Sta=0
    status = FranklinWHAlarmStatus.from_registers(
        system_alrm=0,      # Your value: 0
        solar_evt=0,        # Your value: 0
        dc_port_alrm=0,     # Your value: 0
        battery_sta=0,      # Your value: 0 (IDLE)
        ctrl_modes=14271,   # Your value
        der_mode=1,         # Your value
    )
    print(status)
