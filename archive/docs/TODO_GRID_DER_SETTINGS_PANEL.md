# TODO: Grid/DER Settings Panel

**Status:** Proposed  
**Created:** 2026-02-24  
**Priority:** Medium  
**Related Models:** 701 (DERMeasureAC), 702 (DERCapacity), 703 (DEREnterService)

## Summary

Add a dedicated panel/card to the terminal monitor showing Grid settings, Enter Service parameters, and DER operational characteristics from Model 701 and related models.

## Data to Display

### Model 701: DERMeasureAC Fields

| Address | Name | Description | Current Value |
|---------|------|-------------|---------------|
| 40072 | ACType | AC Wiring Type | 0 (Single-Phase) |
| 40073 | St | Operating State | 1 (STANDBY) |
| 40074 | InvSt | Inverter State | 3 (Running) |
| 40075 | ConnSt | Grid Connection State | 1 (Connected) |
| 40076 | Alrm | Alarm Bitfield | 0x00000000 |
| 40078 | DERMode | DER Operational Characteristics | 1 (Grid Following) |

### Grid-Related Metrics
- **AC Wiring Type**: Single-Phase / Split-Phase / Three-Phase
- **Operating State**: OFF / STANDBY / RUNNING / FAULT
- **Inverter State**: Off / Sleeping / Starting / Running / Throttled / Shutting Down / Fault / Standby
- **Grid Connection**: Connected / Disconnected / Fault
- **DER Mode**: Grid Following / Grid Forming (from DERMode bitfield)
- **Alarm Bitfield**: Hex display of active alarms

### Model 703: DEREnterService (Future)
- **ES**: Permit Enter Service (1 = Enabled)
- **ESVHi**: Enter Service Voltage High (253%)
- **ESVLo**: Enter Service Voltage Low (205%)
- **ESHzHi**: Enter Service Frequency High (50.15 Hz)
- **ESHzLo**: Enter Service Frequency Low (47.5 Hz)

## Proposed Layout

Replace or supplement the existing "AC Power" panel with a "Grid/DER Settings" panel:

```
╭──────────────────────── Grid & DER Settings ────────────────────────╮
│  AC Type:     Single-Phase (230V)                                   │
│  Op.State:    STANDBY [1]       Inv.State: Running [3]              │
│  Grid Conn:   ✓ Connected       DER Mode: Grid Following            │
│  Alarms:      None (0x00000000)                                     │
│  Enter Svc:   Enabled (ESV: 205-253%, ESHz: 47.5-50.15Hz)           │
╰─────────────────────────────────────────────────────────────────────╯
```

## Implementation Notes

1. **Read from Model 701** - Already being read in `read_grid_status()`
2. **Extend existing data** - Add new fields to grid status dictionary
3. **Display in monitor** - Either:
   - Replace AC Power panel with Grid/DER Settings
   - Add as separate panel (requires layout adjustment)
   - Combine with Device Info panel

## Files to Modify

- `src/franklinwh/controller.py` - Add DERMode, Enter Service fields to `read_grid_status()`
- `src/franklinwh/monitor.py` - Add `render_grid_settings()` method
- `src/franklinwh/monitor.py` - Update layout to include new panel

## References

- SunSpec DER Information Model (Models 701-703)
- Current Modbus register dump shows all values available
