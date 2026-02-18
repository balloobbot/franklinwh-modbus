

# FranklinWH Control Script Architecture

## Overview

This document describes the design decisions, control flow, and component interactions of the FranklinWH aGate battery control system.

## System Architecture
┌─────────────────────────────────────────────────────────────────────────┐

│                         USER INTERFACE LAYER                             │

│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │

│  │ --status    │  │ --healthck  │  │ --power     │  │ --mode          │ │

│  │ (read only) │  │ (diagnostic)│  │ (direct)    │  │ (virtual modes) │ │

│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │

│         └─────────────────┴─────────────────┴─────────────────┘          │

│                              │                                           │

│                              ▼                                           │

│  ┌─────────────────────────────────────────────────────────────────────┐ │

│  │                    FranklinWHController (Hardware Abstraction)       │ │

│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │ │

│  │  │ SunSpec 704 │  │ SunSpec 713 │  │ SunSpec 701 │  │ SunSpec 714│ │ │

│  │  │ (Control)   │  │ (Battery)   │  │ (Grid)      │  │ (Solar)    │ │ │

│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │ │

│  │  ┌────────────────────────────────────────────────────────────────┐ │ │

│  │  │ Health Check Engine (Zombie detection, safety validation)       │ │ │

│  │  └────────────────────────────────────────────────────────────────┘ │ │

│  └─────────────────────────────────────────────────────────────────────┘ │

│                              │                                           │

│                              ▼                                           │

│  ┌─────────────────────────────────────────────────────────────────────┐ │

│  │              VirtualModeController (Software Modes)                  │ │

│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │ │

│  │  │ SELF_CONS   │  │ EMERG_BACKUP│  │ TIME_OF_USE │  │ GRID_ZERO  │ │ │

│  │  │ PEAK_SHAVE  │  │ MANUAL      │  │             │  │            │ │ │

│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │ │

│  │  ┌────────────────────────────────────────────────────────────────┐ │ │

│  │  │ Tick-based execution engine (5-second control loop)             │ │ │

│  │  └────────────────────────────────────────────────────────────────┘ │ │

│  └─────────────────────────────────────────────────────────────────────┘ │

│                              │                                           │

│                              ▼                                           │

│  ┌─────────────────────────────────────────────────────────────────────┐ │

│  │              Modbus TCP Transport (sunspec2 + pymodbus)              │ │

│  │                    ┌─────────────────────┐                           │ │

│  │                    │   FranklinWH aGate  │                           │ │

│  │                    │   (192.168.0.110)   │                           │ │

│  │                    └─────────────────────┘                           │ │

│  └─────────────────────────────────────────────────────────────────────┘ │

└─────────────────────────────────────────────────────────────────────────┘

## Component Responsibilities

### FranklinWHController

| Method | Purpose | SunSpec Model |
|--------|---------|---------------|
| `connect()` | Establish Modbus TCP, scan models | — |
| `healthcheck()` | Comprehensive system validation | 704, 713, 701 |
| `reset_control_state()` | Clear zombie state, return to idle | 704 |
| `send_command()` | Direct power setpoint control | 704 |
| `read_battery_status()` | SoC, SoH, capacity | 713 |
| `read_grid_status()` | Power, voltage, frequency | 701 |
| `read_solar_status()` | DC power, energy counters | 714 |
| `read_control_status()` | WSetEna, WSet, revert timers | 704 |

### VirtualModeController

| Mode | Algorithm | Use Case |
|------|-----------|----------|
| `SELF_CONSUMPTION` | Maximize solar self-use, maintain reserve | Daily operation |
| `EMERGENCY_BACKUP` | Aggressive charge to target SOC | Storm preparation |
| `TIME_OF_USE` | Price arbitrage: charge cheap, discharge expensive | Grid cost optimization |
| `GRID_ZERO` | Minimize grid import/export | Island simulation |
| `PEAK_SHAVE` | Discharge during high demand | Demand charge reduction |
| `MANUAL` | Direct power setpoint | Testing, grid services |

## Control Flow: Virtual Mode Execution

┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐

