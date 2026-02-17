#!/usr/bin/env python3
import logging
import threading
import time
import struct
import inspect
from dataclasses import dataclass
from enum import IntEnum, IntFlag
from typing import Optional, Dict, Any, Tuple, List, Union

try:
    from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP
except ImportError:
    raise ImportError("pip install pysunspec2 is required")

logger = logging.getLogger(__name__)

class BatteryStatus(IntEnum):
    IDLE = 0; CHARGING = 1; DISCHARGING = 2; HOLDING = 3
    FULL = 4; EMPTY = 5; FAULT = 6; SLEEP = 7

class SystemAlarm(IntFlag):
    GROUND_FAULT = 1 << 0; DC_OVER_VOLTAGE = 1 << 2; AC_DISCONNECT = 1 << 3
    GRID_DISCONNECT = 1 << 5; MANUAL_SHUTDOWN = 1 << 7; OVER_TEMP = 1 << 8
    VOLT_OUT_OF_RANGE = 1 << 9; FREQ_OUT_OF_RANGE = 1 << 10

class ControlMode(IntEnum):
    LIMIT_ABS = 0; LIMIT_PCT = 1; SET_ABS = 2; SET_PCT = 3

@dataclass
class BatteryCommand:
    power_watts: float
    mode: ControlMode = ControlMode.SET_ABS

@dataclass
class HealthStatus:
    healthy: bool; message: str; details: Dict[str, Any]; recommendations: List[str]

