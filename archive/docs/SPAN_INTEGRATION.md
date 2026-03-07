# SPAN Smart Panel Integration

## Overview

The FranklinWH aGate includes proprietary Modbus extensions (registers 15500+) designed for integration with **SPAN Smart Panels**. These extensions provide additional monitoring and control capabilities beyond standard SunSpec models.

> **Important**: Write access to SPAN extensions requires installer activation via the FranklinWH installer app. Select "SPAN Modbus" instead of "Enable SunSpec Modbus".

## Register Map

| Address | Name | Access | Units | Description |
|---------|------|--------|-------|-------------|
| 15500 | Reserved | — | — | Extension base address |
| 15502 | PV_Total_Power | R | W | Total solar PV production |
| 15503 | PV_Proximal_Power | R | W | Local/primary PV array |
| 15504 | PV_Remote1_Power | R | W | Remote PV source 1 |
| 15505 | PV_Remote2_Power | R | W | Remote PV source 2 |
| 15506 | Home_Load_Power | R | W | Total home consumption |
| 15507 | OnGridMode | **R/W*** | enum | Operating mode: 0=Backup, 1=Self, 2=TOU, 3=Manual |
| 15508 | SelfReserve | **R/W*** | % | Self-consumption reserve SOC |
| 15509 | TOUReserve | **R/W*** | % | Time-of-use reserve SOC |

\* Write access requires SPAN Modbus enablement by certified installer.

## OnGridMode Values

| Value | Mode | Description | Remote Control Safe |
|-------|------|-------------|-------------------|
| 0 | Backup | Prioritize battery reserve | ⚠️ Caution |
| 1 | Self-Consumption | Maximize solar self-use | ✅ **Recommended** |
| 2 | Time-of-Use | Grid price arbitrage | ⚠️ Caution |
| 3 | Manual | Direct control via app | ⚠️ Caution |

> **Safety Note**: Remote control via this script is recommended only when OnGridMode=1 (Self-Consumption). Other modes may conflict with aGate's internal logic.

## Enabling SPAN Modbus

### Prerequisites

- Certified FranklinWH installer account
- FranklinWH installer mobile application
- Physical access to aGate for local Bluetooth connection

### Procedure

1. Open FranklinWH installer app
2. Connect to aGate via Bluetooth
3. Navigate to: **Settings → Modbus Configuration**
4. Select **"SPAN Modbus"** (not "SunSpec Modbus")
5. Confirm activation
6. Verify: registers 15507-15509 become writable

### Verification

After enablement, test with:

```bash
python franklinwh_control_standalone.py -i 192.168.0.110 --healthcheck
```

Expected output:
SPAN Extensions:

Status:               ✓ Detected (writable)

OnGridMode:           1 (Self)

Remote Control:       ✓ Safe

## Fallback Behavior

If SPAN Modbus is **not enabled**, the script operates in **SunSpec-only mode**:

| Feature | SPAN Enabled | SunSpec Only |
|---------|-------------|--------------|
| PV/Load monitoring | 15500+ registers | Derived from 701/714 |
| OnGridMode read | Direct | Not available |
| OnGridMode write | Direct | ❌ Not possible |
| Mode change | Via 15507 | ❌ Use installer app |
| Reserve settings | Via 15508-15509 | ❌ Use installer app |

## Virtual Modes vs. Hardware Modes

| Approach | Control Path | Persistence | Use Case |
|----------|-----------|-------------|----------|
| **Hardware modes** (15507) | Direct register write | aGate internal | Permanent behavior change |
| **Virtual modes** (script) | Model 704 WSet | Runtime only | Flexible, temporary control |

### Recommendation

Use **virtual modes** for:
- Daily optimization
- Testing
- Grid services participation
- Temporary peak shaving

Use **hardware mode change** (15507, SPAN required) for:
- Permanent operational mode change
- Installer configuration
- Integration with SPAN panel automation

## Conflict Avoidance

### Scenario: Mode Mismatch

| OnGridMode | Virtual Mode | Risk | Mitigation |
|------------|-------------|------|------------|
| 0 (Backup) | Any | High | Script warns, blocks control |
| 1 (Self) | Any | Low | ✅ Recommended configuration |
| 2 (TOU) | TIME_OF_USE | Medium | May conflict, monitor closely |
| 3 (Manual) | MANUAL | High | Both try to control, undefined |

### Best Practice

1. Set OnGridMode=1 (Self-Consumption) via installer app or SPAN write
2. Use virtual modes for all runtime control
3. Never mix hardware TOU (15507=2) with virtual TIME_OF_USE

## Implementation Details

### Detection Logic

```python
def _detect_span_capability(self) -> dict:
    """
    Runtime detection of SPAN extension availability.
    Attempts read, then test write to determine writability.
    """
    # Phase 1: Attempt read
    try:
        # Read OnGridMode (15507)
        result = raw_client.read_holding_registers(15507, 1)
        if result.isError():
            return {'readable': False, 'writable': False}
        
        ongrid_mode = result.registers[0]
    except:
        return {'readable': False, 'writable': False}
    
    # Phase 2: Test write (destructive test, restore after)
    original = ongrid_mode
    try:
        # Try to write same value back
        write_result = raw_client.write_register(15507, original)
        writable = not write_result.isError()
    except:
        writable = False
    
    return {
        'readable': True,
        'writable': writable,
        'ongrid_mode': ongrid_mode,
    }

### SAFETY INTERLOCK ###

# Before any virtual mode operation
health = controller.healthcheck()
if not health.details.get('remote_control_safe', False):
    logger.error("OnGridMode != Self-Consumption. Remote control unsafe.")
    sys.exit(1)

