"""
FranklinWH Battery Manager - Main Entry Point

This is the main application entry point that initializes all components:
- Modbus client for communicating with the battery
- MQTT bridge for Home Assistant integration
- Web server for the management interface
- Background tasks for data polling and publishing
"""

import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# Add SQLite handler for web UI logs (initialized after config is loaded)
def init_sqlite_logging(config):
    """Initialize SQLite logging with config settings."""
    try:
        from src.log_manager import get_log_manager, SQLiteLogHandler
        
        # Get log manager with config retention days
        lm = get_log_manager(config)
        
        # Create handler
        sqlite_handler = SQLiteLogHandler(lm)
        sqlite_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(sqlite_handler)
        
        logger.info(f"SQLite logging enabled (retention: {config.log_retention_days} days)")
        return lm
    except Exception as e:
        logger.warning(f"SQLite logging not available: {e}")
        return None

# Import components
# Import models first (no dependencies)
from src.models import BatteryMode
from src.config_manager import config_manager, DeviceConfig
from src.connection_manager import ConnectionManager

# Try to import mock client (always available)
try:
    from src.mock_modbus_client import MockFranklinWHModbusClient
    MOCK_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import mock client: {e}")
    MOCK_AVAILABLE = False

# Try to import real Modbus client (requires sunspec2)
try:
    from src.modbus_client import FranklinWHModbusClient
    REAL_MODBUS_AVAILABLE = True
except ImportError as e:
    error_msg = str(e)
    if "sunspec2" in error_msg.lower():
        logger.warning("sunspec2 not installed - Live mode unavailable, Mock mode only")
        REAL_MODBUS_AVAILABLE = False
    else:
        logger.error(f"Failed to import Modbus client: {e}")
        raise

# Import remaining components
try:
    from src.mqtt_handler import HomeAssistantMQTTBridge
    from src.web_server import create_app
    MQTT_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import MQTT/Web components: {e}")
    MQTT_AVAILABLE = False
    raise


