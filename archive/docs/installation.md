# Installation & Setup Guide

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker | 20.10+ | Or Docker Desktop |
| Docker Compose | 2.0+ | Optional but recommended |
| Home Assistant | 2023.1+ | For add-on installation |
| Network Access | TCP 502, 1883, 8080 | Firewall configuration |

## Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 core | 2 cores |
| RAM | 256 MB | 512 MB |
| Storage | 100 MB | 1 GB (for logs) |
| Network | 100 Mbps | 1 Gbps |

## Installation Methods

### Method 1: Docker Compose (Recommended)

#### 1. Create Project Directory

```bash
mkdir ~/franklinwh-manager
cd ~/franklinwh-manager
```

#### 2. Create `docker-compose.yml`

```yaml
version: '3.8'

services:
  franklinwh:
    image: ghcr.io/yourusername/franklinwh-ha:latest
    container_name: franklinwh-manager
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - MODBUS_HOST=192.168.0.110
      - MODBUS_PORT=502
      - MODBUS_UNIT=2
      - MQTT_HOST=192.168.0.109
      - MQTT_PORT=1883
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/data
    networks:
      - franklinwh-net

networks:
  franklinwh-net:
    driver: bridge
```

#### 3. Start the Container

```bash
docker-compose up -d
```

#### 4. Verify Installation

```bash
# Check logs
docker-compose logs -f

# Test connectivity
curl http://localhost:8080/api/health
```

### Method 2: Home Assistant Add-on

#### 1. Add Repository

In Home Assistant, go to **Settings** → **Add-ons** → **Add-on Store** → **⋮** → **Repositories**

Add: `https://github.com/yourusername/hassio-addons`

#### 2. Install Add-on

Find "FranklinWH Battery Manager" and click **Install**

#### 3. Configure

```yaml
modbus_host: 192.168.0.110
modbus_port: 502
modbus_unit: 2
mqtt_host: 192.168.0.109
mqtt_port: 1883
mqtt_username: ""
mqtt_password: ""
log_level: info
```

#### 4. Start

Click **Start** and enable **Start on boot**

### Method 3: Standalone Python

#### 1. Clone Repository

```bash
git clone https://github.com/yourusername/franklinwh-ha.git
cd franklinwh-ha
```

#### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 4. Create `.env` File

```bash
cat > .env << 'EOF'
MODBUS_HOST=192.168.0.110
MODBUS_PORT=502
MODBUS_UNIT=2
MQTT_HOST=192.168.0.109
MQTT_PORT=1883
LOG_LEVEL=INFO
EOF
```

#### 5. Run Application

```bash
python -m src.main
```

## Initial Configuration

### Step 1: Access Web Interface

Open browser to: `http://<host-ip>:8080`

### Step 2: Configure Modbus Connection

1. Click **⚙️ Settings** (top right)
2. Enter FranklinWH device IP (default: 192.168.0.110)
3. Set Unit ID (default: 2)
4. Click **Save Settings**

### Step 3: Configure MQTT (Optional)

1. In Settings, scroll to **MQTT Broker**
2. Enter Home Assistant IP (default: 192.168.0.109)
3. Add credentials if required
4. Save

### Step 4: Verify Data

1. Return to **Dashboard**
2. Check connection status (green dot = connected)
3. Verify SOC, power readings appear

## Configuration File Reference

### Location

| Method | Path |
|--------|------|
| Docker | `./data/config.json` (mounted volume) |
| Add-on | `/config/franklinwh/config.json` |
| Standalone | `./data/config.json` |

### Schema

```json
{
  "modbus": {
    "host": "192.168.0.110",
    "port": 502,
    "unit_id": 2,
    "base_address": 40000,
    "timeout": 5.0
  },
  "mqtt": {
    "host": "192.168.0.109",
    "port": 1883,
    "username": "",
    "password": "",
    "discovery_prefix": "homeassistant"
  },
  "theme": {
    "mode": "auto",
    "primary_color": "#3b82f6"
  },
  "widgets": {
    "battery_metrics": {
      "enabled": true,
      "position": 0,
      "color": "#10b981"
    }
  },
  "auto_refresh": true,
  "refresh_interval": 30
}
```

## Startup & Shutdown

### Docker Compose

```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Stop and remove data
docker-compose down -v
```

### Home Assistant Add-on

- **Start**: Add-on page → Start
- **Stop**: Add-on page → Stop
- **Restart**: Add-on page → Restart

### Systemd Service (Standalone)

Create `/etc/systemd/system/franklinwh.service`:

```ini
[Unit]
Description=FranklinWH Battery Manager
After=network.target

[Service]
Type=simple
User=franklinwh
WorkingDirectory=/opt/franklinwh-ha
Environment=PATH=/opt/franklinwh-ha/venv/bin
ExecStart=/opt/franklinwh-ha/venv/bin/python -m src.main
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable franklinwh
sudo systemctl start franklinwh
sudo systemctl status franklinwh
```

## Troubleshooting

### Connection Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Connection failed" | Wrong IP | Verify with `ping 192.168.0.110` |
| "No models found" | Wrong unit ID | Try unit IDs 1-5 |
| "Modbus timeout" | Network issue | Check firewall, cable |
| "MQTT connection refused" | Wrong broker IP | Verify HA MQTT addon |

### Debug Mode

```bash
# Enable debug logging
LOG_LEVEL=DEBUG docker-compose up -d

# View raw Modbus traffic
docker-compose exec franklinwh python -m src.modbus_debug
```

### Reset to Defaults

```bash
# Docker
rm ./data/config.json
docker-compose restart

# Add-on
Configuration → Reset to defaults → Save
```

## Security Considerations

1. **Network Isolation**: Place battery on isolated VLAN
2. **MQTT Authentication**: Always use credentials in production
3. **TLS**: Enable for MQTT if跨越 networks
4. **Firewall**: Restrict port 8080 to management hosts only
