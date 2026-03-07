# FranklinWH Time-of-Use (TOU) Schedule Reference

Complete reference for TOU dispatch codes and schedule configuration.

---

## Dispatch Codes

Dispatch codes determine how the battery operates during each time period.

| Code | Name | Description | Behavior |
|------|------|-------------|----------|
| 1 | HOME / HOME_LOADS | Power home from battery | Battery → Home, excess solar → Grid |
| 2 | STANDBY | Battery on standby | Solar → Home → Grid, battery idle |
| 3 | SOLAR / SOLAR_CHARGE | Charge from solar only | Solar → Battery, home from grid if needed |
| 6 | SELF / SELF_CONSUMPTION | Self-consumption mode | Solar → Home → Battery → Grid |
| 7 | GRID_EXPORT / GRID_DISCHARGE | Export to grid | Battery → Grid (discharge for profit) |
| 8 | GRID_CHARGE / GRID_IMPORT | Charge from grid | Grid → Battery (buy low) |

---

## Wave Types (Pricing Periods)

| Value | Name | Typical Usage |
|-------|------|---------------|
| 0 | Off-Peak | Night time, lowest prices |
| 1 | Mid-Peak | Shoulder periods |
| 2 | On-Peak | Peak demand, highest prices |
| 4 | Super Off-Peak | Deep night, EV charging rates |

---

## JSON Schedule Format

### Minimum Required Fields
```json
{
  "startHourTime": "00:00",
  "endHourTime": "06:00",
  "waveType": 0,
  "name": "Off-Peak Charging",
  "dispatchId": 8
}
```

### Full Schedule Example
```json
[
  {
    "startHourTime": "00:00",
    "endHourTime": "06:00",
    "waveType": 0,
    "name": "Off-Peak Charging",
    "dispatchId": 8,
    "minDischargeSoc": 20,
    "maxChargeSoc": 100
  },
  {
    "startHourTime": "06:00",
    "endHourTime": "15:00",
    "waveType": 1,
    "name": "Self-Consumption",
    "dispatchId": 6
  },
  {
    "startHourTime": "15:00",
    "endHourTime": "21:00",
    "waveType": 2,
    "name": "Peak Export",
    "dispatchId": 7
  },
  {
    "startHourTime": "21:00",
    "endHourTime": "24:00",
    "waveType": 1,
    "name": "Evening Normal",
    "dispatchId": 1
  }
]
```

---

## Predefined Schedules

### 1. Charge from Grid (Night)
```json
[
  {
    "startHourTime": "00:00",
    "endHourTime": "24:00",
    "waveType": 2,
    "name": "On-Peak",
    "dispatchId": 8
  }
]
```

### 2. Power Home Only
```json
[
  {
    "startHourTime": "00:00",
    "endHourTime": "24:00",
    "waveType": 2,
    "name": "On-Peak",
    "dispatchId": 1
  }
]
```

### 3. Export to Grid at Peak
```json
[
  {
    "startHourTime": "18:00",
    "endHourTime": "21:00",
    "waveType": 2,
    "name": "On-Peak",
    "dispatchId": 7
  }
]
```

### 4. Complete Daily Schedule
```json
[
  {
    "startHourTime": "00:00",
    "endHourTime": "06:00",
    "waveType": 0,
    "name": "Off-Peak",
    "dispatchId": 8
  },
  {
    "startHourTime": "06:00",
    "endHourTime": "15:00",
    "waveType": 1,
    "name": "Mid-Peak",
    "dispatchId": 6
  },
  {
    "startHourTime": "15:00",
    "endHourTime": "21:00",
    "waveType": 2,
    "name": "On-Peak",
    "dispatchId": 7
  },
  {
    "startHourTime": "21:00",
    "endHourTime": "24:00",
    "waveType": 1,
    "name": "Mid-Peak",
    "dispatchId": 1
  }
]
```

---

## Time Format

- **Format**: "HH:MM" (24-hour)
- **Range**: 00:00 to 24:00
- **Overlap**: Periods must not overlap
- **Gaps**: Gaps between periods use default behavior

---

## Validation Rules

1. **Required Fields**: `startHourTime`, `endHourTime`, `waveType`, `name`, `dispatchId`
2. **Time Format**: Must match regex `^([0-1]?[0-9]|2[0-3]):[0-5][0-9]|24:00$`
3. **WaveType**: Must be 0, 1, 2, or 4
4. **DispatchId**: Must be 1, 2, 3, 6, 7, or 8
5. **No Overlaps**: Time periods cannot overlap
6. **Ordered**: Periods should be in chronological order

---

## Use Cases

### Arbitrage (Buy Low, Sell High)
```
00:00-06:00:  Charge from grid (off-peak rates)
15:00-21:00:  Export to grid (peak rates)
```

### Self-Consumption Maximization
```
06:00-18:00:  Self-consumption (use solar + battery)
Other times:  Power home from battery
```

### Backup Preparation
```
00:00-06:00:  Charge to 100% (prepare for outages)
All day:      Self-consumption with high reserve
```

---

## API Integration

### Validating Schedules
```python
from franklinwh.constants import tou_json_schema
import jsonschema

jsonschema.validate(schedule_data, tou_json_schema)
```

### Dispatch Code Lookup
```python
from franklinwh.constants import DISPATCH_CODES

# Get code from name
code = DISPATCH_CODES["GRID_EXPORT"]  # Returns 7

# Get name from code
description = DISPATCH_CODES[7]  # Returns "aPower to home/grid"
```

---

*Last Updated: February 22, 2026*
