# DER Control Register Reference

Complete reference of all DER control registers on the FranklinWH aGate, documenting what we use, what works, what's untested, and the future test plan.

**Cross-references:** [ORCHESTRATION_AND_CONTROL.md](./ORCHESTRATION_AND_CONTROL.md) (legacy command sequencing), [FRANKLINWH_SUNSPEC_QUIRKS.md](./FRANKLINWH_SUNSPEC_QUIRKS.md) (known quirks)

---

## 1. Model 704 — DER Control AC (Battery Control)

### Active Power Control (WSet Group)

These are the primary battery control registers. **This is what we use.**

| Address | Field | Label | Type | RW | Used | Status | Code Reference |
|---------|-------|-------|------|----|------|--------|----------------|
| 40318 | `WSetEna` | Active Power Enable | enum16 | RW | ✅ | ✅ **Working** | `send_command()` step 1 (disable=0) & 3 (enable=1) |
| 40319 | `WSetMod` | Active Power Mode | enum16 | RW | ✅ | ✅ **Working** | `send_command()` step 2 (set=0) |
| 40320 | `WSet` | Active Power Setpoint (W) | int32 | RW | ❌ | ⚠️ **Avoided** | Not used — causes mode flickering when set alongside WSetPct |
| 40322 | `WSetRvrt` | Reversion Power (W) | int32 | RW | ❌ | 🔲 **Untested** | Read by `read_control_status()` only |
| 40324 | `WSetPct` | Active Power Setpoint (%) | int16 | RW | ✅ | ✅ **Working** | `send_command()` step 2 — **sign inverted** (see quirks) |
| 40325 | `WSetPctRvrt` | Reversion Power (%) | int16 | RW | ❌ | 🔲 **Untested** | Could set fallback power level |
| 40326 | `WSetEnaRvrt` | Reversion Enable | enum16 | RW | ❌ | 🔲 **Untested** | What happens when command reverts |
| 40327 | `WSetRvrtTms` | Reversion Timeout (s) | uint32 | RW | ⚠️ | ⚠️ **Partially tested** | Read in `healthcheck()` zombie detection; never written |
| 40329 | `WSetRvrtRem` | Reversion Time Remaining (s) | uint32 | R | ✅ | ✅ **Working** | Read in `healthcheck()` and `read_control_status()` |

> [!IMPORTANT]
> **Sign Convention Quirk:** `WSetPct` is inverted on FranklinWH hardware. Positive values = discharge (in standard SunSpec, positive = charge). The library inverts: `m704.WSetPct.value = -pct_raw`. See `FRANKLINWH_SUNSPEC_QUIRKS.md`.

> [!WARNING]
> **WSet vs WSetPct:** Writing to `WSet` (absolute watts) alongside `WSetPct` causes mode flickering on the aGate. The library uses **only WSetPct** for all power commands. `WSet` is zeroed during `reset_control_state()` but never used for active control.

**Current Command Sequence:**
```
1. STOP:    WSetEna = 0               (disable control)
2. CONFIG:  WSetMod = 0, WSetPct = -X (set mode, set power %)
3. ENABLE:  WSetEna = 1               (enable control)
4. VERIFY:  read WSetPct              (confirm value took)
```

**Code entry points:**
- `controller.py:send_command()` — primary charge/discharge interface
- `controller.py:reset_control_state()` — stop and release control
- `controller.py:read_control_status()` — read all WSet fields
- `controller.py:healthcheck()` — zombie state detection

---

### Max Power Limit (WMaxLim Group)

**Not currently used by the library.** Could limit max inverter power.

| Address | Field | Label | Type | RW | Current Value | Status |
|---------|-------|-------|------|----|---------------|--------|
| 40310 | `WMaxLimPctEna` | Max Power Limit Enable | enum16 | RW | 0 (disabled) | 🔲 **Untested** |
| 40311 | `WMaxLimPct` | Max Power Limit (%) | uint16 | RW | 100% (raw: 1000) | 🔲 Untested |
| 40312 | `WMaxLimPctRvrt` | Reversion Limit (%) | uint16 | RW | None | 🔲 Untested |
| 40313 | `WMaxLimPctEnaRvrt` | Reversion Enable | enum16 | RW | None | 🔲 Untested |
| 40314 | `WMaxLimPctRvrtTms` | Reversion Timeout (s) | uint32 | RW | None | 🔲 Untested |
| 40316 | `WMaxLimPctRvrtRem` | Reversion Time Remaining | uint32 | R | None | 🔲 Untested |