│   Startup   │────▶│  Health Check   │────▶│  Reset (if      │

│             │     │  (detect zombie)│     │  --reset-on-start│

└─────────────┘     └─────────────────┘     └─────────────────┘

│

┌─────────────────────┘

▼

┌─────────────────┐

│  set_mode()     │

│  (initialize    │

│   parameters)   │

└────────┬────────┘

│

▼

┌─────────────────┐

│  run_continuous()│

│  ┌───────────┐  │

│  │   tick()  │◄─┼─── every 5 seconds

│  │ (periodic)│  │

│  └─────┬─────┘  │

│        ▼        │

│  ┌───────────┐  │

│  │ calculate │  │

│  │ _power()  │  │

│  │ (mode     │  │

│  │  specific)│  │

│  └─────┬─────┘  │

│        ▼        │

│  ┌───────────┐  │

│  │  apply   │  │

│  │safety   │  │

│  │  limits() │  │

│  └─────┬─────┘  │

│        ▼        │

│  ┌───────────┐  │

│  │  send    │  │

│  │ command() │  │

│  │ (Model 704)│  │

│  └─────┬─────┘  │

│        ▼        │

│  ┌───────────┐  │

│  │   idle    │◄─┼─── on shutdown

│  │  (0W)     │  │

│  └───────────┘  │

└─────────────────┘

## State Machine: Model 704

The aGate control state is governed by three key registers:

| Register | Address | Access | Function |
|----------|---------|--------|----------|
| WSetEna | 40318 | R/W | Enable/disable power setpoint control |
| WSetMod | 40319 | R/W | Mode: 0=LIMIT_ABS, 1=LIMIT_PCT, 2=SET_ABS, 3=SET_PCT |
| WSet | 40320-40321 | R/W | Signed 32-bit power value (W) |
| WSetRvrtTms | 40327-40328 | R/W | Auto-revert timeout (seconds) |
| WSetRvrtRem | 40329-40330 | R | Revert time remaining (seconds) |

### Valid States

| WSetEna | WSetMod | WSet | Meaning |
|---------|---------|------|---------|
| 0 | any | any | **IDLE**: Automatic operation, no setpoint control |
| 1 | 0 | ±N | LIMIT_ABS: Limit power to |N| watts |
| 1 | 1 | ±N | LIMIT_PCT: Limit to |N|% of rated |
| 1 | 2 | ±N | **SET_ABS**: Force power to N watts (charge/discharge) |
| 1 | 3 | ±N | SET_PCT: Force to N% of rated |

### Zombie State Detection

A **zombie state** occurs when:
- WSetEna = 1 (control enabled)
- WSetRvrtRem = 0 (revert timer expired)
- WSetRvrtTms > 0 (timer was configured)

In this state, the aGate accepts commands but may not execute them. The fix is explicit reset:
WSetEna = 0, WSet = 0, WSetRvrtTms = 0

## Safety Architecture

### Layer 1: Health Check (Pre-flight)

| Check | Failure Action |
|-------|---------------|
| Connection failed | Abort |
| Model 704 missing | Abort |
| Zombie state detected | Warn, require --reset-on-start |
| SoC < 5% or > 99% | Block discharge/charge respectively |
| Grid voltage out of range | Abort |
| OnGridMode ≠ 2 (Self) | Warn (SPAN mode conflict risk) |

### Layer 2: Command Validation

| Check | Implementation |
|-------|---------------|
| SoC bounds | `send_command()` pre-check |
| Rate limits | `_apply_safety_limits()` in VirtualModeController |
| Sign validation | BatteryCommand dataclass |

### Layer 3: Runtime Monitoring

| Check | Action |
|-------|--------|
| Connection loss | Log error, retry on next tick |
| Command rejection | Log error, skip to next cycle |
| Signal interrupt (SIGINT/SIGTERM) | Graceful shutdown, idle battery |

### Layer 4: Emergency Shutdown

| Trigger | Action |
|---------|--------|
| `atexit` handler | Send idle command (0W) |
| Unhandled exception | `finally:` block idle command |
| Power loss | aGate hardware failsafe (independent) |

## Data Flow: Status Reading
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  read_*()   │────▶│  sunspec2 read  │────▶│  Scale factor   │
│  method     │     │  (model point)  │     │  application    │
│  called     │     │                 │     │  (10^SF)        │
└─────────────┘     └─────────────────┘     └─────────────────┘
│
┌─────────────────────┘
▼
┌─────────────────┐

│  Return dict    │
│  with SI units  │
│  (W, V, Hz, %)  │
└─────────────────┘


## Threading and Concurrency

| Aspect | Design |
|--------|--------|
| Threading model | Single-threaded with `tick()` polling |
| Control interval | 5 seconds (`tick_interval`) |
| Sleep strategy | `time.sleep(0.1)` between ticks to prevent busy-wait |
| Signal handling | Synchronous (signal handlers set flags) |
| Modbus access | Synchronous blocking I/O |

## Error Handling Strategy

| Error Type | Handling | Log Level |
|------------|----------|-----------|
| Connection timeout | Retry once, then abort | ERROR |
| Modbus exception | Log, skip tick, continue | WARNING |
| Write verification fail | Log, skip tick, continue | ERROR |
| Safety limit triggered | Clamp value, log reason | INFO |
| Zombie state | Require explicit reset | WARNING |

## Future Extensions

| Feature | Status | Integration Point |
|---------|--------|-------------------|
| Cloud API | Planned v2.0 | `FranklinWHCloudClient` class |
| SPAN write access | Conditional | `_detect_span_capability()` |
| Async/await | Under consideration | Replace `tick()` with `async def` |
| Configuration file | Planned | YAML/JSON mode definitions |

## References

- SunSpec Alliance: [DER Information Model 802](https://sunspec.org/)
- FranklinWH aGate: V10R01B04D00 (detected firmware)
- Modbus TCP: Port 502, Unit ID 2 (default)
