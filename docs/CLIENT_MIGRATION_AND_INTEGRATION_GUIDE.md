# Library Client Integration & Migration Guide

This guide is for developers and systems (such as the *FranklinWH Energy Manager* or VPP Orchestrators) consuming the `franklinwh-modbus` library. It covers recent changes around raw register support in the sequencer and the new standby handshake safety mechanism during control release.

---

## 1. Standby Handshake during Control Release

### Background
Previously, calling `reset_control_state()` instantly wrote `WSetEna=0` to release remote control. If the battery was actively charging or discharging at high rates (e.g., 5000W), this abrupt termination could cause electrical transients and timing issues in the aGate microgrid.

### The Solution: Two-Stage Handshake
The library now performs a **Standby Handshake** when remote control is active:
1. **Stage 1 (Force Standby)**: Writes `WSetPct=0` and `WSet=0` while keeping `WSetEna=1` (Remote Control active) to force the battery to idle.
2. **Stage 2 (Settle Delay)**: Pauses for `handshake_wait_s` (default `1.0` second) to let the inverter safely ramp down to 0W.
3. **Stage 3 (Release)**: Writes `WSetEna=0`, `WSetPct=0`, `WSet=0` to release control cleanly back to the aGate's native operating mode.

### API Changes
The signature of `reset_control_state` has been updated:
```python
def reset_control_state(self, handshake_wait_s: float = 1.0) -> bool:
```

### Action Required for Clients
* **Normal Shutdown (Recommended)**: Do nothing. The default `1.0` second wait time is safe and handles ramp-down automatically.
* **Immediate / Fast Release**: If you must release control instantly (e.g., in a crash handler or critical watchdog thread where you cannot block), pass `handshake_wait_s=0` to bypass the handshake:
  ```python
  # Bypasses the 1s sleep and immediately sets WSetEna=0
  controller.reset_control_state(handshake_wait_s=0)
  ```
* **Mock Implementations**: If you mock the `FranklinWHController` in your tests, ensure your mock's `reset_control_state` signature accepts parameters:
  ```python
  def reset_control_state(self, handshake_wait_s: float = 1.0):
      return True
  ```

---

## 2. Raw Extension Register Support & Scaling in Sequencer

### Background
SunSpec models do not cover the proprietary extension registers (the `15500+` and `16000+` address ranges). Previously, the sequencer could not resolve scaling, 32-bit widths, or enum text descriptions for these registers, returning raw integers or failing to read multi-register values.

### The Solution: Registry-Aware Resolution
The sequencer now resolves proprietary extension registers automatically using the `EXTENSION_REGISTRY` mapping.

* **32-Bit Register Support**: Registers like `15510` and `15512` (generating power registers) are automatically identified as `uint32` data types and read across **2 registers** (Modbus Function 3, count=2) and unpacked as big-endian.
* **Auto-Scaling**: Applies the appropriate scale factor (e.g. `15507` uses `sf=0`, while other registers apply their defined offsets).
* **Enum Symbol Translation**: When reading registers like `15507` (OnGridMode), the output automatically translates to human-readable names (e.g., `3 (TOU)`).

### Sequence Schema Updates (Backward-Compatible)
Sequence step lists can now define inline overrides for custom registers or unmapped registers.

#### Example: Basic In-line Reads (using automatic registry)
```json
{
  "reads": ["15507", "15510", "15512"]
}
```

#### Example: Step-level Inline Override (Overriding type or scale factors)
If you need to query a custom register that is not in the registry, you can define its schema inline in the `reads` array using a dictionary:
```json
{
  "reads": [
    {
      "address": 15510,
      "name": "CustomActivePower",
      "type": "uint32",
      "sf": 0
    }
  ]
}
```

#### Example: Step-level Inline Write Override
```json
{
  "writes": {
    "15507": 3
  }
}
```
If you need to write a custom type or map a value with a specific scale factor:
```json
{
  "writes": {
    "15510": {
      "value": 1500,
      "type": "uint32",
      "sf": 0
    }
  }
}
```