> [!NOTE]
> **Potential Use Case:** Could be used to cap inverter output during grid-sensitive periods or to implement soft power ramp-down. Worth testing if the aGate respects this limit.

---

### Power Factor Control (PFW Groups)

**Not currently used by the library.** Controls inverter power factor.

| Address | Field | Label | Type | RW | Current Value | Status |
|---------|-------|-------|------|----|---------------|--------|
| 40298 | `PFWInjEna` | PF Enable (W Inject) | enum16 | RW | **1 (enabled!)** | ⚠️ **Active but unused** |
| 40299 | `PFWInjEnaRvrt` | PF Reversion Enable (Inj) | enum16 | RW | None | 🔲 Untested |
| 40300 | `PFWInjRvrtTms` | PF Reversion Time (Inj) | uint32 | RW | None | 🔲 Untested |
| 40302 | `PFWInjRvrtRem` | PF Rev Time Remaining | uint32 | R | None | 🔲 Untested |
| 40304 | `PFWAbsEna` | PF Enable (W Absorb) | enum16 | RW | None | 🔲 Untested |
| 40305 | `PFWAbsEnaRvrt` | PF Reversion Enable (Abs) | enum16 | RW | None | 🔲 Untested |
| 40306 | `PFWAbsRvrtTms` | PF Reversion Time (Abs) | uint32 | RW | None | 🔲 Untested |
| 40308 | `PFWAbsRvrtRem` | PF Rev Time Remaining | uint32 | R | None | 🔲 Untested |

> [!WARNING]
> `PFWInjEna` = 1 — **this is already enabled by the aGate's default config.** We are not setting it. Unknown what PF target it's using. This could affect grid export behavior.

---

### Reactive Power Control (VarSet Group)

**Not currently used by the library.** Controls reactive power (Var) output.

| Address | Field | Label | Type | RW | Current Value | Status |
|---------|-------|-------|------|----|---------------|--------|
| 40331 | `VarSetEna` | Reactive Power Enable | enum16 | RW | 0 | 🔲 Untested |
| 40332 | `VarSetMod` | Reactive Power Mode | enum16 | RW | 1 | 🔲 Untested |
| 40333 | `VarSetPri` | Reactive Power Priority | enum16 | RW | 2 | 🔲 Untested |
| 40334 | `VarSet` | Reactive Power (Var) | int32 | RW | 0 | 🔲 Untested |
| 40336 | `VarSetRvrt` | Reversion Reactive Power | int32 | RW | None | 🔲 Untested |
| 40338 | `VarSetPct` | Reactive Power (%) | int16 | RW | None | 🔲 Untested |
| 40339 | `VarSetPctRvrt` | Reversion Reactive (%) | int16 | RW | None | 🔲 Untested |
| 40340 | `VarSetEnaRvrt` | Reversion Enable | enum16 | RW | None | 🔲 Untested |
| 40341 | `VarSetRvrtTms` | Reversion Timeout (s) | uint32 | RW | None | 🔲 Untested |
| 40343 | `VarSetRvrtRem` | Reversion Time Remaining | uint32 | R | None | 🔲 Untested |

---

### Ramp Rate Control

**Not currently used.** Controls how fast power ramps up/down.

| Address | Field | Label | Type | RW | Current Value | Status |
|---------|-------|-------|------|----|---------------|--------|
| 40345 | `WRmp` | Normal Ramp Rate | uint16 | RW | None | 🔲 Untested |
| 40346 | `WRmpRef` | Ramp Rate Reference | enum16 | RW | None | 🔲 Untested |
| 40347 | `VarRmp` | Reactive Ramp Rate | uint16 | RW | None | 🔲 Untested |

---

### Anti-Islanding

| Address | Field | Label | Type | RW | Current Value | Status |
|---------|-------|-------|------|----|---------------|--------|
| 40348 | `AntiIslEna` | Anti-Islanding Enable | enum16 | RW | None | 🔲 Untested — **DO NOT disable** |

