import asyncio
import logging
from typing import Dict, Optional, List
from .modbus_client import FranklinWHModbusClient
from .config_manager import DeviceConfig

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages connections to multiple Modbus devices."""
    
    def __init__(self):
        self._clients: Dict[str, FranklinWHModbusClient] = {}
        self._lock = asyncio.Lock()
        
    async def initialize_from_config(self, device_configs: Dict[str, DeviceConfig]):
        """Initialize clients from configuration."""
        async with self._lock:
            # Close existing clients that are not in new config
            active_ids = set(device_configs.keys())
            current_ids = set(self._clients.keys())
            
            for device_id in current_ids - active_ids:
                logger.info(f"Removing device {device_id}")
                await self.remove_client(device_id)
            
            # Add or update clients
            for device_id, config in device_configs.items():
                if not config.enabled:
                    if device_id in self._clients:
                        await self.remove_client(device_id)
                    continue
                    
                if device_id not in self._clients:
                    logger.info(f"Initializing device {device_id} ({config.host}:{config.port})")
                    client = FranklinWHModbusClient(
                        host=config.host,
                        port=config.port,
                        unit_id=config.unit_id,
                        timeout=config.timeout
                    )
                    self._clients[device_id] = client
                    # Start connection in background
                    asyncio.create_task(self._connect_client(device_id, client))
    
    async def _connect_client(self, device_id: str, client: FranklinWHModbusClient):
        """Attempt to connect a client and discover device info."""
        try:
            connected = await client.connect()
            if connected:
                logger.info(f"Device {device_id} connected successfully")
                # Auto-discover device info
                await self._discover_device_info(device_id, client)
            else:
                logger.warning(f"Device {device_id} failed to connect")
        except Exception as e:
            logger.error(f"Error connecting device {device_id}: {e}")
    
    async def _discover_device_info(self, device_id: str, client: FranklinWHModbusClient):
        """Discover and store device information after connection."""
        try:
            # Import here to avoid circular imports
            from src.config_manager import config_manager
            
            # Get device info from Modbus (SunSpec Model 1)
            info = await client.get_device_info()
            if info:
                logger.info(f"Discovered device info for {device_id}: {info.manufacturer} {info.model} (S/N: {info.serial_number})")
                
                # Update config with discovered info using helper method
                updated = config_manager.update_device_model1_info(
                    device_id=device_id,
                    manufacturer=info.manufacturer,
                    model=info.model,
                    serial_number=info.serial_number,
                    firmware_version=info.version
                )
                
                if updated:
                    # Save config
                    await config_manager.save()
                    logger.info(f"Updated device config for {device_id}")
        except Exception as e:
            logger.warning(f"Could not discover device info for {device_id}: {e}")

    async def get_client(self, device_id: str = "default") -> Optional[FranklinWHModbusClient]:
        """Get a client by ID. Returns the first available if not specified."""
        if not self._clients:
            return None
            
        if device_id == "default" or not device_id:
            # Return first available client if specific one not requested/found
            # This maintains backward compatibility for dashboard
            return next(iter(self._clients.values()))
            
        return self._clients.get(device_id)

    def get_all_clients(self) -> Dict[str, FranklinWHModbusClient]:
        """Get all registered clients."""
        return self._clients.copy()

    async def add_client(self, device_config: DeviceConfig, validate: bool = True) -> bool:
        """Add a new client dynamically.
        
        Args:
            device_config: Device configuration
            validate: If True, validates device is a FranklinWH. If False, adds without validation.
        
        Returns:
            True if connected successfully, False if offline but added
        """
        async with self._lock:
            if device_config.id in self._clients:
                await self.remove_client(device_config.id)
            
            client = FranklinWHModbusClient(
                host=device_config.host,
                port=device_config.port,
                unit_id=device_config.unit_id,
                timeout=device_config.timeout
            )
            
            connected = await client.connect()
            if not connected:
                # Close possibly open socket just in case
                client.close()
                raise ConnectionError(f"Failed to connect to {device_config.host}:{device_config.port}")
                
            # Validate device (if requested)
            if validate:
                try:
                    info = await client.get_device_info()
                    if not info or "FranklinWH" not in info.manufacturer:
                        logger.error(f"Device validation failed: Manufacturer is '{info.manufacturer if info else 'None'}'")
                        client.close()
                        raise ValueError(f"Device is not a FranklinWH aGate (Manufacturer: {info.manufacturer if info else 'Unknown'})")
                except Exception as e:
                    logger.error(f"Validation error: {e}")
                    client.close()
                    raise
                
            self._clients[device_config.id] = client
            return True

    async def remove_client(self, device_id: str):
        """Remove and disconnect a client."""
        if device_id in self._clients:
            client = self._clients[device_id]
            client.close()
            del self._clients[device_id]

    def close_all(self):
        """Close all connections."""
        for client in self._clients.values():
            client.close()
