#!/bin/bash
# FranklinWH Battery Manager - Startup Script

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found. Please run setup first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Set default environment variables
export MODBUS_HOST="${MODBUS_HOST:-192.168.0.110}"
export MODBUS_PORT="${MODBUS_PORT:-502}"
export MODBUS_UNIT="${MODBUS_UNIT:-2}"
export MQTT_HOST="${MQTT_HOST:-192.168.0.109}"
export MQTT_PORT="${MQTT_PORT:-1883}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Run the application
echo "Starting FranklinWH Battery Manager..."
echo "  Modbus: $MODBUS_HOST:$MODBUS_PORT (Unit $MODBUS_UNIT)"
echo "  MQTT: $MQTT_HOST:$MQTT_PORT"
echo "  Web UI: http://localhost:8080"
echo ""
python -m src.main "$@"