class FranklinWHApplication:
    """Main application class that orchestrates all components."""
    
    def __init__(self):
        self.connection_manager: ConnectionManager | None = None
        self.mqtt: HomeAssistantMQTTBridge | None = None
        self.web_app = None
        self.running = False
        self._tasks: list[asyncio.Task] = []
        
    async def initialize(self) -> bool:
        """Initialize all application components."""
        logger.info("Initializing FranklinWH Battery Manager...")
        
        # Load configuration
        await config_manager.load()
        config = config_manager.get()
        
        # Initialize SQLite logging with config
        init_sqlite_logging(config)
        
        # Initialize Connection Manager
        self.connection_manager = ConnectionManager()
        
        # Check if mock mode is enabled or use real client
        primary_client = None
        
        if config.mock_mode:
            logger.info("=" * 50)
            logger.info("🎭 MOCK MODE ENABLED - Using simulated device")
            logger.info("=" * 50)
            # Create Mock Client
            if MOCK_AVAILABLE:
                primary_client = MockFranklinWHModbusClient(
                    host=config.modbus.host,
                    port=config.modbus.port,
                    unit_id=config.modbus.unit_id,
                    base_address=config.modbus.base_address,
                    timeout=config.modbus.timeout,
                )
        else:
            # Initialize real Modbus client
            if not REAL_MODBUS_AVAILABLE:
                logger.error("\n" + "="*70)
                logger.error("LIVE MODE NOT AVAILABLE")
                logger.error("="*70)
                # ... (keep error docs)
                raise SystemExit(1)
            
            primary_client = FranklinWHModbusClient(
                host=config.modbus.host,
                port=config.modbus.port,
                unit_id=config.modbus.unit_id,
                base_address=config.modbus.base_address,
                timeout=config.modbus.timeout,
            )

        # Add primary device to Connection Manager and Config
        # This ensures the device persists and is recognized by the topology
        primary_device_config = DeviceConfig(
            id="default",
            name="Primary aGate",
            host=config.modbus.host,
            port=config.modbus.port,
            unit_id=config.modbus.unit_id,
            base_address=config.modbus.base_address,
            timeout=config.modbus.timeout,
            enabled=True
        )
        
        # Add to config so it's persisted and visible in topology
        config_manager.add_device(primary_device_config)
        await config_manager.save()
        
        # Add to connection manager
        self.connection_manager._clients["default"] = primary_client
        
        # Try to connect (primary)
        if not await primary_client.connect():
             logger.error("Failed to connect to Primary Modbus device")
        else:
             logger.info("Connected to Primary Modbus device")
             
             # Discover and store Model 1 info for mock mode
             try:
                 device_info = await primary_client.get_device_info()
                 if device_info:
                     config_manager.update_device_model1_info(
                         device_id="default",
                         manufacturer=device_info.manufacturer,
                         model=device_info.model,
                         serial_number=device_info.serial_number,
                         firmware_version=device_info.version
                     )
                     await config_manager.save()
                     logger.info(f"Stored device info: {device_info.manufacturer} {device_info.model} (S/N: {device_info.serial_number})")
             except Exception as e:
                 logger.warning(f"Could not store device info: {e}")

        # Determine site_id from primary device
        site_id = "default"
        if config.devices:
            primary_device = next(iter(config.devices.values()))
            site_id = primary_device.site_id
        
        # Initialize MQTT bridge (using primary client and site)
        self.mqtt = HomeAssistantMQTTBridge(
            modbus_client=primary_client,
            broker_host=config.mqtt.host,
            broker_port=config.mqtt.port,
            username=config.mqtt.username,
            password=config.mqtt.password,
            client_id=config.mqtt.client_id,
            discovery_prefix=config.mqtt.discovery_prefix,
            state_prefix=config.mqtt.state_prefix,
            site_id=site_id,
            enabled=config.mqtt.enabled,
        )
        
        # Get device info and set it on MQTT handler for discovery
        try:
            device_info = await primary_client.get_device_info()
            if device_info:
                self.mqtt.set_device_info(device_info)
                logger.info(f"Set device info for MQTT discovery: {device_info.manufacturer} {device_info.model} (FW: {device_info.version})")
        except Exception as e:
            logger.warning(f"Could not get device info for MQTT: {e}")
        
        # Start MQTT bridge
        await self.mqtt.start()
        logger.info(f"MQTT bridge started (status: {self.mqtt.status.value})")
        
        # Initialize network health monitor
        from src.network_health import NetworkHealthMonitor
        self.network_monitor = NetworkHealthMonitor(host=config.modbus.host)
        logger.info(f"Network health monitor initialized for {config.modbus.host}")
        
        # Run initial ping check (non-blocking)
        try:
            stats = await asyncio.wait_for(
                self.network_monitor.ping_check(count=5),
                timeout=10
            )
            if stats:
                logger.info(
                    f"Initial network check: {stats.quality.value} "
                    f"({stats.packet_loss:.1f}% loss, {stats.avg_ms:.1f}ms avg)"
                )
                # TODO: Show warning modal if quality is CRITICAL
            else:
                logger.warning("Initial network check failed - host may be unreachable")
        except asyncio.TimeoutError:
            logger.warning("Initial network check timed out")
        except Exception as e:
            logger.warning(f"Initial network check error: {e}")
        
        # Create web application
        self.web_app = create_app(
            connection_manager=self.connection_manager,
            mqtt_bridge=self.mqtt,
            config_manager=config_manager,
            mock_mode=config.mock_mode,
        )
        
        # Attach network monitor to web app state
        self.web_app.state.network_monitor = self.network_monitor
        
        logger.info("Application initialization complete")
        return True
    
    async def start(self) -> None:
        """Start all background tasks and the web server."""
        self.running = True
        
        # Start data publishing task (always runs, MQTT will buffer if not connected)
        if self.mqtt and self.mqtt.is_enabled:
            publish_task = asyncio.create_task(self._data_publish_loop())
            self._tasks.append(publish_task)
            logger.info("Started MQTT data publishing task")
        
        # Start Modbus keepalive/reconnect task
        if self.connection_manager:
            keepalive_task = asyncio.create_task(self._modbus_keepalive_loop())
            self._tasks.append(keepalive_task)
            logger.info("Started Modbus keepalive task")
        
        # Start web server
        import uvicorn
        config = config_manager.get()
        logger.info(f"Starting web server on http://0.0.0.0:8080")
        
        # Create uvicorn server
        server = uvicorn.Server(
            uvicorn.Config(
                self.web_app,
                host="0.0.0.0",
                port=8080,
                log_level="info",
            )
        )
        
        # Run web server (this blocks until shutdown)
        try:
            await server.serve()
        except Exception as e:
            logger.error(f"Web server error: {e}")
    
    async def stop(self) -> None:
        """Stop all tasks and cleanup."""
        if not self.running:
            return  # Already shutting down
        
        self.running = False
        logger.info("Shutting down...")
        
        # Cancel all background tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Don't wait for tasks - let them cancel async
        self._tasks = []
        
        # Disconnect from services (fire and forget)
        try:
            if self.mqtt:
                await self.mqtt.stop()
        except Exception:
            pass
        
        try:
            if self.connection_manager:
                self.connection_manager.close_all()
        except Exception:
            pass
        
        logger.info("Shutdown complete")
    
    async def _data_publish_loop(self) -> None:
        """Background loop to periodically publish data to MQTT."""
        while self.running:
            try:
                # Use default client for MQTT for now
                if self.mqtt and self.connection_manager:
                    client = await self.connection_manager.get_client("default")
                    
                    if client and client._connected:
                        # Read current data
                        results = await client.read_all()
                        
                        # Publish to MQTT
                        if results.get("battery"):
                            await self.mqtt.publish_battery_metrics(results["battery"])
                        if results.get("inverter_ac"):
                            await self.mqtt.publish_inverter_metrics(results["inverter_ac"])
                        if results.get("capacity"):
                            await self.mqtt.publish_capacity(results["capacity"])
                        if results.get("solar_pv"):
                            await self.mqtt.publish_solar_metrics(results["solar_pv"])
                        if results.get("home_loads"):
                            await self.mqtt.publish_home_loads(results["home_loads"])
                        
                        await self.mqtt.publish_connection_status(True)
                        await self.mqtt.publish_control_states(inverter_connected=True)  # PoC select entity
                    else:
                         if self.mqtt.is_connected:
                             await self.mqtt.publish_connection_status(False)
                             await self.mqtt.publish_control_states(inverter_connected=False)  # PoC select entity
                    
                await asyncio.sleep(30)  # Publish every 30 seconds
                
            except Exception as e:
                logger.error(f"Data publish error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _modbus_keepalive_loop(self) -> None:
        """Background loop to maintain Modbus connection."""
        reconnect_delay = 5
        max_reconnect_delay = 60
        
        while self.running:
            try:
                if self.connection_manager:
                    clients = self.connection_manager.get_all_clients()
                    
                    for device_id, client in clients.items():
                        if not client._connected:
                            logger.info(f"Attempting to reconnect device {device_id}...")
                            
                            # Force disconnect to clear stale connection objects
                            try:
                                await client.disconnect()
                            except Exception as e:
                                logger.debug(f"Error during forced disconnect: {e}")
                            
                            # Now try fresh connection
                            if await client.connect():
                                logger.info(f"✓ Reconnected device {device_id}")
                            else:
                                logger.debug(f"Reconnect failed for {device_id}, will retry in 10s")
                
                await asyncio.sleep(10)  # Check every 10 seconds
                    
            except Exception as e:
                logger.error(f"Modbus keepalive error: {e}")
                await asyncio.sleep(reconnect_delay)


async def main():
    """Main entry point."""
    app = FranklinWHApplication()
    shutdown_triggered = False
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig):
        nonlocal shutdown_triggered
        if shutdown_triggered:
            return  # Ignore multiple signals
        shutdown_triggered = True
        logger.info(f"Received signal {sig}, shutting down...")
        # Schedule shutdown
        asyncio.create_task(app.stop())
        # Force exit after 3 seconds
        loop = asyncio.get_event_loop()
        loop.call_later(3.0, lambda: os._exit(0))
    
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
    
    try:
        # Initialize
        if await app.initialize():
            # Run
            await app.start()
    except asyncio.CancelledError:
        logger.info("Main task cancelled")
    except Exception as e:
        logger.exception("Fatal error")
        sys.exit(1)
    finally:
        if not shutdown_triggered:
            await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
