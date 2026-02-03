"""
Background task handler for FranklinWH-specific register extensions.
This module provides the extension loop that publishes FranklinWH-specific
data and handles control operations.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mqtt_handler import HomeAssistantMQTTBridge
    from modbus_client import FranklinWHModbusClient

logger = logging.getLogger(__name__)


class FranklinWHExtensionTask:
    """
    Background task manager for FranklinWH-specific extensions.
    Handles polling and publishing of proprietary registers (15000+ range).
    """
    
    def __init__(
        self,
        modbus_client: "FranklinWHModbusClient",
        mqtt_bridge: "HomeAssistantMQTTBridge",
        interval: float = 5.0
    ):
        self.modbus = modbus_client
        self.mqtt = mqtt_bridge
        self.interval = interval
        self.running = False
        self._task: asyncio.Task | None = None
    
    async def start(self) -> None:
        """Start the extension background task."""
        if self._task is not None:
            logger.warning("Extension task already running")
            return
        
        self.running = True
        self._task = asyncio.create_task(self._extension_loop())
        logger.info("FranklinWH extension task started")
    
    async def stop(self) -> None:
        """Stop the extension background task."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("FranklinWH extension task stopped")
    
    async def _extension_loop(self) -> None:
        """Background task for FranklinWH-specific registers."""
        # Import here to avoid circular imports
        from modbus_client_franklinwh import FranklinWHRegisterMap
        
        # Initialize register map
        register_map = FranklinWHRegisterMap(self.modbus)
        
        while self.running:
            try:
                # Read all extension metrics
                metrics = await register_map.read_all_metrics()
                
                # Publish operating mode
                if metrics.operating_mode is not None:
                    mode_text = await register_map.get_operating_mode_text(metrics.operating_mode)
                    await self.mqtt.publish_state("extensions/operating_mode", {
                        "mode": mode_text,
                        "raw": metrics.operating_mode
                    })
                
                # Publish reserve SOC values
                if metrics.reserve_soc is not None:
                    await self.mqtt.publish_state("extensions/reserve_soc", metrics.reserve_soc)
                
                if metrics.reserve_soc_2 is not None:
                    # Handle signed value conversion
                    soc_2 = metrics.reserve_soc_2 if metrics.reserve_soc_2 <= 32767 else metrics.reserve_soc_2 - 65536
                    await self.mqtt.publish_state("extensions/reserve_soc_2", soc_2)
                
                # Publish raw metrics with scaling
                if metrics.soc_raw is not None:
                    await self.mqtt.publish_state("extensions/soc_raw", {
                        "raw": metrics.soc_raw,
                        "scaled": round(metrics.soc_raw * 0.1, 1)
                    })
                
                if metrics.power_raw is not None:
                    # Handle signed power value
                    power = metrics.power_raw if metrics.power_raw <= 32767 else metrics.power_raw - 65536
                    await self.mqtt.publish_state("extensions/power_raw", {
                        "raw": metrics.power_raw,
                        "scaled": power
                    })
                
                if metrics.soh_raw is not None:
                    await self.mqtt.publish_state("extensions/soh_raw", {
                        "raw": metrics.soh_raw,
                        "scaled": round(metrics.soh_raw * 0.1, 1)
                    })
                
                if metrics.status_flags is not None:
                    await self.mqtt.publish_state("extensions/status_flags", {
                        "raw": metrics.status_flags,
                        "binary": format(metrics.status_flags, '016b')
                    })
                
                # Wait for next iteration
                await asyncio.sleep(self.interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"FranklinWH extension loop error: {e}")
                await asyncio.sleep(self.interval * 2)  # Wait longer on error


async def franklinwh_extension_loop(self) -> None:
    """
    Background task method for FranklinWH-specific registers.
    This is a compatibility wrapper that can be used as a method
    in the main application class.
    """
    while self.running:
        try:
            # Publish extension data using the dedicated handler
            await self.mqtt.publish_franklinwh_extensions()
            
            # Short interval for controls
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"FranklinWH extension loop error: {e}")
            await asyncio.sleep(10)
