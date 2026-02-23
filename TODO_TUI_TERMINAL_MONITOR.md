# TODO: TUI Terminal Monitor UI

**Status:** Approved (pending implementation)  
**Approved:** 2026-02-23  
**Priority:** Medium  
**Estimated Effort:** 4-6 hours

---

## Description

A Terminal User Interface (TUI) for real-time battery monitoring and control. Provides a live updating dashboard directly in the terminal, similar to `htop` or `bpytop`, for users who prefer CLI over web interface.

---

## Requirements (as approved)

### Core Features (Phase 1 - Complete ✅)

**Keyboard Controls:**

| Key | Action | Note |
|-----|--------|------|
| `c` | Charge prompt | Enter watts, press Enter |
| `d` | Discharge prompt | Enter watts, press Enter |
| `s` | Standby | Hold 0W, keep Modbus control |
| `r` | **Release** | Same as `--stop`, cloud takes over |
| `m` | Max charge | Use rated max charge rate |
| `M` | Max discharge | Use rated max discharge rate |
| `+` | +100W | Increase current power |
| `-` | -100W | Decrease current power |
| `R` | Toggle refresh | Pause/resume display updates |
| `1-9` | Set refresh rate | 1-9 seconds |
| `q` | Quit | Exit monitor |

**Important:** `s` (standby) and `r` (release) are different!
- `s` = Stay in control at 0W
- `r` = Give up control to cloud/app

- [x] **Live Power Flow Display**
  - Real-time battery power (charge/discharge)
  - Solar generation
  - Home load
  - Grid import/export
  
- [x] **Battery Status Panel**
  - State of Charge (SoC) with visual bar
  - State of Health (SoH)
  - Temperature
  - Current power direction and magnitude
  
### Phase 2 Enhancements (TODO)
- [x] **Quit Key Not Working** ✅ FIXED
  - Footer shows `[q]` but only Ctrl+C actually quits
  - ~~Need to implement proper keyboard handling in Rich Live mode~~
  - Implemented KeyboardInput class with tty.setcbreak()

- [x] **Command Console Output** ✅ FIXED
  - ~~Commands scroll below CLI line and screen redraws~~
  - Now: Commands appear in dedicated panel within dashboard
  - Shows last 5 commands with timestamps
  - Color-coded by type (charge/discharge/standby/error)

- [x] **Solar State Display** ✅ FIXED
  - Was: "0W Producing" when no sun
  - Now: Shows "Idle" when solar < 50W threshold

- [x] **Header Timestamp Format** ✅ FIXED
  - Was: No timestamp
  - Now: "23-Feb-25 14:30" format (DD-Mmm-YY HH:MM)

- [x] **Serial Number in Header** ✅ FIXED
  - Shows aGate serial instead of IP when available
  - IP shown as fallback if serial not read yet

- [ ] **Three-Phase AC Display** (Future)
  - Currently shows Single-Phase (LNV, A, etc.)
  - For Split/Three-Phase: Should expand to show L1/L2/L3
  - Per-phase voltage, current, power readings
  - See M701 PhVphA, PhVphB, PhVphC, AphA, AphB, AphC

- [ ] **Enhanced SoC Bar Chart**
  - Current SOC bar with embedded reserve indicator
  - Show Self Reserve or TOU Reserve (based on current mode)
  - Optional: --min-discharge-soc / --max-charge-soc targets
  - ETA estimate to reach reserve or target based on:
    - Current charge/discharge rate
    - Battery capacity (rated vs available)
    - Linear projection: `minutes = (target_soc - current_soc) * capacity_wh / power_w / 60`
  - Visual markers: `|███▓▓▓░░░|` where ▓ = reserve zone
  
  Example:
  ```
  SoC: [████████████▓▓▓▓▓▓░░░░░░░░] 50.0%
        │        Current │ Reserve│ Target │
        │         50%    │  20%   │  100%  │
  ETA: +42min to 100% | -31min to 20% reserve
  ```

- [ ] **System Metrics**
  - AC voltage, frequency
  - Inverter status
  - Active alarms/warnings

- [ ] **Control Interface**
  - Quick charge/discharge buttons (keyboard shortcuts)
  - Set power level
  - Enable/disable control
  - Emergency stop

### UI/UX
- [ ] **Visual Design**
  - Color-coded values (green=good, yellow=warning, red=critical)
  - Progress bars for SoC
  - Trend arrows for power flow
  - Clean, bordered panels

- [ ] **Layout Modes**
  - Compact mode (minimal terminal size)
  - Full mode (all metrics)
  - Focus mode (single metric enlarged)

- [ ] **Interaction**
  - Keyboard shortcuts for all actions
  - Mouse support (optional)
  - Configurable refresh rate (default: 2s)

### Technical
- [ ] **Implementation Options** (to be decided)
  - Option A: `rich` library (Python, simpler)
  - Option B: `textual` library (Python, more features)
  - Option C: `ncurses` (C/ctypes, lowest dependency)

- [ ] **CLI Integration**
  - New flag: `--monitor` or `--tui`
  - Standalone command: `franklinwh_monitor`
  - Library support for programmatic use

---

## Implementation Notes

### Proposed Architecture
```
franklinwh_tui.py
├── MonitorApp (main TUI class)
├── PowerFlowPanel (live power display)
├── BatteryPanel (SoC, SoH, temp)
├── SystemPanel (alarms, status)
└── ControlPanel (quick actions)
```

### Dependencies to Evaluate
```python
# Option A: rich
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel

# Option B: textual
from textual.app import App
from textual.widgets import Header, Footer, Static

# Option C: ncurses (builtin)
import curses
```

### Refresh Strategy
- Async data updates (non-blocking UI)
- Configurable poll interval (1-10s)
- Connection status indicator
- Auto-reconnect on connection loss

---

## Usage Examples

```bash
# Launch TUI monitor
python franklinwh_cli.py -i 192.168.0.110 --monitor

# Or standalone
python franklinwh_tui.py -i 192.168.0.110

# Compact mode
python franklinwh_tui.py -i 192.168.0.110 --compact

# Custom refresh rate
python franklinwh_tui.py -i 192.168.0.110 --refresh 5
```

### Keyboard Shortcuts (proposed)
| Key | Action |
|-----|--------|
| `q` / `Ctrl+C` | Quit |
| `c` | Charge mode |
| `d` | Discharge mode |
| `s` | Standby |
| `+` / `-` | Increase/decrease power |
| `m` | Max charge |
| `M` | Max discharge |
| `r` | Reset control |
| `h` | Help overlay |

---

## Related

- Original approval context: User mentioned in previous session (2026-02-22)
- Current CLI: `franklinwh_cli.py` (one-shot commands)
- Web Dashboard: `templates/dashboard.html` (reference for metrics)
- Library: `franklinwh_modbus_library.py` (data source)

---

## Future Enhancements (Phase 2)

- [ ] Historical data mini-graphs (sparklines)
- [ ] TOU schedule visualization
- [ ] Alarm history panel
- [ ] Export data to CSV from TUI
- [ ] Multi-device view (if multi-agate support added)

---

*Documented: 2026-02-23*  
*Awaiting implementation assignment*
