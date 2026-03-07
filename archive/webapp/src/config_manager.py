"""
Configuration manager for persistent settings.
Handles user preferences, widget enablement, and UI customization.
Supports environment variable overrides and .env file loading.
"""

import json
import os
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field, replace
from datetime import datetime


# Try to load python-dotenv if available
try:
    from dotenv import load_dotenv
    # Load .env file if it exists
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


@dataclass
class WidgetConfig:
    """Configuration for a dashboard widget."""
    enabled: bool = True
    position: int = 0
    refresh_interval: int = 30  # seconds
    color: str = "#3b82f6"  # default blue
    expanded: bool = True
    title: str = "Widget"
    icon: str = "fa-cube"


@dataclass
class ThemeConfig:
    """UI theme configuration."""
    mode: str = "auto"  # light, dark, auto
    primary_color: str = "#3b82f6"
    secondary_color: str = "#10b981"
    accent_color: str = "#f59e0b"
    background_color: str = "#ffffff"
    surface_color: str = "#f3f4f6"
    text_color: str = "#111827"


@dataclass
class ModbusConfig:
    """Modbus configuration (Legacy/Single Device)."""
    host: str = "192.168.0.110"
    port: int = 502
    unit_id: int = 1
    base_address: int = 40001
    timeout: int = 3

@dataclass
class SiteConfig:
    """Configuration for a site (location) with one or more aGates."""
    id: str  # Unique site identifier
    name: str  # Display name
    description: str = ""  # Optional description
    is_local: bool = True  # True = local network, False = remote/cloud
    # Connection settings for remote sites
    remote_host: str = ""  # For remote sites
    remote_port: int = 502
    # Metadata
    created_at: str = ""  # ISO timestamp
    updated_at: str = ""  # ISO timestamp


@dataclass
class DeviceConfig:
    """Configuration for a single FranklinWH aGate device."""
    id: str
    name: str
    host: str
    port: int = 502
    unit_id: int = 1
    base_address: int = 40001
    timeout: int = 3
    enabled: bool = True
    description: str = ""  # User description for this aGate
    site_id: str = "default"  # Link to SiteConfig
    
    # SunSpec Model 1 - Device Information (persisted after discovery)
    # These are read once and stored to avoid repeated Modbus reads
    manufacturer: str = ""  # Mn - Manufacturer
    model: str = ""  # Md - Model
    serial_number: str = ""  # SN - Serial Number
    firmware_version: str = ""  # Vr - Version
    device_address: int = 0  # DA - Device Address (unit ID confirmed)
    
    # Discovery metadata
    last_connected: str = ""  # ISO timestamp
    first_discovered: str = ""  # ISO timestamp
    
    # MQTT Publishing state
    mqtt_publish_enabled: bool = True  # Whether to publish this device to MQTT
    mqtt_publish_state: str = "setup"  # setup, publishing, not_publishing, error
    
    @property
    def display_name(self) -> str:
        """Generate display name from Model 1 info."""
        if self.model and self.serial_number:
            short_serial = self.serial_number[-4:] if len(self.serial_number) >= 4 else self.serial_number
            return f"{self.model} {short_serial}"
        return self.name
    
    @property
    def unique_id_base(self) -> str:
        """Generate unique ID base for this device."""
        if self.serial_number and self.serial_number != "Unknown":
            serial_short = self.serial_number[-8:] if len(self.serial_number) >= 8 else self.serial_number
            return f"franklinwh_{serial_short}"
        return f"franklinwh_{self.id}"

