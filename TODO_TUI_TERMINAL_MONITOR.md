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
- [ ] **Quit Key Not Working**
  - Footer shows `[q]` but only Ctrl+C actually quits
  - Need to implement proper keyboard handling in Rich Live mode
  
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