### Scale Factors

| Address | Field | Value | Applied To |
|---------|-------|-------|-----------|
| 40349 | `PF_SF` | -3 | Power Factor (÷1000) |
| 40350 | `WMaxLimPct_SF` | -1 | Max Power Limit (÷10) |
| 40351 | `WSet_SF` | 0 | Active Power (×1) |
| 40352 | `WSetPct_SF` | -1 | Active Power % (÷10) |
| 40353 | `VarSet_SF` | 0 | Reactive Power (×1) |
| 40354 | `VarSetPct_SF` | -1 | Reactive Power % (÷10) |

---

## 2. Model 715 — DER Control

| Address | Field | Label | Type | RW | Current Value | Status | Notes |
|---------|-------|-------|------|----|---------------|--------|-------|
| 41089 | `LocRemCtl` | Control Mode | enum16 | R | **1 (Local)** | ⚠️ **Read-only** | SunSpec says this should be writable to switch to remote control — **aGate does not support** |
| 41090 | `DERHb` | DER Heartbeat | uint32 | R | 0 | 🔲 Untested | aGate's own heartbeat counter |
| 41092 | `ControllerHb` | Controller Heartbeat | uint32 | RW | 0 | 🔲 **Untested** | We should write this as keep-alive |
| 41094 | `AlarmReset` | Alarm Reset | uint16 | RW | 0 | 🔲 Untested | Used in `check_blocking_alarms()` but never written |
| 41095 | `OpCtl` | Set Operation | enum16 | RW | 0 | 🔲 Untested | Start/Stop/Standby the DER |

> [!CAUTION]
> **LocRemCtl = 1 (Local) and read-only.** This is a significant deviation from SunSpec. Standard SunSpec requires a remote controller to write `LocRemCtl = 0` before taking control. FranklinWH ignores this — M704 writes work regardless, but the aGate considers itself under "local" (Cloud API) control at all times. See `FRANKLINWH_SUNSPEC_QUIRKS.md` for full implications.

> [!IMPORTANT]
> **ControllerHb (Keep-Alive):** SunSpec2 standard defines this as a heartbeat the remote controller writes to signal it is alive. If the DER doesn't receive heartbeat updates, it may revert to local control. **We are not writing this.** Testing needed to determine if the aGate monitors this and whether writing it affects command persistence.

---

## 3. FranklinWH Extension Controls (15507–15509)

| Address | Field | Label | Type | RW | Current Value | Status | Notes |
|---------|-------|-------|------|----|---------------|--------|-------|
| 15507 | `OnGridMode` | Operating Mode | uint16 | R* | 2 (Self-Consumption) | ✅ **Read works** | ❌ Write blocked without SPAN |
| 15508 | `SelfReserve` | Self-Consumption Reserve | uint16 | R* | 20 (%) | ✅ **Read works** | ❌ Write blocked without SPAN |
| 15509 | `TouReserve` | TOU Reserve | uint16 | R* | 20 (%) | ✅ **Read works** | ❌ Write blocked without SPAN |

*R = Read-only without SPAN Modbus unlock. See `FRANKLINWH_SUNSPEC_QUIRKS.md` "Write Access Asymmetry".

---

## 4. Test Status Summary

```
Legend:  ✅ Working   ⚠️ Partial   🔲 Untested   ❌ Broken/Blocked
```

| Category | Registers | Status | Evidence |
|----------|-----------|--------|----------|
| **Battery Power (WSetPct)** | 40318-40324 | ✅ Working | Live verified — charge/discharge confirmed |
| **WSet (absolute watts)** | 40320 | ⚠️ Avoided | Causes flickering when used with WSetPct |
| **Reversion Timer** | 40327-40329 | ⚠️ Read-only use | Read in healthcheck; never written to set timeout |
| **Reversion Power** | 40322/40325 | 🔲 Untested | Could set fallback power after timeout |
| **Max Power Limit** | 40310-40316 | 🔲 Untested | Could cap inverter output |
| **Power Factor** | 40298-40308 | 🔲 Untested | PFWInjEna=1 already active (default) |
| **Reactive Power** | 40331-40343 | 🔲 Untested | Full VarSet group unused |
| **Ramp Rates** | 40345-40347 | 🔲 Untested | Could smooth power transitions |
| **Controller Heartbeat** | 41092 | 🔲 **Critical untested** | May affect command persistence |
| **DER Heartbeat** | 41090 | 🔲 Untested | aGate heartbeat — monitoring only |
| **OpCtl (Start/Stop)** | 41095 | 🔲 Untested | Could start/stop DER |
| **LocRemCtl** | 41089 | ❌ Read-only | SunSpec handoff not supported |
| **Extension Mode/Reserves** | 15507-15509 | ❌ Write blocked | Need SPAN Modbus unlock |

