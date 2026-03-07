# Modbus Register Write Verification Pattern

Extracted from `franklinwh_diagnostics.py` (retired) — a 5-strategy approach for verifying
whether Modbus register writes actually take effect vs being silently accepted and ignored.

## Why This Matters

The FranklinWH aGate ACKs many Modbus writes at the protocol level but silently ignores them
at the firmware level. A successful Modbus response ≠ the value was actually applied.
This pattern catches "silent rejection" by verifying actual register state changes.

## The 5-Strategy Verification

```python
def test_register(client, addr, test_value, name, delay=0.5):
    """
    Comprehensive write test with multiple verification strategies.
    Uses pymodbus raw Modbus TCP client.
    """
    # Strategy 1: Read current value (baseline)
    pre = client.read_holding_registers(address=addr, count=1, device_id=DEVICE_ID)
    original = pre.registers[0]

    # If current value == test value, toggle to force a detectable change
    if original == test_value:
        test_value = 1 if test_value == 2 else 2

    # Strategy 2: Attempt write
    result = client.write_register(address=addr, value=test_value, device_id=DEVICE_ID)
    write_acked = not result.isError()  # Protocol-level ACK (NOT proof of acceptance)

    # Strategy 3: Immediate readback (catches synchronous writes)
    time.sleep(delay)  # 0.5s default
    post1 = client.read_holding_registers(address=addr, count=1, device_id=DEVICE_ID)
    immediate_changed = (post1.registers[0] == test_value)

    # Strategy 4: Delayed readback (catches async/queued writes)
    time.sleep(3)
    post2 = client.read_holding_registers(address=addr, count=1, device_id=DEVICE_ID)
    delayed_changed = (post2.registers[0] == test_value)

    # Strategy 5: Restore original value if changed
    if delayed_changed and post2.registers[0] != original:
        client.write_register(address=addr, value=original, device_id=DEVICE_ID)

    return immediate_changed or delayed_changed
```

## Context-Dependent Write Test

Some registers may only accept writes when the device is in a specific operating mode.
This pattern tests all mode contexts:

```python
def test_with_context_change(client):
    """Try writing in different mode contexts to find unlock conditions."""
    mode_addr = 15507    # FranklinWH OnGridMode register
    reserve_addr = 15508 # Self-consumption reserve %

    mode_pre = read_reg(client, mode_addr)
    reserve_pre = read_reg(client, reserve_addr)

    for test_mode in [1, 2, 3]:  # TOU, Self-Consumption, Manual
        if test_mode == mode_pre:
            continue

        # Change mode context
        write_reg(client, mode_addr, test_mode)
        time.sleep(1)

        # Try writing reserve in this context
        test_reserve = 25 if reserve_pre != 25 else 30
        write_reg(client, reserve_addr, test_reserve)
        time.sleep(0.5)

        reserve_now = read_reg(client, reserve_addr)
        if reserve_now == test_reserve:
            # Found a context that unlocks writes!
            # Restore and report
            write_reg(client, mode_addr, mode_pre)
            write_reg(client, reserve_addr, reserve_pre)
            return True

    # Restore original mode
    write_reg(client, mode_addr, mode_pre)
    return False
```

## When to Use This Pattern

- When testing writable registers on new firmware versions
- When FranklinWH enables Ethernet/SPAN access (LocRemCtl=REMOTE)
- When verifying whether new registers are functional after firmware updates
- Any Modbus device where protocol-level ACK doesn't guarantee write acceptance

## Key Finding (Australian Beta, Feb 2026)

Using this pattern, we confirmed:
- Native registers **15507-15509 are READ-ONLY** via WiFi (write ACKed but ignored)
- SunSpec M715 registers are **readable but reject writes** (LocRemCtl=LOCAL)
- Only M704 `WSetPct`, `WSetEna`, `WSetMod` accept and apply writes
