"""
MQTT handler for Home Assistant discovery and state publishing.
Creates entities for battery metrics, inverter status, and control.

Features:
- Non-blocking startup (app works even without MQTT)
- Automatic background reconnection
- Manual enable/disable control
- Connection status tracking (ONLINE, OFFLINE, FAILED, DISABLED)
"""

import asyncio
import json
import logging
from typing import Dict, Optional, Any, Callable
from dataclasses import asdict
from enum import Enum

try:
    from asyncio_mqtt import Client, MqttError
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logging.warning("asyncio-mqtt not available")

from src.models import (
    BatteryMode,
    BatteryMetrics,
    InverterACMetrics,
    DERCapacity,
    DeviceInfo,
)

# TYPE_CHECKING import to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.modbus_client import FranklinWHModbusClient


class MQTTStatus(str, Enum):
    """MQTT connection status."""
    DISABLED = "disabled"      # MQTT explicitly disabled by user
    OFFLINE = "offline"        # Not connected, will retry
    ONLINE = "online"          # Connected and working
    FAILED = "failed"          # Connection failed, retries exhausted
    CONNECTING = "connecting"  # Currently attempting connection


class HomeAssistantMQTTBridge:
    """
    Bridges FranklinWH Modbus data to Home Assistant via MQTT discovery.
    
    Connection behavior:
    - Startup: Non-blocking, starts in OFFLINE state
    - Automatic: Background task retries connection every 30s
    - Manual: Can be enabled/disabled via API at runtime
    - Fault tolerance: MQTT errors never crash the main application
    """
    
    def __init__(
        self,
        modbus_client: "FranklinWHModbusClient",
        broker_host: str = "192.168.0.109",
        broker_port: int = 1883,
        username: str = "",
        password: str = "",
        client_id: str = "franklinwh_bridge",
        discovery_prefix: str = "homeassistant",
        state_prefix: str = "franklinwh",
        enabled: bool = True,  # Can be disabled on startup
    ):
        self.modbus = modbus_client
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.discovery_prefix = discovery_prefix
        self.state_prefix = state_prefix
        
        self._client: Optional[Client] = None
        self._status = MQTTStatus.DISABLED if not enabled else MQTTStatus.OFFLINE
        self._logger = logging.getLogger(__name__)
        
        # Background tasks
        self._enabled = enabled
        self._retry_task: Optional[asyncio.Task] = None
        self._running = False
        self._retry_interval = 30  # seconds between retries
        self._max_retries = None  # None = retry forever
        self._retry_count = 0
        
        # Entity IDs for cleanup
        self._entities: Dict[str, str] = {}
        
        # Device info for HA
        self._device_info: Optional[DeviceInfo] = None
        
        # Track if we've ever connected (for "first time" behavior)
        self._has_ever_connected = False
        
        # Callback for status changes
        self._status_callbacks: List[Callable[[MQTTStatus], None]] = []
    
    @property
    def status(self) -> MQTTStatus:
        """Get current MQTT connection status."""
        return self._status
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._status == MQTTStatus.ONLINE
    
    @property
    def is_enabled(self) -> bool:
        """Check if MQTT is enabled."""
        return self._enabled
    
    def add_status_callback(self, callback: Callable[[MQTTStatus], None]) -> None:
        """Add callback for status changes."""
        self._status_callbacks.append(callback)
    
    def remove_status_callback(self, callback: Callable[[MQTTStatus], None]) -> None:
        """Remove status callback."""
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)
    
    async def _set_status(self, status: MQTTStatus) -> None:
        """Set status and notify callbacks."""
        if self._status != status:
            old_status = self._status
            self._status = status
            self._logger.info(f"MQTT status changed: {old_status.value} -> {status.value}")
            
            for callback in self._status_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(status)
                    else:
                        callback(status)
                except Exception as e:
                    self._logger.error(f"Status callback error: {e}")
    
    async def start(self) -> None:
        """
        Start MQTT bridge (non-blocking).
        Begins background retry loop if enabled.
        """
        if not MQTT_AVAILABLE:
            self._logger.warning("MQTT library not available, bridge disabled")
            await self._set_status(MQTTStatus.FAILED)
            return
        
        if not self._enabled:
            self._logger.info("MQTT bridge is disabled")
            await self._set_status(MQTTStatus.DISABLED)
            return
        
        self._running = True
        self._logger.info("Starting MQTT bridge (non-blocking)")
        
        # Start background retry loop
        self._retry_task = asyncio.create_task(self._retry_loop())
    
    async def stop(self) -> None:
        """Stop MQTT bridge and cleanup."""
        self._running = False
        self._enabled = False
        
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
            self._retry_task = None
        
        await self.disconnect()
        await self._set_status(MQTTStatus.DISABLED)
    
    async def enable(self) -> bool:
        """
        Enable MQTT bridge (can be called at runtime).
        
        Returns:
            True if bridge was enabled (may not be connected yet)
        """
        if self._enabled:
            self._logger.debug("MQTT bridge already enabled")
            return True
        
        self._enabled = True
        self._retry_count = 0
        self._logger.info("MQTT bridge enabled")
        
        # Start retry loop if not running
        if not self._retry_task or self._retry_task.done():
            self._running = True
            self._retry_task = asyncio.create_task(self._retry_loop())
        
        return True
    
    async def disable(self) -> None:
        """Disable MQTT bridge (can be called at runtime)."""
        self._enabled = False
        await self.disconnect()
        await self._set_status(MQTTStatus.DISABLED)
        self._logger.info("MQTT bridge disabled")
    
    async def _retry_loop(self) -> None:
        """Background loop to maintain connection with retry logic."""
        while self._running and self._enabled:
            try:
                # Check if we need to connect
                if self._status not in (MQTTStatus.ONLINE, MQTTStatus.CONNECTING):
                    await self._set_status(MQTTStatus.CONNECTING)
                    
                    if await self._connect_once():
                        self._has_ever_connected = True
                        self._retry_count = 0
                        await self._set_status(MQTTStatus.ONLINE)
                        
                        # Setup entities on first connect
                        if self._device_info:
                            await self.setup_entities(self._device_info)
                        
                        # Start message processing
                        await self._process_messages()
                    else:
                        self._retry_count += 1
                        if self._max_retries and self._retry_count >= self._max_retries:
                            self._logger.error(f"MQTT max retries ({self._max_retries}) reached")
                            await self._set_status(MQTTStatus.FAILED)
                            break
                        else:
                            await self._set_status(MQTTStatus.OFFLINE)
                
                # Wait before next retry
                await asyncio.sleep(self._retry_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"MQTT retry loop error: {e}")
                await self._set_status(MQTTStatus.OFFLINE)
                await asyncio.sleep(self._retry_interval)
    
    async def _connect_once(self) -> bool:
        """Attempt a single connection."""
        try:
            auth = {}
            if self.username:
                auth["username"] = self.username
                auth["password"] = self.password
            
            self._client = Client(
                hostname=self.broker_host,
                port=self.broker_port,
                client_id=self.client_id,
                **auth,
            )
            
            await self._client.connect()
            self._logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            
            # Subscribe to command topics
            await self._subscribe_commands()
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            self._logger.warning(f"MQTT connection failed: {error_msg}")
            # Provide more helpful error messages for common issues
            if "Not authorized" in error_msg or "not authorised" in error_msg.lower():
                self._logger.error("MQTT authentication failed - check username/password")
            elif "Connection refused" in error_msg:
                self._logger.error(f"MQTT broker refused connection at {self.broker_host}:{self.broker_port}")
            elif "Name or service not known" in error_msg or "getaddrinfo failed" in error_msg:
                self._logger.error(f"Cannot resolve MQTT broker hostname: {self.broker_host}")
            self._client = None
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self._client:
            try:
                await self._client.disconnect()
            except Exception as e:
                self._logger.debug(f"Error disconnecting MQTT: {e}")
            finally:
                self._client = None
        
        if self._status == MQTTStatus.ONLINE:
            await self._set_status(MQTTStatus.OFFLINE)
    
    async def _process_messages(self) -> None:
        """Process incoming MQTT messages until disconnected."""
        if not self._client:
            return
        
        try:
            async with self._client.messages() as messages:
                async for message in messages:
                    try:
                        topic = message.topic.value
                        payload = message.payload.decode()
                        self._logger.debug(f"Received: {topic} = {payload}")
                        await self._handle_command(topic, payload)
                    except Exception as e:
                        self._logger.error(f"Error processing message: {e}")
        except MqttError as e:
            self._logger.warning(f"MQTT connection lost: {e}")
            await self._set_status(MQTTStatus.OFFLINE)
        except Exception as e:
            self._logger.error(f"MQTT message loop error: {e}")
            await self._set_status(MQTTStatus.OFFLINE)
    
    def _get_device_payload(self, ha_device_name: Optional[str] = None) -> Dict[str, Any]:
        """Get device payload for HA discovery."""
        # Use provided name or default
        display_name = ha_device_name or "FranklinWH Battery"
        
        if self._device_info:
            # If using default name, append last 4 of serial for uniqueness
            if ha_device_name is None and self._device_info.serial_number:
                short_serial = self._device_info.serial_number[-4:]
                display_name = f"FranklinWH {self._device_info.model} {short_serial}"
            return {
                "identifiers": [f"franklinwh_{self._device_info.serial_number}"],
                "name": display_name,
                "manufacturer": self._device_info.manufacturer,
                "model": self._device_info.model,
                "sw_version": self._device_info.version,
            }
        return {
            "identifiers": ["franklinwh_battery"],
            "name": display_name,
            "manufacturer": "FranklinWH",
            "model": "aPower",
        }
    
    async def setup_entities(self, device_info: Optional[DeviceInfo] = None, mqtt_config: Optional[Any] = None) -> None:
        """Setup Home Assistant discovery entities with configurable options.
        
        Args:
            device_info: Device information for HA device registry
            mqtt_config: MQTTConfig with entity selection options (optional)
        """
        if not self._client or self._status != MQTTStatus.ONLINE:
            self._logger.debug("Cannot setup entities: not connected")
            return
        
        if device_info:
            self._device_info = device_info
        
        # Extract config options with defaults
        if mqtt_config:
            unique_prefix = getattr(mqtt_config, 'unique_id_prefix', 'franklinwh')
            ha_device_name = getattr(mqtt_config, 'ha_device_name', None)
            retain = getattr(mqtt_config, 'retain_discovery', True)
            publish_battery = getattr(mqtt_config, 'publish_battery', True)
            publish_inverter = getattr(mqtt_config, 'publish_inverter', True)
            publish_solar = getattr(mqtt_config, 'publish_solar', True)
            publish_home_loads = getattr(mqtt_config, 'publish_home_loads', True)
            publish_capacity = getattr(mqtt_config, 'publish_capacity', True)
            publish_controls = getattr(mqtt_config, 'publish_controls', True)
        else:
            unique_prefix = 'franklinwh'
            ha_device_name = None
            retain = True
            publish_battery = True
            publish_inverter = True
            publish_solar = True
            publish_home_loads = True
            publish_capacity = True
            publish_controls = True
        
        device = self._get_device_payload(ha_device_name)
        
        # Build entity list based on config
        entities = []
        
        if publish_battery:
            entities.extend([
                {"type": "sensor", "name": f"{unique_prefix}_soc", "config": {
                    "name": "State of Charge",
                    "state_topic": f"{self.state_prefix}/battery/soc",
                    "unit_of_measurement": "%",
                    "device_class": "battery",
                    "state_class": "measurement",
                    "value_template": "{{ value | float | round(1) }}",
                    "icon": "mdi:battery",
                }},
                {"type": "sensor", "name": f"{unique_prefix}_soh", "config": {
                    "name": "State of Health",
                    "state_topic": f"{self.state_prefix}/battery/soh",
                    "unit_of_measurement": "%",
                    "state_class": "measurement",
                    "value_template": "{{ value | float | round(1) }}",
                    "icon": "mdi:heart-pulse",
                }},
                {"type": "sensor", "name": f"{unique_prefix}_temperature", "config": {
                    "name": "Battery Temperature",
                    "state_topic": f"{self.state_prefix}/battery/temperature",
                    "unit_of_measurement": "°C",
                    "device_class": "temperature",
                    "state_class": "measurement",
                    "icon": "mdi:thermometer",
                }},
                {"type": "sensor", "name": f"{unique_prefix}_cycles", "config": {
                    "name": "Cycle Count",
                    "state_topic": f"{self.state_prefix}/battery/cycles",
                    "state_class": "total_increasing",
                    "icon": "mdi:counter",
                }},
            ])
        
        if publish_inverter:
            entities.extend([
                {"type": "sensor", "name": f"{unique_prefix}_power", "config": {
                    "name": "Power",
                    "state_topic": f"{self.state_prefix}/inverter/power",
                    "unit_of_measurement": "W",
                    "device_class": "power",
                    "state_class": "measurement",
                    "icon": "mdi:flash",
                }},
                {"type": "sensor", "name": f"{unique_prefix}_voltage", "config": {
                    "name": "Voltage",
                    "state_topic": f"{self.state_prefix}/inverter/voltage",
                    "unit_of_measurement": "V",
                    "device_class": "voltage",
                    "state_class": "measurement",
                    "icon": "mdi:lightning-bolt",
                }},
                {"type": "sensor", "name": f"{unique_prefix}_current", "config": {
                    "name": "Current",
                    "state_topic": f"{self.state_prefix}/inverter/current",
                    "unit_of_measurement": "A",
                    "device_class": "current",
                    "state_class": "measurement",
                    "icon": "mdi:current-ac",
                }},
                {"type": "sensor", "name": f"{unique_prefix}_frequency", "config": {
                    "name": "Frequency",
                    "state_topic": f"{self.state_prefix}/inverter/frequency",
                    "unit_of_measurement": "Hz",
                    "device_class": "frequency",
                    "state_class": "measurement",
                    "icon": "mdi:sine-wave",
                }},
            ])
        
        if publish_solar:
            entities.extend([
                {"type": "sensor", "name": f"{unique_prefix}_solar_power", "config": {
                    "name": "Solar Power",
                    "state_topic": f"{self.state_prefix}/solar/output_power",
                    "unit_of_measurement": "W",
                    "device_class": "power",
                    "state_class": "measurement",
                    "icon": "mdi:solar-power",
                }},
                {"type": "sensor", "name": f"{unique_prefix}_solar_energy", "config": {
                    "name": "Solar Energy",
                    "state_topic": f"{self.state_prefix}/solar/output_energy",
                    "unit_of_measurement": "Wh",
                    "device_class": "energy",
                    "state_class": "total_increasing",
                    "icon": "mdi:solar-panel",
                }},
            ])
        
        if publish_home_loads:
            entities.extend([
                {"type": "sensor", "name": f"{unique_prefix}_home_loads", "config": {
                    "name": "Home Loads",
                    "state_topic": f"{self.state_prefix}/home_loads/home_loads_w",
                    "unit_of_measurement": "W",
                    "device_class": "power",
                    "state_class": "measurement",
                    "icon": "mdi:home-lightning-bolt",
                }},
                {"type": "sensor", "name": f"{unique_prefix}_pv_output", "config": {
                    "name": "PV Output",
                    "state_topic": f"{self.state_prefix}/home_loads/pv_output_w",
                    "unit_of_measurement": "W",
                    "device_class": "power",
                    "state_class": "measurement",
                    "icon": "mdi:solar-panel-large",
                }},
            ])
        
        if publish_capacity:
            entities.extend([
                {"type": "sensor", "name": f"{unique_prefix}_max_charge", "config": {
                    "name": "Max Charge Power",
                    "state_topic": f"{self.state_prefix}/capacity/max_charge_w",
                    "unit_of_measurement": "W",
                    "device_class": "power",
                    "icon": "mdi:arrow-down-bold",
                }},
                {"type": "sensor", "name": f"{unique_prefix}_max_discharge", "config": {
                    "name": "Max Discharge Power",
                    "state_topic": f"{self.state_prefix}/capacity/max_discharge_w",
                    "unit_of_measurement": "W",
                    "device_class": "power",
                    "icon": "mdi:arrow-up-bold",
                }},
            ])
        
        # Always add status sensors
        entities.extend([
            {"type": "binary_sensor", "name": f"{unique_prefix}_connected", "config": {
                "name": "Connected",
                "state_topic": f"{self.state_prefix}/status/connected",
                "payload_on": "true",
                "payload_off": "false",
                "device_class": "connectivity",
            }},
            {"type": "sensor", "name": f"{unique_prefix}_mqtt_status", "config": {
                "name": "MQTT Status",
                "state_topic": f"{self.state_prefix}/status/mqtt",
                "icon": "mdi:network-outline",
            }},
        ])
        
        # Publish discovery messages
        for entity in entities:
            await self._publish_discovery(entity["type"], entity["name"], entity["config"], device, retain)
        
        self._logger.info(f"Published {len(entities)} discovery entities")
    
    async def _publish_discovery(self, entity_type: str, name: str, config: Dict, device: Dict, retain: bool = True) -> None:
        """Publish a discovery message for an entity."""
        topic = f"{self.discovery_prefix}/{entity_type}/{name}/config"
        
        payload = {
            **config,
            "unique_id": name,
            "device": device,
        }
        
        if entity_type == "sensor" and "state_class" in config:
            payload["availability_topic"] = f"{self.state_prefix}/status/connected"
            payload["payload_available"] = "true"
            payload["payload_not_available"] = "false"
        
        await self._publish(topic, json.dumps(payload), retain=retain)
        self._entities[name] = topic
    
    async def _subscribe_commands(self) -> None:
        """Subscribe to command topics."""
        if not self._client:
            return
        
        try:
            mode_topic = f"{self.state_prefix}/mode/set"
            await self._client.subscribe(mode_topic)
            self._logger.debug(f"Subscribed to {mode_topic}")
        except Exception as e:
            self._logger.error(f"Error subscribing to commands: {e}")
    
    async def _handle_command(self, topic: str, payload: str) -> None:
        """Handle incoming command."""
        if "/mode/set" in topic:
            try:
                mode = int(payload)
                await self.modbus.set_battery_mode(BatteryMode(mode))
                self._logger.info(f"Set battery mode to {mode}")
            except Exception as e:
                self._logger.error(f"Failed to set mode: {e}")
    
    async def publish_state(self, subtopic: str, value: Any) -> None:
        """Publish a state value."""
        if not self.is_connected:
            return
        
        topic = f"{self.state_prefix}/{subtopic}"
        if isinstance(value, (dict, list)):
            payload = json.dumps(value)
        else:
            payload = str(value)
        await self._publish(topic, payload)
    
    async def _publish(self, topic: str, payload: str, retain: bool = False) -> None:
        """Publish a message."""
        if self._client and self.is_connected:
            try:
                await self._client.publish(topic, payload, retain=retain)
            except Exception as e:
                self._logger.debug(f"Publish error: {e}")
    
    async def publish_battery_metrics(self, metrics: BatteryMetrics) -> None:
        """Publish battery metrics."""
        if not self.is_connected:
            return
        
        if metrics.state_of_charge_percent is not None:
            await self.publish_state("battery/soc", metrics.state_of_charge_percent)
        if metrics.state_of_health_percent is not None:
            await self.publish_state("battery/soh", metrics.state_of_health_percent)
        if metrics.temperature_c is not None:
            await self.publish_state("battery/temperature", metrics.temperature_c)
        if metrics.cycle_count is not None:
            await self.publish_state("battery/cycles", metrics.cycle_count)
        if metrics.rated_energy_wh is not None:
            await self.publish_state("battery/rated_energy", metrics.rated_energy_wh)
        if metrics.available_energy_wh is not None:
            await self.publish_state("battery/available_energy", metrics.available_energy_wh)
    
    async def publish_inverter_metrics(self, metrics: InverterACMetrics) -> None:
        """Publish inverter metrics."""
        if not self.is_connected:
            return
        
        if metrics.power_w is not None:
            await self.publish_state("inverter/power", metrics.power_w)
        if metrics.voltage_v is not None:
            await self.publish_state("inverter/voltage", metrics.voltage_v)
        if metrics.current_a is not None:
            await self.publish_state("inverter/current", metrics.current_a)
        if metrics.frequency_hz is not None:
            await self.publish_state("inverter/frequency", metrics.frequency_hz)
        if metrics.power_factor is not None:
            await self.publish_state("inverter/power_factor", metrics.power_factor)
        if metrics.apparent_power_va is not None:
            await self.publish_state("inverter/apparent_power", metrics.apparent_power_va)
        if metrics.reactive_power_var is not None:
            await self.publish_state("inverter/reactive_power", metrics.reactive_power_var)
    
    async def publish_capacity(self, capacity: DERCapacity) -> None:
        """Publish capacity info."""
        if not self.is_connected:
            return
        
        if capacity.max_charge_w is not None:
            await self.publish_state("capacity/max_charge", capacity.max_charge_w)
        if capacity.max_discharge_w is not None:
            await self.publish_state("capacity/max_discharge", capacity.max_discharge_w)
    
    async def publish_connection_status(self, connected: bool) -> None:
        """Publish connection status."""
        await self.publish_state("status/connected", "true" if connected else "false")
        await self.publish_state("status/mqtt", self._status.value)
