# Network Scanner

A comprehensive Python-based network scanner for discovering IoT and energy devices on local networks.

## Features

- **Multi-threaded scanning** for fast network discovery
- **Multiple device type support**:
  - Modbus TCP SunSpec compliant devices (Model 1)
  - Enphase Solar Inverters (REST API)
  - SolarEdge Solar Inverters (Modbus/REST API)
  - Home Assistant instances
  - MQTT Brokers
  - Homey Smart Home Hub
- **Flexible input formats**: Single IP, CIDR notation, IP ranges
- **Multiple output formats**: Table, JSON, CSV
- **Configurable timeout and thread count**

## Installation

```bash
# Install required dependencies
pip install pymodbus requests

# Optional: Install for enhanced table output
pip install tabulate colorama
```

Or use the requirements file:
```bash
pip install -r network_scanner_requirements.txt
```

## Usage

### Basic Examples

```bash
# Scan entire network for all supported devices
python3 network_scanner.py 192.168.1.0/24

# Scan specific device types only
python3 network_scanner.py 192.168.1.0/24 --devices modbus,enphase

# Scan specific IP with custom timeout
python3 network_scanner.py 192.168.1.50 --timeout 10

# Scan range of IPs
python3 network_scanner.py 192.168.1.1-192.168.1.100

# Wildcard notation
python3 network_scanner.py "192.168.1.*"
```

### Port Specification

```bash
# Scan custom ports
python3 network_scanner.py 192.168.1.0/24 --ports 502,80,443,1883,8123
```

### Output Formats

```bash
# JSON output (for integration with other tools)
python3 network_scanner.py 192.168.1.0/24 -o json > results.json

# CSV output (for spreadsheet analysis)
python3 network_scanner.py 192.168.1.0/24 -o csv > results.csv

# Human-readable table (default)
python3 network_scanner.py 192.168.1.0/24 -o table
```

### Performance Tuning

```bash
# Fast scan with more threads
python3 network_scanner.py 192.168.1.0/24 --threads 100 --timeout 2

# Conservative scan (fewer threads, longer timeout)
python3 network_scanner.py 192.168.1.0/24 --threads 10 --timeout 10
```

## Device Types

| Device Type | Identifier | Ports Scanned | Detection Method |
|-------------|------------|---------------|------------------|
| SunSpec Modbus | `modbus`, `sunspec` | 502, 5020, 1502 | Reads Model 1 (Common) registers |
| Enphase | `enphase` | 80, 443 | HTTP API endpoints |
| SolarEdge | `solaredge` | 80, 502 | HTTP SetApp or Modbus |
| Home Assistant | `ha`, `homeassistant` | 8123 | API endpoint detection |
| MQTT Broker | `mqtt`, `broker` | 1883, 8883, 1884 | CONNECT/CONNACK handshake |
| Homey | `homey` | 80, 443 | HTTP API detection |

## JSON Output Format

```json
[
  {
    "ip": "192.168.1.50",
    "port": 502,
    "device_type": "modbus_sunspec",
    "is_reachable": true,
    "response_time_ms": 45.2,
    "manufacturer": "FranklinWH",
    "model": "aGate X",
    "serial_number": "0091XXXXXXXX",
    "version": "2.1.0",
    "sunspec_model": 1,
    "extra_data": {
      "sunspec_base_addr": 40000
    },
    "error": null
  }
]
```

## CSV Output Format

```csv
ip,port,device_type,is_reachable,response_time_ms,manufacturer,model,serial_number,version
192.168.1.50,502,modbus_sunspec,true,45.2,"FranklinWH","aGate X","0091XXXXXXXX","2.1.0"
192.168.1.60,8123,home_assistant,true,12.3,"Nabu Casa","Home Assistant","","2024.1.0"
```

## How It Works

1. **IP Range Generation**: Parses CIDR, ranges, or wildcards into individual IPs
2. **Port Pre-check**: Fast TCP connect to check if port is open
3. **Protocol Probing**: Device-specific detection:
   - **SunSpec**: Reads Model 1 registers at common base addresses (40000, 0, 50000)
   - **HTTP devices**: Checks specific endpoints and response signatures
   - **MQTT**: Sends CONNECT packet, validates CONNACK response
4. **Result Aggregation**: Collects and formats results

## SunSpec Detection Details

The scanner attempts to read SunSpec Model 1 (Common) from the following base addresses:
- 40000 (most common)
- 0 (some devices)
- 50000 (alternative)
- 30000 (alternative)

For each base address, it:
1. Connects to Modbus TCP port 502
2. Reads registers at base address (should contain "SunS" magic bytes)
3. If valid, reads manufacturer, model, version, serial number

## Troubleshooting

### No devices found
- Verify network connectivity: `ping <target_ip>`
- Check firewall rules on target devices
- Increase timeout: `--timeout 5`
- Enable verbose mode: `-v`

### Permission denied
Some systems require root/administrator for raw socket operations:
```bash
sudo python3 network_scanner.py 192.168.1.0/24
```

### Missing dependencies
```bash
pip install pymodbus requests
```

## Performance Considerations

- **Thread count**: Default 50 is good for most networks
- **Timeout**: Default 3s balances speed and reliability
- **Large networks**: For /16 networks, increase threads to 100+ or scan in chunks

## Security Notes

- This scanner only performs read operations
- No authentication credentials are sent (except anonymous MQTT probe)
- Some devices may log connection attempts
- Respect network policies and only scan networks you own/manage

## Integration Examples

### Home Assistant
```bash
# Add to shell_command in configuration.yaml
shell_command:
  scan_network: 'python3 /config/tools/network_scanner.py 192.168.1.0/24 -o json > /config/www/scan_results.json'
```

### Cron Job (Periodic Scanning)
```bash
# Run daily at 2 AM and save results
0 2 * * * /usr/bin/python3 /path/to/network_scanner.py 192.168.1.0/24 -o json > /var/log/device_scan.json 2>/dev/null
```

### Python Integration
```python
from network_scanner import NetworkScanner, DeviceType

scanner = NetworkScanner(
    device_types=[DeviceType.MODBUS_SUNSPEC, DeviceType.HOME_ASSISTANT],
    timeout=5.0,
    max_workers=30
)

results = scanner.scan(["192.168.1.0/24"])
for device in results:
    print(f"Found {device.manufacturer} {device.model} at {device.ip}")
```

## License

This is part of the modbus project. See main project license.
