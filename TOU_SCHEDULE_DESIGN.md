# TOU Schedule File Design

> **Purpose**: External schedule configuration for Time-of-Use mode  
> **Status**: Design Phase  
> **Future Integration**: Service Engine scheduler/monitor

---

## Overview

Replace hardcoded TOU schedule with file-based configuration that can be:
1. **Loaded by CLI** (`--schedule-file schedule.json`)
2. **Passed to library** (`TOUSchedule.from_file()`)
3. **Extended by Service Engine** (future scheduler integration)

---

## Design Principles

1. **Simple First** - JSON format, human-readable
2. **Backward Compatible** - Hardcoded schedule remains default
3. **Library-Friendly** - Easy to construct programmatically
4. **Future-Ready** - Structure supports scheduler integration

---

## JSON Schema

### Basic Schedule (v1)

```json
{
  "version": "1.0",
  "name": "Ausgrid TOU",
  "description": "Australian Ausgrid Time of Use rates",
  "timezone": "Australia/Sydney",
  
  "periods": [
    {
      "id": "peak",
      "name": "Peak",
      "hours": [16, 17, 18, 19, 20],
      "price": 0.55,
      "color": "#ff4444",
      "strategy": "discharge"
    },
    {
      "id": "shoulder",
      "name": "Shoulder",
      "hours": [7, 8, 9, 10, 11, 12, 13, 14, 15, 21, 22],
      "price": 0.25,
      "color": "#ffaa00",
      "strategy": "self_consumption"
    },
    {
      "id": "off_peak",
      "name": "Off-Peak",
      "hours": [23, 0, 1, 2, 3, 4, 5, 6],
      "price": 0.12,
      "color": "#44aa44",
      "strategy": "charge"
    }
  ],
  
  "rules": {
    "min_soc": 10,
    "max_soc": 95,
    "charge_from_grid": true,
    "export_limit_w": 5000
  }
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Schema version |
| `name` | string | Yes | Schedule name |
| `description` | string | No | Human description |
| `timezone` | string | No | IANA timezone name |
| `periods` | array | Yes | Time periods |
| `periods[].id` | string | Yes | Unique identifier |
| `periods[].name` | string | Yes | Display name |
| `periods[].hours` | array[int] | Yes | Hours (0-23) in this period |
| `periods[].price` | number | Yes | $/kWh |
| `periods[].strategy` | string | Yes | Battery strategy |
| `rules` | object | No | Constraint rules |

### Strategy Values

| Strategy | Behavior |
|----------|----------|
| `charge` | Charge battery (from solar or grid) |
| `discharge` | Discharge battery to power home/export |
| `self_consumption` | Use solar first, then battery, then grid |
| `grid_zero` | Minimize grid import/export |
| `standby` | Let aGate manage itself |

---

## Library Integration

### Current TOUSchedule Class Extension

```python
@dataclass
class TOUSchedule:
    """Time-of-use rate periods for arbitrage."""
    
    # Existing fields (remain for backward compat)
    peak_hours: Tuple[int, int] = (16, 21)
    shoulder_hours: Tuple[int, int] = (7, 16)
    off_peak_hours: Tuple[int, int] = (21, 7)
    peak_price: float = 0.50
    shoulder_price: float = 0.25
    off_peak_price: float = 0.10
    
    # New: File-based schedule
    schedule_file: Optional[str] = None
    _schedule_data: Optional[Dict] = None
    
    @classmethod
    def from_file(cls, filepath: str) -> "TOUSchedule":
        """Load schedule from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Validate schema
        cls._validate_schema(data)
        
        # Create instance with loaded data
        instance = cls(schedule_file=filepath, _schedule_data=data)
        
        # Extract legacy fields if present
        instance._populate_from_schedule(data)
        
        return instance
    
    def get_current_period(self) -> str:
        """Determine current period (file-based or legacy)."""
        if self._schedule_data:
            hour = datetime.now().hour
            for period in self._schedule_data['periods']:
                if hour in period['hours']:
                    return period['id']
            return "unknown"
        
        # Legacy logic
        return self._get_legacy_period()
    
    def get_strategy(self) -> str:
        """Get battery strategy for current period."""
        if self._schedule_data:
            period_id = self.get_current_period()
            for period in self._schedule_data['periods']:
                if period['id'] == period_id:
                    return period.get('strategy', 'self_consumption')
        return 'self_consumption'
    
    def get_rules(self) -> Dict:
        """Get constraint rules."""
        if self._schedule_data:
            return self._schedule_data.get('rules', {})
        return {}
```

---

## CLI Usage

### Load Schedule File

```bash
# Use schedule file
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode time_of_use --schedule-file ausgrid_tou.json

# Show current schedule
python franklinwh_control_standalone.py --show-schedule ausgrid_tou.json

# Validate schedule file
python franklinwh_control_standalone.py --validate-schedule my_schedule.json
```

### CLI Arguments Addition

```python
parser.add_argument('--schedule-file', type=str, metavar='FILE',
                    help='TOU schedule JSON file (for time_of_use mode)')
parser.add_argument('--show-schedule', type=str, metavar='FILE',
                    help='Display schedule and exit')
parser.add_argument('--validate-schedule', type=str, metavar='FILE',
                    help='Validate schedule file and exit')
```

---

## Example Schedules

### Simple 2-Period (Day/Night)

```json
{
  "version": "1.0",
  "name": "Simple Day/Night",
  "periods": [
    {
      "id": "day",
      "name": "Day",
      "hours": [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
      "price": 0.30,
      "strategy": "self_consumption"
    },
    {
      "id": "night",
      "name": "Night",
      "hours": [21, 22, 23, 0, 1, 2, 3, 4, 5, 6],
      "price": 0.15,
      "strategy": "charge"
    }
  ],
  "rules": {
    "min_soc": 20
  }
}
```

### Australian Ausgrid (3-period)

```json
{
  "version": "1.0",
  "name": "Ausgrid TOU",
  "timezone": "Australia/Sydney",
  "periods": [
    {
      "id": "peak",
      "name": "Peak",
      "hours": [14, 15, 16, 17, 18, 19, 20],
      "price": 0.55,
      "strategy": "discharge"
    },
    {
      "id": "shoulder",
      "name": "Shoulder",
      "hours": [7, 8, 9, 10, 11, 12, 13, 21, 22],
      "price": 0.24,
      "strategy": "self_consumption"
    },
    {
      "id": "off_peak",
      "name": "Off-Peak",
      "hours": [23, 0, 1, 2, 3, 4, 5, 6],
      "price": 0.12,
      "strategy": "charge"
    }
  ],
  "rules": {
    "min_soc": 10,
    "max_soc": 95,
    "charge_from_grid": true
  }
}
```

### Weekend- Aware Schedule (Future v2)

```json
{
  "version": "2.0",
  "name": "Weekend Aware",
  "periods": [
    {
      "id": "weekday_peak",
      "name": "Weekday Peak",
      "days": ["mon", "tue", "wed", "thu", "fri"],
      "hours": [16, 17, 18, 19, 20],
      "price": 0.55,
      "strategy": "discharge"
    },
    {
      "id": "weekend_offpeak",
      "name": "Weekend Off-Peak",
      "days": ["sat", "sun"],
      "hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
      "price": 0.15,
      "strategy": "charge"
    }
  ]
}
```

---

## Future: Service Engine Integration

### Scheduler Library Integration

```python
# Future integration with APScheduler or similar
from apscheduler.schedulers.background import BackgroundScheduler

class TOUScheduler:
    """Service Engine component for TOU scheduling."""
    
    def __init__(self, schedule: TOUSchedule, controller: FranklinWHController):
        self.schedule = schedule
        self.controller = controller
        self.scheduler = BackgroundScheduler()
        
    def start(self):
        """Start scheduled mode transitions."""
        for period in self.schedule.get_periods():
            for hour in period['hours']:
                # Schedule strategy change at each hour
                self.scheduler.add_job(
                    self._apply_strategy,
                    'cron',
                    hour=hour,
                    minute=0,
                    args=[period['strategy']]
                )
        self.scheduler.start()
    
    def _apply_strategy(self, strategy: str):
        """Apply battery strategy for current period."""
        # Calculate power based on strategy
        power = self._calculate_strategy_power(strategy)
        cmd = BatteryCommand(power_watts=power)
        self.controller.send_command(cmd)
```

### Service Engine Provider

```python
# In franklinwh-energy-manager providers/modbus.py
class ModbusProvider(EnergyDataProvider):
    def __init__(self, config: dict):
        self.controller = FranklinWHController(...)
        self.schedule = None
        
    def load_schedule(self, schedule_file: str):
        """Load TOU schedule for automated operation."""
        self.schedule = TOUSchedule.from_file(schedule_file)
        # Register with service engine scheduler
        self.service_engine.register_schedule(self.schedule)
```

---

## Implementation Phases

### Phase 1: Basic File Support (Now)
- [ ] Add `TOUSchedule.from_file()` classmethod
- [ ] Add `--schedule-file` CLI argument
- [ ] Add `--show-schedule` for validation
- [ ] Create example schedule files
- [ ] Update `_calc_time_of_use()` to use file-based strategy

### Phase 2: Enhanced Strategies (Future)
- [ ] Implement all strategy types (charge, discharge, etc.)
- [ ] Add rule enforcement (min_soc, max_soc)
- [ ] Weekend/day-of-week support
- [ ] Seasonal schedules

### Phase 3: Service Engine Integration (Future)
- [ ] Scheduler library integration
- [ ] Background service mode
- [ ] Schedule switching without restart
- [ ] Web UI for schedule editing

---

## File Locations

```
schedules/
├── ausgrid_tou.json          # Australian Ausgrid
├── simple_day_night.json     # Basic 2-period
├── custom_template.json      # Starting point for users
└── README.md                 # Schedule documentation
```

---

*End of TOU Schedule Design*
