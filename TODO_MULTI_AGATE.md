# TODO: Multi-aGate Orchestration & Three-Phase Support

## Objective
Implement coordinated control of multiple FranklinWH aGate units for optimized Time-of-Use (TOU) operation and Australian three-phase load balancing.

## Background

### Multi-aGate Scenarios
FranklinWH customers can install multiple aGate units for:
- Increased storage capacity (multiple battery packs)
- Redundancy and reliability
- Phased system expansion
- Three-phase installations (one aGate per phase)

### Australian Three-Phase Systems
- Residential three-phase: L1 (Red), L2 (White), L3 (Blue) + Neutral
- Each phase: 230V, combined 400V line-to-line
- Net metering: Import/export calculated per-phase or aggregate
- Load balancing: Distribute battery discharge evenly across phases

## Key Use Cases

### 1. Coordinated TOU Optimization
**Scenario**: Customer has 2 aGates with 26.5kWh each (53kWh total)

**Requirements**:
- Synchronize charge/discharge schedules across both units
- Coordinate mode changes (all units switch together)
- Optimize total system output for pricing periods
- Handle individual unit faults gracefully

**Example**:
```
17:00 Peak Period Start
- aGate 1: Set to TOU mode, discharge 5kW
- aGate 2: Set to TOU mode, discharge 5kW
- Total export: 10kW to grid during peak pricing
```

### 2. Three-Phase Load Balancing
**Scenario**: Customer has 3 aGates, one per phase (Australian 3-phase)

**Requirements**:
- Monitor per-phase voltage and current
- Balance discharge across all three phases
- Prevent phase imbalance >specified threshold
- Coordinate with net metering requirements

**Example**:
```
Phase 1: Home load 3kW, aGate 1 discharge 2kW
Phase 2: Home load 5kW, aGate 2 discharge 4kW  
Phase 3: Home load 2kW, aGate 3 discharge 1kW
Total: Balanced to ±10% across phases
```

### 3. Capacity Aggregation
**Scenario**: Multiple aGates acting as single virtual battery

**Requirements**:
- Report aggregate SOC to user
- Coordinate charging to balance all units
- Optimize which units discharge based on SOC differences
- Provide unified control interface

## Technical Architecture

### Multi-aGate Manager
```python
class MultiAGateOrchestrator:
    def __init__(self, agate_configs: List[dict]):
        self.agates = [ModbusClient(cfg) for cfg in agate_configs]
        self.phase_mapping = {}  # aGate -> Phase mapping
        
    async def get_aggregate_status(self) -> dict:
        """Get combined status of all aGates"""
        statuses = [await ag.get_status() for ag in self.agates]
        return {
            'total_soc': self._calculate_weighted_soc(statuses),
            'total_capacity': sum(s['capacity'] for s in statuses),
            'total_power': sum(s['power'] for s in statuses),
            'phase_balance': self._calculate_phase_balance(statuses)
        }
    
    async def set_coordinated_mode(self, mode: int):
        """Set operating mode on all aGates simultaneously"""
        tasks = [ag.set_operating_mode(mode) for ag in self.agates]
        await asyncio.gather(*tasks)
        
    async def balance_three_phase(self):
        """Balance discharge across three phases"""
        phase_loads = await self._get_phase_loads()
        target_discharge = self._calculate_balanced_discharge(phase_loads)
        
        for agate, phase, discharge in zip(self.agates, self.phase_mapping, target_discharge):
            await agate.set_discharge_power(discharge)
```

### Phase Balancing Algorithm
```python
def calculate_balanced_discharge(phase_loads: List[float], total_power: float) -> List[float]:
    """
    Distribute discharge power across phases to minimize imbalance
    
    Args:
        phase_loads: Current load on each phase [L1, L2, L3] in watts
        total_power: Total power available to discharge
        
    Returns:
        Optimal discharge per phase [P1, P2, P3]
    """
    # Target: Make net load (load - discharge) equal across phases
    avg_load = sum(phase_loads) / len(phase_loads)
    
    # Calculate needed discharge to balance
    discharge = []
    for load in phase_loads:
        needed = load - avg_load
        discharge.append(max(0, needed))  # Only discharge, don't charge
    
    # Scale to match total available power
    total_needed = sum(discharge)
    if total_needed > 0:
        scale = min(1.0, total_power / total_needed)
        discharge = [d * scale for d in discharge]
    
    return discharge
```

