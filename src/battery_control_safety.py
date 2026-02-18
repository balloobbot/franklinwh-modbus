"""
Battery Control Safety Module

Provides safety checks for SunSpec2 battery control operations using
the FranklinWH Cloud API to verify operating mode and VPP enrollment.

Critical: SunSpec2 battery controls (Model 702/704) should ONLY be used
when Operating Mode = Self-Consumption to avoid conflicts with built-in
orchestration strategies.
"""

import logging
import sys
import os
from typing import Optional, Dict, List
from dataclasses import dataclass

# Add parent directory to path for Cloud API client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'ha', 'docker', 'fhp_demo'))

from franklinwh.client import Client, TokenFetcher
from franklinwh.const import MODE_TIME_OF_USE, MODE_SELF_CONSUMPTION, MODE_EMERGENCY_BACKUP

logger = logging.getLogger(__name__)


@dataclass
class SafetyCheckResult:
    """Result of battery control safety check"""
    safe: bool
    current_mode: str
    current_mode_id: int
    vpp_enrolled: bool
    vpp_programme_name: Optional[str]
    warnings: List[str]
    can_auto_switch: bool = True
    
    # Feature availability (based on Cloud credentials)
    vpp_check_available: bool = True
    auto_switch_available: bool = True
    cloud_api_enabled: bool = True


