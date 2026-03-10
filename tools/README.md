# Network & Device Scanner Tools

Cross-platform network scanner for IoT and energy devices with mDNS/Bonjour and Modbus SunSpec support.

## Quick Start

```bash
# Activate virtual environment
source ../venv/bin/activate

# mDNS Discovery (fast, no IP needed)
python3 network_scanner.py --mdns -v

# Modbus SunSpec scan
python3 network_scanner.py 192.168.0.110 --devices modbus -v

# Full network scan
python3 network_scanner.py 192.168.0.0/24 --threads 100 -v
```

## Installation

```bash
pip install pymodbus requests zeroconf tabulate
```

Or use requirements file:
```bash
pip install -r network_scanner_requirements.txt
```

## Main Tool: `network_scanner.py`

A comprehensive scanner supporting:
- **mDNS/Bonjour discovery** (cross-platform, fast)
- **Modbus TCP SunSpec** (Model 1 - manufacturer, model, serial, version)
- **HTTP API detection** (Enphase, SolarEdge, Home Assistant, Homey)
- **MQTT broker detection**

### Usage Examples

```bash
# mDNS discovery (recommended)
python3 network_scanner.py --mdns
python3 network_scanner.py --mdns --devices ha,enphase,homey
python3 network_scanner.py --mdns-all  # Comprehensive IoT scan

# SPAN Panel detection
python3 network_scanner.py 192.168.0.0/24 --devices span
python3 network_scanner.py --mdns --devices span

# IP range scanning
python3 network_scanner.py 192.168.0.0/24
python3 network_scanner.py 192.168.0.1-192.168.0.100
python3 network_scanner.py 192.168.0.110 --devices modbus

# Output formats
python3 network_scanner.py --mdns -o json > devices.json
python3 network_scanner.py 192.168.0.0/24 -o csv > devices.csv

# Performance tuning
python3 network_scanner.py 192.168.0.0/24 --threads 100 --timeout 2
```

### Supported Device Types

| Type | Identifier | Discovery Method |
|------|------------|------------------|
| SunSpec Modbus | `modbus`, `sunspec` | Modbus TCP port 502 |
| Enphase | `enphase` | mDNS or HTTP API |
| SolarEdge | `solaredge` | HTTP or Modbus |
| Home Assistant | `ha`, `homeassistant` | mDNS or HTTP port 8123 |
| MQTT Broker | `mqtt`, `broker` | mDNS or TCP port 1883 |
| Homey | `homey` | mDNS or HTTP |
| SPAN Panel | `span`, `spanpanel` | HTTP port 80/443 |

### SPAN Smart Panel Detection

SPAN Panels (MAIN 32, MAIN 40, MLO 48) and SPAN Drive EV chargers are detected via HTTP API:

```bash
# Scan network for SPAN devices
python3 network_scanner.py 192.168.0.0/24 --devices span -v

# Quick check specific IP
python3 network_scanner.py 192.168.0.35 --devices span -v

# mDNS discovery for SPAN
python3 network_scanner.py --mdns --devices span
```

**Quick SPAN Check via main CLI** (no extra dependencies):
```bash
# Scans aGate's /24 subnet for SPAN panels, reports extension register status
python3 franklinwh_cli.py -i 192.168.0.110 --check-span
```

**SPAN API Versions:**
- **Gen 1 & 2 (MAIN 32)**: REST API on port 80/443
- **Gen 3 (MAIN 40/MLO 48)**: gRPC protocol + HTTP for setup
- **SPAN Drive**: Port 50058

**Testing SPAN API:**
```bash
# Check if API is accessible
curl http://192.168.0.35/api/v1/status
curl http://192.168.0.35/api/v1/circuits

# Get panel info
curl http://192.168.0.35/api/v1/status | python3 -m json.tool
```

**Detection Method:**
- Checks for "span" + "panel" keywords in HTTP response
- Probes `/api/v1/status` and `/api/v1/circuits` endpoints
- Detects SPAN-specific JSON structure
- Supports SPAN login page detection (Gen 1/2)

## Alternative Tool: `modbus_scan_network.py`

Deep SunSpec scanner using `pysunspec2` library.

