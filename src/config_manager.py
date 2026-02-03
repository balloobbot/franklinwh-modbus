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
from dataclasses import dataclass, asdict, field
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


@dataclass
class UITheme:
    """UI theme configuration."""
    mode: str = "auto"  # light, dark, auto
    primary_color: str = "#3b82f6"
    secondary_color: str = "#10b981"
    accent_color: str = "#f59e0b"
    background_color: str = "#ffffff"
    surface_color: str = "#f3f4f6"
    text_color: str = "#111827"
    border_radius: int = 12
    shadow_intensity: str = "medium"  # none, low, medium, high


@dataclass
class ModbusConfig:
    """Modbus connection configuration."""
    host: str = "192.168.0.110"
    port: int = 502
    unit_id: int = 2
    base_address: int = 40000
    timeout: float = 5.0
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class MQTTConfig:
    """MQTT broker configuration."""
    host: str = "192.168.0.109"
    port: int = 1883
    username: str = ""
    password: str = ""
    client_id: str = "franklinwh_bridge"
    discovery_prefix: str = "homeassistant"
    state_prefix: str = "franklinwh"


@dataclass
class AppConfig:
    """Main application configuration."""
    modbus: ModbusConfig = field(default_factory=ModbusConfig)
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    theme: UITheme = field(default_factory=UITheme)
    auto_refresh: bool = True
    refresh_interval: int = 30
    log_level: str = "INFO"
    log_retention_days: int = 7
    mock_mode: bool = False  # Enable mock device simulation
    
    # Widget configurations
    widgets: Dict[str, WidgetConfig] = field(default_factory=lambda: {
        "battery_metrics": WidgetConfig(enabled=True, position=0, color="#10b981"),
        "inverter_status": WidgetConfig(enabled=True, position=1, color="#3b82f6"),
        "power_flow": WidgetConfig(enabled=True, position=2, color="#f59e0b"),
        "energy_stats": WidgetConfig(enabled=True, position=3, color="#8b5cf6"),
        "system_health": WidgetConfig(enabled=True, position=4, color="#ef4444"),
        "control_panel": WidgetConfig(enabled=True, position=5, color="#06b6d4"),
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
            data = self._serialize(self._config)
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            await self._notify_listeners()
    
    def _serialize(self, config: AppConfig) -> Dict[str, Any]:
        """Convert dataclass to dict."""
        return {
            "modbus": asdict(config.modbus),
            "mqtt": asdict(config.mqtt),
            "theme": asdict(config.theme),
            "auto_refresh": config.auto_refresh,
            "refresh_interval": config.refresh_interval,
            "log_level": config.log_level,
            "log_retention_days": config.log_retention_days,
            "mock_mode": config.mock_mode,
            "widgets": {k: asdict(v) for k, v in config.widgets.items()},
            "enabled_models": config.enabled_models,
            "last_updated": datetime.now().isoformat(),
        }
    
    def _deserialize(self, data: Dict[str, Any]) -> AppConfig:
        """Convert dict to dataclass."""
        config = AppConfig()
        
        if "modbus" in data:
            config.modbus = ModbusConfig(**data["modbus"])
        if "mqtt" in data:
            config.mqtt = MQTTConfig(**data["mqtt"])
        if "theme" in data:
            config.theme = UITheme(**data["theme"])
        
        config.auto_refresh = data.get("auto_refresh", True)
        config.refresh_interval = data.get("refresh_interval", 30)
        config.log_level = data.get("log_level", "INFO")
        config.log_retention_days = data.get("log_retention_days", 7)
        config.mock_mode = data.get("mock_mode", False)
        
        if "widgets" in data:
            config.widgets = {
                k: WidgetConfig(**v) for k, v in data["widgets"].items()
            }
        
        config.enabled_models = data.get("enabled_models", config.enabled_models)
        
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
