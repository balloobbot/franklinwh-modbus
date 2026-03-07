# CLI Telemetry Enhancement - Demo

> **Fixes**: DEFECT-002 - Insufficient CLI output  
> **File**: `franklinwh_control_standalone.py`  
> **Commit**: `1ddeb97`

---

## Before (Old Output)

```
Command sent: WSetPct=30.0% (raw=300), WSet=1500, WSetEna=1
Status: SOC=75.0%, Grid=-200W
Status: SOC=75.2%, Grid=-180W
...
```

**Problems**:
- No home load information
- No solar PV data
- No elapsed time tracking
- No target SoC visibility
- Minimal context for what the mode is doing

---

## After (New Output)

```
======================================================================
  STARTING: self_consumption mode
  DURATION: 02:00:00
  Press Ctrl+C to stop
======================================================================

======================================================================
  MODE: SELF_CONSUMPTION
  ────────────────────────────────────────────────────────────────────
  ⏱️  ELAPSED: 00:05:32  |  ⏳ REMAINING: 01:54:28
  🎯 TARGET:   20% reserve
  ────────────────────────────────────────────────────────────────────
  BATTERY:    ⚡ CHARGING        1500W  |  SoC: 75.0%
  SOLAR PV:   ☀️  PRODUCING      2800W  |  
  HOME LOAD:  🏠 CONSUMING      1500W  |  
  GRID:       ↑ EXPORTING         200W
  ────────────────────────────────────────────────────────────────────
  CMD: WSetPct=30.0%  (1500W)
======================================================================

======================================================================
  MODE: EMERGENCY_BACKUP
  ────────────────────────────────────────────────────────────────────
  ⏱️  ELAPSED: 00:15:45
  🎯 TARGET:   95%
  ────────────────────────────────────────────────────────────────────
  BATTERY:    ⚡ CHARGING        3500W  |  SoC: 82.3%
  SOLAR PV:   ☀️  PRODUCING      1200W  |  
  HOME LOAD:  🏠 CONSUMING       800W  |  
  GRID:       ↓ IMPORTING       3100W
  ────────────────────────────────────────────────────────────────────
  CMD: WSetPct=70.0%  (3500W)
======================================================================

======================================================================
  MODE: TIME_OF_USE
  ────────────────────────────────────────────────────────────────────
  ⏱️  ELAPSED: 00:45:12  |  ⏳ REMAINING: 00:14:48
  🎯 TARGET:   N/A
  ────────────────────────────────────────────────────────────────────
  BATTERY:    🔋 DISCHARGING     4200W  |  SoC: 68.5%
  SOLAR PV:   ☀️  PRODUCING       800W  |  
  HOME LOAD:  🏠 CONSUMING      3500W  |  
  GRID:       ↑ EXPORTING       1500W
  ────────────────────────────────────────────────────────────────────
  CMD: WSetPct=-84.0%  (-4200W)
======================================================================

======================================================================
  MODE: MANUAL
  ────────────────────────────────────────────────────────────────────
  ⏱️  ELAPSED: 00:02:15
  🎯 TARGET:   N/A
  ────────────────────────────────────────────────────────────────────
  BATTERY:    💤 IDLE              0W  |  SoC: 85.0%
  SOLAR PV:   ☀️  PRODUCING      2400W  |  
  HOME LOAD:  🏠 CONSUMING      2400W  |  
  GRID:       ─ BALANCED           0W
  ────────────────────────────────────────────────────────────────────
  CMD: WSetPct=0.0%  (0W)
======================================================================

======================================================================
  SHUTTING DOWN: Releasing Modbus control (WSetEna=0)
======================================================================
✓ Control released - aGate will resume configured mode
```

---

## New Features

| Feature | Description | Status |
|---------|-------------|--------|
| ⏱️ Elapsed Time | Shows how long mode has been running | ✅ Added |
| ⏳ Remaining Time | Shows time left when `--duration` used | ✅ Added |
| 🎯 Target SoC | Mode-specific target (reserve or target_soc) | ✅ Added |
| ☀️ Solar PV | Current solar production in watts | ✅ Added |
| 🏠 Home Load | Calculated home consumption | ✅ Added |
| ⚡/🔋/💤 Battery State | Visual indicator with power | ✅ Added |
| ↓/↑/─ Grid State | Import/export/balanced with watts | ✅ Added |
| Refresh Rate | Every 5 seconds to console | ✅ Added |

---

## Usage Examples

### Self-Consumption Mode
```bash
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode self_consumption --reserve 20
```

### Emergency Backup (with target)
```bash
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode emergency_backup --target-soc 90
```

### Manual with Duration
```bash
python franklinwh_control_standalone.py -i 192.168.0.110 \
  --reset-on-start --mode manual --power 1500 --duration 7200
```

---

## Target Display by Mode

| Mode | Target Display | Description |
|------|----------------|-------------|
| `emergency_backup` | `95%` | Target SoC to charge to |
| `self_consumption` | `20% reserve` | Minimum reserve percentage |
| `time_of_use` | `N/A` | Uses external schedule |
| `grid_zero` | `N/A` | No specific target |
| `peak_shave` | `2000W` | Threshold for discharge |
| `manual` | `N/A` | Direct power control |

---

## Technical Details

### New Methods Added

```python
def _format_duration(self, seconds: float) -> str:
    """Format seconds as HH:MM:SS."""

def _get_target_soc_display(self) -> str:
    """Get target SoC display based on current mode."""

def _print_telemetry(self, status: Dict, start_time: float, 
                     duration_seconds: Optional[float] = None):
    """Print formatted telemetry to console."""
```

### Update Frequency

| Output Type | Frequency | Destination |
|-------------|-----------|-------------|
| Console telemetry | Every 5 seconds | stdout (terminal) |
| Log status | Every 60 seconds | Log file |
| Control tick | Every 5 seconds | Modbus write |

---

## Benefits

1. **Immediate Feedback**: See if the mode is working as expected
2. **Power Flow Visibility**: Understand solar → home → battery → grid
3. **Progress Tracking**: Elapsed/remaining time for duration-limited runs
4. **Target Alignment**: Verify the system is working toward the right goal
5. **Debugging Aid**: If something's wrong, you can see it immediately

---

*End of Demo*
