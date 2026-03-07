## Batch Read Performance Strategy

### Current Problem
- `/api/data` takes 30+ seconds to load
- Using individual `read_model()` calls for each model (piecemeal reads)
- Each call opens connection → scan → read → close
- With 30s timeout, aGate is slow but this amplifies it

### Solution: Batch Read All Models
Add `batch_read_all_models()` to `modbus_client.py`:

```python
async def batch_read_all_models(self) -> dict:
    """
    Read ALL essential models in ONE connection.
    Much faster than individual read_model() calls.
    """
    essential_models = [
        1,    # Common (device info)
        802,  # Battery SOC
        703,  # DER Capacity  
        713,  # Storage Capacity
        714,  # Storage Status
        704,  # Storage Control
        203,  # AC Measurements
        160,  # Solar PV
    ]
    
    # Connect ONCE
    # Scan ONCE  
    # Read all models
    # Close connection
    
    # Returns dict with all data cached
```

### Benefits
- **1 connection** instead of 8+
- **1 scan** instead of 8+
- **Parallel model reads** (SunSpec supports this)
- Estimated: **30s → 3-5s**

### Implementation
1. Add method to `FranklinWHModbusClient`
2. Call from `/api/data` endpoint
3. Cache results with existing TTL
4. Fallback to individual reads if batch fails

### Testing
```bash
# Before: 30+ seconds
time curl http://localhost:8080/api/data

# After: 3-5 seconds  
time curl http://localhost:8080/api/data
```
