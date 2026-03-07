# Battery Control Orchestration & Logic

This document details the hardware interaction sequences and software logic for controlling the FranklinWH aGate battery system.

## 1. Core Hardware Command Sequence

**CRITICAL**: All battery control relies on a mandatory, multi-step sequence of **direct register writes**. High-level `sunspec2` model point writes are ignored by the hardware.

**Sign Convention**:
- **Positive (+) Power**: Discharges the battery.
- **Negative (-) Power**: Charges the battery.

```mermaid
sequenceDiagram
    participant App as Application Code
    participant Ctrl as FranklinWHController
    participant H as aGate Hardware (Modbus)

    Note over App, H: Primary Command (Charge/Discharge)
    
    App->>Ctrl: send_command(power_watts)
    
    Ctrl->>H: 1. Disable Control (Write Reg 317 = 0)
    H-->>Ctrl: Ack
    
    Ctrl->>H: 2. Configure (Write Reg 318 = 0) & Disable Reversion (Write Reg 326 = 0)
    H-->>Ctrl: Ack
    
    Ctrl->>H: 3. Write Power (Write Reg 319 = watts)
    Note right of Ctrl: Uses Negative for Charge, Positive for Discharge
    H-->>Ctrl: Ack
    
    Ctrl->>H: 4. Enable Control (Write Reg 317 = 1)
    H-->>Ctrl: Ack
    
    Ctrl->>H: 5. Verify (Read Reg 319)
    H-->>Ctrl: Return Power Value
    Ctrl-->>App: Success, Command Sent
```

---
## 2. Standby / Release Control Sequence

To return the battery to its native mode, control must be explicitly released.

```mermaid
sequenceDiagram
    participant App as Application Code
    participant Ctrl as FranklinWHController
    participant H as aGate Hardware (Modbus)

    Note over App, H: Release Control (Standby/Idle)

    App->>Ctrl: reset_control_state()
    
    Ctrl->>H: 1. Disable Control (Write Reg 317 = 0)
    H-->>Ctrl: Ack

    Ctrl->>H: 2. Zero Power (Write Reg 319 = 0)
    H-->>Ctrl: Ack
```

---
## 3. Software Logic: SoC Limits & Ramping

Before any hardware commands are sent, the `VirtualModeController` calculates and sanitizes the power request based on the following SoC parameters. This entire process occurs within the application and acts as a safety guardrail.

| Parameter | Purpose | Scope |
| :--- | :--- | :--- |
| `target-soc` | The desired SoC for automated modes like Emergency Backup. | Mode-specific |
| `max-charge-soc` | The absolute maximum SoC allowed. Charging is disabled above this. | Global |
| `min-discharge-soc` | The absolute minimum SoC allowed. Discharging is disabled below this. | Global |
| `soc_ramp_window`| The SoC percentage range where power is ramped down to avoid "slamming" into limits. | Global |

### Logic Flow Diagram
```mermaid
graph TD
    A[Start: Raw Power Request] --> B{Mode Logic Calculation};
    B -->|e.g., charge at -5000W| C(SoC Safety Check);
    subgraph "Software Guardrails (modes.py)"
        C --> D{Current SoC vs. Limits};
        D -->|SoC >= max-charge-soc?| E[Block Charge: Return 0W];
        D -->|SoC <= min-discharge-soc?| F[Block Discharge: Return 0W];
        D -->|In Ramping Window?| G[Apply Ramping: Reduce Power];
        D -->|SoC OK| H[Power Approved];
    end
    H --> I(Sanitized Power Value);
    I --> J[FranklinWHController];
    J --> K(Execute Hardware Sequence);
```

---

## 4. Operational Entry Points & Orchestration Mapping

The following table maps user-facing actions to their underlying orchestration and hardware sequences.

| User Action | Entry Point | Controller Call | Hardware Sequence (Model 704) |
| :--- | :--- | :--- | :--- |
| **CLI/TUI Charge** (`--charge W` or 'c') | `franklinwh_cli.py` / `monitor.py` | `ctrl.send_command(W)` | 1. 317=0 (Stop) <br> 2. 318=0, 326=0 (Config) <br> 3. 319=-W (Charge) <br> 4. 317=1 (Enable) |
| **CLI/TUI Discharge** (`--discharge W` or 'd') | `franklinwh_cli.py` / `monitor.py` | `ctrl.send_command(W)` | 1. 317=0 (Stop) <br> 2. 318=0, 326=0 (Config) <br> 3. 319=+W (Discharge) <br> 4. 317=1 (Enable) |
| **CLI/TUI Standby** (`--standby` or 's') | `franklinwh_cli.py` / `monitor.py` | `ctrl.send_command(0)` | 1. 317=0 (Stop) <br> 2. 318=0, 326=0 (Config) <br> 3. 319=0 (Standby) <br> 4. 317=1 (Enable) |
| **CLI/TUI Stop / Release** (`--stop` or 'r') | `franklinwh_cli.py` / `monitor.py` | `ctrl.reset_control_state()` | 1. 317=0 (Disable Control) <br> 2. 318=0 (Set Normal) <br> 3. 319=0 (Zero Power) |
| **Function Call** (Python API) | `controller.py` | `send_command(W)` | Direct register writes to 704 via sequence |
| **Virtual Mode** (`--mode X`) | `modes.py` -> `set_mode` | `ctrl.send_command(...)` | Repeated updates based on SoC/Target logic |

---
## 5. Register Reference (Model 704)

| Register | PDU Address | Name | Type | Unit | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 40318 | 317 | `WSetEna` | uint16 | Enum | 1=Local Control Enabled, 0=Disabled |
| 40319 | 318 | `WSetMod` | uint16 | Enum | 0=Normal/VPP Mode |
| 40320 | 319 | `WSetPct` | int16 | %/W | Power (+Discharge, -Charge) |
| 40327 | 326 | `WSetRvrtTms` | uint32 | sec | Reversion Timeout (0 to disable) |
