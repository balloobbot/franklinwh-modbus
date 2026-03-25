# Network Scanner Feasibility Analysis

## Overview
Building a comprehensive network scanner for IoT/energy devices with focus on Modbus SunSpec and solar inverters.

## Protocol Support Analysis

### 1. Modbus TCP (SunSpec Compliant) ✅ HIGHLY FEASIBLE
- **Library**: `pymodbus` (already installed)
- **Detection Method**: 
  - Connect to port 502
  - Read Model 1 (Common) at address 40000 or 0
  - Check for SunSpec ID "SunS" (0x53756e53)
  - Extract manufacturer, model, serial, version
- **Device Types**: FranklinWH, SolarEdge, SMA, Sungrow, etc.
- **Reliability**: High - standardized protocol

### 2. Enphase Inverters (REST API) ✅ FEASIBLE
- **Protocol**: HTTP/HTTPS on port 80/443
- **Detection**: 
  - Check `/api/v1/production` or `/production.json`
  - Look for Enphase-specific headers/responses
  - Local Envoy endpoints
- **Authentication**: May require JWT token for newer firmware
- **Library**: `requests` (already installed)

### 3. SolarEdge (Modbus/REST) ✅ FEASIBLE
- **Modbus**: Port 502, SunSpec compliant
- **REST API**: Port 80, SetApp interface
- **Detection**: HTTP endpoints like `/web/v1/maintenance` or Modbus scan

### 4. Home Assistant ✅ FEASIBLE
- **Discovery**: mDNS/Bonjour (_home-assistant._tcp)
- **HTTP Check**: Port 8123, look for `/api/` or HTML title
- **Characteristics**: Returns "Home Assistant" in page title

### 5. MQTT Brokers ✅ FEASIBLE
- **Port**: 1883 (plain), 8883 (TLS)
- **Detection**: 
  - TCP connect to 1883
  - Send CONNECT packet, wait for CONNACK
  - Or use MQTT ping if authentication known
- **Library**: `paho-mqtt` (optional) or raw socket

### 6. Homey Smart Hub ⚠️ MODERATE
- **Discovery**: mDNS (_http._tcp or proprietary)
- **HTTP**: Port 80, specific API endpoints
- **Challenge**: Less standardized, may require specific user-agent

## Implementation Strategy

### Core Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                  Network Scanner (Python)                    │
├─────────────────────────────────────────────────────────────┤
│  Input Parser (IP/CIDR/Range/Port/Device Type/Timeout)      │
├─────────────────────────────────────────────────────────────┤
│  IP Range Generator                                         │
├─────────────────────────────────────────────────────────────┤
│  Thread Pool Executor (configurable workers)                │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│ Modbus TCP  │ HTTP/REST   │ MQTT        │ Raw TCP           │
│ Prober      │ Prober      │ Prober      │ Prober            │
├─────────────┴─────────────┴─────────────┴───────────────────┤
│  Result Aggregator & Formatter (JSON/CSV/Table)             │
└─────────────────────────────────────────────────────────────┘
```

### Detection Methods by Device

| Device | Method | Port | Signature/Endpoint |
|--------|--------|------|-------------------|
| SunSpec Modbus | TCP + Modbus read | 502 | Model 1 at 40000, "SunS" header |
| Enphase Envoy | HTTP GET | 80/443 | `/api/v1/production`, `envoy*` in response |
| SolarEdge | Modbus or HTTP | 502/80 | SunSpec model OR SetApp web interface |
| Home Assistant | HTTP GET | 8123 | Title contains "Home Assistant" |
| MQTT Broker | TCP/MQTT | 1883 | CONNACK response to CONNECT packet |
| Homey | HTTP GET | 80 | `/api/` endpoints, specific headers |

### Multi-threading Strategy
- Use `concurrent.futures.ThreadPoolExecutor`
- Configurable max workers (default: 50)
- Timeout per probe (default: 2-5 seconds)
- Thread-safe result collection with `queue.Queue`

### Output Formats
1. **Standard**: Human-readable table
2. **JSON**: Structured data for integration
3. **CSV**: Spreadsheet-friendly

## Required Libraries
- `pymodbus` ✅ (installed)
- `requests` ✅ (installed)
- `pythonping` or raw socket (for ping sweep)
- `netaddr` (for CIDR parsing - optional, can use ipaddress stdlib)
- `tabulate` (for pretty tables - optional)
- `colorama` (for colored output - optional)

## Command Line Interface Design

```bash
# Scan entire network for all supported devices
python3 network_scanner.py 192.168.1.0/24

# Scan specific device types only
python3 network_scanner.py 192.168.1.0/24 --devices modbus,enphase

# Specific IP with custom timeout
python3 network_scanner.py 192.168.1.50 --timeout 10

# Range of IPs
python3 network_scanner.py 192.168.1.1-192.168.1.100

# Custom ports
python3 network_scanner.py 192.168.1.0/24 --ports 502,80,443,1883,8123

# Output formats
python3 network_scanner.py 192.168.1.0/24 -o json > results.json
python3 network_scanner.py 192.168.1.0/24 -o csv > results.csv

# Thread control
python3 network_scanner.py 192.168.1.0/24 --threads 100 --timeout 3
```

## Optimization Strategies

1. **Fast Port Pre-check**: Use TCP SYN scan (socket.connect) before protocol-specific probes
2. **Parallel Device Detection**: Run all device probers concurrently for each IP
3. **Early Exit**: Stop probing a device type once found (e.g., if Modbus responds, skip HTTP)
4. **Cache Results**: Avoid duplicate probes within same scan session

## Limitations & Considerations

1. **Network Load**: High thread counts + many IPs can overwhelm networks
2. **Firewalls**: Many devices block ICMP/ping; rely on TCP connect
3. **Authentication**: Some devices require auth (newer Enphase, secured MQTT)
4. **Rate Limiting**: Some devices may temporarily block aggressive scanning
5. **mDNS Dependency**: Home Assistant discovery requires multicast support

## Recommended Defaults
- Timeout: 3 seconds per probe
- Threads: 50 concurrent
- Ports scanned: 502, 80, 443, 1883, 8883, 8123, 5020 (Modbus alternatives)
- Retry: 1 retry on timeout

## Testing Strategy
1. Test against known devices in local network
2. Validate SunSpec detection against FranklinWH device
3. Verify JSON/CSV output formats
4. Test thread safety with high concurrency
