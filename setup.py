#!/usr/bin/env python3
"""
FranklinWH Battery Manager - Setup Wizard

Interactive setup script to configure:
- Modbus connection (real device or mock mode)
- MQTT broker settings
- Web UI preferences
- Creates config.json and optional .env file
"""

import json
import os
import sys
from pathlib import Path


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_step(step: int, total: int, text: str):
    """Print a step indicator."""
    print(f"\n[Step {step}/{total}] {text}")
    print("-" * 40)


def get_input(prompt: str, default: str = "", required: bool = False) -> str:
    """Get user input with default value."""
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    else:
        while True:
            user_input = input(f"{prompt}: ").strip()
            if user_input or not required:
                return user_input
            print("  ⚠️  This field is required.")


def get_boolean(prompt: str, default: bool = False) -> bool:
    """Get yes/no input."""
    default_str = "Y/n" if default else "y/N"
    while True:
        user_input = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not user_input:
            return default
        if user_input in ("y", "yes"):
            return True
        if user_input in ("n", "no"):
            return False
        print("  ⚠️  Please enter 'y' or 'n'.")


def get_integer(prompt: str, default: int, min_val: int = None, max_val: int = None) -> int:
    """Get integer input with validation."""
    while True:
        user_input = input(f"{prompt} [{default}]: ").strip()
        if not user_input:
            return default
        try:
            value = int(user_input)
            if min_val is not None and value < min_val:
                print(f"  ⚠️  Value must be at least {min_val}")
                continue
            if max_val is not None and value > max_val:
                print(f"  ⚠️  Value must be at most {max_val}")
                continue
            return value
        except ValueError:
            print("  ⚠️  Please enter a valid number.")


def get_choice(prompt: str, options: list, default: int = 0) -> int:
    """Get a choice from a list of options."""
    print(f"\n{prompt}")
    for i, option in enumerate(options, 1):
        marker = " (default)" if i - 1 == default else ""
        print(f"  {i}. {option}{marker}")
    
    while True:
        user_input = input(f"Enter choice [1-{len(options)}]: ").strip()
        if not user_input:
            return default
        try:
            choice = int(user_input) - 1
            if 0 <= choice < len(options):
                return choice
            print(f"  ⚠️  Please enter a number between 1 and {len(options)}")
        except ValueError:
            print("  ⚠️  Please enter a valid number.")


