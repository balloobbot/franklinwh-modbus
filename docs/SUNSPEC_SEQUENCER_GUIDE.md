# SunSpec InfoPoint Sequencer Guide

The **SunSpec InfoPoint Sequencer** is a high-level orchestration engine integrated into `franklinwh-cli`. it enables complex, multi-step Modbus operations defined via JSON configuration files.

## Purpose & Intent

FranklinWH aGate systems often require specific sequences of register writes (e.g., enabling Remote Control before setting a power level) or periodic verification of hardware state transitions. This tool automates those sequences, ensuring that:
1.  **Values are Scaled Correctly**: Human-readable values (like `30%`) are automatically converted to raw Modbus values (like `300`) based on the point's Scale Factor (`_SF`).
2.  **State is Verified**: Every write is followed by a readback loop to confirm the hardware actually accepted and persisted the change.
3.  **Fail-Fast Execution**: Sequences can be configured to abort immediately if a critical step fails.

For a detailed list of supported registers and their compliance status, see the [SunSpec Model Reference](SUNSPEC_MODEL_REFERENCE.md).

---

## Native Addressing

While the SunSpec standard often defaults to `40000`, the FranklinWH native base address is **`1`**. The sequencer automatically handles this based on the `-b` or `--base-address` flag.

---

## Usage

Sequences are executed via the `franklinwh_cli.py` tool:

```bash
# Execute a sequence from a JSON file
python3 tools/franklinwh_cli.py -i <IP> --sequence-file examples/reversion_limit_example.json

# Run with custom base address and Modbus unit
python3 tools/franklinwh_cli.py -i <IP> -b 1000 -u 1 --sequence-file <PATH>
```

---

## JSON Sequence Schema

A sequence is a JSON array of "steps". Each step can perform writes or wait for specific conditions.

### 1. Write Step (Default)
Writes one or more values and optionally verifies them.

```json
{
  "name": "Limit Power to 30%",
  "writes": {
    "704.WSetEna": 1,
    "704.WSetPct": 30
  },
  "verify": true,
  "abort_on_failure": true
}
```

### 2. Wait For Step
Polls a register until it matches a specific value (useful for verifying slow state transitions or dead-man timers).

```json
{
  "name": "Wait for Reversion",
  "type": "wait_for",
  "point": "704.WSetPct",
  "value": 0,
  "timeout": 20,
  "interval": 2
}
```

---

## Conformance Diagnostic Suite

Due to inconsistencies in aGate firmware versions (where some SunSpec registers are declared but not implemented), a **Diagnostic Suite** is provided in `examples/diagnostics/`. 

These examples serve as a "Conformance Test" to track when features become functional in your firmware:

| Test File | Purpose | Intent |
| :--- | :--- | :--- |
| `curtailment_conformance.json` | Tests `WMaxLimPct` | Determines if Global Curtailment is functional. |
| `reactive_power_conformance.json` | Tests `VarSet` | Determines if Reactive Power control is enabled. |
| `heartbeat_conformance.json` | Tests `ControllerHb` | Checks if the hardware safety heartbeat is active. |
| `reversion_conformance.json` | Tests `WSetRvrtTms` | Validates if the dead-man switch actually reverts power. |

### 6. Cleanup & Releasing Control

While the CLI provides a dedicated `--stop` flag, you can also include a "Stop" step at the end of your JSON sequences to ensure the gateway returns to its native operating mode automatically.

**A "Clean Release" sequence step:**
```json
{
  "m": 704,
  "p": ["WSetEna", "WSetPct", "WSet"],
  "v": [0, 0, 0],
  "note": "Release Modbus control"
}
```

**Why use the Sequencer to stop?**
- **Atomic Automation**: Charge for N seconds, then release, all in one command without needing a separate `--stop` call.
- **Verification**: The sequencer will verify that `WSetEna` actually returned to `0`, catching any persistent "Zombie States."
- **Custom Fallbacks**: In advanced scenarios, you may want to set a specific power level *before* disabling the master switch.

---

## Hardware-Specific Learnings (aGate X)

*Last Updated: 2026-05-15*

Through development and testing on aGate firmware `V10R01B04D00`, the following patterns were established:

### The "Silent Discard" Pattern
Many registers (like `WMaxLimPctEna` and `ControllerHb`) will return a Modbus **Success (ACK)** when written to, but the internal hardware will **silently discard** the value. The sequencer's verification loop detects this by comparing the readback against the expected value.

### Verified Control Path: WSet (Remote Control)
For curtailing or forcing power, the **Remote Control** group in Model 704 is the only verified working path:
1.  **`704.WSetEna = 1`**: Master switch to enable remote setpoints.
2.  **`704.WSetPct = X`**: Set active power as a percentage of rated capacity.

### Cleanup
To release the gateway from a sequence and return it to its normal operating mode, use the `--stop` flag:
```bash
python3 tools/franklinwh_cli.py -i <IP> --stop
```
