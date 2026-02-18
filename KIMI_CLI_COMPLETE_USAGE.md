# Kimi's fhp_battery_ctrl.py - Complete CLI Usage Guide

**Source:** `fhp_battery_ctrl.py` command-line interface  
**Date:** 2026-02-15

---

## 🚀 QUICK START - FranklinWH aGate

### Basic Commands

```bash
# CHARGE at 2000W
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -p -2000W

# DISCHARGE at 500W  
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -p 500W

# STANDBY (idle)
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --idle

# CHECK STATUS
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --status
```

---

## 📋 ALL COMMAND OPTIONS

### Connection Options

| Option | Default | Description |
|--------|---------|-------------|
| `-i`, `--ip` | **REQUIRED** | IP address of aGate |
| `--port` | 502 | Modbus TCP port |
| `--unit-id` | 1 | Modbus unit ID (**Use 2 for FranklinWH aGate!**) |
| `-t`, `--timeout` | 5.0 | Connection timeout (seconds) |

### Addressing Mode (Pick ONE)

| Option | Description | Base Address |
|--------|-------------|--------------|
| `--franklinwh` | **FranklinWH aGate mode** (recommended) | 1 |
| `--franklinwh-zero-based` | FranklinWH alternate addressing | 0 |
| `--base-addr N` | Custom base address | N (default 40000) |

### Battery Commands (Pick ONE)

| Option | Description | CtlMode | WSet Value |
|--------|-------------|---------|------------|
| `-p POWER`, `--power POWER` | Set power in watts | 3 (SET_W) | As specified |
| `--idle` | Set battery to idle/standby | 3 (SET_W) | 0W |
| `--max-charge` | Request max charge rate | 1 (MAX_CHARGE) | N/A |
| `--max-discharge` | Request max discharge rate | 2 (MAX_DISCHARGE) | N/A |
| `--status` | Read current status only | - | - |

### Reversion Timers (Auto-timeout)

| Option | Description | Example |
|--------|-------------|---------|
| `--wset-rvrt TIME` | WSet reversion timer | `10m`, `3600s`, `1h` |
| `--varset-rvrt TIME` | VarSet reversion timer | `10m` |
| `--vaset-rvrt TIME` | VaSet reversion timer | `10m` |
| `--rvrt-all TIME` | Set ALL reversion timers | `30m` |

**Time format:** `10s`, `5m`, `1h` (seconds, minutes, hours)

### Advanced Options

| Option | Default | Description |
|--------|---------|-------------|
| `--ctl-timeout N` | 60 | Command timeout (seconds) |
| `--verify` | ON | Verify writes (read back) |
| `--no-verify` | - | Skip verification |
| `--retry N` | 3 | Max write retries |
| `--retry-interval N` | 0.5 | Seconds between retries |
| `--verify-delay N` | 0.1 | Delay before read-back |
| `-q`, `--quiet` | - | Minimal output |
| `-v`, `--verbose` | - | Detailed output |
| `--scan-models` | - | Scan for Model 704 location |

---

## 💡 EXAMPLES BY MODE

### 1. CHARGE Commands (Negative Power)

**Charge at 2000W:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -p -2000W
```

**Charge at 3000W with 10-minute timeout:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -p -3000W --wset-rvrt 10m
```

**Charge at maximum rate:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --max-charge
```

**Registers written:**
- CtlMode = 3 (for -p) or 1 (for --max-charge)
- WSet = -2000 (two's complement: 0xFFFF, 0xF830)
- WChaMax = 2147483647 (max int32)
- WDisChaMax = 2147483647 (max int32)
- WSetRvrtTms = 600 seconds (if --wset-rvrt 10m)

---

### 2. DISCHARGE Commands (Positive Power)

**Discharge at 500W:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -p 500W
```

**Discharge at 5000W with 30-minute auto-timeout:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -p 5000W --wset-rvrt 30m
```

**Discharge at maximum rate:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --max-discharge
```

**Registers written:**
- CtlMode = 3 (for -p) or 2 (for --max-discharge)
- WSet = 500 (0x0000, 0x01F4)
- WChaMax = 2147483647 (max int32)
- WDisChaMax = 2147483647 (max int32)
- WSetRvrtTms = 1800 seconds (if --wset-rvrt 30m)

---

### 3. STANDBY/IDLE Commands

**Set to standby (0W):**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --idle
```

**Alternative using -p 0:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -p 0W
```

**Registers written:**
- CtlMode = 3 (SET_W)
- WSet = 0 (0x0000, 0x0000)
- WChaMax = 2147483647 (max int32)
- WDisChaMax = 2147483647 (max int32)
- WSetRvrtTms = 0 (no reversion)

---

### 4. STATUS Check (No Write)

**Check current battery status:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --status
```

**Output includes:**
- Battery State (OFF/STANDBY/CHARGING/DISCHARGING/FAULT)
- Control Mode (MAX_CHARGE/MAX_DISCHARGE/SET_W/SET_VA/SET_VAR)
- Power Setpoint (WSet value)
- Max limits (WChaMax, WDisChaMax)
- Reversion timers

---

## 🔧 ADVANCED USAGE

### With Unit ID Override (FranklinWH uses unit 2)

```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 -p 1000W
```

### With Custom Timeout (For slow WiFi)

```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -t 10.0 -p 2000W
```

### With Auto-Reversion (Safety timeout)

**Command expires after 15 minutes, battery returns to normal:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -p 3000W --wset-rvrt 15m
```