@dataclass
class MQTTConfig:
    """MQTT configuration with Home Assistant discovery options."""
    # Broker settings
    host: str = "localhost"
    port: int = 1883
    username: str = ""
    password: str = ""
    
    # Client settings
    client_id: str = "franklinwh_bridge"
    enabled: bool = False
    qos: int = 0  # MQTT QoS level (0, 1, or 2)
    
    # Site Configuration - which site this MQTT instance publishes
    site_name: str = "Home"  # Display name for the site
    site_id: str = "default"  # Publish devices from this site
    site_description: str = ""  # Optional site description
    is_remote_site: bool = False  # Whether this is a remote site
    
    # Home Assistant Discovery settings
    discovery_prefix: str = "homeassistant"  # HA discovery topic prefix
    state_prefix: str = "franklinwh"  # State topic prefix
    ha_device_name: str = ""  # Override device name in HA
    unique_id_prefix: str = "franklinwh"  # Prefix for unique IDs
    retain_discovery: bool = True  # Retain discovery messages
    
    # Device selection - which devices to publish (empty = all enabled)
    # Format: ["device_id_1", "device_id_2"] 
    publish_device_ids: List[str] = field(default_factory=list)
    # Per-device publish flags (device_id -> bool)
    publish_devices: Dict[str, bool] = field(default_factory=dict)
    
    # Entity selection - which entity types to publish
    publish_battery: bool = True
    publish_inverter: bool = True
    publish_solar: bool = True
    publish_home_loads: bool = True
    publish_capacity: bool = True
    publish_controls: bool = True  # Mode, reserve SOC controls


@dataclass
class AppConfig:
    """Application configuration."""
    # Sites (locations) with one or more aGates
    sites: Dict[str, SiteConfig] = field(default_factory=lambda: {
        "default": SiteConfig(id="default", name="Home", description="Default local site", is_local=True)
    })
    
    # aGate devices (linked to sites)
    devices: Dict[str, DeviceConfig] = field(default_factory=dict)
    
    # Legacy single-device config (for migration)
    modbus: ModbusConfig = field(default_factory=ModbusConfig)
    
    # MQTT configuration
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    
    # UI configuration
    theme: ThemeConfig = field(default_factory=ThemeConfig)
    refresh_interval: int = 5
    auto_refresh: bool = True
    log_level: str = "INFO"
    log_retention_days: int = 30  # Keep logs for 30 days by default
    mock_mode: bool = False
    widgets: Dict[str, WidgetConfig] = field(default_factory=lambda: {
        "soc": WidgetConfig(title="State of Charge", icon="fa-battery-full", color="#3b82f6", position=0),
        "power": WidgetConfig(title="Power", icon="fa-bolt", color="#f59e0b", position=1),
        "health": WidgetConfig(title="System Health", icon="fa-heartbeat", color="#10b981", position=2),
        "mode": WidgetConfig(title="Operating Mode", icon="fa-sliders-h", color="#8b5cf6", position=3),
    })
    # Enabled SunSpec models
    enabled_models: List[int] = field(default_factory=lambda: [
        1,    # Common
        701,  # DER AC Measurements
        702,  # DER DC Measurements
        703,  # DER Capacity
        704,  # DER Enter Service
        705,  # DER AC Controls
        706,  # DER Volt/Var/Watt Controls
        713,  # DER Storage Capacity
        714,  # DER Storage Status
        715,  # DER Storage Controls
    ])


