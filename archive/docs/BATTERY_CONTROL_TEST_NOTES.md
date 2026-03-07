## TEST SESSION NOTES - 2026-02-15

### User Confirmation

**User witnessed successful battery control in previous session:**
- System switched to **VPP Mode**
- Battery went to **Standby** state
- Screenshot from FranklinWH app confirmed the change

### Current Test Failure

Attempted same atomic write sequence:
```python
# Write to address 299 (Model 704 ControlMode)
register_block = [3, 0x7FFF, 0xFFFF, 0x7FFF, 0xFFFF, 0, 500, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 60]
result = client.write_registers(address=299, values=register_block, device_id=2)
```

**Result:**
- Write returned SUCCESS
- Readback: ControlMode = 65535, WSet = -1W  
- Battery not responding

### Questions to Investigate

1. **Was operating mode different in successful test?**
   - Previous: Unknown
   - Current: Self-Consumption (mode 2)
   - Need: VPP Mode (mode 4) first?

2. **Different register approach?**
   - Atomic write to 299 (ControlMode block)
   - vs Sequential writes to 317-319 (WSetEna/Mod/Set)

3. **Prerequisites?**
   - Does battery need specific SOC level?
   - Does system need specific state?
   - Time of day restrictions?

### Next Steps

- [ ] Check current operating mode vs successful test
- [ ] Try sequential write approach (317-319) instead of atomic
- [ ] Check if VPP mode needs to be set first
- [ ] Document exact state when it worked
