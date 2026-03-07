
import asyncio
import logging
import json
import os
import sys

# Ensure we can import src
sys.path.append(os.getcwd())

from src.modbus_client import FranklinWHModbusClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_api_read():
    print("\n=== Initializing Client ===")
    client = FranklinWHModbusClient(host="192.168.0.110", unit_id=1) 
    
    print("\n=== Connecting ===")
    connected = await client.connect()
    
    if not connected:
        print("Failed to connect")
        return

    print("\n=== Simulating API Read logic ===")
    try:
        # Simulate web_server.py /api/data logic
        data = await client.read_all()
        
        # Simulate Extensions read
        extensions_data = None
        try:
            from src.modbus_client_franklinwh import FranklinWHRegisterMap
            register_map = FranklinWHRegisterMap(client)
            metrics = await register_map.read_all_metrics()
            mode_text = await register_map.get_operating_mode_text(metrics.operating_mode)
            extensions_data = {
                "operatingMode": metrics.operating_mode,
                "modeText": mode_text,
                "reserveSoc": metrics.reserve_soc,
                "reserveSoc2": metrics.reserve_soc_2 if metrics.reserve_soc_2 is None or metrics.reserve_soc_2 <= 32767 else metrics.reserve_soc_2 - 65536,
                "reserve_soc_self_consumption": metrics.reserve_soc,
                "reserve_soc_tou": metrics.reserve_soc_2 if metrics.reserve_soc_2 is None or metrics.reserve_soc_2 <= 32767 else metrics.reserve_soc_2 - 65536,
            }
        except Exception as e:
            print(f"Extensions read failed: {e}")

        # Construct payload
        payload = {
            "timestamp": 0,
            "device_info": {
                "manufacturer": data.get("device_info", {}).manufacturer if data.get("device_info") else "Unknown",
                "model": data.get("device_info", {}).model if data.get("device_info") else "Unknown",
                "serial": data.get("device_info", {}).serial_number if data.get("device_info") else "Unknown",
            } if data.get("device_info") else None,
            "battery": {
                "soc": data.get("battery", {}).state_of_charge_percent if data.get("battery") else None,
                "soh": data.get("battery", {}).state_of_health_percent if data.get("battery") else None,
                "temperature": data.get("battery", {}).temperature_c if data.get("battery") else None,
                "cycles": data.get("battery", {}).cycle_count if data.get("battery") else None,
                "rated_energy_wh": data.get("battery", {}).rated_energy_wh if data.get("battery") else None,
                "available_energy_wh": data.get("battery", {}).available_energy_wh if data.get("battery") else None,
                "status": data.get("battery", {}).status if data.get("battery") else None,
                "status_text": data.get("battery", {}).status_text if data.get("battery") else None,
            } if data.get("battery") else None,
            "inverter": {
                "power": data.get("inverter_ac", {}).power_w if data.get("inverter_ac") else None,
                "voltage": data.get("inverter_ac", {}).voltage_v if data.get("inverter_ac") else None,
                "current": data.get("inverter_ac", {}).current_a if data.get("inverter_ac") else None,
                "frequency": data.get("inverter_ac", {}).frequency_hz if data.get("inverter_ac") else None,
                "power_factor": data.get("inverter_ac", {}).power_factor if data.get("inverter_ac") else None,
            } if data.get("inverter_ac") else None,
            "solar_pv": {
                "output_power_w": data.get("solar_pv", {}).output_power_w if data.get("solar_pv") else None,
                "output_energy_wh": data.get("solar_pv", {}).output_energy_wh if data.get("solar_pv") else None,
            } if data.get("solar_pv") else None,
            "extensions": extensions_data,
        }
        
        print("\n=== JSON Dump ===")
        # This will fail if payload contains non-serializable types (like Enum or bytes)
        json_str = json.dumps(payload, default=str, indent=2)
        print(json_str)
        print("\n=== Success ===")

    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n=== Disconnecting ===")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_api_read())
