# TODO: MQTT Home Assistant Discovery - Value Precision Issue

**Status:** OPEN  
**Priority:** MEDIUM  
**Component:** MQTT Integration  
**File:** `src/mqtt_handler.py`

---

## Problem

Values published via MQTT Home Assistant Discovery have excessive floating-point precision, causing:
- Display issues in Home Assistant UI
- Values appearing outside normal ranges
- Poor user experience

### Example

**Current:** `96.2000000000002` (State of Health)  
**Expected:** `96.2`

---

## Root Cause

Floating-point arithmetic in Python creates precision artifacts that are not rounded before publishing to MQTT.

---

## Solution

Round values to appropriate precision before publishing:

```python
# In src/mqtt_handler.py or entity publishing code

def format_value(value, precision=1):
    """Round numeric values to specified decimal places."""
    if isinstance(value, (int, float)):
        return round(value, precision)
    return value

# Apply to MQTT payloads:
payload = {
    "state_of_health": format_value(soh, 1),  # 96.2
    "power": format_value(power, 0),          # 1300
    "voltage": format_value(voltage, 1),      # 242.1
}
```

### Precision Guidelines

- **Percentages:** 1 decimal (96.2%)
- **Power (W/kW):** 0 decimals (1,300 W)
- **Voltage:** 1 decimal (242.1 V)
- **Current:** 2 decimals (2.50 A)
- **Energy (Wh/kWh):** 1 decimal (13.6 kWh)
- **Temperature:** 1 decimal (39.5°C)

---

## Files to Modify

1. **`src/mqtt_handler.py`** - Add rounding to MQTT publish functions
2. **`src/models.py`** - Consider adding `to_mqtt()` methods with rounding

---

## Testing

Verify in Home Assistant that all sensors display clean values:
- State of Health: `96.2` (not `96.2000000000002`)
- Power: `1300` (not `1300.0000000001`)
- Voltage: `242.1` (not `242.09999999`)