### Verbose Mode (See all register writes)

```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -p 500W --verbose
```

**Shows:**
- Connection details
- Register addresses
- Values written
- Read-back verification
- Retry attempts
- Final status

### Scan for Model 704 (Troubleshooting)

```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --scan-models
```

**Searches for Model 704 at different offsets**

---

## 💻 COMPLETE EXAMPLES

### Example 1: Safe Test with Auto-Timeout

**Discharge 1kW for 5 minutes, then auto-return:**
```bash
python3 fhp_battery_ctrl.py \
  -i 192.168.0.110 \
  --franklinwh \
  --unit-id 2 \
  -p 1000W \
  --wset-rvrt 5m \
  --verbose
```

**What happens:**
1. Connects to 192.168.0.110:502
2. Writes atomic 14-register block with WSet=1000W
3. Sets WSetRvrtTms=300 seconds
4. After 5 minutes: automatically returns to normal mode
5. Shows detailed logging

---

### Example 2: Maximum Charge Test

**Charge at max rate with 30-minute timeout:**
```bash
python3 fhp_battery_ctrl.py \
  -i 192.168.0.110 \
  --franklinwh \
  --unit-id 2 \
  --max-charge \
  --wset-rvrt 30m
```

**What happens:**
1. Sets CtlMode = 1 (MAX_CHARGE)
2. WChaMax/WDisChaMax = max
3. After 30 minutes: reverts to normal

---

### Example 3: Quick Status Check

**Just read current state:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 --status
```

**No writes performed**

---

### Example 4: Standby with Verification

**Set idle and verify:**
```bash
python3 fhp_battery_ctrl.py \
  -i 192.168.0.110 \
  --franklinwh \
  --unit-id 2 \
  --idle \
  --verify \
  --verbose
```

**Shows read-back confirmation**

---

## 🎯 POWER VALUE FORMAT

### Supported Formats

| Format | Example | Parsed As | Notes |
|--------|---------|-----------|-------|
| Plain number | `2000` | 2000W | Watts assumed |
| With W suffix | `500W` | 500W | Explicit watts |
| With kW suffix | `2kW` | 2000W | Kilowaatts |
| Negative | `-2000W` | -2000W | Charge mode |
| With VA suffix | `1000VA` | 1000VA | Uses ControlMode.SET_VA |

### Sign Convention

**Positive = Discharge** (battery → load)  
**Negative = Charge** (grid/solar → battery)  
**Zero = Standby** (idle)

---

## ⚙️ CONTROL MODES EXPLAINED

### ControlMode.SET_W (3) - Used for -p option

**What it does:** Direct watt command

**Registers:**
- CtlMode = 3
- WSet = commanded power (int32)
- WChaMax = max
- WDisChaMax = max

**Result:** Battery follows WSet value exactly

---

### ControlMode.MAX_CHARGE (1) - Used for --max-charge

**What it does:** Request maximum charge rate

**Registers:**
- CtlMode = 1
- WSet = NOT_IMPL
- WChaMax = max
- WDisChaMax = max

**Result:** Battery charges at maximum safe rate

---

### ControlMode.MAX_DISCHARGE (2) - Used for --max-discharge

**What it does:** Request maximum discharge rate

**Registers:**
- CtlMode = 2
- WSet = NOT_IMPL
- WChaMax = max
- WDisChaMax = max

**Result:** Battery discharges at maximum safe rate

---

## 🔒 SAFETY NOTES

### Always Use Reversion Timers in Production

**Bad (gets stuck in VPP mode):**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -p 5000W
```

**Good (auto-returns after 30 minutes):**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh -p 5000W --wset-rvrt 30m
```

### FranklinWH Specific

**Always use `--unit-id 2` for aGate:**
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 -p 1000W
```

### Interrupt Handling

**Ctrl+C safely returns to idle:**
- Catches KeyboardInterrupt
- Sends WSet=0W command
- Battery returns to standby

---

## 📊 TYPICAL WORKFLOW

### 1. Check Status
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 --status
```

### 2. Send Command
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 -p 2000W --wset-rvrt 10m
```

### 3. Monitor (repeat status check)
```bash
watch -n 5 'python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 --status'
```

### 4. Return to Idle
```bash
python3 fhp_battery_ctrl.py -i 192.168.0.110 --franklinwh --unit-id 2 --idle
```

---

## 🎯 SUMMARY

**For FranklinWH aGate battery control, use:**

✅ `--franklinwh` (base address 1)  
✅ `--unit-id 2` (aGate unit ID)  
✅ `-p <power>W` (negative=charge, positive=discharge)  
✅ `--wset-rvrt <time>` (auto-timeout for safety)  
✅ `--verbose` (see what's happening)  

**This triggers FranklinWH to auto-switch to VPP Mode and execute battery control commands!**