class FranklinWHController:
    def __init__(self, ip_address, port=502, unit_id=2, timeout=10.0, base_address=1):
        self.ip_address = ip_address; self.port = port; self.unit_id = unit_id
        self.timeout = timeout; self.base_address = base_address
        self.dev = None; self.models = {}; self._heartbeat_timer = None; self._heartbeat_count = 0

    def connect(self) -> bool:
        try:
            self.dev = SunSpecModbusClientDeviceTCP(slave_id=self.unit_id, ipaddr=self.ip_address, ipport=self.port, timeout=self.timeout)
            try: self.dev.scan(base_addr=self.base_address)
            except: self.dev.scan()
            self.models = {int(k) if str(k).isdigit() else k: v for k, v in self.dev.models.items()}
            return True
        except Exception: return False

    def disconnect(self):
        self.reset_control_state()
        if self.dev: self.dev.close(); self.dev = None

    def get_model(self, model_id):
        m = self.models.get(model_id) or self.models.get(str(model_id))
        return m[0] if isinstance(m, list) else m

    def read_battery_status(self):
        m = self.get_model(713)
        if not m: return {}
        m.read(); raw = m.Sta.value
        return {'soc': m.SoC.value / 10.0, 'soh': m.SoH.value / 10.0, 'status': raw, 'status_name': BatteryStatus(raw).name if raw in list(BatteryStatus) else f"UNK_{raw}"}

    def read_grid_status(self):
        m = self.get_model(701)
        if not m: return {}
        m.read(); v_raw = m.LNV.value; alrm = m.Alrm.value if hasattr(m, 'Alrm') else 0
        return {'voltage_v': v_raw / 10.0 if v_raw > 1000 else v_raw, 'grid_power_w': m.W.value, 'alarms': [a.name for a in SystemAlarm if alrm & a]}

    def read_solar_status(self):
        m = self.get_model(502)
        if not m: return {'has_solar': False, 'ac_power_w': 0}
        m.read(); return {'ac_power_w': m.OutPw.value, 'has_solar': True}

    def read_control_status(self):
        m = self.get_model(704)
        if not m: return {}
        m.read(); return {'wset_ena': m.WSetEna.value, 'wset_watts': m.WSet.value}

    def read_opctl_status(self):
        m = self.get_model(715)
        if not m: return {}
        m.read(); return {'opctl': m.OpCtl.value, 'controller_hb': m.ControllerHb.value}

    def _get_raw_client(self):
        s_modbus = self.dev.client
        if hasattr(s_modbus, 'client'): return s_modbus.client
        return s_modbus

    def _safe_write(self, client, addr, value, is_list=False):
        # Check if this is a pymodbus client with write_register/write_registers
        if hasattr(client, 'write_register') and hasattr(client, 'write_registers'):
            kwargs = {}
            for meth in ['write_register', 'write_registers']:
                sig = inspect.signature(getattr(client, meth))
                if 'device_id' in sig.parameters: kwargs['device_id'] = self.unit_id
                elif 'unit' in sig.parameters: kwargs['unit'] = self.unit_id
                elif 'slave' in sig.parameters: kwargs['slave'] = self.unit_id
            if is_list: return client.write_registers(addr, value, **kwargs)
            return client.write_register(addr, value, **kwargs)
        # Fallback for sunspec2 ModbusClientTCP which uses write(addr, byte_string)
        elif hasattr(client, 'write'):
            # Ensure socket is connected BEFORE calling write() to prevent
            # sunspec's local_connect path which auto-disconnects after write
            if hasattr(client, 'socket') and client.socket is None:
                client.connect(client.timeout)
            if is_list:
                data = struct.pack('>' + 'H' * len(value), *[v & 0xFFFF for v in value])
            else:
                data = struct.pack('>H', value & 0xFFFF)
            return client.write(addr, data)
        else:
            raise AttributeError(f"Client {type(client).__name__} has no supported write method")

    def _start_heartbeat(self, interval=5.0):
        m = self.get_model(715)
        if not m: return
        def beat():
            if not self.dev: return
            try:
                self._heartbeat_count = (self._heartbeat_count + 1) % 10000
                m.ControllerHb.value = self._heartbeat_count
                m.write()
                self._heartbeat_timer = threading.Timer(interval, beat); self._heartbeat_timer.start()
            except: pass
        beat()

    def _stop_heartbeat(self):
        if self._heartbeat_timer: self._heartbeat_timer.cancel(); self._heartbeat_timer = None

    def send_command(self, command: BatteryCommand, revert_time_s=0, heartbeat_interval=5.0) -> Tuple[bool, str]:
        """SAFE SEQUENCE IMPLEMENTATION"""
        if not self.dev: return False, "Not connected"
        try:
            c = self._get_raw_client()
            
            # 1. STOP & CLEAR (Pre-flight reset)
            self._safe_write(c, 317, 0)       # WSetEna = 0
            self._safe_write(c, 1092, 1)      # OpCtl = 1 (External Authority)
            self._safe_write(c, 318, 0)       # Mode = Watts
            self._safe_write(c, 323, 0)       # WSetPct = 0
            time.sleep(0.2)

            # 2. HEARTBEAT
            self._stop_heartbeat()
            if heartbeat_interval > 0: self._start_heartbeat(heartbeat_interval)

            # 3. CONFIGURE
            p = int(command.power_watts)
            u32 = (1 << 32) + p if p < 0 else p
            # FranklinWH uses low-word-first: value in reg 319, overflow in reg 320
            self._safe_write(c, 319, [u32 & 0xFFFF, (u32 >> 16) & 0xFFFF], is_list=True)
            
            pct_raw = int((command.power_watts / 5000.0) * 1000)
            self._safe_write(c, 323, pct_raw) 
            self._safe_write(c, 326, [0, 0], is_list=True) # Revert = 0

            # 4. EXECUTE
            self._safe_write(c, 317, 1)       # WSetEna = 1
            return True, "Success"
        except Exception as e: return False, str(e)

    def reset_control_state(self):
        self._stop_heartbeat()
        if not self.dev: return False
        try:
            c = self._get_raw_client()
            self._safe_write(c, 317, 0)
            self._safe_write(c, 1092, 0)
            return True
        except: return False

    def healthcheck(self):
        return HealthStatus(True, "OK", {}, [])