# TOU Schedule Files

This directory contains Time-of-Use (TOU) schedule files for the FranklinWH battery controller.

## Usage

```bash
# Use a schedule file with time_of_use mode
python franklinwh_control_standalone.py -i YOUR_AGATE_IP \
  --reset-on-start --mode time_of_use --schedule-file schedules/ausgrid_tou.json

# Validate a schedule file
python franklinwh_control_standalone.py --validate-schedule schedules/my_schedule.json

# Display schedule contents
python franklinwh_control_standalone.py --show-schedule schedules/ausgrid_tou.json
```

## Available Schedules

| File | Description | Periods |
|------|-------------|---------|
| `simple_day_night.json` | Basic 2-period schedule | Day (self-consumption), Night (charge) |
| `ausgrid_tou.json` | Australian Ausgrid TOU | Peak (discharge), Shoulder (self-consumption), Off-peak (charge) |

## Schedule Format

Schedules are JSON files with the following structure:

```json
{
  "version": "1.0",
  "name": "My Schedule",
  "description": "Description of this schedule",
  "timezone": "Australia/Sydney",
  "periods": [
    {
      "id": "peak",
      "name": "Peak Hours",
      "hours": [16, 17, 18, 19, 20],
      "price": 0.55,
      "color": "#ff4444",
      "strategy": "discharge"
    }
  ],
  "rules": {
    "min_soc": 10,
    "max_soc": 95,
    "charge_from_grid": true
  }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Schema version ("1.0") |
| `name` | string | Yes | Schedule name |
| `description` | string | No | Human-readable description |
| `timezone` | string | No | IANA timezone name |
| `periods` | array | Yes | Array of time periods |
| `periods[].id` | string | Yes | Unique identifier for period |
| `periods[].name` | string | Yes | Display name |
| `periods[].hours` | array[int] | Yes | Hours (0-23) in this period |
| `periods[].price` | number | Yes | Electricity price $/kWh |
| `periods[].strategy` | string | Yes | Battery strategy (see below) |
| `rules` | object | No | Constraint rules |
| `rules.min_soc` | number | No | Minimum SoC (default: 10) |
| `rules.max_soc` | number | No | Maximum SoC (default: 95) |
| `rules.charge_from_grid` | boolean | No | Allow grid charging (default: true) |

### Strategies

| Strategy | Behavior |
|----------|----------|
| `charge` | Charge battery (from solar or grid) |
| `discharge` | Discharge battery to power home/export |
| `self_consumption` | Use solar first, then battery, then grid |
| `grid_zero` | Minimize grid import/export |
| `standby` | Let aGate manage itself |

## Creating Custom Schedules

1. Copy `simple_day_night.json` as a template
2. Modify hours, prices, and strategies
3. Validate with `--validate-schedule`
4. Test with your aGate

## Future Enhancements

- Weekend/weekday differentiation
- Seasonal schedules
- Dynamic pricing from APIs
- Web UI editor