---

## 5. Future Test Plan

### Priority 1 — Command Persistence and Keep-Alive

| Test | What to Do | Expected Outcome | Risk |
|------|-----------|-------------------|------|
| **Write ControllerHb** | Write incrementing counter to 41092 every N seconds | Determine if aGate monitors heartbeat | Low — write test |
| **Set WSetRvrtTms** | Write timeout (e.g., 300s) to 40327 before sending command | Command auto-reverts after timeout | Low — self-healing |
| **Set WSetPctRvrt** | Write fallback power % to 40325 | After timeout, battery reverts to this power level | Low |
| **Monitor reversion** | After WSetRvrtTms expires, read all WSet fields | Understand what state the aGate returns to | Low — read only |

> [!IMPORTANT]
> **Why this matters:** Currently commands may persist indefinitely (no timeout set) or be overridden unpredictably by the aGate's Cloud API. Understanding the reversion mechanism is critical for safe autonomous operation.

### Priority 2 — Power Limiting and Ramp Control

| Test | What to Do | Expected Outcome | Risk |
|------|-----------|-------------------|------|
| **WMaxLimPct** | Write 50% limit to 40311, enable at 40310 | Inverter caps at 50% rated power | Medium — limits output |
| **WRmp ramp rate** | Write ramp value to 40345 | Power changes gradually instead of step | Low |
| **VarSet reactive** | Enable VarSet, write small Var value | Observe reactive power output | Low |

### Priority 3 — Power Factor Investigation

| Test | What to Do | Expected Outcome | Risk |
|------|-----------|-------------------|------|
| **Read PF target** | Investigate what PFWInjEna=1 is doing | Understand default PF behavior | None — read only |
| **Disable PFWInjEna** | Write PFWInjEna=0, observe PF change | Determine if PF control is enforced | Medium |

### Priority 4 — DER Operations

| Test | What to Do | Expected Outcome | Risk |
|------|-----------|-------------------|------|
| **OpCtl start/stop** | Write OpCtl values to 41095 | May start/stop the inverter | ⚠️ **High — could disconnect** |
| **AlarmReset** | Write to 41094 after a fault | Clear fault condition | Low |

---

## 6. Tool Commands for Testing

```bash
# Read all M704 control registers (ground truth)
python3 tools/modbus_sunspec2_reader.py -i 192.168.0.110 -t 10 -dvalues --vals | grep -A 50 'Model 704'

# Read M715 control registers
python3 tools/modbus_sunspec2_reader.py -i 192.168.0.110 -t 10 -dvalues --vals | grep -A 12 'Model 715'

# Read extension mode/reserves
python3 tools/modbus_sunspec2_reader.py -i 192.168.0.110 -t 10 --raw 15507:3

# Library: read control status
python3 -c "
from franklinwh import FranklinWHController
ctrl = FranklinWHController('192.168.0.110')
ctrl.connect()
print(ctrl.read_control_status())
print(ctrl.read_native_mode())
ctrl.disconnect()
"

# Library: healthcheck (includes zombie detection)
python3 -c "
from franklinwh import FranklinWHController
ctrl = FranklinWHController('192.168.0.110')
ctrl.connect()
h = ctrl.healthcheck()
print(f'Healthy: {h.healthy}')
print(f'Message: {h.message}')
for k,v in h.details.items(): print(f'  {k}: {v}')
for r in h.recommendations: print(f'  ⚠️  {r}')
ctrl.disconnect()
"
```

---

*Last Updated: 2026-03-08*  
*See also: [ORCHESTRATION_AND_CONTROL.md](./ORCHESTRATION_AND_CONTROL.md) for command sequencing diagrams*