class BatteryControlSafety:
    """Safety manager for battery control operations"""
    
    # Operating mode mapping
    MODE_MAP = {
        1: "Time-of-Use",
        2: "Self-Consumption",
        3: "Emergency Backup"
    }
    
    def __init__(
        self,
        modbus_client,
        cloud_username: Optional[str] = None,
        cloud_password: Optional[str] = None,
        agate_serial: Optional[str] = None
    ):
        """
        Initialize safety manager
        
        Args:
            modbus_client: Modbus client for local register reads
            cloud_username: FranklinWH mobile app email (OPTIONAL - for enhanced safety)
            cloud_password: FranklinWH mobile app password (OPTIONAL)
            agate_serial: aGate serial number (OPTIONAL - can read from Modbus)
        """
        self.modbus_client = modbus_client
        self.cloud_enabled = bool(cloud_username and cloud_password)
        
        if self.cloud_enabled:
            self.username = cloud_username
            self.password = cloud_password
            self.gateway = agate_serial
            self.client: Optional[Client] = None
            logger.info("Cloud API safety checks ENABLED (enhanced mode)")
        else:
            logger.info("Cloud API NOT configured - using Modbus-only safety checks (default/privacy mode)")
            self.username = None
            self.password = None
            self.gateway = None
            self.client = None
        
    async def _ensure_client(self):
        """Ensure Cloud API client is initialized and authenticated (only if enabled)"""
        if not self.cloud_enabled:
            raise RuntimeError("Cloud API not configured - cannot use Cloud API methods")
            
        if self.client is None:
            fetcher = TokenFetcher(self.username, self.password)
            await fetcher.get_token()
            self.client = Client(fetcher, self.gateway)
            logger.info(f"Cloud API client initialized for gateway {self.gateway}")
    
    async def get_current_mode_modbus(self) -> tuple[int, str]:
        """
        Get current operating mode from LOCAL Modbus register 15507
        
        This is the DEFAULT method - no cloud dependency!
        
        Returns:
            tuple: (mode_id, mode_name)
                mode_id: 1=TOU, 2=Self-Consumption, 3=Emergency Backup
                mode_name: Human-readable mode name
        """
        try:
            # Read current operating mode from Model 702
            model_702 = await self.modbus_client.read_model(702)
            if model_702 and hasattr(model_702, 'ChaSt'):
                mode_id = getattr(model_702.ChaSt, 'value', None)
            else:
                mode_id = None
            mode_name = self.MODE_MAP.get(mode_id, f"Unknown ({mode_id})")
            
            logger.info(f"Current operating mode (Modbus): {mode_name} (ID: {mode_id})")
            return mode_id, mode_name
            
        except Exception as e:
            logger.error(f"Failed to read operating mode from Modbus: {e}")
            raise
    
    async def get_current_mode(self) -> tuple[int, str]:
        """
        Get current operating mode
        
        Uses Modbus by default (privacy-first, offline-capable)
        Falls back to Cloud API if configured and Modbus fails
        
        Returns:
            tuple: (mode_id, mode_name)
        """
        # Try Modbus first (default)
        try:
            return await self.get_current_mode_modbus()
        except Exception as modbus_error:
            logger.warning(f"Modbus mode read failed: {modbus_error}")
            
            # Fallback to Cloud API if enabled
            if self.cloud_enabled:
                logger.info("Falling back to Cloud API for mode detection")
                return await self.get_current_mode_cloud()
            else:
                # No fallback available
                raise
    
    async def get_current_mode_cloud(self) -> tuple[int, str]:
        """
        Get current operating mode from Cloud API (OPTIONAL enhancement)
        
        Only available if Cloud credentials configured
        
        Returns:
            tuple: (mode_id, mode_name)
        """
        await self._ensure_client()
        
        try:
            stats = await self.client.get_stats()
            mode_id = stats.current.work_mode
            mode_name = self.MODE_MAP.get(mode_id, f"Unknown ({mode_id})")
            
            logger.info(f"Current operating mode (Cloud): {mode_name} (ID: {mode_id})")
            return mode_id, mode_name
            
        except Exception as e:
            logger.error(f"Failed to get operating mode from Cloud: {e}")
            raise
    
    async def get_device_info(self) -> Dict:
        """
        Get comprehensive device information including mode, reserves, and power info
        
        Returns:
            dict: Device composite information
        """
        await self._ensure_client()
        
        try:
            device_info = await self.client.get_device_composite_info()
            logger.debug(f"Device info retrieved: {device_info.keys() if isinstance(device_info, dict) else 'N/A'}")
            return device_info
        except Exception as e:
            logger.error(f"Failed to get device info: {e}")
            raise
    
    async def get_power_status(self) -> Dict:
        """
        Get current power flow information
        
        Returns:
            dict: Power information including battery, solar, grid
        """
        await self._ensure_client()
        
        try:
            power_info = await self.client.get_power_info()
            logger.debug("Power status retrieved")
            return power_info
        except Exception as e:
            logger.error(f"Failed to get power info: {e}")
            raise
    
    async def get_vpp_status(self) -> tuple[bool, Optional[str]]:
        """
        Check if aGate is enrolled in VPP (Virtual Power Plant) program
        
        NOTE: VPP enrollment is ONLY available via Cloud API
        If Cloud API not configured, assumes NOT enrolled (safe default)
        
        Returns:
            tuple: (enrolled, programme_name)
                enrolled: True if enrolled in any VPP programme
                programme_name: Name of VPP programme if enrolled, None otherwise
        """
        if not self.cloud_enabled:
            logger.debug("Cloud API not configured - cannot check VPP enrollment (assuming not enrolled)")
            return False, None
        
        await self._ensure_client()
        
        try:
            programmes = await self.client.get_programme_info()
            
            if not programmes:
                logger.info("No VPP programmes found")
                return False, None
            
            # Check if any programme is active
            for prog in programmes:
                if prog.get("enabled") or prog.get("status") == "active":
                    prog_name = prog.get("name", "Unknown Programme")
                    logger.warning(f"VPP enrollment detected: {prog_name}")
                    return True, prog_name
            
            logger.info("VPP programmes exist but none are active")
            return False, None
            
        except Exception as e:
            logger.error(f"Failed to check VPP status: {e}")
            # Assume not enrolled if check fails (safe default)
            return False, None
    
    async def check_battery_control_safety(self) -> SafetyCheckResult:
        """
        Perform comprehensive safety check before allowing battery control
        
        Returns:
            SafetyCheckResult with safety status and warnings
        """
        warnings = []
        safe = True
        
        # Check operating mode (always available via Modbus)
        mode_id, mode_name = await self.get_current_mode()
        
        if mode_id != MODE_SELF_CONSUMPTION:  # 2 = Self-Consumption
            warnings.append(
                f"Operating mode is '{mode_name}' (should be 'Self-Consumption')"
            )
            warnings.append(
                "External battery control may conflict with built-in orchestration"
            )
            safe = False
        
        # Check VPP enrollment (only if Cloud API enabled)
        vpp_enrolled = False
        vpp_programme = None
        
        if self.cloud_enabled:
            vpp_enrolled, vpp_programme = await self.get_vpp_status()
            
            if vpp_enrolled:
                warnings.append(
                    f"System enrolled in VPP programme: '{vpp_programme}'"
                )
                warnings.append(
                    "Battery control may conflict with VPP provider commands"
                )
                safe = False
        else:
            # Cloud not configured - show informational warning
            warnings.append(
                "⚠️ VPP enrollment check: NOT AVAILABLE (Cloud credentials not configured)"
            )
            warnings.append(
                "ℹ️  To enable VPP checking, add FranklinWH Cloud credentials in Settings"
            )
        
        result = SafetyCheckResult(
            safe=safe,
            current_mode=mode_name,
            current_mode_id=mode_id,
            vpp_enrolled=vpp_enrolled,
            vpp_programme_name=vpp_programme,
            warnings=warnings,
            can_auto_switch=(mode_id in [MODE_TIME_OF_USE, MODE_EMERGENCY_BACKUP]),
            vpp_check_available=self.cloud_enabled,
            auto_switch_available=self.cloud_enabled,
            cloud_api_enabled=self.cloud_enabled
        )
        
        if safe:
            logger.info("✅ Battery control safety check PASSED")
        else:
            logger.warning(f"⚠️  Battery control safety check FAILED: {warnings}")
        
        return result
    
    async def enable_safe_battery_control_mode(self, previous_mode_id: Optional[int] = None) -> int:
        """
        Switch to Self-Consumption mode for safe battery control
        
        REQUIRES Cloud API credentials!
        
        Args:
            previous_mode_id: If provided, skip reading current mode
            
        Returns:
            int: Previous mode ID (for restoration)
            
        Raises:
            RuntimeError: If Cloud API not configured
        """
        if not self.cloud_enabled:
            raise RuntimeError(
                "Auto-mode switching requires Cloud API credentials. "
                "Please add credentials in Settings or manually change mode in FranklinWH App."
            )
        
        await self._ensure_client()
        
        # Get current mode if not provided
        if previous_mode_id is None:
            previous_mode_id, previous_mode_name = await self.get_current_mode()
        else:
            previous_mode_name = self.MODE_MAP.get(previous_mode_id, "Unknown")
        
        # Skip if already in Self-Consumption
        if previous_mode_id == MODE_SELF_CONSUMPTION:
            logger.info("Already in Self-Consumption mode")
            return previous_mode_id
        
        try:
            # Switch to Self-Consumption mode
            # Cloud API params: requestedOperatingMode, requestedSOC, reqbackupForeverFlag, reqnextWorkMode, reqdurationMinutes
            await self.client.set_mode(
                requestedOperatingMode=MODE_SELF_CONSUMPTION,
                requestedSOC=20,  # Default reserve
                reqbackupForeverFlag=0,
                reqnextWorkMode=None,
                reqdurationMinutes=None
            )
            
            logger.info(f"✅ Switched from '{previous_mode_name}' to 'Self-Consumption' for battery control")
            return previous_mode_id
            
        except Exception as e:
            logger.error(f"Failed to switch operating mode: {e}")
            raise
    
    async def restore_operating_mode(self, mode_id: int):
        """
        Restore previous operating mode
        
        Args:
            mode_id: Operating mode to restore (1=TOU, 2=Self-Consumption, 3=Emergency Backup)
        """
        await self._ensure_client()
        
        mode_name = self.MODE_MAP.get(mode_id, f"Unknown ({mode_id})")
        
        try:
            await self.client.set_mode(
                requestedOperatingMode=mode_id,
                requestedSOC=20,  # Default reserve
                reqbackupForeverFlag=0,
                reqnextWorkMode=None,
                reqdurationMinutes=None
            )
            
            logger.info(f"✅ Restored operating mode to '{mode_name}'")
            
        except Exception as e:
            logger.error(f"Failed to restore operating mode: {e}")
            raise


