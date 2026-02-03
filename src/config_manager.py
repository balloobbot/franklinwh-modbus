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

@dataclass
class MQTTConfig:
    """MQTT configuration."""
    host: str = "localhost"
    port: int = 1883
    username: str = ""
    password: str = ""
    topic_prefix: str = "franklinwh"
    client_id: str = "franklinwh_bridge"
    discovery_prefix: str = "homeassistant"
    state_prefix: str = "franklinwh"
    enabled: bool = False


@dataclass
class AppConfig:
    """Application configuration."""
    modbus: ModbusConfig = field(default_factory=ModbusConfig)
    devices: Dict[str, DeviceConfig] = field(default_factory=dict)
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    theme: ThemeConfig = field(default_factory=ThemeConfig)
    refresh_interval: int = 5
    auto_refresh: bool = True
    log_level: str = "INFO"
    log_retention_days: int = 7
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

    def add_device(self, device: DeviceConfig) -> None:
        """Add or update a device in the configuration."""
        self._config.devices[device.id] = device

    def remove_device(self, device_id: str) -> None:
        """Remove a device from the configuration."""
        if device_id in self._config.devices:
            del self._config.devices[device_id]

    def _serialize(self, config: AppConfig) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "modbus": asdict(config.modbus),
            "devices": [asdict(d) for d in config.devices.values()],
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
                timeout=config.modbus.timeout
            )
            config.devices["default"] = default_dev
            
        # Load MQTT
        if "mqtt" in data:
            config.mqtt = MQTTConfig(**data["mqtt"])
            
        # Load Theme
        if "theme" in data:
            config.theme = UITheme(**data["theme"])
            
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
                if isinstance(attr, (ModbusConfig, MQTTConfig, UITheme)):
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
