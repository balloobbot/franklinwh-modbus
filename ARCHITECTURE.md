# FranklinWH Battery Manager - Architecture Notes

## Multi-Site & Multi-aGate Architecture

### Overview
The system is designed to support multiple FranklinWH installations (sites), each potentially having multiple aGates, batteries (aPower), and solar arrays.

### Hierarchy Model

```
Site (Plant)
├── Properties
│   ├── name: str                    # e.g., "Home", "Cabin", "Workshop"
│   ├── location: GeoPoint           # Lat/Lng for weather/solar forecasting
│   ├── on_grid: bool                # Grid-tied or off-grid
│   ├── ac_type: enum                # Single, Split, 3-Phase
│   └── utility_services: List[Service]  # One or more grid connections/tariffs
│
└── Devices (aGates)
    ├── aGate 1 (Primary)
    │   ├── connection: ModbusTCP
    │   ├── batteries: List[aPower]  # 1-N units (13.6-15kW each)
    │   │   └── Note: aGate shows LOGICAL view only
    │   │       No individual battery metrics exposed via Modbus
    │   ├── solar_pv: Optional[PVArray]
    │   └── metrics: Aggregate (all batteries + solar)
    │
    └── aGate 2...N (Future)
        └── Same structure
```

### Current Limitations (FranklinWH Modbus)

1. **Battery Aggregation**: aGate exposes only aggregate battery metrics via Modbus
   - Total SOC (average of all batteries)
   - Total power (sum of all batteries)
   - No per-battery visibility in "plant" view
   
2. **No Battery-level Discovery**: Cannot detect:
   - Individual battery serial numbers
   - Per-battery SOC/SOH
   - Which battery is contributing what power
   
3. **Solar Aggregation**: Single PV power/energy reading for entire array

### Future Enhancements

#### Phase 1: Multi-Site Support (Current WIP)
- [x] Basic site configuration in config.json
- [x] Site switching in UI
- [x] **TODO**: Complete setup workflow for site creation/configuration
- [ ] **TODO**: Site-level dashboard (aggregate view of all aGates)
- [ ] **TODO**: Site topology visualization (text or SVG diagram)
- [ ] **TODO**: Multi-site overview dashboard (for WAN/VPN connected sites)
- [x] Site-level MQTT discovery prefix: `homeassistant/franklinwh/{site_id}/`
  - State topics: `franklinwh/{site_id}/battery/soc`, `franklinwh/{site_id}/inverter/power`, etc.
- [x] Dashboard-to-MQTT publishing
  - API endpoints: `/api/mqtt/publish`, `/api/mqtt/publish_dashboard`, `/api/mqtt/publish_grid_power`
  - Calculated values: grid_power, grid_import, grid_export, battery_flow, grid_flow
  - Auto-publishes on each data refresh
  - Live log viewer with pause/resume control

#### System Configuration
- [x] Settings Modal with:
  - [x] Modbus Connection (host, port, unit_id)
  - [x] Data Refresh (auto_refresh toggle, refresh_interval 5-300s)
  - [x] Dashboard Widgets (enable/disable per widget)
  - [x] Appearance (theme, primary color)
  - [x] System (log retention, log level)
- [ ] **TODO**: Advanced settings page (separate from modal)
  - [ ] MQTT detailed configuration
  - [ ] Site management (add/edit/delete sites)
  - [ ] Device management (aGate configuration)
  - [ ] Backup/restore configuration

#### Developer Experience
- [ ] **TODO**: Add token/credit tracking integration so Claude can check available credits before starting tasks (similar to how Claude Desktop shows remaining tokens)

#### Phase 2: Multi-aGate Per Site
- [ ] Discover multiple aGates at one site
- [ ] aGate-level metrics + Site aggregate
- [ ] Redundancy (backup aGate)

#### Phase 3: Enhanced Battery Visibility (Cloud API Required)
FranklinWH Cloud API may expose:
- Individual aPower battery metrics
- Per-battery SOC, temperature, cycles
- Battery health and maintenance alerts

#### Phase 4: Utility Integration
- [ ] Multiple utility services per site
- [ ] Time-of-use rate plans
- [ ] Grid import/export tariff optimization
- [ ] Virtual power plant (VPP) participation

### MQTT Discovery Structure

Current:
```
homeassistant/
└── franklinwh/
    ├── status/...
    ├── inverter/...
    └── battery/...
```

Proposed Multi-Site:
```
homeassistant/
└── franklinwh/
    ├── home/                    # Site ID
    │   ├── status/...
    │   ├── inverter/...
    │   └── battery/...
    ├── cabin/                   # Another site
    │   └── ...
    └── workshop/                # Another site
        └── ...
```

### Data Model Considerations

1. **Time Series**: Each site needs isolated metrics storage
2. **Alarms**: Site-level vs aGate-level alarm aggregation
3. **Control**: Commands target specific aGate or site-wide
4. **Topology**: Visual diagram showing site layout

### AC Type Implications

| AC Type | Markets | Implications |
|---------|---------|--------------|
| Single Phase | Australia, EU residential | L1 only, single current sensor |
| Split Phase | US residential | L1/L2, 120/240V, neutral required |
| 3-Phase | AU commercial, EU | Future FranklinWH product |

- AC Type determines which voltage/current sensors to display
- Affects power calculation (single vs multi-phase)
- Influences grid connection state detection

### Notes

- FranklinWH currently has NO 3-phase aGates for Australian market (in development)
- US market primarily split-phase
- Off-grid sites need different control logic (no grid reference)