# Convenience function for API endpoints
async def create_safety_manager(
    modbus_client,
    cloud_username: Optional[str] = None,
    cloud_password: Optional[str] = None,
    agate_serial: Optional[str] = None
) -> BatteryControlSafety:
    """
    Create and initialize a BatteryControlSafety manager
    
    Args:
        modbus_client: Modbus client instance
        cloud_username: FranklinWH mobile app email (OPTIONAL)
        cloud_password: FranklinWH mobile app password (OPTIONAL)
        agate_serial: aGate serial number (OPTIONAL)
        
    Returns:
        Initialized BatteryControlSafety instance
    """
    manager = BatteryControlSafety(
        modbus_client,
        cloud_username,
        cloud_password,
        agate_serial
    )
    
    if manager.cloud_enabled:
        await manager._ensure_client()
        logger.info("Safety manager created with Cloud API enhancement")
    else:
        logger.info("Safety manager created (Modbus-only mode)")
    
    return manager


if __name__ == "__main__":
    # Test safety check
    import asyncio
    
    async def test():
        # Example usage
        manager = await create_safety_manager(
            cloud_username="user@example.com",
            cloud_password="password",
            agate_serial="10060006A02F24170091"
        )
        
        result = await manager.check_battery_control_safety()
        
        print(f"Safe: {result.safe}")
        print(f"Mode: {result.current_mode}")
        print(f"VPP: {result.vpp_enrolled}")
        print(f"Warnings: {result.warnings}")
        
        if not result.safe and result.can_auto_switch:
            previous = await manager.enable_safe_battery_control_mode(result.current_mode_id)
            print(f"Switched to Self-Consumption (previous: {previous})")
    
    asyncio.run(test())
