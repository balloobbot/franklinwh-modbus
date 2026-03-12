# FranklinWH Official Documentation Reference

> **Purpose**: Reference guide summarizing official FranklinWH features and their Modbus TCP accessibility.  
> **Source**: [FranklinWH Support](https://www.franklinwh.com/support/overview/), [FranklinWH Service Desk](https://service.franklinwh.com/en/support/solutions/)  
> **Extracted**: 2026-03-12  
> **Last Updated**: 2026-03-12

---

## Feature Capability Matrix — App vs Modbus TCP

| Feature | App | Modbus TCP | Registers | Test Evidence |
|---------|-----|------------|-----------|---------------|
| **Read battery SoC/power/temp** | ✅ | ✅ | M713.SoC, M714.DCW/DCV/Tmp | Validated |
| **Read grid power/voltage/freq** | ✅ | ✅ | M701.W/LNV/Hz/ConnSt | Validated |
| **Read solar PV production** | ✅ | ✅ | M502.OutPw, Ext.15502-15505 | Validated |
| **Read home load** | ✅ | ✅ | Ext.15506 | Validated |
| **Read operating mode** | ✅ | ✅ | Ext.15507 (read-only) | Validated |
| **Read reserve SoC** | ✅ | ✅ | Ext.15508-15509 (read-only) | Validated |
| **Battery charge/discharge** | ✅ | ✅ | M704 WSetPct/WSet/WSetEna | Validated 2026-03-12 |
| **Change operating mode** | ✅ | ❌ | Ext.15507 read-only | — |
| **Change reserve SoC** | ✅ | ❌ | Ext.15508-15509 read-only | — |
| **Grid charge toggle** | ✅ | ❌ | No register | — |
| **Grid export toggle** | ✅ | ❌ | No register | — |
| **Grid export limit (kW)** | ✅ | ❌ | WMaxLimPct silently discarded | [2026-03-08 test](../tests/results/2026-03-08_p2p4_control_tests.md) |
| **Go Off-Grid** | ✅ | ❌ | ConnSt read-only | — |
| **Smart Circuits** | ✅ | ❌ | Not exposed at all | — |
| **Generator** | ✅ | ❌ | Not exposed at all | — |
| **V2L (Vehicle-to-Load)** | ✅ | ❌ | Not exposed at all | — |
| **Solar curtailment** | Auto | ❌ | Firmware-controlled | — |
| **Hardware reversion timer** | N/A | ❌ | WSetRvrtTms accepted, never executes | [Quirks doc](./FRANKLINWH_SUNSPEC_QUIRKS.md) |
| **Hardware heartbeat** | N/A | ❌ | ControllerHb silently ignored | [Quirks doc](./FRANKLINWH_SUNSPEC_QUIRKS.md) |

> **With SPAN Modbus unlock**: Ext.15507-15509 become writable, enabling mode changes and reserve control via Modbus TCP. See [FRANKLINWH_SUNSPEC_QUIRKS.md](./FRANKLINWH_SUNSPEC_QUIRKS.md) for full details.

---

## Operating Modes

### Self-Consumption (Ext.15507 = 2)

**Source**: [Understanding Operating Modes](https://service.franklinwh.com/en/support/solutions/articles/73000647816), [Self-Consumption](https://www.franklinwh.com/support/overview/system-operation-mode)

**How It Works** (official):
1. **Solar Power First** — Solar energy powers home loads in real-time
2. **Charge Batteries** — Excess solar stored in aPower (not exported)
3. **Battery Discharge** — When solar insufficient, aPower discharges to cover home load
4. **Grid as Last Resort** — Grid import only when battery depleted AND solar unavailable

**Key Details**:
- When aPower full, excess solar exported to grid (if export not restricted)
- During outage: auto-switches to emergency backup, uses ALL stored energy including reserve
- User sets **Reserved energy for outage** (slider in app → Ext.15508)
- Best for: flat tariffs, high solar capacity relative to load

### Emergency Backup (Ext.15507 = 0)

**Source**: [Emergency Backup](https://service.franklinwh.com/en/support/solutions/articles/73000649111), [System Operation Mode](https://www.franklinwh.com/support/overview/system-operation-mode)

**How It Works** (official):
1. **Battery kept at 100%** — Charges from solar + grid to maintain full charge
2. **Home powered by grid + solar** — Battery does NOT discharge for self-consumption
3. **Grid outage detected** — Auto-disconnects (anti-islanding), switches to battery within milliseconds
4. **Solar recharges in off-grid** — If PV available, recharges battery. Curtails solar if battery full.
5. **Grid restored** — Auto-reconnects, returns to previous mode, recharges battery

**Key Details**:
- Initial setup may draw from grid to charge batteries to 100%
- Battery does NOT discharge to cover home load when on-grid (key difference from self-consumption)
- Smart energy management prioritizes critical loads during outage
- User can customize backup duration and recovery mode type

### Time-of-Use / TOU (Ext.15507 = 1)

**Source**: [Time of Use](https://service.franklinwh.com/en/support/solutions/articles/73000647820), [System Operation Mode](https://www.franklinwh.com/support/overview/system-operation-mode)

**How It Works** (official):
1. **Peak Hours (Expensive)** — Discharge battery to power home, avoid grid import. Solar used first.
2. **Off-Peak Hours (Cheap)** — Charge batteries from solar + cheap grid. Home runs on grid.
3. **Solar Integration** — Solar powers home + charges batteries. Excess stored, not exported (unless net metering beneficial).

**Rate Periods** (user-defined):
- **Super Off-Peak** — Lowest electricity price
- **Off-Peak** — Lower electricity price
- **Mid-Peak** — Moderate electricity price
- **On-Peak** — Highest electricity price

**Key Details**:
- Requires carefully planned schedule for optimal performance
- Advanced settings allow per-rate customization of charge/discharge behavior
- User sets reserve SoC (slider → Ext.15509)
- Best for: utility rate plans with variable pricing

---

## Grid Import & Export Settings

**Source**: [Grid Import & Export](https://www.franklinwh.com/support/overview/grid-charge--export)

### Grid Import (Charge from Grid)
- **Default**: Charge from grid **not allowed**
- When enabled: aGate uses grid to charge batteries in TOU mode during off-peak/super-off-peak
- When disabled: aPower charges from solar only
- **Modbus TCP**: ❌ No register to toggle this setting

### Energy Export
- Two export modes: **Only Solar** or **Solar + aPower**
- If **Solar + aPower**: set Grid Export Limit (kW) based on utility requirements
- If **Only Solar**: batteries do not export to grid
- Battery prioritizes home energy needs first, exports excess during peak times
- **Modbus TCP**: ❌ No register. WMaxLimPct writes silently discarded.

---

## Go Off-Grid

**Source**: [Go Off-Grid](https://www.franklinwh.com/support/overview/go-off-grid)

Programmatically disconnects home from grid (simulates grid outage).
- Does NOT open/close breakers or disconnect utility service
- Solar + battery power home
- Auto-reconnects if: user reconnects via app, battery depleted, or loads exceed capacity
- Activated via app Settings → Go Off-Grid button
- **Modbus TCP**: ❌ M701.ConnSt is read-only (can detect off-grid, cannot trigger it)

---

## Smart Circuits

**Source**: [Smart Circuits](https://www.franklinwh.com/support/overview/smart-circuits)

Optional aGate module providing control of **3 circuits**:
- **Manual on/off** — Toggle per circuit
- **Time Schedule** — Automatic on/off based on time and cycle intervals
- **SoC Auto Cut-off** (off-grid only) — Disconnect circuits in sequence as battery SoC drops below thresholds
- **Overload Cut-off** — Auto-disconnect if load exceeds panel capacity
- Circuits can be **merged** (2-pole switch), renamed, and scene-automated
- Event logs available for disconnection history

**Modbus TCP**: ❌ **Not exposed at all** — no registers in SunSpec models or extension range. App-only feature.

---

## Generator

**Source**: [Generator](https://www.franklinwh.com/support/overview/generator)

Optional aGate hardware connection for backup generator:
- Functions as backup power source for home loads + aPower charging **when off-grid**
- Combination with FranklinWH provides long-duration uninterrupted power
- Configured via installer in app
- **Modbus TCP**: ❌ **Not visible** — no registers, no status, no control

---

## Vehicle-to-Load (V2L)

**Source**: [Vehicle to Load](https://www.franklinwh.com/support/overview/vehicle-to-load)

EV-to-home power support:
- EV supplies power to home via FranklinWH system
- Optional: EV can **charge the aPower** (configurable toggle)
- Supported vehicle types selectable in app (or custom entry)
- Dashboard shows vehicle power, voltage, frequency
- When EV charging aPower: shows SoC and time to full
- **Modbus TCP**: ❌ **Not visible** — no registers, no status, no control

---

## Related Documents

- [FRANKLINWH_SUNSPEC_QUIRKS.md](./FRANKLINWH_SUNSPEC_QUIRKS.md) — Hardware register quirks and known defects
- [VIRTUAL_MODE_SPECIFICATIONS.md](./VIRTUAL_MODE_SPECIFICATIONS.md) — Virtual mode definitions and validation targets
- [DER_CONTROL_REFERENCE.md](./DER_CONTROL_REFERENCE.md) — M704/M715 register map
- [FRANKLINWH_MODBUS_GUIDE.md](./FRANKLINWH_MODBUS_GUIDE.md) — Implementation guide

---

## Official FranklinWH URLs

| Topic | URL |
|-------|-----|
| Understanding Operating Modes | https://service.franklinwh.com/en/support/solutions/articles/73000647816 |
| Emergency Backup | https://service.franklinwh.com/en/support/solutions/articles/73000649111 |
| Time of Use | https://service.franklinwh.com/en/support/solutions/articles/73000647820 |
| System Operation Mode | https://www.franklinwh.com/support/overview/system-operation-mode |
| Grid Import & Export | https://www.franklinwh.com/support/overview/grid-charge--export |
| Go Off-Grid | https://www.franklinwh.com/support/overview/go-off-grid |
| Smart Circuits | https://www.franklinwh.com/support/overview/smart-circuits |
| Generator | https://www.franklinwh.com/support/overview/generator |
| Vehicle to Load | https://www.franklinwh.com/support/overview/vehicle-to-load |
| Backup Reserve | https://www.franklinwh.com/support/overview/backup-reserve |
| Storm Hedge | https://www.franklinwh.com/support/overview/storm-hedge |
| Virtual Power Plant | https://www.franklinwh.com/support/overview/virtual-power-plant |
| Tariff Settings | https://www.franklinwh.com/support/overview/tariff-settings |
| Direct Connect | https://www.franklinwh.com/support/overview/direct-connect |
