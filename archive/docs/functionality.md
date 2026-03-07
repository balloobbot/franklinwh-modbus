# Functionality & Features

## Core Purpose

FranklinWH Battery Manager serves as a bridge between FranklinWH battery systems and modern home automation platforms, providing both direct control capabilities and seamless Home Assistant integration.

## Feature Categories

### 1. Data Acquisition & Monitoring

#### Battery Metrics (Model 713/714)
| Metric | Source | Scale Factor | Unit | Update Rate |
|--------|--------|--------------|------|-------------|
| State of Charge (SoC) | 15011 | -1 | % | 5s |
| State of Health (SoH) | 15036 | -1 | % | 30s |
| Rated Energy | 713.WHRtg | 0 | Wh | 300s |
| Available Energy | 713.WHAvail | 0 | Wh | 30s |
| Temperature | 714.Tmp | -1 | °C | 10s |
| Cycle Count | 714.CyC | 0 | - | 300s |

#### Inverter Metrics (Model 701)
| Metric | Registers | Scale Factor | Unit |
|--------|-----------|--------------|------|
| AC Power | W | W_SF | W |
| Voltage | PhV | V_SF | V |
| Current | A | A_SF | A |
| Frequency | Hz | Hz_SF | Hz |
| Power Factor | PF | PF_SF | - |
| Apparent Power | VA | VA_SF | VA |
| Reactive Power | VAR | VAR_SF | VAR |

### 2. Control Operations

#### Operating Modes

```python
class OperatingMode(Enum):
    STANDBY = 0          # System idle, no power flow
    NORMAL = 1           # Automatic operation based on conditions
    BACKUP_RESERVE = 2   # Maintain reserve SOC for outages
    SELF_CONSUMPTION = 3 # Maximize self-use of solar
    TIME_OF_USE = 4      # Follow utility rate schedule
```

Mode transitions are protected:
- Minimum 5-second delay between changes
- Validation of reserve SOC compatibility
- Automatic fallback on communication failure

#### Reserve SOC Management

| Parameter | Register | Range | Default | Description |
|-----------|----------|-------|---------|-------------|
| Reserve SOC Primary | 15017 | 0-100% | 20% | Minimum battery level for backup |
| Reserve SOC Secondary | 15040 | -128 to 127 | -9 | Extended reserve (purpose TBD) |

#### Power Limit Control

Set charge/discharge limits via:
- **Absolute power** (kW or W)
- **Current** (A, voltage-compensated)
- **Percentage** of rated capacity

```python
# Example: Set 3kW charge limit
await client.set_charge_limit(power_w=3000)

# Example: Set 10A discharge (converted to W)
await client.set_discharge_limit(amps=10)

# Example: 80% of max capacity
await client.set_discharge_limit(percent=80)
```

### 3. Home Assistant Integration

#### Auto-Discovery

The application publishes MQTT discovery messages for automatic entity creation:

```yaml
# Example discovery topic
homeassistant/sensor/franklinwh_soc/config

# Payload
{
  "name": "FranklinWH State of Charge",
  "state_topic": "franklinwh/battery/soc",
  "unit_of_measurement": "%",
  "device_class": "battery",
  "unique_id": "franklinwh_abc123_soc"
}
```

#### Entity Types

| Type | Count | Examples |
|------|-------|----------|
| sensor | 25 | SOC, SOH, power, voltage, current, temperature |
| binary_sensor | 5 | Fault status, grid status, communication status |
| number | 4 | Reserve SOC, power limits |
| select | 1 | Operating mode |
| switch | 3 | Force charge, force discharge, reset faults |

#### Command Topics

| Topic | Payload | Action |
|-------|---------|--------|
| `franklinwh/operating_mode/set` | `Backup Reserve` | Change mode |
| `franklinwh/reserve_soc/set` | `25` | Set reserve to 25% |
| `franklinwh/max_charge_power/set` | `5000` | Limit charge to 5kW |

### 4. Web Interface Features

#### Dashboard Widgets

| Widget | Purpose | Customization |
|--------|---------|---------------|
| Battery Metrics | Core battery status | Color, position, auto-expand |
| Inverter Status | AC electrical parameters | Refresh interval |
| Power Flow | Real-time power visualization | Chart type, history length |
| Energy Stats | Daily/weekly energy totals | Date range, comparison |
| System Health | Alerts and diagnostics | Severity filtering |
| Reserve Settings | Quick reserve adjustment | Slider vs numeric input |
| Control Panel | Mode selection | Confirmation dialogs |

#### Theme System

```javascript
// Theme configuration
{
  mode: 'auto',        // 'light' | 'dark' | 'auto'
  primary_color: '#3b82f6',
  secondary_color: '#10b981',
  accent_color: '#f59e0b',
  shadow_intensity: 'medium'  // 'none' | 'low' | 'medium' | 'high'
}
```

#### Responsive Breakpoints

| Breakpoint | Layout | Columns |
|------------|--------|---------|
| < 640px | Mobile | 1 |
| 640-1024px | Tablet | 2 |
| 1024-1280px | Desktop | 2-3 |
| > 1280px | Wide | 3-4 |

### 5. Data Logging & Diagnostics

#### Log Levels

| Level | Use Case | Storage |
|-------|----------|---------|
| DEBUG | Raw register reads, calculations | Memory (last 100) |
| INFO | Mode changes, setting updates | File + Memory |
| WARNING | Communication retries, bounds clamping | File + Memory |
| ERROR | Failed operations, timeouts | File + Memory + Alert |

#### Raw Register Explorer

Features for debugging:
- Address range selection
- Multiple interpretation formats (uint16, int16, hex, binary)
- Pattern matching against known values
- Export to CSV/JSON

### 6. Safety & Protection

#### Write Protection

| Check | Action |
|-------|--------|
| SOC reserve > current SOC | Block mode change, alert user |
| Power limit > rated capacity | Clamp to rated, log warning |
| Rapid mode switching | Enforce 5-second cooldown |
| Communication timeout | Revert to last known good state |

#### Automatic Recovery

```python
# Retry logic for Modbus operations
for attempt in range(3):
    try:
        return await operation()
    except ModbusTimeout:
        await asyncio.sleep(2 ** attempt)  # Exponential backoff
raise CommunicationFailure()
```

## Performance Specifications

| Metric | Target | Maximum |
|--------|--------|---------|
| UI Response Time | < 100ms | 500ms |
| Data Refresh Rate | 5s | 1s (configurable) |
| Modbus Timeout | 5s | 30s |
| MQTT Reconnect | 5s | 60s |
| Simultaneous Connections | 10 | 50 |

## Future Enhancements

- [ ] Time-of-Use schedule editor
- [ ] Solar forecasting integration
- [ ] Virtual power plant (VPP) protocols
- [ ] Battery degradation modeling
- [ ] Predictive maintenance alerts