```bash
# Scan specific IP
python3 modbus_scan_network.py --ip 192.168.0.110 -v

# Scan network
python3 modbus_scan_network.py --network 192.168.0.0/24 --threads 50

# Specific base address
python3 modbus_scan_network.py --ip 192.168.0.110 --base-address 40000
```

### Comparison

| Feature | `network_scanner.py` | `modbus_scan_network.py` |
|---------|----------------------|--------------------------|
| mDNS Discovery | ✅ Yes | ❌ No |
| HTTP Devices | ✅ Yes | ❌ No |
| All SunSpec Models | ❌ Model 1 only | ✅ Yes |
| Library | pymodbus | pysunspec2 |
| Speed | Fast | Moderate |
| Cross-platform | ✅ Yes | ✅ Yes |

## Output Format

### Table (Default)
```
IP Address       Port   Proto    Device Type        Manufacturer     Model        Serial         Version   
-------------------------------------------------------------------------------------------------------------------
192.168.0.35     80     HTTP     span               SPAN             SPAN Smart P -              -         
192.168.0.109    8123   mDNS     home_assistant     Nabu Casa        Home         -              2026.2.2  
192.168.0.110    502    Modbus   modbus_sunspec     FranklinWH Techn aGate X      10060006A02F24 V10R01B04D
192.168.0.118    80     HTTP     span               SPAN             SPAN Smart P -              -         
192.168.0.224    80     mDNS     enphase            Enphase          envoy        -              -         
192.168.0.253    80     mDNS     homey              Athom            homey6q      -              12.12.0   
```

### JSON
```bash
python3 network_scanner.py --mdns -o json
```

```json
[
  {
    "ip": "192.168.0.110",
    "port": 502,
    "device_type": "modbus_sunspec",
    "manufacturer": "FranklinWH Technologies Co., Ltd",
    "model": "aGate X",
    "serial_number": "10060006A02F24170091",
    "version": "V10R01B04D00",
    "extra_data": {
      "discovery_method": "Modbus",
      "sunspec_base_addr": 0
    }
  }
]
```

## Protocol Column

| Protocol | Meaning |
|----------|---------|
| `mDNS` | Discovered via mDNS/Bonjour multicast |
| `Modbus` | Discovered via Modbus TCP scan |
| `HTTP` | Discovered via HTTP API |
| `MQTT` | Discovered via MQTT CONNECT packet |
| `TCP` | Generic TCP port scan |

## Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | This file - quick start guide |
| `network_scanner_README.md` | Detailed usage documentation |
| `NETWORK_SCANNER_MDNS_GUIDE.md` | mDNS-specific guide |
| `NETWORK_SCANNER_SUMMARY.md` | Implementation details |
| `MDNS_DISCOVERY.md` | Comparison with Avahi |

## Programmatic Usage

```python
from network_scanner import NetworkScanner, DeviceType

# mDNS discovery
scanner = NetworkScanner(device_types=[DeviceType.HOME_ASSISTANT, DeviceType.ENPHASE])
devices = scanner.discover_mdns(timeout=5.0)

for device in devices:
    print(f"{device.manufacturer} {device.model} at {device.ip}")

# Modbus scan
scanner = NetworkScanner(device_types=[DeviceType.MODBUS_SUNSPEC])
results = scanner.scan(["192.168.0.0/24"])

# SPAN Panel detection
scanner = NetworkScanner(device_types=[DeviceType.SPAN])
results = scanner.scan(["192.168.0.0/24"])
for panel in results:
    print(f"SPAN Panel at {panel.ip} - Generation: {panel.extra_data.get('generation')}")
```

## Troubleshooting

### "zeroconf not installed"
```bash
pip install zeroconf
```

### No Modbus devices found
- Verify IP address: `ping 192.168.0.110`
- Check port 502 is open: `nc -zv 192.168.0.110 502`
- Try different base address: Scanner tries 0, 40000, 50000 automatically

### mDNS not finding devices
- Check firewall allows UDP port 5353
- Some routers block mDNS multicast
- Try IP scanning as fallback

## License

Part of the modbus project. See main project license.
