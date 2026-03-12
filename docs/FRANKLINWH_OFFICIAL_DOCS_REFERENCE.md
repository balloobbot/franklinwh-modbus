# FranklinWH Official Documentation Reference

> **Purpose**: Reference guide summarizing official FranklinWH features and their Modbus TCP accessibility.  
> **Source**: [FranklinWH Support](https://www.franklinwh.com/support/overview/), [FranklinWH Service Desk](https://service.franklinwh.com/en/support/solutions/)  
> **Extracted**: 2026-03-12  
> **Last Updated**: 2026-03-12 (added SPAN, SunSpec references)

---

## Feature Capability Matrix — App vs Modbus TCP

| Feature | App | Modbus TCP | Registers | Test Evidence |
|---------|-----|------------|-----------|---------------|
| **Read battery SoC/power/temp** | ✅ | ✅ | M713.SoC, M714.DCW/DCV/Tmp | Validated |
| **Read grid power/voltage/freq** | ✅ | ✅ | M701.W/LNV/Hz/ConnSt | Validated |
| **Read solar PV production** | ✅ | ✅ | M502.OutPw, Ext.15502-15505 | Validated |
| **Read home load** | ✅ | ✅ | Ext.15506 | Validated |
| **Read operating mode** | ✅ | ✅ | Ext.15507 (read-only) | Validated |
| **Read reserve SoC** | ✅ | ✅ | Ext.15508-15509 (read-only) | Validated |
| **Battery charge/discharge** | ✅ | ✅ | M704 WSetPct/WSet/WSetEna | Validated 2026-03-12 |
| **Change operating mode** | ✅ | ❌ | Ext.15507 read-only | — |
| **Change reserve SoC** | ✅ | ❌ | Ext.15508-15509 read-only | — |
| **Grid charge toggle** | ✅ | ❌ | No register | — |
| **Grid export toggle** | ✅ | ❌ | No register | — |
| **Grid export limit (kW)** | ✅ | ❌ | WMaxLimPct silently discarded | [2026-03-08 test](../tests/results/2026-03-08_p2p4_control_tests.md) |
| **Go Off-Grid** | ✅ | ❌ | ConnSt read-only | — |
| **Smart Circuits** | ✅ | ❌ | Not exposed at all | — |
| **Generator** | ✅ | ❌ | Not exposed at all | — |
| **V2L (Vehicle-to-Load)** | ✅ | ❌ | Not exposed at all | — |
| **Solar curtailment** | Auto | ❌ | Firmware-controlled | — |
| **Hardware reversion timer** | N/A | ❌ | WSetRvrtTms accepted, never executes | [Quirks doc](./FRANKLINWH_SUNSPEC_QUIRKS.md) |
| **Hardware heartbeat** | N/A | ❌ | ControllerHb silently ignored | [Quirks doc](./FRANKLINWH_SUNSPEC_QUIRKS.md) |

> **With SPAN Modbus unlock**: Ext.15507-15509 become writable, enabling mode changes and reserve control via Modbus TCP. See [FRANKLINWH_SUNSPEC_QUIRKS.md](./FRANKLINWH_SUNSPEC_QUIRKS.md) for full details.

---

## Operating Modes

### Self-Consumption (Ext.15507 = 2)

**Source**: [Understanding Operating Modes](https://service.franklinwh.com/en/support/solutions/articles/73000647816), [Self-Consumption](https://www.franklinwh.com/support/overview/system-operation-mode)

**How It Works** (official):
1. **Solar Power First** — Solar energy powers home loads in real-time
2. **Charge Batteries** — Excess solar stored in aPower (not exported)
3. **Battery Discharge** — When solar insufficient, aPower discharges to cover home load
4. **Grid as Last Resort** — Grid import only when battery depleted AND solar unavailable

**Key Details**:
- When aPower full, excess solar exported to grid (if export not restricted)
- During outage: auto-switches to emergency backup, uses ALL stored energy including reserve
- User sets **Reserved energy for outage** (slider in app → Ext.15508)
- Best for: flat tariffs, high solar capacity relative to load

### Emergency Backup (Ext.15507 = 0)

**Source**: [Emergency Backup](https://service.franklinwh.com/en/support/solutions/articles/73000649111), [System Operation Mode](https://www.franklinwh.com/support/overview/system-operation-mode)

**How It Works** (official):
1. **Battery kept at 100%** — Charges from solar + grid to maintain full charge
2. **Home powered by grid + solar** — Battery does NOT discharge for self-consumption
3. **Grid outage detected** — Auto-disconnects (anti-islanding), switches to battery within milliseconds
4. **Solar recharges in off-grid** — If PV available, recharges battery. Curtails solar if battery full.
5. **Grid restored** — Auto-reconnects, returns to previous mode, recharges battery

**Key Details**:
- Initial setup may draw from grid to charge batteries to 100%
- Battery does NOT discharge to cover home load when on-grid (key difference from self-consumption)
- Smart energy management prioritizes critical loads during outage
- User can customize backup duration and recovery mode type

### Time-of-Use / TOU (Ext.15507 = 1)

**Source**: [Time of Use](https://service.franklinwh.com/en/support/solutions/articles/73000647820), [System Operation Mode](https://www.franklinwh.com/support/overview/system-operation-mode)

**How It Works** (official):
1. **Peak Hours (Expensive)** — Discharge battery to power home, avoid grid import. Solar used first.
2. **Off-Peak Hours (Cheap)** — Charge batteries from solar + cheap grid. Home runs on grid.
3. **Solar Integration** — Solar powers home + charges batteries. Excess stored, not exported (unless net metering beneficial).

**Rate Periods** (user-defined):
- **Super Off-Peak** — Lowest electricity price
- **Off-Peak** — Lower electricity price
- **Mid-Peak** — Moderate electricity price
- **On-Peak** — Highest electricity price

**Key Details**:
- Requires carefully planned schedule for optimal performance
- Advanced settings allow per-rate customization of charge/discharge behavior
- User sets reserve SoC (slider → Ext.15509)
- Best for: utility rate plans with variable pricing

---

## Grid Import & Export Settings

**Source**: [Grid Import & Export](https://www.franklinwh.com/support/overview/grid-charge--export)

### Grid Import (Charge from Grid)
- **Default**: Charge from grid **not allowed**
- When enabled: aGate uses grid to charge batteries in TOU mode during off-peak/super-off-peak
- When disabled: aPower charges from solar only
- **Modbus TCP**: ❌ No register to toggle this setting

### Energy Export
- Two export modes: **Only Solar** or **Solar + aPower**
- If **Solar + aPower**: set Grid Export Limit (kW) based on utility requirements
- If **Only Solar**: batteries do not export to grid
- Battery prioritizes home energy needs first, exports excess during peak times
- **Modbus TCP**: ❌ No register. WMaxLimPct writes silently discarded.

---

## Go Off-Grid

**Source**: [Go Off-Grid](https://www.franklinwh.com/support/overview/go-off-grid)

Programmatically disconnects home from grid (simulates grid outage).
- Does NOT open/close breakers or disconnect utility service
- Solar + battery power home
- Auto-reconnects if: user reconnects via app, battery depleted, or loads exceed capacity
- Activated via app Settings → Go Off-Grid button
- **Modbus TCP**: ❌ M701.ConnSt is read-only (can detect off-grid, cannot trigger it)

---

## Smart Circuits

**Source**: [Smart Circuits](https://www.franklinwh.com/support/overview/smart-circuits)

Optional aGate module providing control of **3 circuits**:
- **Manual on/off** — Toggle per circuit
- **Time Schedule** — Automatic on/off based on time and cycle intervals
- **SoC Auto Cut-off** (off-grid only) — Disconnect circuits in sequence as battery SoC drops below thresholds
- **Overload Cut-off** — Auto-disconnect if load exceeds panel capacity
- Circuits can be **merged** (2-pole switch), renamed, and scene-automated
- Event logs available for disconnection history

**Modbus TCP**: ❌ **Not exposed at all** — no registers in SunSpec models or extension range. App-only feature.

---

## Generator

**Source**: [Generator](https://www.franklinwh.com/support/overview/generator)

Optional aGate hardware connection for backup generator:
- Functions as backup power source for home loads + aPower charging **when off-grid**
- Combination with FranklinWH provides long-duration uninterrupted power
- Configured via installer in app
- **Modbus TCP**: ❌ **Not visible** — no registers, no status, no control

---

## Vehicle-to-Load (V2L)

**Source**: [Vehicle to Load](https://www.franklinwh.com/support/overview/vehicle-to-load)

EV-to-home power support:
- EV supplies power to home via FranklinWH system
- Optional: EV can **charge the aPower** (configurable toggle)
- Supported vehicle types selectable in app (or custom entry)
- Dashboard shows vehicle power, voltage, frequency
- When EV charging aPower: shows SoC and time to full
- **Modbus TCP**: ❌ **Not visible** — no registers, no status, no control

---

## SPAN Panel Integration

**Source**: [SPAN Commissioning](https://service.franklinwh.com/en/support/solutions/articles/73000635545), [Checking aGate-SPAN Communication](https://service.franklinwh.com/en/support/solutions/articles/73000625802)

SPAN smart electrical panels integrate with FranklinWH via the aGate's **ETH2 Ethernet port**. This integration is what enables "SPAN Modbus" — the write-access unlock for extension registers 15507-15509.

### Commissioning Steps (Installer)
1. Complete FranklinWH system commissioning first
2. In FranklinWH app: **Settings → Modbus → SPAN Panel**
3. Enable "Connect to SPAN Panel" → Confirm
4. Verify Ethernet cable between aGate ETH2 and SPAN panel
5. Firmware **≥ R06** required (auto-prompted if older)
6. Expected message: "The FHP is ready for SPAN panel integration"
7. SPAN panel should then read Modbus data from the aGate (FHP)

### Communication Troubleshooting
- **ETH2 LED on + blinking**: Communication active ✅
- **ETH2 LED on + NOT blinking**: No IP address assigned from SPAN — network config issue
- **ETH2 LED off**: Physical cable issue — check cable, connectors, use data cable tester
- Certified SPAN installers have access to SPAN commissioning app with ESS wiring diagrams
- FranklinWH support cannot access the SPAN commissioning app

### Modbus TCP Implications
- With SPAN integration active: Ext.15507 (mode), 15508 (self reserve), 15509 (TOU reserve) become **writable**
- Without SPAN: these registers are **read-only** (writes silently rejected)
- Our `--check-span` command (local network scan) can detect SPAN panel presence on the local subnet
- Extension register write probe tests writability during `connect()` — see `controller.py:_probe_extension_writable()`

---

## SunSpec Alliance Membership

**Source**: [SunSpec Contributing Members — FranklinWH](https://sunspec.org/contributing-members/franklin-wh/) (members-only, 403 for public access)

FranklinWH is a **contributing member** of the SunSpec Alliance. Their aGate implements SunSpec 2 models:

| Model | Standard Name | aGate Implementation |
|-------|---------------|---------------------|
| 1 | Common | ✅ Manufacturer, Model, Serial, Firmware |
| 502 | Metrology | ✅ Solar PV power (OutPw) |
| 701 | DER Info | ✅ Grid power, voltage, frequency, connection state |
| 702-703 | DER Capacity/Rating | ✅ Max charge/discharge rates |
| 704 | DER Control | ✅ **Only writable model** — WSetPct, WSetEna |
| 705-712 | DER Status/Pricing | ✅ Read-only (partially populated) |
| 713 | DER Storage Capacity | ✅ SoC, SoH, energy (Sta always 0 — quirk) |
| 714 | DER Storage Status | ✅ DC power, voltage, temp, energy |
| 715 | DER Control 3 | ✅ Read-only (LocRemCtl, heartbeat — non-functional) |

**SunSpec PICS file**: `docs/UPDATED_FranklinWH_Modbus_PICS_SM-000028.xlsx` (local copy)

> [!WARNING]
> The PICS document claims some features as "supported" that our live testing has proven non-functional (WMaxLimPct, ControllerHb, WSetRvrtTms). See [FRANKLINWH_SUNSPEC_QUIRKS.md](./FRANKLINWH_SUNSPEC_QUIRKS.md) for discrepancies.

---

## SPAN API — Local LAN Integration (Public Beta)

**Source**: [SPAN API Client Docs (GitHub)](https://github.com/spanio/SPAN-API-Client-Docs), [Introducing SPAN API (Blog)](https://www.span.io/blog/introducing-span-api-and-span-home-on-premise-public-beta)

> [!IMPORTANT]
> If a user has both a SPAN Panel and FranklinWH aGate, the SPAN API could fill most of the capability gaps that Modbus TCP leaves open — particularly **per-circuit control/monitoring** and **EV visibility**.

### Overview

SPAN API is a **local-only LAN API** (no cloud) running directly on the SPAN Panel, providing:
- **MQTT pub/sub** via eBus/Homie convention (port 8883 MQTTS)
- **REST endpoints** for auth, config, file downloads (port 80/443)
- **Per-circuit relay control** — turn individual circuits on/off
- **Per-circuit power monitoring** — real-time watt/energy readings per circuit
- **SPAN Drive (EV charger) status** — charging state, energy usage via Homie node `energy.ebus.device.evse`

### Status & Compatibility

| Item | Detail |
|------|--------|
| **Hardware** | SPAN Panel MAIN 32 only (MAIN 40, MLO 48, MLO 24 planned H2 2026) |
| **Firmware** | r202603+ (rollout completed Feb 2026) |
| **License** | Personal, non-commercial use only. Commercial requires SPAN Fleet Manager license. |
| **Protocol** | MQTT (primary) + REST (auth/admin). Homie Convention topics. |
| **Security** | Local LAN only, credential-based, self-signed TLS |
| **Support** | Community via GitHub. No SPAN customer support for API. |
| **v1 REST** | Deprecated — sunset December 31, 2026. Migrate to MQTT/Homie + v2 REST. |

### Authentication

Two methods to obtain `hopPassphrase`:
1. **Proof-of-proximity**: Press SPAN Panel door switch 3× rapidly → auth open for ~15 min
2. **SPAN Home app**: Settings → passphrase page

```bash
# Example auth setup (from SPAN scripts)
span-auth setup                    # Uses door bypass
span-auth setup -p YOUR_PASSPHRASE # Using known passphrase
# Credentials saved to ~/.span-auth.json
```

### MQTT Topic Structure

```
ebus/5/[panel-serial]/[node-id]/[property-id]
```

Clients subscribe to SPAN Panel topics for real-time circuit power data and publish to control relays.

### Capabilities vs Modbus TCP — Gap Analysis

| Capability | Modbus TCP | SPAN API | Combined |
|-----------|------------|----------|----------|
| **Battery SoC/power** | ✅ M713/M714 | ❌ | Modbus |
| **Battery charge/discharge control** | ✅ M704 | ❌ | Modbus |
| **Grid power/voltage** | ✅ M701 | Maybe (via panel main breaker) | Modbus |
| **Solar PV production** | ✅ M502 | Maybe (via PV circuits) | Modbus |
| **Per-circuit power monitoring** | ❌ | ✅ | **SPAN API fills gap** |
| **Per-circuit relay on/off** | ❌ | ✅ | **SPAN API fills gap** |
| **Smart circuit load shedding** | ❌ | ✅ (manual relay control) | **SPAN API fills gap** |
| **EV/SPAN Drive status** | ❌ | ✅ `energy.ebus.device.evse` | **SPAN API fills gap** |
| **Operating mode change** | ❌ (without SPAN) | ❌ | Neither (app only) |
| **Go Off-Grid** | ❌ | ❌ | Neither (app only) |
| **Generator visibility** | ❌ | ❌ | Neither |
| **Solar curtailment** | ❌ | ❌ | Neither (firmware only) |

### SPAN Home On-Premise (Beta)

Browser-based web app running on LAN via SPAN API:
- Access SPAN Panel during outages (no internet needed)
- View panel status, per-circuit power
- Toggle circuits on/off
- Adjust backup priorities
- Access via SPAN Home app "connection lost" banner or Settings → On-premise settings

### Potential Integration with `franklinwh-modbus`

If a user has SPAN + aGate, a combined integration could:
1. **Modbus TCP** → battery control (M704), system status (M701/M713/M714)
2. **SPAN API (MQTT)** → per-circuit power monitoring, relay control, EV status
3. **Combined** → smarter load shedding (shed circuits via SPAN when battery low), per-circuit demand response, EV-aware battery scheduling

> [!NOTE]
> This would be a future Phase 4+ feature. Requires user to have both SPAN Panel (MAIN 32+) and FranklinWH aGate, with SPAN integration commissioned.

---

## `franklinwh-energy-manager` — Web App Integration Layer

**Location**: `~/dev/franklinwh-energy-manager` (private project)

The **energy manager** is a Flask/Python web application that consumes both this `franklinwh-modbus` library and the `franklinwh-python` Cloud API client, acting as the integration bridge to **Home Assistant** via MQTT Discovery.

### Architecture

```
┌─────────────────────────────────────────────┐
│         Admin Dashboard (Flask :9090)        │
├──────────┬──────────┬───────────────────────┤
│  Cloud   │  Modbus  │  Hybrid Provider      │
│ Provider │ Provider │  (Modbus → Cloud      │
│ (API)    │ (TCP)    │   fallback)           │
├──────────┴──────────┴───────────────────────┤
│        Service Engine (poll + health)       │
├─────────────────────────────────────────────┤
│    MQTT Publisher (HA Discovery + State)    │
├─────────────────────────────────────────────┤
│        Entity Registry (SQLite)            │
└──────────┬────────────────────┬─────────────┘
      ┌────▼────┐         ┌────▼────────┐
      │  MQTT   │         │ FranklinWH  │
      │ Broker  │         │   aGate     │
      └────┬────┘         └─────────────┘
      ┌────▼────┐
      │  Home   │
      │Assistant│
      └─────────┘
```

### Provider Modes

| Mode | Data Source | Latency | Battery Control | Entities |
|------|------------|---------|-----------------|----------|
| `cloud` | FranklinWH Cloud API only | ~60s | ❌ (read-only) | All (solar, battery, grid, modes, history) |
| `modbus` | Modbus TCP to aGate only | ~5s | ✅ M704 dispatch | SunSpec registers only (subset) |
| `hybrid` | Both (Modbus priority) | ~5s | ✅ M704 dispatch | Full set — Modbus overrides Cloud for real-time |

### Key Dependencies

| Library | Role |
|---------|------|
| `franklinwh-modbus` (this repo) | Modbus TCP provider — controller, modes, CLI |
| `franklinwh-python` | Cloud API provider — async HTTP client |
| `paho-mqtt` | MQTT publisher for Home Assistant Discovery |
| `Flask` / `Gunicorn` | Web server for admin dashboard and REST API |

### How It Uses `franklinwh-modbus`

- **Modbus Provider** imports `FranklinWHController` for hardware reads
- **Battery dispatch** API (`/api/dispatch`) sends M704 commands via `controller.send_command()`
- **Virtual modes** can be orchestrated via the web dashboard or API
- **MQTT entities** published to HA include sensors (SoC, power, voltage) and select controls (operating mode)
- **Home Assistant**: `http://192.168.0.109:8123` — [FranklinWH device](http://192.168.0.109:8123/config/devices/device/a1a85ae1bce62df260b5ddc529ebf68f)

---

## Related Documents

- [FRANKLINWH_SUNSPEC_QUIRKS.md](./FRANKLINWH_SUNSPEC_QUIRKS.md) — Hardware register quirks and known defects
- [VIRTUAL_MODE_SPECIFICATIONS.md](./VIRTUAL_MODE_SPECIFICATIONS.md) — Virtual mode definitions and validation targets
- [DER_CONTROL_REFERENCE.md](./DER_CONTROL_REFERENCE.md) — M704/M715 register map
- [FRANKLINWH_MODBUS_GUIDE.md](./FRANKLINWH_MODBUS_GUIDE.md) — Implementation guide
- `docs/UPDATED_FranklinWH_Modbus_PICS_SM-000028.xlsx` — Official SunSpec PICS certification file
- `~/dev/franklinwh-energy-manager/README.md` — Energy Manager web app documentation
- `~/dev/franklinwh-energy-manager/docs/traceability_matrix.md` — FEM requirements traceability matrix
- `~/dev/franklinwh-python/` — FranklinWH Cloud API Python client
- [ARCHITECTURE.md](./ARCHITECTURE.md) — Modbus library architecture overview

---

## Official URLs

| Topic | URL |
|-------|-----|
| Understanding Operating Modes | https://service.franklinwh.com/en/support/solutions/articles/73000647816 |
| Emergency Backup | https://service.franklinwh.com/en/support/solutions/articles/73000649111 |
| Time of Use | https://service.franklinwh.com/en/support/solutions/articles/73000647820 |
| System Operation Mode | https://www.franklinwh.com/support/overview/system-operation-mode |
| Grid Import & Export | https://www.franklinwh.com/support/overview/grid-charge--export |
| Go Off-Grid | https://www.franklinwh.com/support/overview/go-off-grid |
| Smart Circuits | https://www.franklinwh.com/support/overview/smart-circuits |
| Generator | https://www.franklinwh.com/support/overview/generator |
| Vehicle to Load | https://www.franklinwh.com/support/overview/vehicle-to-load |
| Backup Reserve | https://www.franklinwh.com/support/overview/backup-reserve |
| Storm Hedge | https://www.franklinwh.com/support/overview/storm-hedge |
| Virtual Power Plant | https://www.franklinwh.com/support/overview/virtual-power-plant |
| Tariff Settings | https://www.franklinwh.com/support/overview/tariff-settings |
| Direct Connect | https://www.franklinwh.com/support/overview/direct-connect |
| SPAN Commissioning | https://service.franklinwh.com/en/support/solutions/articles/73000635545 |
| aGate-SPAN Communication | https://service.franklinwh.com/en/support/solutions/articles/73000625802 |
| SunSpec Alliance (FranklinWH) | https://sunspec.org/contributing-members/franklin-wh/ |
| **SPAN API Client Docs** | https://github.com/spanio/SPAN-API-Client-Docs |
| **SPAN API Blog Post** | https://www.span.io/blog/introducing-span-api-and-span-home-on-premise-public-beta |

