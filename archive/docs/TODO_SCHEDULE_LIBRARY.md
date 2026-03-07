# TODO: Python Schedule Library for Built-in TOU Alternative

## Objective
Implement a built-in Time-of-Use (TOU) scheduling system as an alternative to FranklinWH's native TOU mode, providing greater flexibility and control.

## Motivation
- Custom scheduling rules beyond FranklinWH's built-in TOU
- Integration with dynamic pricing APIs
- More granular control over charge/discharge behavior
- Support for complex tariff structures (multiple peak/off-peak periods)
- Backup scheduling when cloud connection fails

## Recommended Library
**Python `schedule` library** - https://schedule.readthedocs.io/

### Pros
- Simple, Pythonic API
- Lightweight (no heavy dependencies)
- Easy to understand and maintain
- Good for periodic tasks

### Example Usage
```python
import schedule
import time

def charge_battery():
    # Set battery to charge mode
    client.set_operating_mode(SELF_CONSUMPTION)
    
def discharge_battery():
    # Set battery to discharge mode for peak pricing
    client.set_operating_mode(TIME_OF_USE)

# Schedule based on tariff periods
schedule.every().day.at("00:00").do(charge_battery)  # Off-peak
schedule.every().day.at("17:00").do(discharge_battery)  # Peak
schedule.every().day.at("21:00").do(charge_battery)  # Off-peak

while True:
    schedule.run_pending()
    time.sleep(60)
```

## Implementation Plan

### Phase 1: Basic Scheduler
- [ ] Install `schedule` library
- [ ] Create `src/scheduler.py` module
- [ ] Implement basic time-based scheduling
- [ ] Add start/stop controls via API
- [ ] Create UI for enabling/disabling built-in scheduler

### Phase 2: Tariff Configuration
- [ ] Design tariff configuration schema (JSON/YAML)
- [ ] Store tariff schedules in database
- [ ] Create UI for tariff period management
- [ ] Support multiple tariff zones (peak/shoulder/off-peak)
- [ ] Add timezone support

### Phase 3: Dynamic Pricing Integration
- [ ] Integrate with electricity pricing APIs (e.g., Amber Electric, OpenNEM)
- [ ] Automatic schedule adjustment based on real-time prices
- [ ] Threshold-based discharge (only when price > $X/kWh)
- [ ] Notifications when high-price events detected

### Phase 4: Advanced Features
- [ ] Weather-based optimization (forecast-aware charging)
- [ ] Battery SOC-aware scheduling (e.g., only discharge if SOC > 80%)
- [ ] Integration with solar forecasting
- [ ] Machine learning for usage pattern optimization
- [ ] Schedule templates (preset tariff profiles)

## Configuration Example
```yaml
# config/tariff_schedule.yaml
tariff:
  timezone: "Australia/Sydney"
  periods:
    - name: "Off-Peak"
      times: ["00:00-07:00", "21:00-23:59"]
      action: "charge"
      max_soc: 100
      
    - name: "Shoulder"
      times: ["07:00-17:00"]
      action: "self_consumption"
      reserve_soc: 20
      
    - name: "Peak"
      times: ["17:00-21:00"]
      action: "discharge"
      min_soc: 20
      discharge_limit: 5000  # watts
```

## Backend Components

### Scheduler Module (`src/scheduler.py`)
```python
class TariffScheduler:
    def __init__(self, config_path, modbus_client):
        self.config = load_config(config_path)
        self.client = modbus_client
        self.schedule = schedule
        
    def setup_schedule(self):
        """Configure schedule from tariff config"""
        pass
        
    def run(self):
        """Run scheduler in background thread"""
        pass
```

### API Endpoints
```python
# New endpoints in web_server.py
GET  /api/scheduler/status
POST /api/scheduler/enable
POST /api/scheduler/disable
GET  /api/scheduler/config
PUT  /api/scheduler/config
GET  /api/tariff/periods
POST /api/tariff/periods
```

## Frontend UI Requirements

### Scheduler Control Panel
- [ ] Enable/Disable toggle
- [ ] Current schedule status
- [ ] Next scheduled action display
- [ ] Manual override button
- [ ] Schedule history log

### Tariff Period Manager
- [ ] Visual timeline editor
- [ ] Period creation/editing
- [ ] Color-coded period types
- [ ] Import/export schedules
- [ ] Schedule templates

## Safety Features
- [ ] Conflict detection with FranklinWH native TOU
- [ ] Battery protection (min/max SOC limits)
- [ ] Grid constraints (max import/export)
- [ ] Failsafe mode (revert to Self-Consumption on errors)
- [ ] Schedule validation before activation

## Integration Points
- Modbus client for mode changes
- Config manager for persistent storage
- Web UI for user control
- MQTT for status updates

## Alternative Libraries to Consider
- **APScheduler** - More features, but heavier
- **Celery** - Overkill for simple scheduling, requires message broker
- **Cron** - System-level, less flexible for dynamic changes

## Priority
Medium-High - Provides significant value but not critical for core functionality

## Dependencies
```
schedule>=1.2.0
pytz>=2023.3  # For timezone support
```

## Notes
- Should coexist with FranklinWH TOU (user can choose which to use)
- Consider logging all schedule actions for audit trail
- May want to visualize schedule on dashboard
- Could integrate with Home Assistant automations