## Configuration

### Multi-aGate Config (`config/multi_agate.yaml`)
```yaml
orchestration:
  enabled: true
  mode: "three_phase"  # Options: coordinated, three_phase, aggregate
  
  agates:
    - name: "aGate Primary"
      ip: "192.168.1.100"
      port: 502
      unit_id: 1
      phase: 1  # Australian Red phase
      capacity_wh: 26500
      
    - name: "aGate Secondary"
      ip: "192.168.1.101"
      port: 502
      unit_id: 1
      phase: 2  # Australian White phase
      capacity_wh: 26500
      
    - name: "aGate Tertiary"
      ip: "192.168.1.102"
      port: 502
      unit_id: 1
      phase: 3  # Australian Blue phase
      capacity_wh: 26500
  
  three_phase:
    balance_enabled: true
    max_imbalance_percent: 10  # Maximum allowed phase imbalance
    rebalance_interval: 30  # seconds
    
  net_metering:
    type: "aggregate"  # Options: aggregate, per_phase
    export_limit_w: 10000  # Per phase or total
    
  failover:
    mode: "continue"  # Options: continue, halt_all, isolate
    min_units_online: 1
```

## Backend Components

### Database Schema
```sql
-- Multi-aGate tracking
CREATE TABLE agate_units (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    phase INTEGER,  -- 1, 2, 3 for three-phase, NULL for single-phase
    capacity_wh INTEGER,
    is_primary BOOLEAN DEFAULT FALSE,
    is_online BOOLEAN DEFAULT TRUE,
    last_seen DATETIME,
    config JSON
);

-- Phase balancing history
CREATE TABLE phase_balance_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    phase1_load_w REAL,
    phase2_load_w REAL,
    phase3_load_w REAL,
    phase1_discharge_w REAL,
    phase2_discharge_w REAL,
    phase3_discharge_w REAL,
    imbalance_percent REAL,
    action_taken TEXT
);
```

### API Endpoints
```python
# Multi-aGate management
GET  /api/agates
POST /api/agates  # Add new aGate
GET  /api/agates/{id}
PUT  /api/agates/{id}
DELETE /api/agates/{id}

# Orchestration
GET  /api/orchestration/status
POST /api/orchestration/mode  # Set coordinated mode for all
POST /api/orchestration/balance  # Trigger manual balance

# Three-phase monitoring
GET  /api/phases/balance
GET  /api/phases/history
POST /api/phases/rebalance
```

## Frontend UI Components

### Multi-aGate Dashboard
```
┌────────────────────────────────────────────────────┐
│ System Overview                                   │
├────────────────────────────────────────────────────┤
│ Total SOC: 85% | Total Capacity: 79.5 kWh         │
│ Total Power: 7.5 kW (Discharging)                 │
│                                                    │
│ ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│ │ aGate 1  │  │ aGate 2  │  │ aGate 3  │         │
│ │ Phase 1  │  │ Phase 2  │  │ Phase 3  │         │
│ │ 85% SOC  │  │ 84% SOC  │  │ 86% SOC  │         │
│ │ 2.5 kW ▼ │  │ 2.5 kW ▼ │  │ 2.5 kW ▼ │         │
│ │ Online ✓ │  │ Online ✓ │  │ Online ✓ │         │
│ └──────────┘  └──────────┘  └──────────┘         │
└────────────────────────────────────────────────────┘
```

### Three-Phase Balance Indicator
```
┌────────────────────────────────────────────────────┐
│ Phase Balance                    Imbalance: 3.2%  │
├────────────────────────────────────────────────────┤
│ L1 (Red):   ████████████░░ 3.2 kW | ← 2.5 kW     │
│ L2 (White): ██████████████ 3.5 kW | ← 2.5 kW     │
│ L3 (Blue):  ██████████░░░░ 2.8 kW | ← 2.5 kW     │
│                                                    │
│ [⚖️ Auto-Balance: ON]  [🔄 Rebalance Now]         │
└────────────────────────────────────────────────────┘
```

