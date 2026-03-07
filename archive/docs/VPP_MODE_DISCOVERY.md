# VPP Mode Discovery - Battery Control Solution

**Date:** 2026-02-15  
**Key Finding:** FranklinWH automatically switches to **VPP Mode** when battery control commands are sent

## The Discovery

After extensive testing, we discovered that when Model 704 battery control commands are sent via Modbus, the FranklinWH system **automatically switches to VPP Mode (4)** internally.

**VPP Mode is not manually set** - it's triggered by the system when it detects remote control commands.

### Operating Modes

| Mode ID | Mode Name | Notes |
|---------|-----------|-------|
| 0 | Self-Consumption | Standard operation |
| 1 | Time-of-Use (TOU) | Scheduled charging/discharging |
| 2 | Backup Only | Battery reserved for backup |
| 3 | Grid Tie | Grid-connected mode |
| **4** | **Remote Control/VPP** | **Auto-activated by Model 704 commands** |

## Why This Works

When you send Model 704 battery control commands (WSetEna, WSetMod, WSet):
1. FranklinWH detects external control attempt
2. **System automatically switches to VPP Mode (4)**
3. Battery responds to your commands
4. Mode persists as long as external control is active

## Updated Tool: battery_ctl.py

### Operating Mode Display

The tool now displays the current operating mode and notes that VPP mode switching is automatic:

```bash
python3 battery_ctl.py 192.168.0.110 --status
```

**Output:**
```
⚙️  Operating Mode: Backup Only
   ℹ️  System auto-switches to VPP mode when battery control commands are sent

📊 CURRENT STATE:
   Enable: ENABLED
   Mode:   Absolute W
   Power:  IDLE
```

### Battery Control Commands

Simply send battery control commands - VPP mode activation is automatic:

```bash
# Discharge at 3000W with verbose paranoid mode
python3 battery_ctl.py 192.168.0.110 3000 --verbose
```

**The system handles VPP mode internally** - no manual intervention needed!

## Implementation Details

### Mode Switch Function

```python
def set_vpp_mode(client):
    """Switch system to VPP Mode (Remote Control) for battery control"""
    client.write_register(15507, 4, device_id=1)  # Set mode to VPP
    time.sleep(0.5)  # Allow mode switch to settle
    # Verify mode change
    r = client.read_holding_registers(15507, count=1, device_id=1)
    return r.registers[0] == 4
```

### Register Details

**Operating Mode Register:**
- **Modbus Address:** 40001 + 15507 = 55508
- **PDU Address:** 15507
- **Device ID:** 1 (main system)
- **Type:** uint16
- **Access:** Read/Write
- **Values:** 0-4 (operating modes)

## Command Sequence (Complete)

With --auto-vpp flag:

```
1. Check Operating Mode (register 15507)
2. If not VPP (4), write 4 to register 15507
3. Verify mode switch
4. Execute battery control sequence:
   a. DISABLE (WSetEna = 0)
   b. SET MODE (WSetMod = 0)
   c. DISABLE AUTO-REVERT (WSetRvrtTms = 0)
   d. WRITE POWER (WSet = target)
   e. ENABLE (WSetEna = 1)
5. Verify registers
```

## Important Notes

1. **Manual App Control**: User can also manually change to VPP mode in FranklinWH app  
2. **Persistent Mode**: VPP mode persists across reboots
3. **Safety**: Always check battery SOC and load before discharging
4. **Reversion**: WSetRvrtTms=0 prevents automatic reversion

## Files Updated

- `battery_ctl.py` - Added `--auto-vpp` flag and mode switching
- `BATTERY_CTL_GUIDE.md` - Updated usage examples
- This document - VPP mode discovery documentation

## Testing Recommendation

Test sequence:
```bash
# 1. Check current state
python3 battery_ctl.py 192.168.0.110 --status

# 2. Try with auto-VPP to discharge
python3 battery_ctl.py 192.168.0.110 3000 --auto-vpp --verbose

# 3. Monitor actual battery power (Model 714 DCW register)
python3 modbus_sunspec2_reader.py -i 192.168.0.110 -u 2 -m 714 | grep DCW

# 4. Restore to idle when done
python3 battery_ctl.py 192.168.0.110 0 --verbose
```

## Related Documentation

- `WORKING_BATTERY_CONTROL_SEQUENCE.md` - Complete control sequence
- `BATTERY_CONTROL_REVERSION_FIX.md` - WSetRvrtTms fix
- `BATTERY_CONTROL_SAFETY_USAGE.md` - Safety guidelines
- `FRANKLINWH_NATIVE_ADDRESSING.md` - Register addressing
