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

# Import components
# Import models first (no dependencies)
from src.models import BatteryMode
from src.config_manager import config_manager

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
        self.modbus: FranklinWHModbusClient | None = None
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
        
        # Check if mock mode is enabled
        if config.mock_mode:
            logger.info("=" * 50)
            logger.info("🎭 MOCK MODE ENABLED - Using simulated device")
            logger.info("=" * 50)
            self.modbus = MockFranklinWHModbusClient(
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
                logger.error("sunspec2 library is required for live mode but not installed.")
                logger.error("")
                logger.error("To install:")
                logger.error("  source venv/bin/activate")
                logger.error("  pip install pysunspec2")
                logger.error("")
                logger.error("Then run:")
                logger.error("  ./run.sh")
                logger.error("")
                logger.error("Or run in mock mode:")
                logger.error("  ./run-mock.sh")
                logger.error("="*70 + "\n")
                raise SystemExit(1)
            
            self.modbus = FranklinWHModbusClient(
                host=config.modbus.host,
                port=config.modbus.port,
                unit_id=config.modbus.unit_id,
                base_address=config.modbus.base_address,
                timeout=config.modbus.timeout,
            )
        
        # Try to connect to Modbus
        if not await self.modbus.connect():
            logger.error("Failed to connect to Modbus device")
            # Continue anyway - will retry in background
        else:
            logger.info("Connected to Modbus device")
            # Get initial device info
            device_info = await self.modbus.get_device_info()
            if device_info:
                logger.info(f"Device: {device_info.manufacturer} {device_info.model}")
        
        # Initialize MQTT bridge (non-blocking startup)
        self.mqtt = HomeAssistantMQTTBridge(
            modbus_client=self.modbus,
            broker_host=config.mqtt.host,
            broker_port=config.mqtt.port,
            username=config.mqtt.username,
            password=config.mqtt.password,
            client_id=config.mqtt.client_id,
            discovery_prefix=config.mqtt.discovery_prefix,
            state_prefix=config.mqtt.state_prefix,
            enabled=True,  # Start enabled, will retry in background
        )
        
        # Start MQTT bridge (non-blocking - will retry in background)
        await self.mqtt.start()
        logger.info(f"MQTT bridge started (status: {self.mqtt.status.value})")
        
        # Setup entities if already connected, or they'll be set up on connect
        if self.mqtt.is_connected:
            device_info = await self.modbus.get_device_info() if self.modbus else None
            await self.mqtt.setup_entities(device_info)
        
        # Create web application
        self.web_app = create_app(
            modbus_client=self.modbus,
            mqtt_bridge=self.mqtt,
            config_manager=config_manager,
            mock_mode=config.mock_mode,
        )
        
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
        if self.modbus:
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
            if self.modbus:
                await self.modbus.disconnect()
        except Exception:
            pass
        
        logger.info("Shutdown complete")
    
    async def _data_publish_loop(self) -> None:
        """Background loop to periodically publish data to MQTT."""
        while self.running:
            try:
                if self.mqtt and self.modbus:
                    # Read current data
                    results = await self.modbus.read_all()
                    
                    # Publish to MQTT
                    if results.get("battery"):
                        await self.mqtt.publish_battery_metrics(results["battery"])
                    if results.get("inverter_ac"):
                        await self.mqtt.publish_inverter_metrics(results["inverter_ac"])
                    if results.get("capacity"):
                        await self.mqtt.publish_capacity(results["capacity"])
                    
                    await self.mqtt.publish_connection_status(True)
                    
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
                if self.modbus and not self.modbus._connected:
                    logger.info("Attempting to reconnect to Modbus...")
                    if await self.modbus.connect():
                        logger.info("Reconnected to Modbus device")
                        reconnect_delay = 5  # Reset delay
                    else:
                        # Exponential backoff
                        reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                        logger.warning(f"Reconnect failed, retrying in {reconnect_delay}s...")
                        await asyncio.sleep(reconnect_delay)
                else:
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