### aGate Management Panel
- [ ] List view of all connected aGates
- [ ] Add/remove aGate units
- [ ] Configure phase assignments
- [ ] Set primary/secondary designations
- [ ] View individual unit status
- [ ] Test connectivity

## Implementation Phases

### Phase 1: Multi-aGate Discovery & Monitoring
- [ ] Extend topology to support multiple aGates
- [ ] Implement aggregate status reporting
- [ ] Create multi-aGate dashboard widget
- [ ] Add database schema for multiple units
- [ ] UI for managing multiple aGates

### Phase 2: Coordinated Control
- [ ] Implement coordinated mode changes
- [ ] Synchronize TOU schedules
- [ ] Capacity aggregation and virtual battery view
- [ ] Failover and fault handling
- [ ] Load distribution across units

### Phase 3: Three-Phase Support
- [ ] Phase mapping configuration
- [ ] Real-time phase monitoring
- [ ] Implement balancing algorithm
- [ ] Automatic rebalancing service
- [ ] Phase imbalance alerts

### Phase 4: Advanced Features
- [ ] Predictive load balancing
- [ ] Optimized charge/discharge sequencing
- [ ] Unit-specific wear leveling
- [ ] Integration with pricing API for multi-unit optimization
- [ ] Advanced net metering strategies

## Australian Three-Phase Specifics

### Net Metering Rules
- **Aggregate metering**: Import/export summed across all phases
- **Per-phase metering**: Each phase tracked separately (less common)
- **Export limits**: May be per-phase (5kW) or total (15kW)

### Phase Color Codes
```
Phase 1: Red    (230V)
Phase 2: White  (230V)
Phase 3: Blue   (230V)
Neutral: Black
Earth:   Green/Yellow stripe
```

### Compliance Requirements
- [ ] AS/NZS 4777.2 grid connection compliance
- [ ] Phase imbalance limits (typically ±10%)
- [ ] Export limiting per DNSP requirements
- [ ] Anti-islanding protection coordination

## Safety Considerations

### Fault Handling
- [ ] Individual unit failure isolation
- [ ] Automatic failover to remaining units
- [ ] Alert on unit offline detection
- [ ] Safe shutdown on critical errors

### Phase Protection
- [ ] Overvoltage protection per phase
- [ ] Overcurrent protection per phase
- [ ] Phase loss detection
- [ ] Automatic disconnect on excessive imbalance

### Coordination Safety
- [ ] Prevent conflicting commands to units
- [ ] Timeout on coordinated operations
- [ ] Manual override capability
- [ ] Emergency stop for all units

## Testing Strategy

### Unit Tests
- Phase balancing algorithm validation
- Aggregate status calculation
- Failover logic

### Integration Tests
- Multi-aGate communication
- Coordinated mode changes
- Phase balancing in simulation

### Field Testing
- Deploy on actual 3-phase installation
- Monitor phase balance over 24h
- Verify net metering accuracy
- Test fault scenarios

## Performance Considerations

- Parallel communication to all aGates (async)
- Cache aggregate status to reduce polling
- Optimize phase balance calculations
- Rate limit rebalancing operations

## Related Features
- See `TODO_SCHEDULE_LIBRARY.md` for multi-unit scheduling
- See `TODO_PRICING_APIS.md` for coordinated TOU optimization
- Integrates with existing network topology

## Priority
Medium - Important for customers with multi-aGate installations, especially in Australia

## Dependencies
```
asyncio>=3.4.3         # Async coordination
numpy>=1.24.0          # Phase balance calculations (optional)
```

## Notes
- Start with dual-aGate support, extend to N units
- Three-phase support critical for Australian market
- May need to coordinate with grid-tie inverter
- Consider future integration with aGate cloud API for official multi-unit support
