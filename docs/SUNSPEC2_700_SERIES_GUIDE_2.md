# SunSpec2 700 Series — Grid Export, Import, Power Setting & Standby

-----

## Source Documents

All rules, write sequences, and point behaviour in this guide are drawn from the
following official SunSpec Alliance publications. These are the authoritative sources
— always check for updated versions at [sunspec.org/specifications](https://sunspec.org/specifications/).

|# |Document                                                                          |Status      |Version|URL                                                                                                                                     |
|--|----------------------------------------------------------------------------------|------------|-------|----------------------------------------------------------------------------------------------------------------------------------------|
|S1|SunSpec DER Information Model Specification                                       |**APPROVED**|V1.2.1 |<https://sunspec.org/wp-content/uploads/2025/01/SunSpec-DER-Information-Model-Specification-V1-2-1.pdf>                                 |
|S2|SunSpec Information Model Specification (legacy, applies to multi-write procedure)|Approved    |v1.x   |<https://sunspec.org/wp-content/uploads/2019/08/SunSpec-Information-Models-12041.pdf>                                                   |
|S3|SunSpec Modbus Specification Updates (timing & enable clarifications)             |Published   |2025   |<https://sunspec.org/modbus-specification-updates/>                                                                                     |
|S4|SunSpec Modbus IEEE 1547-2018 Profile Specification and Implementation Guide      |**APPROVED**|V1.1   |<https://sunspec.org/wp-content/uploads/2025/01/SunSpec-Modbus-IEEE-1547-2018-Profile-Specification-and-Implementation-Guide-v1.1-1.pdf>|
|S5|pySunSpec2 README (official reference implementation)                             |Released    |master |<https://github.com/sunspec/pysunspec2/blob/master/README.rst>                                                                          |
|S6|sunspec/models model_704.json (authoritative point definitions)                   |Released    |master |<https://github.com/sunspec/models/blob/master/json/model_704.json>                                                                     |

-----

## Correction: The “Disable First” Rule

A common misconception — including in earlier versions of this guide — is that you
must disable a function before writing new settings to it. **The spec says the
opposite.**

> *“For operations that require multiple writes (e.g. set operating parameters and then
> enable), the procedure is recommended. **It is not recommended to disable** the
> [function].”*
> — **[S2] SunSpec Information Model Specification, Section: Procedures for
> Multi-Write Operations**

The correct procedure for Model 704 scalar setpoints (`WSet`, `WMaxLimPct`) is:

1. **Write values first** (mode, setpoint, reversion value, timer)
1. **Set `Ena = 1` last** — this is the atomic trigger that makes settings live
1. **Never disable first** — the spec explicitly discourages it

For curve-based models (705, 706 etc.), atomicity is handled differently via the
`AdptCrvReq` staging mechanism (see Section: Curve Models), so disabling is also
not needed there.

The **only spec-supported exception** is if `Ena` is already 1 and you need to
change `WSetMod` (the mode) at the same time as the value — in that case a
defensive disable avoids a brief intermediate state where the old mode is active
with the new value. This is a defensive coding choice, not a spec requirement.

-----

## Model Map for Power Control

|Model|Name             |Purpose                                              |
|-----|-----------------|-----------------------------------------------------|
|701  |`DERMeasureAC`   |Read-only — current watts, amps, voltage, energy     |
|702  |`DERCapacity`    |Read-only — rated limits (max export W, max import W)|
|703  |`DEREnterService`|Connection control — standby / reconnect             |
|704  |`DERCtlAC`       |Writable — active power limits, setpoints, timers    |

Source: **[S1]** Table of contents; **[S4]** Table 17–22.

-----

## 0. Connect and Discover

```python
import sunspec2.modbus.client as client
import time

# TCP connection (adjust IP, port, slave_id for your inverter)
d = client.SunSpecModbusClientDeviceTCP(
    slave_id=1,
    ipaddr='192.168.1.100',
    ipport=502
)
d.scan()

# Confirm 700 series models are present
print(d.models.keys())
# Expected: dict_keys([1, 'common', 701, 'DERMeasureAC',
#            702, 'DERCapacity', 703, 'DEREnterService',
#            704, 'DERCtlAC', ...])
```

> **[S5]** — “Scan invokes the device model discovery process. For Modbus, scan
> searches three device addresses (0, 40000, 50000), looking for the ‘SunS’
> identifier. Upon discovery of the SunS identifier, scan uses the model ID and
> model length to find each model present in the device.”

-----

## 1. Read Current Grid Export / Import (Model 701)

Model 701 (`DERMeasureAC`) is **read-only**. It provides the live operating state
of the DER.

```python
m = d.DERMeasureAC[0]
m.read()

# Active power (W) — positive = exporting to grid, negative = importing from grid
watts_now = m.W.cvalue          # e.g. 4800.0 W export, or -2000.0 W import

# Other useful live readings
va_now    = m.VA.cvalue         # apparent power
var_now   = m.Var.cvalue        # reactive power
pf_now    = m.PF.cvalue         # power factor
hz_now    = m.Hz.cvalue         # AC frequency
v_ll_now  = m.LLV.cvalue        # line-to-line voltage (average)
v_ln_now  = m.LNV.cvalue        # line-to-neutral voltage (average)
a_now     = m.A.cvalue          # total AC current

# Cumulative energy
wh_inj = m.TotWhInj.cvalue      # total Wh injected (export) — Quadrants 1 & 4
wh_abs = m.TotWhAbs.cvalue      # total Wh absorbed (import) — Quadrants 2 & 3

print(f"Now: {watts_now:.0f} W | Export: {wh_inj:.0f} Wh | Import: {wh_abs:.0f} Wh")
```

> **Sign convention:** positive W = export to grid, negative W = import from grid.
> Source: **[S1]** Section: DER AC Measurement (701) — point descriptions for
> `TotWhInj` (Quadrants 1 & 4) and `TotWhAbs` (Quadrants 2 & 3).

-----

## 2. Read Maximum Rated Capacity (Model 702)

Model 702 (`DERCapacity`) is **read-only**. It gives the device’s hard nameplate
limits. You cannot command beyond these values.

```python
cap = d.DERCapacity[0]
cap.read()

max_export_w = cap.WRtg.cvalue       # Max rated export power (W) e.g. 10000.0
max_import_w = cap.AbsWRtg.cvalue    # Max rated import/charging power (W) e.g. -8000.0
max_va       = cap.VARtg.cvalue      # Max rated apparent power (VA)
max_var_inj  = cap.VArRtgQ1.cvalue  # Max vars injectable (Q1)
max_var_abs  = cap.VArRtgQ4.cvalue  # Max vars absorbable (Q4)

# For storage — charge/discharge rates
max_dis_w = cap.WDisChaRte.cvalue    # Max discharge rate (W)
max_cha_w = cap.WChaRte.cvalue       # Max charge rate (W, negative convention)

print(f"Max export: {max_export_w} W  |  Max import: {max_import_w} W")
print(f"Max discharge: {max_dis_w} W  |  Max charge: {max_cha_w} W")
```

Source: **[S1]** Section: DER Capacity (702).

-----

## 3. Read Current Active Control Settings (Model 704)

Always read the current state before writing. This avoids overwriting unrelated
settings that may already be active.

```python
ctl = d.DERCtlAC[0]
ctl.read()

# --- Export limit (% of nameplate) ---
pct_limit_ena = ctl.WMaxLimPctEna.value      # 0=disabled, 1=enabled
pct_limit     = ctl.WMaxLimPct.cvalue        # e.g. 90.0 (%)
pct_rvrt_tms  = ctl.WMaxLimPctRvrtTms.value  # reversion timer (s)
pct_rvrt_rem  = ctl.WMaxLimPctRvrtRem.value  # time remaining (s, read-only)
pct_rvrt_val  = ctl.WMaxLimPctRvrt.cvalue    # value to revert to (%)

# --- Active power setpoint ---
wset_ena  = ctl.WSetEna.value      # 0=disabled, 1=enabled
wset_mod  = ctl.WSetMod.value      # 0=percent-of-max, 1=watts
wset_w    = ctl.WSet.cvalue        # active setpoint in watts (signed int32)
wset_rvrt = ctl.WSetRvrt.cvalue    # reversion setpoint in watts
wset_rtms = ctl.WSetRvrtTms.value  # reversion timer (s)
wset_rrem = ctl.WSetRvrtRem.value  # time remaining (s, read-only)

print("=== Current Control State ===")
print(f"Export limit: {'ENABLED' if pct_limit_ena else 'DISABLED'} at {pct_limit}%")
print(f"Reversion: to {pct_rvrt_val}% in {pct_rvrt_tms}s (rem: {pct_rvrt_rem}s)")
print(f"WSet: {'ENABLED' if wset_ena else 'DISABLED'}, "
      f"mode={'WATTS' if wset_mod == 1 else 'PCT'}, value={wset_w} W")
print(f"WSet reversion: to {wset_rvrt} W in {wset_rtms}s (rem: {wset_rrem}s)")
```

Point types sourced from: **[S6]** `model_704.json` — authoritative field
definitions for `WMaxLimPctEna` (enum16, RW), `WMaxLimPct` (uint16, RW),
`WSet` (int32, RW), `WSetMod` (enum16, RW).

-----

### Enable Point Behaviour (Model 704) — Key Rule

> *“When the enable field is set to 0, any changes made to the setting will not
> take effect. For example, if `704.WMaxLimPct` is set to 90% but
> `704.WMaxLimPctEna = 0`, the `WMaxLimPct` register will have the value of 90%
> but the DER will not limit the active power to 90% of its nameplate rating.
> When `WMaxLimPctEna` is set to 1, this update will take effect.”*
> 
> *“If an enable is set to 1, any changes to the corresponding settings will be
> applied to the DER. **Rewriting the enable is not required for the changes to
> be applied.**”*
> — **[S1] SunSpec DER Information Model Specification V1.2.1, Section: DER AC
> Controls (704)**

This means:

- If the function is **currently disabled**: write your values, then set `Ena = 1`.
- If the function is **currently enabled**: write your new values directly — they
  take effect immediately. You do not need to disable first and do not need to
  re-write the enable.

-----

## 4. Limit Grid Export — Percentage Mode (Timed)

Limit export to 60% of rated capacity for 30 minutes, then auto-revert to 100%.

```python
ctl = d.DERCtlAC[0]
ctl.read()
time.sleep(1)   # 1 s settle — see timing rule below

# Write values first, enable last (per [S2] multi-write procedure)
ctl.WMaxLimPct.cvalue       = 60.0   # limit to 60% of WRtg
ctl.WMaxLimPctRvrt.cvalue   = 100.0  # revert back to 100%
ctl.WMaxLimPctRvrtTms.value = 1800   # 30 minutes = 1800 s
ctl.WMaxLimPctEnaRvrt.value = 1      # enable the reversion
ctl.WMaxLimPctEna.value     = 1      # ENABLE last — this makes settings live

ctl.write()
time.sleep(1)   # allow device to apply the write before reading back

# Verify — [S5] best practice: always read back after write
ctl.read()
assert ctl.WMaxLimPctEna.value == 1,        "Export limit not enabled!"
assert ctl.WMaxLimPct.cvalue   == 60.0,     "Export limit value mismatch!"
assert ctl.WMaxLimPctRvrtTms.value == 1800, "Reversion timer mismatch!"
print(f"Export limited to {ctl.WMaxLimPct.cvalue}%  "
      f"| Reverts in {ctl.WMaxLimPctRvrtRem.value}s")
```

Convert the % limit to actual watts using Model 702:

```python
max_export_w = d.DERCapacity[0].WRtg.cvalue        # e.g. 10000 W
limit_watts  = max_export_w * (ctl.WMaxLimPct.cvalue / 100.0)
print(f"Effective export cap: {limit_watts:.0f} W")  # → 6000 W
```

> **Timing rule — [S3]:** “A definitive delay of 1000 ms has been added to
> ensure consistent read/write performance.” (Section 6.5 of the Modbus spec.)
> A `time.sleep(1)` between a write and the next read satisfies this requirement.

-----

## 5. Set Exact Export Power in Watts (Timed)

Command a specific watt output (e.g. 5000 W export) for 15 minutes, then revert.

```python
ctl = d.DERCtlAC[0]
ctl.read()
time.sleep(1)

EXPORT_W = 5000   # watts to export (positive = export)
REVERT_W = 0      # revert to 0 W when timer expires
TIMER_S  = 900    # 15 minutes

# Write values first, enable last — per [S2] multi-write procedure
ctl.WSetMod.value     = 1          # 1 = WATTS mode (per [S6] WSetMod enum: WATTS=1)
ctl.WSet.cvalue       = EXPORT_W   # int32, signed — positive = export
ctl.WSetRvrt.cvalue   = REVERT_W
ctl.WSetRvrtTms.value = TIMER_S
ctl.WSetEnaRvrt.value = 1          # enable reversion
ctl.WSetEna.value     = 1          # ENABLE last

ctl.write()
time.sleep(1)

# Verify — [S5]
ctl.read()
assert ctl.WSetEna.value == 1,        "WSet not enabled!"
assert ctl.WSetMod.value == 1,        "WSet mode not WATTS!"
assert ctl.WSet.cvalue   == EXPORT_W, f"WSet mismatch: {ctl.WSet.cvalue}"
print(f"Exporting {ctl.WSet.cvalue} W  |  Reverts in {ctl.WSetRvrtRem.value}s")
```

> **Mode + value together:** If `WSetEna` is already 1 and you need to change
> both `WSetMod` AND `WSet` in the same operation, write them in the same
> `write()` call. Because pySunSpec2 batches all dirty points into a single
> Modbus transaction, there is no intermediate state visible to the device.
> Source: **[S5]** — “When models or groups are written, only point values that
> have been set in the object since the last read or write are actually written.”

-----

## 6. Set Import Power in Watts — Grid Charging (Storage Only)

A **negative** `WSet` commands import from the grid (charging). The `WSet` point
is defined as `int32` in **[S6]** — the signed type is what makes negative values
meaningful.

```python
ctl = d.DERCtlAC[0]
cap  = d.DERCapacity[0]
ctl.read()
cap.read()
time.sleep(1)

IMPORT_W = -3000   # negative = absorbing from grid (charging)
REVERT_W = 0       # return to zero when timer expires
TIMER_S  = 3600    # 1 hour charge window

# Guard: don't exceed rated import capacity from [S1] Model 702
max_import = cap.AbsWRtg.cvalue    # e.g. -8000 W
if IMPORT_W < max_import:
    raise ValueError(
        f"Requested {IMPORT_W} W exceeds device limit {max_import} W"
    )

# Write values first, enable last — per [S2]
ctl.WSetMod.value     = 1
ctl.WSet.cvalue       = IMPORT_W   # negative → import/charge
ctl.WSetRvrt.cvalue   = REVERT_W
ctl.WSetRvrtTms.value = TIMER_S
ctl.WSetEnaRvrt.value = 1
ctl.WSetEna.value     = 1

ctl.write()
time.sleep(1)

# Verify — [S5]
ctl.read()
assert ctl.WSetEna.value == 1
assert ctl.WSet.cvalue   == IMPORT_W
print(f"Importing {abs(ctl.WSet.cvalue):.0f} W from grid  "
      f"| Reverts in {ctl.WSetRvrtRem.value}s")
```

-----

## 7. Timed Curtailment — Zero Export for a Fixed Window

Curtail export to 0 W for 10 minutes then auto-restore to full. Useful for demand
response or grid events.

```python
ctl = d.DERCtlAC[0]
ctl.read()
time.sleep(1)

ctl.WMaxLimPct.cvalue       = 0.0    # 0% → zero export
ctl.WMaxLimPctRvrt.cvalue   = 100.0  # restore to full
ctl.WMaxLimPctRvrtTms.value = 600    # 10 minutes
ctl.WMaxLimPctEnaRvrt.value = 1
ctl.WMaxLimPctEna.value     = 1      # ENABLE last

ctl.write()
time.sleep(1)

# Verify
ctl.read()
print(f"Export curtailed to {ctl.WMaxLimPct.cvalue}%  "
      f"| Auto-restores in {ctl.WMaxLimPctRvrtRem.value}s")
```

Poll `WMaxLimPctRvrtRem` to track countdown:

```python
while True:
    ctl.read()
    rem = ctl.WMaxLimPctRvrtRem.value
    ena = bool(ctl.WMaxLimPctEna.value)
    print(f"Remaining: {rem}s  |  Limit active: {ena}")
    if rem == 0:
        break
    time.sleep(10)
```

> **Reversion timer behaviour — [S1]:** “The timer SHALL be reinitialized with
> the reversion timeout value, and the timer SHALL be restarted” if the setting
> is re-written while active. This means writing a new `WMaxLimPctRvrtTms`
> while the limit is enabled resets the countdown.

-----

## 8. Put Inverter into Standby / Disconnect (Model 703)

Standby is controlled via the `Conn` point in Model 703 `DEREnterService`. This
is a **soft disconnect** — the inverter ceases to energise the AC output but
does not trip protection.

```python
es = d.DEREnterService[0]
es.Conn.value = 0   # DISCONNECT
es.write()
time.sleep(1)

es.read()
assert es.Conn.value == 0, "Inverter did not disconnect!"
print("Inverter in STANDBY")

# --- Restore to service ---
es.Conn.value = 1   # CONNECT
es.write()
time.sleep(1)

es.read()
assert es.Conn.value == 1, "Inverter did not reconnect!"
print("Inverter CONNECTED — entering service per enter-service conditions")
```

> **[S4]** — After reconnecting, the inverter observes its own enter-service
> voltage and frequency conditions before delivering power. The thresholds
> (`ESVLo`, `ESVHi`, `ESHzLo`, `ESHzHi`) and ramp time (`ESRmpTms`) are also
> held in Model 703.

-----

## 9. Full Helper-Function Script

```python
import sunspec2.modbus.client as client
import time


def connect(ip, port=502, slave=1):
    d = client.SunSpecModbusClientDeviceTCP(slave_id=slave, ipaddr=ip, ipport=port)
    d.scan()
    return d


def get_status(d):
    """Read live measurements and current control state. Sources: [S1] M701, M702, M704."""
    m   = d.DERMeasureAC[0]
    cap = d.DERCapacity[0]
    ctl = d.DERCtlAC[0]
    m.read(); cap.read(); ctl.read()
    return {
        "live_w":       m.W.cvalue,
        "wh_export":    m.TotWhInj.cvalue,
        "wh_import":    m.TotWhAbs.cvalue,
        "max_export_w": cap.WRtg.cvalue,
        "max_import_w": cap.AbsWRtg.cvalue,
        "limit_ena":    ctl.WMaxLimPctEna.value,
        "limit_pct":    ctl.WMaxLimPct.cvalue,
        "wset_ena":     ctl.WSetEna.value,
        "wset_w":       ctl.WSet.cvalue,
    }


def set_export_limit_pct(d, pct, revert_pct=100.0, timer_s=0):
    """
    Limit export to pct% of WRtg.
    Write values first, enable last — per [S2] multi-write procedure.
    Verify with read-back — per [S5] best practice.
    1 s delays — per [S3] Section 6.5 timing requirement.
    """
    ctl = d.DERCtlAC[0]
    ctl.read()
    time.sleep(1)
    ctl.WMaxLimPct.cvalue       = pct
    ctl.WMaxLimPctRvrt.cvalue   = revert_pct
    ctl.WMaxLimPctRvrtTms.value = timer_s
    ctl.WMaxLimPctEnaRvrt.value = 1 if timer_s > 0 else 0
    ctl.WMaxLimPctEna.value     = 1    # ENABLE last
    ctl.write()
    time.sleep(1)
    ctl.read()
    assert ctl.WMaxLimPctEna.value == 1
    assert abs(ctl.WMaxLimPct.cvalue - pct) < 0.1
    return ctl.WMaxLimPct.cvalue


def set_power_watts(d, watts, revert_w=0, timer_s=0):
    """
    Set active power in watts (positive=export, negative=import).
    Write values first, enable last — per [S2] multi-write procedure.
    WSet is int32 per [S6] model_704.json.
    """
    ctl = d.DERCtlAC[0]
    ctl.read()
    time.sleep(1)
    ctl.WSetMod.value     = 1          # WATTS mode
    ctl.WSet.cvalue       = watts
    ctl.WSetRvrt.cvalue   = revert_w
    ctl.WSetRvrtTms.value = timer_s
    ctl.WSetEnaRvrt.value = 1 if timer_s > 0 else 0
    ctl.WSetEna.value     = 1          # ENABLE last
    ctl.write()
    time.sleep(1)
    ctl.read()
    assert ctl.WSetEna.value == 1
    assert ctl.WSet.cvalue   == watts
    return ctl.WSet.cvalue


def standby(d):
    """Soft-disconnect inverter. Conn point in Model 703 — per [S1] DEREnterService."""
    es = d.DEREnterService[0]
    es.Conn.value = 0
    es.write()
    time.sleep(1)
    es.read()
    assert es.Conn.value == 0
    print("STANDBY confirmed")


def reconnect(d):
    """Reconnect inverter. Device will observe enter-service ramp — per [S4]."""
    es = d.DEREnterService[0]
    es.Conn.value = 1
    es.write()
    time.sleep(1)
    es.read()
    assert es.Conn.value == 1
    print("CONNECTED confirmed")


# --- Example usage ---
d = connect('192.168.1.100')

status = get_status(d)
print(f"Live: {status['live_w']} W | Max export: {status['max_export_w']} W")

# Limit export to 70% for 20 minutes, then auto-restore
actual = set_export_limit_pct(d, pct=70.0, revert_pct=100.0, timer_s=1200)
print(f"Export limited to {actual}%")

# Set exact watts for 5 minutes, then revert to 0
actual_w = set_power_watts(d, watts=4000, revert_w=0, timer_s=300)
print(f"Power set to {actual_w} W")

# Standby
standby(d)

d.close()
```

-----

## Key Rules — With Sources

|Rule                                       |Source                                                                                                                                |
|-------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
|Always `read()` before `write()`           |**[S5]** — “A read will overwrite values that have been set and not written”                                                          |
|Write values first, enable (`Ena`) last    |**[S2]** — “For operations that require multiple writes (e.g. set operating parameters and then enable), the procedure is recommended”|
|Do NOT disable before writing              |**[S2]** — “It is not recommended to disable the [function]” for multi-write operations                                               |
|Wait ≥ 1 s between write and read          |**[S3]** — “A definitive delay of 1000 ms has been added to ensure consistent read/write performance” (Section 6.5)                   |
|Verify with `read()` after every `write()` |**[S5]** — “It is considered a best practice with Modbus to verify values written to the device by reading them back”                 |
|Positive `WSet` = export, negative = import|**[S6]** `model_704.json` — `WSet` is `int32` (signed); comment: “may be negative for charging”                                       |
|`WSet` in watts requires `WSetMod = 1`     |**[S6]** `model_704.json` — `WSetMod` enum: `W_MAX_PCT=0`, `WATTS=1`                                                                  |
|Reversion timer restarts on re-write       |**[S1]** — “The timer SHALL be reinitialized with the reversion timeout value, and the timer SHALL be restarted”                      |
|`Conn = 0` for standby                     |**[S1]** — `Conn` lives in Model 703 `DEREnterService`, not Model 704                                                                 |
|Curve models use `AdptCrvReq` for atomicity|**[S1]** — “New curve settings SHALL be selected by writing one of the curve indexes to the adopt curve request point (`AdptCrvReq`)” |
|Do not exceed `WRtg` / `AbsWRtg`           |**[S1]** Model 702 `DERCapacity` — nameplate limits are hard ceilings                                                                 |

-----

## Point Reference — Model 704 DERCtlAC

Source: **[S6]** `sunspec/models` — `json/model_704.json`

|Point              |Type  |Access|Units|Description                                         |
|-------------------|------|------|-----|----------------------------------------------------|
|`WMaxLimPctEna`    |enum16|RW    |—    |Enable export % limit (0=DISABLED, 1=ENABLED)       |
|`WMaxLimPct`       |uint16|RW    |Pct  |Export limit as % of `WRtg`; uses `WMaxLimPct_SF`   |
|`WMaxLimPctRvrt`   |uint16|RW    |Pct  |Reversion % value                                   |
|`WMaxLimPctEnaRvrt`|enum16|RW    |—    |Enable reversion (0=off, 1=on)                      |
|`WMaxLimPctRvrtTms`|uint32|RW    |Secs |Reversion countdown timer                           |
|`WMaxLimPctRvrtRem`|uint32|R     |Secs |Reversion time remaining (read-only)                |
|`WSetEna`          |enum16|RW    |—    |Enable active power setpoint (0=DISABLED, 1=ENABLED)|
|`WSetMod`          |enum16|RW    |—    |Mode: 0=W_MAX_PCT (percent), 1=WATTS                |
|`WSet`             |int32 |RW    |W    |Active power setpoint (signed — negative = import)  |
|`WSetRvrt`         |int32 |RW    |W    |Reversion watts value                               |
|`WSetEnaRvrt`      |enum16|RW    |—    |Enable reversion (0=off, 1=on)                      |
|`WSetRvrtTms`      |uint32|RW    |Secs |Reversion countdown timer                           |
|`WSetRvrtRem`      |uint32|R     |Secs |Reversion time remaining (read-only)                |
|`WSet_SF`          |sunssf|R     |—    |Scale factor for `WSet`                             |
|`WMaxLimPct_SF`    |sunssf|R     |—    |Scale factor for `WMaxLimPct`                       |
