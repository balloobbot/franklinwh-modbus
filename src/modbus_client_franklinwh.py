"""
FranklinWH-specific register extensions and raw Modbus access.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable
import struct
import logging
import asyncio

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    from pymodbus.client.tcp import ModbusTcpClient


@dataclass
class FranklinWHRawRegisters:
    """Raw register values from FranklinWH extended address space."""
    # Address 15000-15040 range
    soc_raw: Optional[int] = None           # 15011: 621 (62.1% with SF -1)
    soh_raw: Optional[int] = None           # 15036: 963 (96.3% with SF -1)
    wh_rtg_raw: Optional[int] = None        # 15020: 13600 (13600 Wh)
    power_raw: Optional[int] = None         # 15022: 13 (13W?)
    voltage_raw: Optional[int] = None       # 15025: 2407 (240.7V with SF -1)
    current_raw: Optional[int] = None       # 15024: -15567 (signed?)
    
    # Control registers (RW) - these are the key ones you mentioned
    operating_mode: Optional[int] = None    # 15016: 2 (matches AbnOpCatRtg, VarSetPri)
    reserve_soc: Optional[int] = None       # 15017: 20 (matches PF - power factor?)
    reserve_soc_2: Optional[int] = None     # 15040: -9 (FFF7)
    
    # Additional status
    status_flags: Optional[int] = None      # 15007: 263 (0107h)
    unknown_15034: Optional[int] = None     # 15034: 28704 (7020h)


class FranklinWHRegisterMap:
    """
    FranklinWH-specific register map for non-standard extensions.
    Based on analysis of raw register dumps.
    """
    
    # Register addresses in the 15500+ range (Confirmed by User)
    REGISTERS = {
        # Control registers (read-write)
        "operating_mode":    {"addr": 15507, "type": "uint16", "access": "rw", 
                              "enum": {0: "Standby", 1: "Backup Reserve", 2: "Self-Consumption", 3: "Time-of-Use"}},
        "reserve_soc":       {"addr": 15508, "type": "uint16", "access": "rw", 
                              "sf": 0, "unit": "%", "min": 0, "max": 100},
        "reserve_soc_2":     {"addr": 15509, "type": "uint16", "access": "rw",
                              "sf": 0, "unit": "%"},
        
        # Metrics from 15500 block
        "pv_output_w":       {"addr": 15502, "type": "uint16", "access": "r", "sf": 0, "unit": "W"},
        "home_loads_w":      {"addr": 15506, "type": "uint16", "access": "r", "sf": 0, "unit": "W"},
        "pv_output_wh":      {"addr": 15510, "type": "acc32",  "access": "r", "sf": 0, "unit": "Wh"},
    }
    
    # Block read optimization
    BLOCK_RANGES = [
        (15500, 14),   # Main extension block
    ]
    
    def __init__(self, modbus_client):
        self.client = modbus_client
        self._logger = logging.getLogger(__name__)
        self._cache: Dict[int, int] = {}
        self._cache_time: float = 0
        self._cache_ttl = 2.0
        self._raw_client: Optional[ModbusTcpClient] = None
    
    async def _get_raw_client(self) -> Optional[ModbusTcpClient]:
        """Get or create a raw Modbus client for extension reads."""
        # If main client has raw client, use it
        if self.client._client:
            return self.client._client
        
        # Otherwise create our own raw client
        if not self._raw_client:
            self._raw_client = ModbusTcpClient(
                host=self.client.host,
                port=self.client.port,
                timeout=self.client.timeout,
            )
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._raw_client.connect
            )
            if not result:
                self._logger.error("Failed to connect raw client for extensions")
                return None
        
        return self._raw_client
    
    async def close(self) -> None:
        """Close the raw client if we created one."""
        if self._raw_client:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._raw_client.close
                )
            except Exception:
                pass
            finally:
                self._raw_client = None
    
    async def read_raw_block(self, start_addr: int, count: int, force: bool = False) -> Dict[int, int]:
        """
        Read a block of raw registers.
        
        Args:
            start_addr: Starting register address
            count: Number of registers to read
            force: Force re-read even if cache is valid
        
        Returns:
            Dictionary of {address: raw_value}
        """
        import asyncio
        
        # Check cache
        now = asyncio.get_event_loop().time()
        if not force and (now - self._cache_time) < self._cache_ttl:
            # Check if all requested addresses are in cache
            if all(start_addr + i in self._cache for i in range(count)):
                return {start_addr + i: self._cache[start_addr + i] for i in range(count)}
        
        # Get raw client (may need to create one)
        raw_client = await self._get_raw_client()
        if not raw_client:
            return {}
        
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: raw_client.read_holding_registers(
                    address=start_addr,
                    count=count,
                    device_id=self.client.unit_id
                )
            )
            
            if result.isError():
                self._logger.debug(f"Modbus error reading {start_addr}:{count}")
                return {}
            
            # Update cache
            for i, value in enumerate(result.registers):
                self._cache[start_addr + i] = value
            
            self._cache_time = now
            
            return {start_addr + i: v for i, v in enumerate(result.registers)}
            
        except Exception as e:
            self._logger.error(f"Error reading registers {start_addr}:{count}: {e}")
            return {}
    
    async def read_register(self, name: str, force: bool = False) -> Optional[Dict]:
        """
        Read a single named register with full metadata.
        
        Args:
            name: Register name from REGISTERS map
            force: Force re-read
        
        Returns:
            Dictionary with raw_value, scaled_value, and metadata
        """
        if name not in self.REGISTERS:
            self._logger.error(f"Unknown register: {name}")
            return None
        
        reg = self.REGISTERS[name]
        addr = reg["addr"]
        
        # Read single register
        block = await self.read_raw_block(addr, 1, force)
        if addr not in block:
            return None
        
        raw_value = block[addr]
        
        # Build result
        result = {
            "name": name,
            "address": addr,
            "raw_value": raw_value,
            "type": reg.get("type", "uint16"),
            "access": reg.get("access", "r"),
        }
        
        # Apply scale factor
        sf = reg.get("sf", 0)
        if sf != 0:
            result["scaled_value"] = raw_value * (10 ** sf)
            result["unit"] = reg.get("unit", "")
        else:
            result["scaled_value"] = raw_value
            result["unit"] = reg.get("unit", "")
        
        # Apply enum mapping
        if "enum" in reg and raw_value in reg["enum"]:
            result["enum_value"] = reg["enum"][raw_value]
        
        return result
    
    async def write_register(self, name: str, value) -> bool:
        """
        Write to a named register.
        
        Args:
            name: Register name
            value: Value to write (will be scaled if needed)
        
        Returns:
            True if successful
        """
        import asyncio
        
        if name not in self.REGISTERS:
            self._logger.error(f"Unknown register: {name}")
            return False
        
        reg = self.REGISTERS[name]
        
        if reg.get("access") != "rw":
            self._logger.error(f"Register {name} is not writable")
            return False
        
        addr = reg["addr"]
        
        # Apply inverse scale factor
        sf = reg.get("sf", 0)
        if sf != 0:
            raw_value = int(value / (10 ** sf))
        else:
            raw_value = int(value)
        
        # Check bounds
        if "min" in reg and raw_value < reg["min"]:
            self._logger.warning(f"Value {raw_value} below minimum {reg['min']}")
            raw_value = reg["min"]
        if "max" in reg and raw_value > reg["max"]:
            self._logger.warning(f"Value {raw_value} above maximum {reg['max']}")
            raw_value = reg["max"]
        
        # Get raw client
        raw_client = await self._get_raw_client()
        if not raw_client:
            return False
        
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: raw_client.write_register(
                    address=addr,
                    value=raw_value,
                    device_id=self.client.unit_id
                )
            )
            
            if result.isError():
                self._logger.error(f"Modbus error writing {name}={raw_value} to {addr}")
                return False
            
            # Update cache
            self._cache[addr] = raw_value
            
            self._logger.info(f"Wrote {name}={value} (raw={raw_value}) to address {addr}")
            return True
            
        except Exception as e:
            self._logger.error(f"Error writing register {name}: {e}")
            return False
    
    async def read_all_metrics(self) -> FranklinWHRawRegisters:
        """Read all known FranklinWH registers."""
        regs = FranklinWHRawRegisters()
        
        # Read main block (15500-15513)
        block = await self.read_raw_block(15500, 14)
        
        # Map values
        if 15507 in block:
            regs.operating_mode = block[15507]
        if 15508 in block:
            regs.reserve_soc = block[15508]
        if 15509 in block:
            regs.reserve_soc_2 = block[15509]
            
        # We don't have soc_raw etc in this block, leave them None
        
        return regs
    
    # Control methods for the three key RW registers
    
    async def set_operating_mode(self, mode: int) -> bool:
        """
        Set battery operating mode.
        
        Modes:
            0: Standby
            1: Backup Reserve
            2: Self-Consumption
            3: Time-of-Use
        """
        return await self.write_register("operating_mode", mode)
    
    async def set_reserve_soc(self, soc_percent: int) -> bool:
        """
        Set reserve SOC percentage.
        
        Args:
            soc_percent: 0-100
        """
        return await self.write_register("reserve_soc", soc_percent)
    
    async def set_reserve_soc_2(self, soc_percent: int) -> bool:
        """
        Set secondary reserve SOC (purpose TBD).
        
        Args:
            soc_percent: -128 to 127 (signed)
        """
        return await self.write_register("reserve_soc_2", soc_percent)
    
    async def get_operating_mode_text(self, mode: Optional[int] = None) -> str:
        """Get text description of operating mode."""
        if mode is None:
            reg = await self.read_register("operating_mode")
            mode = reg["raw_value"] if reg else None
        
        modes = {
            0: "Standby",
            1: "Backup Reserve",
            2: "Self-Consumption",
            3: "Time-of-Use",
        }
        return modes.get(mode, f"Unknown({mode})")
