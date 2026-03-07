# Modbus TCP Implementation Report
**For**: FranklinWH Support Ticket #100405  
**Date**: 2026-02-07  
**System**: FranklinWH Battery Manager Dashboard (Custom SunSpec2 Implementation)  
**Author**: David (Beta Tester - Custom Dashboard Development)

---

## Executive Summary

This report documents the Modbus TCP implementation used to communicate with FranklinWH aGate devices. We are observing intermittent "broken pipe" errors and have identified TCP connection lifecycle behavior that may require optimization.

**Key Finding**: Connection pooling is implemented at the application layer, but the underlying pysunspec2 library may be creating/destroying TCP sockets more frequently than optimal, resulting in TIME-WAIT socket accumulation.

---

## System Architecture

### Software Stack

```
┌─────────────────────────────────────┐
│  FastAPI Web Dashboard              │
│  (User Interface Layer)             │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  ConnectionManager                  │
│  - Pools FranklinWHModbusClient     │
│  - One persistent client per device │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  FranklinWHModbusClient             │
│  - Wraps pysunspec2 library         │
│  - Implements SunSpec models 701-715│
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  pysunspec2 (SunSpec2 Library)      │
│  - Modbus TCP transport layer       │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  aGate (192.168.0.110:502)          │
│  - FranklinWH Gateway Device        │
│  - Modbus TCP Server                │
└─────────────────────────────────────┘
```

### Connection Management Implementation

**File**: `src/connection_manager.py`

**Design**:
- Maintains a dictionary of persistent `FranklinWHModbusClient` objects
- One client instance per configured device
- Clients are long-lived (created at startup, destroyed at shutdown)
- All data polling operations reuse the same client instance

**Code Reference**:
```python
class ConnectionManager:
    def __init__(self):
        self._clients: Dict[str, FranklinWHModbusClient] = {}
    
    async def get_client(self, device_id: str = "default"):
        """Returns persistent client - NOT recreated per request"""
        return self._clients.get(device_id)
```

---

## Observed Behavior

### TCP Connection Statistics

**Test Duration**: 2 minutes of normal operation  
**Poll Interval**: Dashboard refreshes every 5 seconds  
**Timestamp**: 2026-02-07 14:00-14:02 AEDT

#### Connection States (ss -tan output)

```bash
$ ss -tan | grep 192.168.0.110:502 | awk '{print $1}' | sort | uniq -c

ESTABLISHED:  1 connection
TIME-WAIT:   14 connections (accumulated over time)
```

#### Detailed Connection Snapshot

```
State      Local Port    Remote            Status
─────      ──────────    ──────            ──────
ESTAB      39288         192.168.0.110:502 Active
TIME-WAIT  46072         192.168.0.110:502 Closing
TIME-WAIT  46088         192.168.0.110:502 Closing
TIME-WAIT  46094         192.168.0.110:502 Closing
... (11 more TIME-WAIT entries)
```

### Error Patterns

**Error Message**: `Socket write error: [Errno 32] Broken pipe`

**Frequency**: Intermittent (approximately 5-10 errors per minute during polling)

**Affected Models**: All SunSpec models (502, 703, 701, 714, etc.)

**Sample Log Entry**:
```
2026-02-07T02:57:51.114767  ERROR  src.modbus_client
Error reading model 502: Socket write error: [Errno 32] Broken pipe
```

---

## Technical Analysis

### TIME-WAIT State Accumulation

**Observation**: Multiple TIME-WAIT connections accumulate despite using a single persistent `FranklinWHModbusClient`.

**Hypothesis**: The `pysunspec2` library's internal Modbus TCP implementation may be:
1. Creating new TCP sockets for individual model reads
2. Closing sockets immediately after each read completes
3. Not reusing a persistent socket connection

**Linux TIME-WAIT Behavior**:
- Duration: 60-120 seconds (kernel default)
- Purpose: Prevent port reuse conflicts
- Side Effect: Can exhaust ephemeral port range (32768-60999) under heavy load

### Broken Pipe Error Root Cause

**Scenario**:
1. Application attempts to write to socket
2. Socket was recently closed by previous operation
3. Socket is in TIME-WAIT state
4. Write operation fails with EPIPE (Errno 32)

**Why This Occurs**:
- Race condition between socket closure and next read attempt
- Application layer thinks socket is still open
- Kernel has already marked socket as closing

---

## Current Mitigation Efforts

### 1. Connection Layer Improvements (In Progress)

Investigating whether `pysunspec2` has configuration options for:
- Persistent connection mode
- Connection keep-alive settings
- Socket reuse parameters

### 2. Error Handling

Currently implementing:
- Automatic reconnection on broken pipe errors
- Connection health checks before reads
- Exponential backoff for failed connections

### 3. Application-Level Buffering

Considering:
- Request queuing to reduce connection churn
- Batch model reads into single transaction
- Adaptive polling rate based on error frequency

---

## Network Configuration

### Client System
- **OS**: Ubuntu Linux (desktop mini PC)
- **IP**: 192.168.0.181
- **Ephemeral Ports**: 32768-60999 (default Linux range)
- **Firewall**: None (local network)

### aGate Device
- **Model**: FranklinWH aGate
- **IP**: 192.168.0.110
- **Port**: 502 (Modbus TCP standard)
- **Connectivity**: ✓ Pingable, port accessible

### Network Path
- **Topology**: Direct LAN connection
- **Latency**: <1ms (local network)
- **Packet Loss**: 0% (verified with ping)

---

## Diagnostic Commands Used

```bash
# 1. TCP connection state monitoring
ss -tan | grep 192.168.0.110:502

# 2. Connection count by state
ss -tan | grep :502 | awk '{print $1}' | sort | uniq -c

# 3. Process-specific socket inspection
ss -tanp | grep python

# 4. TIME-WAIT specific monitoring
ss -tan state time-wait | grep :502

# 5. Real-time connection tracking
watch -n1 'ss -tan | grep :502 | wc -l'
```

---

## Questions for FranklinWH Engineering

1. **Recommended Connection Pattern**: Does the aGate prefer:
   - Persistent TCP connections with keep-alive?
   - Connection per transaction (current behavior)?
   - Connection pooling with specific timeout?

2. **Concurrent Connection Limit**: How many simultaneous TCP connections can the aGate handle?

3. **SunSpec Implementation**: Are there known optimal settings for `pysunspec2` when communicating with aGate devices?

4. **Error Recovery**: What is the recommended retry strategy for broken pipe errors?

5. **Connection Timeout**: What timeout values does FranklinWH recommend for stable operation?

---

## Proposed Next Steps

1. **Short-term**: Implement connection retry logic with exponential backoff
2. **Medium-term**: Investigate switching to raw `pymodbus` with explicit connection management
3. **Long-term**: Implement connection pooling with configurable keep-alive

---

## Technical Contact

**Beta Tester**: David  
**Support Ticket**: #100405  
**Implementation**: Custom SunSpec2 dashboard  
**GitHub**: (Custom development - using pysunspec2 library)

---

## Appendices

### A. Library Versions
- `pysunspec2`: Latest (pip installed)
- `pymodbus`: 3.x (fallback option)
- `Python`: 3.10+
- `FastAPI`: Latest

### B. SunSpec Models Implemented
- Model 1: Common (device info)
- Model 502: Solar PV
- Model 701: DER AC Measurements
- Model 703: DER Capacity
- Model 713: Battery Capacity
- Model 714: Battery Status
- Model 715: Battery Control

### C. Polling Frequency
- Dashboard data: Every 5 seconds
- MQTT publishing: Every 30 seconds
- Deep discovery: On-demand only
