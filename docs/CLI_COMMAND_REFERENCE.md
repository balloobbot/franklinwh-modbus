# CLI Command Reference

*Last Updated: 2026-05-15 18:56 | Version: 1.2.0*

The `franklinwh_cli.py` tool is the primary interface for controlling and monitoring FranklinWH aGate systems via Modbus TCP. It supports both native hardware modes and advanced virtual software orchestration.

## 1. Connection & Global Options

| Option | Alias | Default | Description |
|:-------|:------|:--------|:------------|
| `-i` | `--ip` | **Required** | Target aGate IP address. |
| `-p` | `--port` | `502` | Modbus TCP port. |
| `-u` | `--unit` | `2` | Modbus Unit ID (aGate default is 2). |
| `-b` | `--base-address` | `40000` | Start address for SunSpec discovery. |
| `-t` | `--timeout` | `10.0` | Connection timeout in seconds. |

## 2. Operating Modes

### Native Hardware Mode (`--mode`)
Switches the aGate's native firmware operating mode via Register 15507.
- **Values**: `backup`, `self-consumption` (or `self`, `sc`), `tou`.
- **Note**: Requires "SPAN Modbus" unlock. The CLI performs a read-back verification to ensure the hardware accepted the change.

### Virtual Software Mode (`--vmode`)
Runs a software-orchestrated control loop using standard SunSpec Model 704 commands.
- **Values**: `self_consumption`, `emergency_backup`, `time_of_use`, `peak_shave`, `manual`.
- **Note**: Does not require SPAN unlock. Operates by overriding aGate logic with direct charge/discharge commands.

## 3. Battery Control Actions

| Option | Argument | Description |
|:-------|:---------|:------------|
| `--charge` | `WATTS` | Force charge from grid at specific wattage. |
| `--discharge` | `WATTS` | Force discharge to home/grid at specific wattage. |
| `--max-charge` | - | Charge at the device's maximum rated nameplate power. |
| `--max-discharge` | - | Discharge at the device's maximum rated nameplate power. |
| `--standby` | - | Set battery to 0W idle (grid powers home). |
| `--power` | `WATTS` | Legacy alias: Positive=Charge, Negative=Discharge. |
| `--stop` | - | **Release control** and return the aGate to native firmware mode. |

## 4. Control Parameters & Thresholds

| Option | Default | Description |
|:-------|:--------|:------------|
| `--target-soc` | `100` | Target SoC for charge/discharge operations. |
| `--reserve` | `20` | SoC reserve level for Self-Consumption/TOU modes. |
| `--threshold` | `2000` | Power threshold (W) for Peak Shave mode. |
| `--target-soc-auto`| `PCT` | Target SoC % - auto-stop when reached (for charge/discharge). |
| `--max-charge-soc` | - | Max charge SoC - will EXIT when reached during charging. |
| `--min-discharge-soc`| - | Min discharge SoC - will EXIT when reached during discharging. |
| `--soc-ramp-window` | - | SoC ramping window for smooth transitions. |
| `--loop` | - | Monitor SoC continuously and auto-stop at target. |

## 5. Execution & Safety

| Option | Description |
|:-------|:------------|
| `--duration` | Run the command for N seconds and then exit. |
| `--revert` | **Safety**: Auto-release control after N seconds (Software watchdog). |
| `--force` | Override safety SoC limits (use with caution). |
| `--off-grid-permitted`| Allow operation when grid is disconnected. |
| `--assume-clean-state`| Skip startup conflict detection (prevents "VPP mode active" warning). |
| `--reset-on-start` | Explicitly reset control state (WSetEna=0) before starting. |
| `--dry-run` | Simulate command execution without writing to registers. |

## 6. Monitoring & Diagnostics

| Option | Description |
|:-------|:------------|
| `--status` | Show system summary (SoC, Power Flow, Control State). |
| `--detail` | Add granular register data and lifetime energy metrics to `--status`. |
| `--monitor` | Launch the interactive Terminal UI (TUI) dashboard. |
| `--healthcheck` | Run comprehensive system diagnostics and zombie detection. |
| `--check-alarms` | Display detailed bitfield status for all system and DC alarms. |
| `--clear-alarms` | Attempt to reset active alarms via the `AlarmReset` register. |
| `--test-extension-write`| Test if 15507-15509 extension registers are writable. |
| `--check-span` | Scan local network for SPAN panels. |

## 7. Sequencing & Automation

Execute complex multi-step register operations with automated timing and verification.

| Option | Description |
|:-------|:------------|
| `--sequence` | Execute a JSON string sequence (e.g., `'[{"charge": 1000}, {"wait": 10}]'`). |
| `--sequence-file` | Execute a multi-step sequence from a JSON file. |
| `--brief` | Minimal output for automated sequencing scripts. |
| `--schedule-file` | Load a JSON TOU schedule for virtual mode orchestration. |
| `--show-schedule` | Visualize the contents of a schedule file. |
| `--validate-schedule`| Perform schema validation on a schedule JSON. |

> **See also:** [SunSpec DER Sequencing Protocol](./SUNSPEC_DER_SEQUENCER_REFERENCE.md) for timing and implementation details.

## 8. Global UI & Logging

| Option | Description |
|:-------|:------------|
| `-v`, `--verbose` | Enable debug logging of SunSpec discovery and Modbus traffic. |
| `-q`, `--quiet` | Suppress all non-error output. |
| `--theme` | Set TUI theme: `dark` (default), `green`, `amber`, `white`, `paper`. |

---

## Example Scenarios

### Force Charge for 1 Hour with Safety Timeout
```bash
# Charges at 3000W, reverts to cloud control automatically after 3600s
python3 tools/franklinwh_cli.py -i 192.168.0.110 --charge 3000 --revert 3600 --loop
```

### Run Virtual Peak Shaving
```bash
python3 tools/franklinwh_cli.py -i 192.168.0.110 --vmode peak_shave --threshold 1500
```

### Execute a Hardware Test Sequence
```bash
python3 tools/franklinwh_cli.py -i 192.168.0.110 --sequence-file examples/test_write_reversion.json
```
