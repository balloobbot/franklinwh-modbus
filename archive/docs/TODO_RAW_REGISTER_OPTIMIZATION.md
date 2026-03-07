# TODO: Optimize Battery Control with Raw Modbus Registers

**Status:** FUTURE OPTIMIZATION  
**Priority:** MEDIUM  
**Created:** 2026-02-14

---

## Background

Currently implementing battery control using SunSpec2 library (`pysunspec2`) for development. This provides:
- ✅ Model discovery and validation
- ✅ Point name abstraction
- ✅ Scale factor handling
- ✅ Type safety

However, for production deployment, we should optimize to raw Modbus register access.

---

## Benefits of Raw Register Implementation

| Benefit | Impact |
|---------|--------|
| **Performance** | ~10-50x faster reads/writes (no model parsing) |
| **Dependency Reduction** | Remove `pysunspec2` library dependency |
| **Smaller Footprint** | Reduced memory usage |
| **Faster Startup** | No model scanning on init |
| **Predictable Timing** | Direct register access = consistent latency |

---

## Implementation Strategy

### Phase 1: Development (Current)
✅ Use SunSpec2 to:
- Discover available models (701-715)
- Identify writable control points
- Understand scale factors and data types
- Test write operations safely
- Document working configurations

### Phase 2: Production Optimization (Future)

**Map SunSpec2 Points → Raw Registers:**

```python
# Instead of:
model_702 = await client.get_model(702)
model_702.points['WChaRteMax']['value'] = 2500
await model_702.write()

# Use direct register writes:
await client.write_holding_register(
    address=40XXX,  # Discovered from SunSpec2 testing
    value=2500,
    unit=1
)
```

**Critical Mappings to Document:**

| SunSpec2 Point | Register Address | Data Type | Scale Factor |
|----------------|------------------|-----------|--------------|
| 702.WChaRteMax | TBD | uint16 | 0 (watts) |
| 702.WDisChaRteMax | TBD | uint16 | 0 (watts) |
| 704.WMaxLimPctEna | TBD | uint16 | N/A (enum) |
| 704.WMaxLimPct | TBD | uint16 | -2 (percent) |

---

## Migration Path

1. ✅ **Test with SunSpec2** (now)
   - Validate all write operations work
   - Document successful configurations
   - Determine timeout/heartbeat requirements

2. 🔲 **Document Register Mappings**
   - Use `modbus_sunspec2_reader.py --map` to get addresses
   - Create register mapping table
   - Document scale factors and data types

3. 🔲 **Implement Raw Register Functions**
   ```python
   # src/battery_control_raw.py
   
   async def set_charge_limit_raw(client, limit_w: int):
       """Set charge limit using raw register (fast path)"""
       await client.write_holding_register(
           address=REGISTER_CHARGE_LIMIT,  # From mapping
           value=limit_w,
           unit=1
       )
   
   async def set_discharge_limit_raw(client, limit_w: int):
       """Set discharge limit using raw register (fast path)"""
       await client.write_holding_register(
           address=REGISTER_DISCHARGE_LIMIT,  # From mapping
           value=limit_w,
           unit=1
       )
   ```

4. 🔲 **Add Feature Flag**
   ```python
   # config/battery_control.json
   {
     "use_raw_registers": false,  # Default: false (SunSpec2)
     "raw_register_mappings": {
       "charge_limit": 40XXX,
       "discharge_limit": 40XXX,
       # ...
     }
   }
   ```

5. 🔲 **Parallel Testing**
   - Run both implementations side-by-side
   - Verify identical behavior
   - Benchmark performance improvement

6. 🔲 **Production Switchover**
   - Set `use_raw_registers: true`
   - Remove `pysunspec2` dependency
   - Update deployment docs

---

## Register Discovery Commands

```bash
# Get Model 702 register addresses
python src/modbus_sunspec2_reader.py -i 192.168.0.110 -m 702 --map

# Get Model 704 register addresses
python src/modbus_sunspec2_reader.py -i 192.168.0.110 -m 704 --map
```

---

## Performance Expectations

**Current (SunSpec2):**
- Write operation: ~500-1000ms
- Includes model parsing, point lookup, validation

**Future (Raw Registers):**
- Write operation: ~10-50ms
- Direct register write, no overhead

**For heartbeat monitoring:** Raw registers enable sub-100ms control loops if needed.

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Register addresses change in firmware | Pin to known-good firmware version |
| Scale factors change | Document and test on each firmware update |
| Breaking changes | Keep SunSpec2 as fallback option |
| Lost abstraction safety | Add validation layer in raw implementation |

---

## References

- Current SunSpec2 implementation: `src/modbus_client.py`
- Register mapping tool: `src/modbus_sunspec2_reader.py --map`
- Battery control testing: `test_battery_control.sh`
- Control point analysis: `/home/david/.gemini/antigravity/brain/.../sunspec2_control_points_analysis.md`

---

## Next Steps (After Testing Completes)

1. Run `test_battery_control.sh` to validate SunSpec2 writes
2. Capture register addresses with `--map` flag
3. Create register mapping table
4. Implement raw register functions
5. Benchmark performance difference
6. Deploy with feature flag

---

**Strategy:** Use SunSpec2 to learn, raw registers to optimize.