class ConfigManager:
    """Manages application configuration with file persistence."""
    
    # Environment variable mappings
    ENV_MAPPINGS = {
        # Modbus settings
        "MODBUS_HOST": ("modbus", "host"),
        "MODBUS_PORT": ("modbus", "port"),
        "MODBUS_UNIT": ("modbus", "unit_id"),
        "MODBUS_BASE_ADDRESS": ("modbus", "base_address"),
        "MODBUS_TIMEOUT": ("modbus", "timeout"),
        # MQTT settings
        "MQTT_HOST": ("mqtt", "host"),
        "MQTT_PORT": ("mqtt", "port"),
        "MQTT_USERNAME": ("mqtt", "username"),
        "MQTT_PASSWORD": ("mqtt", "password"),
        "MQTT_CLIENT_ID": ("mqtt", "client_id"),
        "MQTT_DISCOVERY_PREFIX": ("mqtt", "discovery_prefix"),
        "MQTT_ENABLED": ("mqtt", "enabled"),
        # App settings
        "LOG_LEVEL": ("log_level", None),
        "MOCK_MODE": ("mock_mode", None),
    }
    
    def __init__(self, config_path: str = "./data/config.json"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config = AppConfig()
        self._lock = asyncio.Lock()
        self._listeners: List[callable] = []
    
    async def load(self) -> AppConfig:
        """Load configuration from file and apply environment overrides."""
        async with self._lock:
            # First load from file
            if self.config_path.exists():
                try:
                    with open(self.config_path, 'r') as f:
                        data = json.load(f)
                    self._config = self._deserialize(data)
                except Exception as e:
                    print(f"Failed to load config: {e}, using defaults")
                    self._config = AppConfig()
            
            # Then apply environment variable overrides
            self._apply_env_overrides()
            
            return self._config
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        for env_var, (section, key) in self.ENV_MAPPINGS.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    # Convert value to appropriate type
                    if section == "modbus":
                        target = self._config.modbus
                    elif section == "mqtt":
                        target = self._config.mqtt
                    else:
                        target = self._config
                    
                    # Get current value to determine type
                    current_val = getattr(target, key or section)
                    
                    # Convert string to appropriate type
                    if isinstance(current_val, bool):
                        converted = value.lower() in ("true", "1", "yes", "on")
                    elif isinstance(current_val, int):
                        converted = int(value)
                    elif isinstance(current_val, float):
                        converted = float(value)
                    else:
                        converted = value
                    
                    setattr(target, key or section, converted)
                    print(f"Config override from env: {env_var}={value}")
                    
                except Exception as e:
                    print(f"Failed to apply env var {env_var}: {e}")
    
    async def save(self) -> None:
        """Save configuration to file."""
        async with self._lock:
            try:
                data = self._serialize(self._config)
                with open(self.config_path, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"Failed to save config: {e}")
            await self._notify_listeners()
    
    def get(self) -> AppConfig:
        """Get current configuration."""
        return self._config

    def add_site(self, site: SiteConfig) -> None:
        """Add or update a site in the configuration."""
        self._config.sites[site.id] = site

    def remove_site(self, site_id: str) -> bool:
        """Remove a site if no devices are linked to it."""
        if site_id == "default":
            return False  # Cannot remove default site
        
        # Check if any devices are linked to this site
        for device in self._config.devices.values():
            if device.site_id == site_id:
                return False  # Cannot remove site with linked devices
        
        if site_id in self._config.sites:
            del self._config.sites[site_id]
            return True
        return False

    def add_device(self, device: DeviceConfig) -> None:
        """Add or update a device in the configuration."""
        self._config.devices[device.id] = device

    def remove_device(self, device_id: str) -> None:
        """Remove a device from the configuration."""
        if device_id in self._config.devices:
            del self._config.devices[device_id]
    
    def get_devices_by_site(self, site_id: str) -> Dict[str, DeviceConfig]:
        """Get all devices linked to a specific site."""
        return {k: v for k, v in self._config.devices.items() if v.site_id == site_id}
    
    def update_device_model1_info(self, device_id: str, manufacturer: str, model: str, 
                                   serial_number: str, firmware_version: str) -> bool:
        """Update device Model 1 info after discovery."""
        if device_id not in self._config.devices:
            return False
        
        device = self._config.devices[device_id]
        device.manufacturer = manufacturer
        device.model = model
        device.serial_number = serial_number
        device.firmware_version = firmware_version
        from datetime import datetime
        device.last_connected = datetime.now().isoformat()
        if not device.first_discovered:
            device.first_discovered = device.last_connected
        return True

    def _serialize(self, config: AppConfig) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "sites": {k: asdict(v) for k, v in config.sites.items()},
            "devices": [asdict(d) for d in config.devices.values()],
            "modbus": asdict(config.modbus),
            "mqtt": asdict(config.mqtt),
            "theme": asdict(config.theme),
            "auto_refresh": config.auto_refresh,
            "refresh_interval": config.refresh_interval,
            "log_level": config.log_level,
            "log_retention_days": config.log_retention_days,
            "mock_mode": config.mock_mode,
            "widgets": {k: asdict(v) for k, v in config.widgets.items()},
        }
    
    def _deserialize(self, data: Dict[str, Any]) -> AppConfig:
        """Deserialize config from dict."""
        config = AppConfig()
        
        # Load Sites
        if "sites" in data:
            for site_id, site_data in data["sites"].items():
                try:
                    site = SiteConfig(**site_data)
                    config.sites[site_id] = site
                except Exception as e:
                    print(f"Error loading site config: {e}")
        
        # Ensure default site exists
        if "default" not in config.sites:
            config.sites["default"] = SiteConfig(id="default", name="Home", is_local=True)
        
        # Load Modbus (Legacy)
        if "modbus" in data:
            config.modbus = ModbusConfig(**data["modbus"])
        
        # Load Devices
        if "devices" in data:
            for d in data["devices"]:
                try:
                    dev = DeviceConfig(**d)
                    config.devices[dev.id] = dev
                except Exception as e:
                    print(f"Error loading device config: {e}")
        
        # If no devices but legacy modbus exists, migrate it
        if not config.devices and config.modbus:
            # Create a default device from legacy config
            default_dev = DeviceConfig(
                id="default",
                name="Primary aGate",
                host=config.modbus.host,
                port=config.modbus.port,
                unit_id=config.modbus.unit_id,
                base_address=config.modbus.base_address,
                timeout=config.modbus.timeout,
                site_id="default"  # Link to default site
            )
            config.devices["default"] = default_dev
            
        # Load MQTT
        if "mqtt" in data:
            # Handle migration from old format
            mqtt_data = data["mqtt"]
            # Remove old fields that no longer exist
            mqtt_data.pop("site_name", None)  # Replaced by site_id reference
            try:
                config.mqtt = MQTTConfig(**mqtt_data)
            except Exception as e:
                print(f"Error loading MQTT config: {e}")
            
        # Load Theme
        if "theme" in data:
            config.theme = ThemeConfig(**data["theme"])
            
        # Load General Settings
        config.refresh_interval = data.get("refresh_interval", 5)
        config.auto_refresh = data.get("auto_refresh", True)

        # Load Widgets
        if "widgets" in data:
            for k, v in data["widgets"].items():
                if k in config.widgets:
                    try:
                        # Only update existing keys to preserve defaults/structure
                        w_data = {key: val for key, val in v.items() if key in config.widgets[k].__dict__}
                        config.widgets[k] = replace(config.widgets[k], **w_data)
                    except Exception as e:
                        print(f"Error loading widget {k}: {e}")
            
        return config
    
    def get(self) -> AppConfig:
        """Get current configuration."""
        return self._config
    
    async def update(self, updates: Dict[str, Any]) -> None:
        """Update configuration with partial updates."""
        async with self._lock:
            self._apply_updates(self._config, updates)
        await self.save()
    
    def _apply_updates(self, config: AppConfig, updates: Dict[str, Any]) -> None:
        """Apply nested updates to configuration."""
        for key, value in updates.items():
            if hasattr(config, key):
                attr = getattr(config, key)
                if isinstance(attr, (ModbusConfig, MQTTConfig, ThemeConfig)):
                    for sub_key, sub_value in value.items():
                        if hasattr(attr, sub_key):
                            setattr(attr, sub_key, sub_value)
                elif isinstance(attr, dict) and key == "widgets":
                    for widget_key, widget_data in value.items():
                        if widget_key in attr:
                            for sub_key, sub_value in widget_data.items():
                                if hasattr(attr[widget_key], sub_key):
                                    setattr(attr[widget_key], sub_key, sub_value)
                        else:
                            attr[widget_key] = WidgetConfig(**widget_data)
                else:
                    setattr(config, key, value)
    
    def add_listener(self, callback: callable) -> None:
        """Add configuration change listener."""
        self._listeners.append(callback)
    
    def remove_listener(self, callback: callable) -> None:
        """Remove configuration change listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    async def _notify_listeners(self) -> None:
        """Notify all listeners of configuration change."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(self._config)
                else:
                    listener(self._config)
            except Exception as e:
                print(f"Listener error: {e}")


# Global config manager instance
config_manager = ConfigManager()