def main():
    """Main setup wizard."""
    print_header("🔋 FranklinWH Battery Manager - Setup Wizard")
    print("\nThis wizard will help you configure the application.")
    print("You can change these settings later via the web UI or by editing")
    print("the configuration files.")
    
    config = {
        "modbus": {},
        "mqtt": {},
        "theme": {},
        "widgets": {}
    }
    
    # Step 1: Mode selection
    print_step(1, 5, "Select Operation Mode")
    print("Choose how you want to run the application:")
    print("\n  1. 🎭 MOCK MODE - Use simulated device data (for testing)")
    print("  2. 🔌 LIVE MODE - Connect to real FranklinWH device")
    
    mode_choice = get_choice("Select mode:", ["Mock Mode (Simulated)", "Live Mode (Real Device)"], 0)
    config["mock_mode"] = (mode_choice == 0)
    
    if config["mock_mode"]:
        print("\n  ✓ Mock mode selected. The app will generate simulated battery data.")
        print("    You can test the UI without connecting to a real device.")
        # Use default Modbus settings for mock mode
        config["modbus"] = {
            "host": "mock://localhost",
            "port": 502,
            "unit_id": 2,
            "base_address": 40000,
            "timeout": 5.0,
            "retry_attempts": 3,
            "retry_delay": 1.0
        }
    else:
        print_step(2, 5, "Modbus Device Configuration")
        print("Enter your FranklinWH battery's network details.")
        print("You can find these in your device's network settings.")
        print()
        
        config["modbus"] = {
            "host": get_input("Device IP Address", "192.168.0.110"),
            "port": get_integer("Port", 502, min_val=1, max_val=65535),
            "unit_id": get_integer("Unit ID (Slave Address)", 2, min_val=1, max_val=247),
            "base_address": get_integer("Base Register Address", 40000),
            "timeout": float(get_input("Connection Timeout (seconds)", "5.0")),
            "retry_attempts": get_integer("Retry Attempts", 3, min_val=0),
            "retry_delay": float(get_input("Retry Delay (seconds)", "1.0"))
        }
    
    # Step 3: MQTT Configuration
    print_step(3, 5, "MQTT Broker Configuration (Optional)")
    print("MQTT is used for Home Assistant integration.")
    print("If you don't use Home Assistant, you can skip this.")
    
    enable_mqtt = get_boolean("Configure MQTT?", not config["mock_mode"])
    
    if enable_mqtt:
        print("\nEnter your MQTT broker details:")
        config["mqtt"] = {
            "host": get_input("Broker IP/Hostname", "192.168.0.109"),
            "port": get_integer("Port", 1883, min_val=1, max_val=65535),
            "username": get_input("Username (leave blank if none)", ""),
            "password": get_input("Password (leave blank if none)", ""),
            "client_id": get_input("Client ID", "franklinwh_bridge"),
            "discovery_prefix": get_input("HA Discovery Prefix", "homeassistant"),
            "state_prefix": get_input("State Topic Prefix", "franklinwh")
        }
    else:
        config["mqtt"] = {
            "host": "192.168.0.109",
            "port": 1883,
            "username": "",
            "password": "",
            "client_id": "franklinwh_bridge",
            "discovery_prefix": "homeassistant",
            "state_prefix": "franklinwh"
        }
    
    # Step 4: Web UI Preferences
    print_step(4, 5, "Web Interface Preferences")
    
    theme_modes = ["Auto (follows system)", "Light", "Dark"]
    theme_choice = get_choice("Default theme:", theme_modes, 0)
    
    config["theme"] = {
        "mode": ["auto", "light", "dark"][theme_choice],
        "primary_color": "#3b82f6",
        "secondary_color": "#10b981",
        "accent_color": "#f59e0b",
        "background_color": "#ffffff",
        "surface_color": "#f3f4f6",
        "text_color": "#111827",
        "border_radius": 12,
        "shadow_intensity": "medium"
    }
    
    config["auto_refresh"] = get_boolean("Enable auto-refresh?", True)
    config["refresh_interval"] = get_integer("Refresh interval (seconds)", 30, min_val=5, max_val=300)
    config["log_level"] = ["DEBUG", "INFO", "WARNING", "ERROR"][
        get_choice("Log level:", ["DEBUG", "INFO", "WARNING", "ERROR"], 1)
    ]
    
    # Step 5: Save configuration
    print_step(5, 5, "Save Configuration")
    
    # Create data directory
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Save config.json
    config_path = data_dir / "config.json"
    
    # Add metadata
    config["enabled_models"] = [1, 701, 702, 703, 704, 705, 706, 713, 714, 715]
    config["widgets"] = {
        "battery_metrics": {"enabled": True, "position": 0, "color": "#10b981", "refresh_interval": 30, "expanded": True},
        "inverter_status": {"enabled": True, "position": 1, "color": "#3b82f6", "refresh_interval": 30, "expanded": True},
        "power_flow": {"enabled": True, "position": 2, "color": "#f59e0b", "refresh_interval": 30, "expanded": True},
        "energy_stats": {"enabled": True, "position": 3, "color": "#8b5cf6", "refresh_interval": 30, "expanded": True},
        "system_health": {"enabled": True, "position": 4, "color": "#ef4444", "refresh_interval": 30, "expanded": True},
        "control_panel": {"enabled": True, "position": 5, "color": "#06b6d4", "refresh_interval": 30, "expanded": True}
    }
    config["log_retention_days"] = 7
    
    # Write config file
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"\n  ✓ Configuration saved to: {config_path.absolute()}")
    
    # Offer to create .env file
    create_env = get_boolean("Create .env file for environment variable overrides?", False)
    
    if create_env:
        env_path = Path(".env")
        env_content = f"""# FranklinWH Battery Manager - Environment Configuration
# These values override settings in config.json

# Operation Mode
MOCK_MODE={'true' if config['mock_mode'] else 'false'}

# Modbus Settings
MODBUS_HOST={config['modbus']['host']}
MODBUS_PORT={config['modbus']['port']}
MODBUS_UNIT={config['modbus']['unit_id']}

# MQTT Settings
MQTT_HOST={config['mqtt']['host']}
MQTT_PORT={config['mqtt']['port']}
MQTT_USERNAME={config['mqtt']['username']}
MQTT_PASSWORD={config['mqtt']['password']}

# Logging
LOG_LEVEL={config['log_level']}
"""
        with open(env_path, "w") as f:
            f.write(env_content)
        print(f"\n  ✓ Environment file created: {env_path.absolute()}")
    
    # Print summary
    print_header("✅ Setup Complete!")
    print("\n📋 Configuration Summary:")
    print(f"  Mode: {'🎭 MOCK (Simulated Device)' if config['mock_mode'] else '🔌 LIVE (Real Device)'}")
    
    if not config["mock_mode"]:
        print(f"  Device: {config['modbus']['host']}:{config['modbus']['port']} (Unit {config['modbus']['unit_id']})")
    
    print(f"  MQTT: {'Enabled' if enable_mqtt else 'Disabled'}")
    if enable_mqtt:
        print(f"    Broker: {config['mqtt']['host']}:{config['mqtt']['port']}")
    
    print(f"  Web UI: http://localhost:8080")
    print(f"  Theme: {config['theme']['mode'].title()}")
    
    print("\n🚀 To start the application:")
    print("  ./run.sh")
    print("\n   or manually:")
    print("  source venv/bin/activate")
    print("  python -m src.main")
    
    print("\n📖 You can change settings later via:")
    print("  - Web UI: Settings button (top right)")
    print(f"  - Config file: {config_path.absolute()}")
    if create_env:
        print(f"  - Environment file: {env_path.absolute()}")
    
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user.")
        sys.exit(1)
