# Battery Control Testing - Quick Start

## Run Test (Virtual Environment Only)

```bash
cd /home/david/dev/modbus
source venv/bin/activate
python test_battery_control.py
```

## Test Phases

### Phase 1: Baseline Read (Safe)
- Reads current Model 702/704 values
- No writes
- Documents starting state

### Phase 2: Model 702 Limits
- Writes: `WChaRteMax = 2500W`, `WDisChaRteMax = 3000W`
- Tests absolute power limiting
- Monitors for 30 seconds

### Phase 3: Model 704 Percentage
- Writes: `WMaxLimPctEna = 1`, `WMaxLimPct = 50%`
- Tests percentage-based limiting
- Monitors for 30 seconds

### Phase 4: Timeout Test (Optional - 10 minutes)
- **Tests if FranklinWH requires heartbeat**
- Monitors limits every minute WITHOUT any writes
- Checks if limits persist or auto-revert
- Checks if connection drops

**If Phase 4 succeeds** → No heartbeat required! ✅  
**If Phase 4 fails** → Need to implement heartbeat monitoring ⚠️

## Safety Features

- User confirmation before each write
- Automatic rollback on errors
- Reads back values to verify writes
- Connection monitoring throughout

## Files Created

- `test_battery_control.py` - Test script
- `BATTERY_CONTROL_SAFETY.md` - Safety guidelines
